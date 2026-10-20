#!/usr/bin/env python3
"""AnyPS5 Tracker: acompanhe progresso oficial, commits e releases sem dependencias externas."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.request

BASE = 'https://boykopovar.github.io/AnyPS5'
PROGRESS_URL = BASE + '/progress.json'
HISTORY_URL = BASE + '/history.html'
HISTORY_JSON_URL = BASE + '/history.json'
REPO_URL = 'https://github.com/boykopovar/AnyPS5'
API_URL = 'https://api.github.com/repos/boykopovar/AnyPS5'
DISCUSSION_URL = REPO_URL + '/discussions/675'
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'dados'
STATE_FILE = DATA_DIR / 'estado.json'
HISTORY_FILE = DATA_DIR / 'historico.jsonl'
DASHBOARD_FILE = ROOT / 'painel.html'
RELEVANT = re.compile(
    r'ghost[ -]?of[ -]?y[oō]tei|\by[oō]tei\b|\batsu\b|vram|memory|mem[oó]ria|'
    r'vulkan|shader|relink|render|texture|graphics|\bgpu\b|\bagc\b|\bfps\b|'
    r'heap|allocat|cache|frame ?rate|performance|driver|out.of.memory|oom|'
    r'video.?out|viewport|pipeline', re.IGNORECASE
)
PRIORITY_LIBS = (
    'libSceAgc', 'libSceAgcDriver', 'libSceVideoOut', 'libkernel', 'libc',
    'libSceAmpr', 'libSceAudioOut', 'libScePad', 'libSceAjm.native',
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def request_json(url: str, token: str | None = None):
    headers = {'User-Agent': 'AnyPS5-Tracker/0.1 (personal progress monitor)',
               'Accept': 'application/vnd.github+json' if 'api.github.com' in url else 'application/json'}
    if token and 'api.github.com' in url:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('A resposta excedeu 8 MiB.')
        return json.loads(raw.decode('utf-8'))


def atomic_json(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     suffix='.tmp', delete=False) as f:
        temp = Path(f.name)
        json.dump(content, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(temp, path)


def atomic_text(path: Path, content):
    """O navegador nunca deve recarregar um HTML ainda pela metade."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         suffix='.tmp', delete=False) as f:
            temp = Path(f.name)
            f.write(content)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def load_json(path: Path):
    if not path.exists():
        return None
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def compact_progress(raw):
    """Conserva nomes implementados para apontar exatamente quais novas funcoes surgiram."""
    if not isinstance(raw, dict) or not isinstance(raw.get('libraries'), dict) or not isinstance(raw.get('shaders'), dict):
        raise ValueError('progress.json mudou de estrutura: faltam libraries/shaders')
    result = {}
    for key in ('libraries', 'shaders'):
        section = raw[key]
        done, total = int(section['done']), int(section['total'])
        if done < 0 or total < 0 or done > total:
            raise ValueError(f'Totais inconsistentes em {key}: {done}/{total}')
        groups = {}
        for group in section.get('groups', []):
            name = group.get('name')
            if not name:
                continue
            groups[name] = {
                'done': int(group.get('done', 0)),
                'total': int(group.get('done', 0)) + int(group.get('todo', 0)),
                'done_names': sorted(group.get('done_names', [])),
            }
        result[key] = {'done': done, 'total': total,
                       'percent': round(100 * done / total, 2) if total else 0,
                       'groups': groups}
    return result


def compact_history(raw):
    """Valida a serie diaria oficial sem atribuir horarios a datas publicadas."""
    if not isinstance(raw, list) or not raw:
        raise ValueError('history.json deve conter uma lista de medições diárias')
    result = {}
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError('Registro inválido em history.json')
        day = row.get('date')
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError('Data inválida em history.json')
        if day in result:
            raise ValueError('Data duplicada em history.json: ' + day)
        entry = {'date': day}
        for key in ('libraries', 'shaders'):
            stat = row.get(key)
            if not isinstance(stat, dict):
                raise ValueError('Métricas ausentes em history.json: ' + key)
            done, total = stat.get('done'), stat.get('total')
            if type(done) is not int or type(total) is not int or not 0 <= done <= total:
                raise ValueError('Totais inconsistentes em history.json: ' + key)
            entry[key] = {'done': done, 'total': total,
                          'percent': round(100 * done / total, 2) if total else 0}
        result[day] = entry
    return [result[day] for day in sorted(result)]


def extract_release(raw):
    if not isinstance(raw, list):
        return None
    for entry in raw:
        if not entry.get('draft'):
            return {'tag': entry.get('tag_name') or '?',
                    'url': entry.get('html_url') or REPO_URL + '/releases'}
    return None


