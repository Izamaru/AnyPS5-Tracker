"""Painel local e independente de rede para os dados coletados pelo Tracker."""
from datetime import datetime, timedelta, timezone
import html
import math
from pathlib import Path
import re


AREAS = {
    'libSceAgc': 'Gráficos', 'libSceAgcDriver': 'Driver gráfico',
    'libSceVideoOut': 'Saída de vídeo', 'libkernel': 'Sistema',
    'libc': 'Runtime C', 'libSceAmpr': 'API PS5',
    'libSceAudioOut': 'Saída de áudio', 'libScePad': 'Controles',
    'libSceAjm.native': 'Processamento de áudio',
}
KINDS = {'progress': 'Métricas', 'group': 'Bibliotecas / GPU',
         'release': 'Releases', 'commit': 'Commits'}
HISTORY_DAYS = 30


def escape(value):
    return html.escape(str(value), quote=True)


def number(value):
    return f'{value:,}'.replace(',', '.')


def percent(value, digits=1):
    return f'{value:.{digits}f}'.replace('.', ',') + '%'


def safe_url(value):
    value = str(value)
    return escape(value) if value.startswith('https://') else '#'


def date_label(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%d/%m/%Y às %H:%M')
    except (ValueError, TypeError, AttributeError):
        return str(value or 'Sem registro')


def history_points(current, history):
    """Inclui a coleta atual uma vez e ignora registros sem métricas."""
    rows = [row for row in history or [] if row.get('summary', {}).get('libraries')
            and row.get('at') and row['at'] < current.get('checked_at', '')]
    if (current.get('progress') or {}).get('libraries'):
        rows.append({'at': current.get('checked_at', ''), 'summary': current['progress'],
                     'errors': current.get('errors', [])})
    return rows


def daily_history_points(current, history, tz=None):
    """Um ponto por data: oficial nos dias fechados e leitura atual no dia de hoje."""
    try:
        checked = datetime.fromisoformat(current['checked_at']).astimezone(tz)
    except (ValueError, TypeError, KeyError):
        return []
    today = checked.date().isoformat()
    by_day, latest = {}, {}
    measurements = list(history or [])
    if (current.get('progress') or {}).get('libraries'):
        measurements.append({'at': current['checked_at'], 'summary': current['progress'],
                             'errors': current.get('errors', [])})
    for row in measurements:
        if not (row.get('summary') or {}).get('libraries'):
            continue
        try:
            at = datetime.fromisoformat(row['at']).astimezone(tz)
        except (ValueError, TypeError, KeyError):
            continue
        if at > checked:
            continue
        day = at.date().isoformat()
        if day not in latest or at >= latest[day]:
            latest[day] = at
            by_day[day] = {'date': day, 'summary': row['summary'],
                           'source': 'current' if day == today else 'local',
                           'errors': row.get('errors', [])}
    for row in current.get('official_history') or []:
        day = row['date']
        if day <= today and (day < today or day not in by_day):
            by_day[day] = {'date': day, 'summary': {'libraries': row['libraries']},
                           'source': 'official', 'cached': bool(current.get('history_error'))}
    return [by_day[day] for day in sorted(by_day)]


def daily_label(row):
    return datetime.fromisoformat(row['date']).strftime('%d/%m/%Y')


def daily_source(row):
    if row['source'] == 'current':
        return 'Hoje · parcial'
    if row['source'] == 'official':
        return 'Oficial (salvo)' if row.get('cached') else 'Oficial'
    return 'Local'


def previous_day_record(current, history, tz=None):
    """Prioriza a data publicada no historico oficial; usa o local como alternativa."""
    try:
        yesterday = datetime.fromisoformat(current['checked_at']).astimezone(tz).date() - timedelta(days=1)
    except (ValueError, TypeError, KeyError):
        return None
    # A data oficial e um dia de calendario, nao um instante UTC a converter.
    for row in current.get('official_history') or []:
        if row.get('date') == yesterday.isoformat():
            return {'date': row['date'], 'source': 'official',
                    'summary': {'libraries': row['libraries']}}
    candidates = []
    for row in history or []:
        if row.get('errors') or not row.get('summary', {}).get('libraries'):
            continue
        try:
            at = datetime.fromisoformat(row['at']).astimezone(tz)
        except (ValueError, TypeError, KeyError):
            continue
        if at.date() == yesterday:
            candidates.append((at, row))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def chart_scale(points):
    maximum = max((row['summary']['libraries'][key] for row in points for key in ('done', 'total')), default=0)
    rough = max(1, maximum / 4)
    magnitude = 10 ** math.floor(math.log10(rough))
    step = next(factor * magnitude for factor in (1, 2, 5, 10) if factor * magnitude >= rough)
    return max(step, math.ceil(maximum / step) * step), step


def chart(points):
    if len(points) < 2:
        return '<div class="empty chart-empty">O gráfico aparece quando houver dados de pelo menos dois dias.<br><span>As consultas do mesmo dia são agrupadas em um único ponto.</span></div>'
    points = points[-HISTORY_DAYS:]
    def timestamp(row):
        return datetime.fromisoformat(row['date']).replace(tzinfo=timezone.utc).timestamp()
    times = [timestamp(row) for row in points]
    span = times[-1] - times[0]
    ceiling, step = chart_scale(points)
    coords = []
    grid = ''
    for value in range(0, ceiling + 1, step):
        y = 198 - 176 * value / ceiling
        grid += (f'<line x1="58" y1="{y:.2f}" x2="744" y2="{y:.2f}" class="gridline"/>'
                 f'<text x="46" y="{y+4:.2f}" text-anchor="end">{number(value)}</text>')
    for index, row in enumerate(points):
        x = 58 + 686 * ((times[index] - times[0]) / span if span else index / (len(points) - 1))
        stat = row['summary']['libraries']
        y = 198 - 176 * stat['done'] / ceiling
        declared_y = 198 - 176 * stat['total'] / ceiling
        coords.append((x, y, declared_y, row))
    path = ' '.join(f'{x:.2f},{y:.2f}' for x, y, _, _ in coords)
    declared_path = ' '.join(f'{x:.2f},{y:.2f}' for x, _, y, _ in coords)
    dots = ''.join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" class="chart-dot"><title>'
                   f'{daily_label(row)} · {daily_source(row)}: '
                   f'{number(row["summary"]["libraries"]["done"])} implementadas · {number(row["summary"]["libraries"]["total"])} declaradas'
                   f'{" (fonte com aviso; pode usar dados anteriores)" if row.get("errors") else ""}'
                   '</title></circle>' for x, y, _, row in coords)
    last = points[-1]['summary']['libraries']
    return (f'<svg class="history-chart" viewBox="0 0 776 234" role="img" aria-labelledby="chart-title chart-description">'
            '<title id="chart-title">Evolução da quantidade de funções das bibliotecas PS5</title>'
            '<desc id="chart-description">Quantidade diária de funções implementadas, em linha contínua, e declaradas, em linha tracejada. Escala comum a partir de zero, ajustada ao maior total. Um ponto por dia; hoje é parcial. Valores e fontes na tabela diária.</desc>'
            f'{grid}<polygon points="58,198 {path} 744,198" class="chart-area"/>'
            f'<polyline points="{declared_path}" class="chart-declared-line"/>'
            f'<polyline points="{path}" class="chart-line"/>{dots}'
            f'<text x="58" y="225">{daily_label(points[0])}</text>'
            f'<text x="744" y="225" text-anchor="end">{daily_label(points[-1])}</text></svg>'
            f'<div class="chart-summary"><span>Implementadas <strong class="green">{number(last["done"])}</strong></span>'
            f'<span>Declaradas <strong>{number(last["total"])}</strong></span><small>{daily_label(points[-1])}</small></div>')


