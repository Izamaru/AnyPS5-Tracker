"""Obtém ferramentas portáteis oficiais, sem alterar Java/SDK do sistema."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import urllib.request
from xml.etree import ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / '.tools'
TOOLS.mkdir(exist_ok=True)


def download(name, url, checksum=None):
    archive = TOOLS / (name + '.zip')
    folder = TOOLS / name
    if folder.exists():
        print(name + ': já disponível', flush=True)
        return
    if not archive.exists():
        print('Baixando ' + name, flush=True)
        with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as output:
            while data := response.read(1024 * 1024):
                output.write(data)
    if checksum:
        actual = hashlib.sha1(archive.read_bytes()).hexdigest()
        if actual != checksum:
            raise ValueError('Checksum inválido: ' + name)
    with zipfile.ZipFile(archive) as source:
        source.extractall(folder)
    print(name + ': extraído', flush=True)


if __name__ == '__main__':
    raw = urllib.request.urlopen('https://dl.google.com/android/repository/repository2-3.xml', timeout=40).read()
    packages = ET.fromstring(raw)
    jobs = [('jdk', 'https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.zip', None)]
    for package, name in [('platforms;android-35', 'platform'), ('build-tools;35.0.0', 'build-tools')]:
        entry = next(p for p in packages.findall('remotePackage') if p.get('path') == package)
        archive = next(a for a in entry.findall('./archives/archive') if a.findtext('host-os') in ('windows', None))
        jobs.append((name, 'https://dl.google.com/android/repository/' + archive.findtext('./complete/url'), archive.findtext('./complete/checksum')))
    with ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(lambda args: download(*args), jobs):
            pass