def extract_commits(raw):
    if not isinstance(raw, list):
        return []
    return [{'sha': c['sha'], 'message': c.get('commit', {}).get('message', '').split('\n')[0],
             'body': c.get('commit', {}).get('message', ''),
             'url': c.get('html_url') or REPO_URL}
            for c in raw if c.get('sha')]


def diff_progress(prev, curr):
    events = []
    for key, label in (('libraries', 'Bibliotecas'), ('shaders', 'Instruções GPU')):
        old, new = prev[key], curr[key]
        if (old['done'], old['total']) != (new['done'], new['total']):
            events.append({'kind': 'progress', 'text':
                f"{label}: {old['done']}/{old['total']} ({old['percent']:.2f}%) → "
                f"{new['done']}/{new['total']} ({new['percent']:.2f}%) ",
                'url': PROGRESS_URL})
        for name, now in new['groups'].items():
            was = old.get('groups', {}).get(name)
            if not was:
                if now['done'] or now['total']:
                    events.append({'kind': 'group', 'text': f"Nova categoria {name}: {now['done']}/{now['total']}", 'url': PROGRESS_URL})
                continue
            if (was['done'], was['total']) != (now['done'], now['total']):
                added = sorted(set(now['done_names']) - set(was['done_names']))
                detail = f"; novas: {', '.join(added[:4])}" if added else ''
                if len(added) > 4:
                    detail += f' (+{len(added)-4} outras)'
                events.append({'kind': 'group', 'text':
                    f"{name}: {was['done']}/{was['total']} → {now['done']}/{now['total']}{detail}",
                    'url': PROGRESS_URL})
    return events


def check_updates(previous, current):
    events = []
    if not previous:
        return events
    if previous.get('progress') and current.get('progress'):
        events.extend(diff_progress(previous['progress'], current['progress']))
    old_tag = (previous.get('release') or {}).get('tag')
    new_rel = current.get('release')
    if old_tag and new_rel and new_rel.get('tag') != old_tag:
        events.append({'kind': 'release', 'text': 'Nova versão publicada: ' + new_rel['tag'],
                       'url': new_rel['url']})
    previous_shas = set(previous.get('commit_shas', []))
    # Sem baseline anterior nao infere que commits antigos sao novos.
    if previous_shas and current.get('commits'):
        for c in reversed(current['commits']):
            if c['sha'] not in previous_shas and RELEVANT.search(c['body']):
                events.append({'kind': 'commit', 'text': 'Commit relevante: ' + c['message'],
                               'url': c['url']})
    return events


def get_snapshot(previous):
    issues = []
    current = {'checked_at': utc_now(), 'progress': None, 'release': None,
               'commits': [], 'commit_shas': [], 'errors': [],
               'official_history': [], 'history_error': None, 'progress_error': None}
    try:
        raw = request_json(PROGRESS_URL)
        current['progress'] = compact_progress(raw)
    except Exception as exc:
        current['progress_error'] = 'Falha ao consultar progress.json: ' + str(exc)
        issues.append(current['progress_error'])
    try:
        current['official_history'] = compact_history(request_json(HISTORY_JSON_URL))
    except Exception as exc:
        current['history_error'] = 'Falha ao consultar history.json: ' + str(exc)
        issues.append(current['history_error'])
    token = os.environ.get('GITHUB_TOKEN')
    try:
        current['release'] = extract_release(request_json(API_URL + '/releases?per_page=5', token))
    except Exception as exc:
        issues.append('Falha ao consultar releases: ' + str(exc))
    try:
        current['commits'] = extract_commits(request_json(API_URL + '/commits?per_page=100', token))
        current['commit_shas'] = [c['sha'] for c in current['commits']]
    except Exception as exc:
        issues.append('Falha ao consultar commits: ' + str(exc))
    # Falhas temporarias nao devem apagar o baseline anterior de nenhuma fonte.
    if previous:
        for key in ('progress', 'release', 'commits', 'commit_shas', 'official_history'):
            if not current[key] and previous.get(key):
                current[key] = previous[key]
    current['errors'] = issues
    return current


def event_message(events, current):
    p = current.get('progress') or {}
    l, s = p.get('libraries', {}), p.get('shaders', {})
    header = f"🎮 AnyPS5 Tracker — {current['checked_at']}\n"
    totals = (f"Bibliotecas: {l.get('done', '?')}/{l.get('total', '?')} "
              f"({l.get('percent', '?')}%) | GPU: {s.get('done', '?')}/{s.get('total', '?')} "
              f"({s.get('percent', '?')}%)\n")
    # Limite de tamanho para mensageiros
    selected = events[:20]
    lines = '\n'.join('• ' + ev['text'] + '\n' + ev['url'] for ev in selected)
    extra = f'\n… e mais {len(events)-len(selected)} alterações.' if len(events) > len(selected) else ''
    return (header + totals + lines + extra + '\n\nPercentuais não indicam compatibilidade geral dos jogos.')[:3800]