def render_panel(current, events, history, priority):
    progress = current.get('progress') or {}
    libs, gpu = progress.get('libraries', {}), progress.get('shaders', {})
    measurements = history_points(current, history)
    previous = measurements[-2]['summary'].get('libraries') if len(measurements) > 1 else None
    points = daily_history_points(current, history)[-HISTORY_DAYS:]
    has_libs, has_gpu = bool(libs), bool(gpu)
    done, total = libs.get('done', 0), libs.get('total', 0)
    coverage = libs.get('percent', 0)
    delta_html = '<span class="muted">Sem medição do dia anterior</span>'
    day_before = previous_day_record(current, history)
    if day_before and has_libs:
        daily_delta = done - day_before['summary']['libraries']['done']
        daily_sign = '+' if daily_delta > 0 else '−' if daily_delta < 0 else ''
        daily_tone = 'rose' if daily_delta < 0 else 'delta' if daily_delta > 0 else 'muted'
        if day_before.get('source') == 'official':
            day_label = datetime.fromisoformat(day_before['date']).strftime('%d/%m/%Y')
            source_name = 'histórico oficial (salvo)' if current.get('history_error') else 'histórico oficial'
            baseline_label = escape(f'Referência do dia anterior: {day_label} · {number(day_before["summary"]["libraries"]["done"])} funções · {source_name}')
            source_html = f' · <a href="https://boykopovar.github.io/AnyPS5/history.html" target="_blank" rel="noopener noreferrer">{source_name} ↗</a>'
        else:
            baseline_label = escape('Última medição do dia anterior: ' + date_label(day_before['at']) + ' · histórico local')
            source_html = ' · histórico local'
        delta_html = (f'<span title="{baseline_label}"><span class="{daily_tone}">{daily_sign}{number(abs(daily_delta))} funções</span>'
                      f'<span class="muted"> vs. dia anterior{source_html}</span></span>')
    insight = 'Execute o Tracker novamente para comparar a evolução entre checagens.'
    if previous and has_libs:
        delta_done, delta_total = done - previous['done'], total - previous['total']
        delta_pct = coverage - previous['percent']
        signed = lambda n: ('+' if n > 0 else '−' if n < 0 else '') + number(abs(n))
        change = f'{delta_pct:+.2f}'.replace('.', ',')
        insight = (f'{signed(delta_done)} implementadas e {signed(delta_total)} declaradas desde a checagem anterior. '
                   f'A cobertura variou {change} p.p.')
        if delta_done > 0 and delta_pct < 0:
            insight += ' O total declarado cresceu mais que as implementações; a queda percentual não significa perda de funções.'
    if current.get('errors'):
        insight = 'Uma ou mais fontes falharam nesta coleta. Confira os avisos antes de interpretar a comparação; dados anteriores podem ter sido preservados.'
    if current.get('progress_error') or (current.get('errors') and 'progress_error' not in current):
        delta_html = '<span class="muted">Coleta com avisos; os números podem vir da leitura anterior.</span>'
    rows = []
    groups = libs.get('groups', {})
    ordered = [name for name in priority if name in groups] + sorted(set(groups) - set(priority))
    for name in ordered:
        group = groups[name]
        completed, declared = group['done'], group['total']
        value = 100 * completed / declared if declared else 0
        tone = 'green' if value >= 90 else 'amber' if value >= 50 else 'rose'
        level = 'complete' if declared and completed == declared else 'pending'
        area = AREAS.get(name, 'Biblioteca do sistema')
        rows.append(f'<tr data-priority="{str(name in priority).lower()}" data-level="{level}" data-percent="{value:.4f}" data-name="{escape(name.lower())}"'
                    f'{" hidden" if name not in priority else ""}>'
                    f'<th scope="row"><span class="lib-name">{escape(name)}</span><span class="lib-area">{area}</span></th>'
                    f'<td>{number(completed)}<span class="of-total"> / {number(declared)}</span></td>'
                    f'<td>{number(max(0, declared-completed))}</td><td><div class="coverage {tone}"><span>{percent(value) if declared else "—"}</span>'
                    f'<div class="mini-track" aria-hidden="true"><i style="width:{max(0,min(100,value)):.2f}%"></i></div></div></td></tr>')
    event_rows = []
    counts = {kind: sum(ev.get('kind') == kind for ev in events) for kind in KINDS}
    for ev in events:
        kind = ev.get('kind', 'other')
        text = ev.get('text', '').removeprefix('Commit relevante: ')
        event_rows.append(f'<li data-kind="{escape(kind)}"><span class="event-mark {escape(kind)}" aria-hidden="true">'
                          f'{"↗" if kind == "commit" else "◈" if kind == "release" else "+"}</span><div>'
                          f'<span class="event-kind">{KINDS.get(kind, "Atualização")}</span>'
                          f'<a href="{safe_url(ev.get("url", ""))}" target="_blank" rel="noopener noreferrer">{escape(text)} <span class="external" aria-hidden="true">↗</span></a>'
                          '</div></li>')
    filters = ''.join(f'<button type="button" data-filter="{kind}" aria-pressed="false">{label} <span>{counts[kind]}</span></button>' for kind, label in KINDS.items())
    release = current.get('release') or {}
    errors = ''.join(f'<li>{escape(err)}</li>' for err in current.get('errors', []))
    history_rows = ''.join(f'<tr><th scope="row">{daily_label(row)}<span class="lib-area">{daily_source(row)}{" · com avisos" if row.get("errors") else ""}</span></th>'
                           f'<td>{number(row["summary"]["libraries"]["done"])}</td>'
                           f'<td>{number(row["summary"]["libraries"]["total"])}</td>'
                           f'<td>{percent(row["summary"]["libraries"]["percent"], 2)}</td></tr>' for row in reversed(points))
    values = {
        'checked_at': escape(current.get('checked_at', '')),
        'checked_label': escape(date_label(current.get('checked_at'))),
        'status_class': 'amber' if errors else 'green',
        'status': 'Coleta com avisos' if errors else 'Última coleta concluída',
        'lib_done': number(done) if has_libs else '—', 'lib_total': number(total) if has_libs else '—',
        'lib_percent': percent(coverage, 2) if has_libs else '—',
        'lib_width': f'{max(0,min(100,coverage)):.2f}',
        'remaining': number(max(0, total-done)) if has_libs else '—',
        'delta': delta_html, 'insight': escape(insight),
        'gpu_percent': percent(gpu.get('percent', 0), 2) if has_gpu else '—',
        'gpu_done': number(gpu.get('done', 0)) if has_gpu else '—',
        'gpu_total': number(gpu.get('total', 0)) if has_gpu else '—',
        'gpu_width': f'{max(0,min(100,gpu.get("percent",0))):.2f}',
        'release': escape(release.get('tag', 'Sem registro')),
        'release_url': safe_url(release.get('url', 'https://github.com/boykopovar/AnyPS5/releases')),
        'chart': chart(points), 'history_rows': history_rows,
        'history_count': str(len(points)), 'library_count': str(len(groups)),
        'priority_count': str(sum(name in groups for name in priority)),
        'library_rows': ''.join(rows), 'event_count': str(len(events)),
        'event_filters': filters, 'event_rows': ''.join(event_rows),
        'event_empty_hidden': ' hidden' if events else '',
        'errors': f'<aside class="collection-warning" role="status"><strong>Avisos da coleta</strong><ul>{errors}</ul></aside>' if errors else '',
    }
    template = Path(__file__).with_name('painel-template.html').read_text(encoding='utf-8')
    return re.sub(r'\{\{(\w+)\}\}', lambda m: values[m[1]], template)
