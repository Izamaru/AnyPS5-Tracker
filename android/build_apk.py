"""Compila e assina um APK pessoal com as ferramentas oficiais portáteis."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / '.tools'
BUILD = ROOT / 'build'
RELEASES = ROOT.parent / 'AnyPS5-Tracker' / 'releases'
VERSION_NAME = '0.2.2'
VERSION_CODE = '3'


def locate(name, folder):
    found = list((TOOLS / folder).rglob(name))
    if not found:
        raise SystemExit('Ferramenta ausente: ' + name + '. Execute android/download_tools.py primeiro.')
    return found[0]


def run(*args):
    result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=ENV)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    java = locate('java.exe', 'jdk')
    jdk = java.parent
    android_jar = locate('android.jar', 'platform')
    aapt = locate('aapt2.exe', 'build-tools')
    align = locate('zipalign.exe', 'build-tools')
    d8 = locate('d8.jar', 'build-tools')
    signer = locate('apksigner.jar', 'build-tools')
    ENV = dict(os.environ, JAVA_HOME=str(jdk.parent))
    for path in (BUILD/'classes', BUILD/'generated', BUILD/'dex', ROOT/'keystore', RELEASES):
        path.mkdir(parents=True, exist_ok=True)
    run(sys.executable, ROOT/'prepare_assets.py')
    run(aapt, 'compile', '--dir', ROOT/'res', '-o', BUILD/'resources.zip')
    run(aapt, 'link', '-o', BUILD/'base.apk', '--manifest', ROOT/'AndroidManifest.xml', '-I', android_jar,
        '--min-sdk-version', '26', '--target-sdk-version', '35', '--version-code', VERSION_CODE, '--version-name', VERSION_NAME,
        '--java', BUILD/'generated', '-R', BUILD/'resources.zip', '-A', BUILD/'assets')
    sources = list((ROOT/'src').rglob('*.java')) + list((BUILD/'generated').rglob('*.java'))
    run(jdk/'javac.exe', '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-classpath', android_jar, '-d', BUILD/'classes', *sources)
    run(java, '-cp', d8, 'com.android.tools.r8.D8', '--lib', android_jar, '--min-api', '26', '--output', BUILD/'dex', *list((BUILD/'classes').rglob('*.class')))
    with zipfile.ZipFile(BUILD/'base.apk', 'a', compression=zipfile.ZIP_DEFLATED) as apk:
        for dex in (BUILD/'dex').glob('*.dex'):
            apk.write(dex, dex.name)
    run(align, '-f', '4', BUILD/'base.apk', BUILD/'aligned.apk')
    keystore = ROOT/'keystore'/'personal-debug.jks'
    if not keystore.exists():
        run(jdk/'keytool.exe', '-genkeypair', '-keystore', keystore, '-storepass', 'android', '-keypass', 'android',
            '-alias', 'androiddebugkey', '-dname', 'CN=AnyPS5 Tracker Personal Build', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000')
    output = RELEASES/f'AnyPS5-Tracker-Android-v{VERSION_NAME}.apk'
    run(java, '-jar', signer, 'sign', '--ks', keystore, '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', output, BUILD/'aligned.apk')
    run(java, '-jar', signer, 'verify', '--verbose', '--print-certs', output)
    run(aapt, 'dump', 'badging', output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.apk.sha256').write_text(digest + '  ' + output.name + '\n', encoding='ascii')
    print('APK pronto:', output)
    print('SHA-256:', digest)