def send_webhooks(message):
    errors = []
    discord = os.environ.get('ANYPS5_DISCORD_WEBHOOK')
    telegram_token = os.environ.get('ANYPS5_TELEGRAM_BOT_TOKEN')
    telegram_chat = os.environ.get('ANYPS5_TELEGRAM_CHAT_ID')
    if discord:
        if not discord.startswith('https://discord.com/api/webhooks/') and not discord.startswith('https://discordapp.com/api/webhooks/'):
            errors.append('Discord: webhook deve ser URL oficial https://discord.com/api/webhooks/...')
        else:
            try:
                post_json(discord, {'content': message[:1900]})
            except Exception as exc:
                errors.append('Discord: ' + str(exc))
    if telegram_token and telegram_chat:
        try:
            post_json(f'https://api.telegram.org/bot{telegram_token}/sendMessage',
                      {'chat_id': telegram_chat, 'text': message})
        except Exception as exc:
            errors.append('Telegram: ' + str(exc))
    return errors


def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                 headers={'Content-Type': 'application/json',
                                          'User-Agent': 'AnyPS5-Tracker/0.1'}, method='POST')
    with urllib.request.urlopen(req, timeout=20) as response:
        response.read()


def load_history(path=HISTORY_FILE):
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
        except ValueError:
            print(f'AVISO: linha {line_number} do histórico inválida; ignorada no painel.', file=sys.stderr)
    return records


def render_dashboard(current, events, history=None):
    from dashboard import render_panel
    return render_panel(current, events, history or [], PRIORITY_LIBS)


def run():
    parser = argparse.ArgumentParser(description='Monitora o progresso de AnyPS5 no GitHub')
    parser.add_argument('--once', action='store_true', help='Executa uma checagem (padrao)')
    parser.add_argument('--no-notify', action='store_true', help='Nunca envia notificacoes externas')
    parser.add_argument('--render-only', action='store_true',
                        help='Regera o painel com os dados locais, sem coletar nem notificar')
    args = parser.parse_args()
    previous = load_json(STATE_FILE)
    history = load_history()
    if args.render_only:
        if not previous:
            print('ERRO: execute uma coleta antes de gerar o painel offline.', file=sys.stderr)
            return 1
        events = next((row.get('events', []) for row in reversed(history)
                       if row.get('at') == previous.get('checked_at')), [])
        atomic_text(DASHBOARD_FILE, render_dashboard(previous, events, history))
        print('Painel gerado com os dados locais:', DASHBOARD_FILE)
        return 0
    print('Consultando progresso oficial do AnyPS5 e GitHub...')
    current = get_snapshot(previous)
    if not current['progress']:
        print('ERRO: nenhuma medição do progresso disponível. Verifique a conexão.', file=sys.stderr)
        return 1
    events = check_updates(previous, current)
    is_first = previous is None
    status = current['progress']
    print(f"Bibliotecas: {status['libraries']['done']}/{status['libraries']['total']} ({status['libraries']['percent']}%)")
    print(f"GPU:         {status['shaders']['done']}/{status['shaders']['total']} ({status['shaders']['percent']}%)")
    if is_first:
        print('Primeira execução: linha de base criada (sem alerta de novidades antigas).')
    elif events:
        print(f'{len(events)} alterações relevantes:')
        for ev in events[:12]:
            print(' -', ev['text'])
    else:
        print('Nenhuma mudança relevante em relação à última checagem.')
    if current['errors']:
        for err in current['errors']:
            print('AVISO:', err, file=sys.stderr)
    if events and not args.no_notify:
        for err in send_webhooks(event_message(events, current)):
            print('AVISO: falha na notificação:', err, file=sys.stderr)
    DATA_DIR.mkdir(exist_ok=True)
    with HISTORY_FILE.open('a', encoding='utf-8') as f:
        summary = {key: {k: current['progress'][key][k] for k in ('done', 'total', 'percent')}
                   for key in ('libraries', 'shaders')}
        f.write(json.dumps({'at': current['checked_at'], 'summary': summary,
                            'events': events, 'errors': current['errors']}, ensure_ascii=False) + '\n')
    atomic_text(DASHBOARD_FILE, render_dashboard(current, events, history))
    atomic_json(STATE_FILE, current)
    print('Painel gerado:', DASHBOARD_FILE)
    return 0


if __name__ == '__main__':
    sys.exit(run())
