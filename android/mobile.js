/* Coleta e apresentação Android. Não depende do Python ou de um PC ligado. */
(function () {
  'use strict';
  const BASE = 'https://boykopovar.github.io/AnyPS5';
  const REPO = 'https://github.com/boykopovar/AnyPS5';
  const API = 'https://api.github.com/repos/boykopovar/AnyPS5';
  const CACHE_KEY = 'anyps5-android-data-v1';
  const PRIORITY = ['libSceAgc', 'libSceAgcDriver', 'libSceVideoOut', 'libkernel', 'libc', 'libSceAmpr', 'libSceAudioOut', 'libScePad', 'libSceAjm.native'];
  const AREAS = {libSceAgc:'Gráficos', libSceAgcDriver:'Driver gráfico', libSceVideoOut:'Saída de vídeo', libkernel:'Sistema', libc:'Runtime C', libSceAmpr:'API PS5', libSceAudioOut:'Saída de áudio', libScePad:'Controles', 'libSceAjm.native':'Processamento de áudio'};
  const KINDS = {progress:'Métricas', group:'Bibliotecas / GPU', release:'Releases', commit:'Commits'};
  const RELEVANT = /ghost[ -]?of[ -]?y[oō]tei|\by[oō]tei\b|\batsu\b|vram|memory|mem[oó]ria|vulkan|shader|relink|render|texture|graphics|\bgpu\b|\bagc\b|\bfps\b|heap|allocat|cache|frame ?rate|performance|driver|video.?out|viewport|pipeline|out.of.memory|oom/i;
  const escape = value => String(value == null ? '' : value).replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#x27;'}[char]));
  const number = value => Number(value).toLocaleString('pt-BR');
  const percent = (value, digits=1) => Number(value).toFixed(digits).replace('.', ',') + '%';
  const signed = value => (value > 0 ? '+' : value < 0 ? '−' : '') + number(Math.abs(value));
  const width = value => Math.max(0, Math.min(100, Number(value) || 0)).toFixed(2);
  const safeURL = value => typeof value === 'string' && value.startsWith('https://') ? escape(value) : '#';
  const localDay = value => {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) throw new Error('Data inválida');
    return date.getFullYear() + '-' + String(date.getMonth()+1).padStart(2,'0') + '-' + String(date.getDate()).padStart(2,'0');
  };
  const dayLabel = day => day.split('-').reverse().join('/');
  const dateLabel = value => new Date(value).toLocaleString('pt-BR', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'});
  function metric(raw) {
    if (!raw || !Number.isInteger(raw.done) || !Number.isInteger(raw.total) || raw.done < 0 || raw.total < raw.done) throw new Error('Totais inconsistentes');
    return {done:raw.done, total:raw.total, percent:raw.total ? Math.round(10000*raw.done/raw.total)/100 : 0};
  }
  function compactProgress(raw) {
    const result = {};
    for (const key of ['libraries', 'shaders']) {
      result[key] = metric(raw && raw[key]);
      const groups = {};
      for (const group of raw[key].groups || []) {
        if (typeof group.name !== 'string' || !group.name) continue;
        const stat = metric({done:group.done, total:group.done+group.todo});
        groups[group.name] = {...stat, done_names:(group.done_names || []).map(String).sort()};
      }
      result[key].groups = groups;
    }
    return result;
  }
  function compactHistory(raw) {
    if (!Array.isArray(raw) || !raw.length) throw new Error('Histórico diário inválido');
    const days = new Map();
    for (const row of raw) {
      if (!row || !/^\d{4}-\d{2}-\d{2}$/.test(row.date) || !Number.isFinite(Date.parse(row.date)) || new Date(row.date).toISOString().slice(0,10) !== row.date || days.has(row.date)) throw new Error('Data inválida no histórico');
      days.set(row.date, {date:row.date, libraries:metric(row.libraries), shaders:metric(row.shaders)});
    }
    return Array.from(days.values()).sort((a,b) => a.date.localeCompare(b.date));
  }
  function extractRelease(raw) {
    if (!Array.isArray(raw)) throw new Error('Resposta de releases inválida');
    const release = raw.find(item => !item.draft);
    return release ? {tag:release.tag_name || '?', url:release.html_url || REPO+'/releases'} : null;
  }
  function extractCommits(raw) {
    if (!Array.isArray(raw)) throw new Error('Resposta de commits inválida');
    return raw.filter(row => row.sha).map(row => ({sha:row.sha, message:String(row.commit && row.commit.message || '').split('\n')[0], body:String(row.commit && row.commit.message || ''), url:row.html_url || REPO}));
  }
  async function collectSnapshot(previous, fetcher) {
    const checked = new Date().toISOString();
    const current = {checked_at:checked, progress:null, progress_as_of:previous && (previous.progress_as_of || previous.checked_at), official_history:[], release:null, commits:[], commit_shas:[], errors:[], progress_error:null, history_error:null};
    const specs = [
      ['progress', BASE+'/progress.json', compactProgress],
      ['official_history', BASE+'/history.json', compactHistory],
      ['release', API+'/releases?per_page=5', extractRelease],
      ['commits', API+'/commits?per_page=100', extractCommits],
    ];
    await Promise.all(specs.map(async ([key,url,validate]) => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 18000);
      try {
        const response = await fetcher(url, {signal:controller.signal, cache:'no-store', headers:{Accept:'application/json'}});
        if (!response.ok) throw new Error('HTTP '+response.status);
        current[key] = validate(await response.json());
        if (key === 'progress') current.progress_as_of = checked;
      } catch (error) {
        const label = {progress:'progresso', official_history:'histórico oficial', release:'releases', commits:'commits'}[key];
        const message = 'Não foi possível atualizar '+label+'. '+(error.name === 'AbortError' ? 'Tempo de resposta excedido.' : String(error.message || error));
        current.errors.push(message);
        if (key === 'progress') current.progress_error = message;
        if (key === 'official_history') current.history_error = message;
        if (previous && previous[key]) current[key] = previous[key];
      } finally { clearTimeout(timer); }
    }));
    current.commit_shas = current.commits.map(commit => commit.sha);
    return current;
  }
  function eventsBetween(previous, current) {
    if (!previous) return [];
    const events = [];
    if (previous.progress && current.progress && !current.progress_error) {
      for (const [key,label] of [['libraries','Bibliotecas'],['shaders','Instruções GPU']]) {
        const before = previous.progress[key], now = current.progress[key];
        if (before.done !== now.done || before.total !== now.total) events.push({kind:'progress', text:label+': '+before.done+'/'+before.total+' → '+now.done+'/'+now.total, url:BASE+'/progress.json'});
        for (const [name,stat] of Object.entries(now.groups || {})) {
          const old = (before.groups || {})[name];
          if (!old || old.done !== stat.done || old.total !== stat.total) {
            const added = stat.done_names.filter(value => !old || !old.done_names.includes(value));
            let text = name+': '+(old ? old.done+'/'+old.total+' → ' : 'nova categoria ')+stat.done+'/'+stat.total;
            if (added.length) text += '; novas: '+added.slice(0,4).join(', ')+(added.length > 4 ? ' (+'+(added.length-4)+' outras)' : '');
            events.push({kind:'group', text, url:BASE+'/progress.json'});
          }
        }
      }
    }
    if (previous.release && current.release && previous.release.tag !== current.release.tag) events.push({kind:'release', text:'Nova versão publicada: '+current.release.tag, url:current.release.url});
    const known = new Set(previous.commit_shas || []);
    if (known.size) for (const commit of [...current.commits].reverse()) if (!known.has(commit.sha) && RELEVANT.test(commit.body)) events.push({kind:'commit', text:commit.message, url:commit.url});
    return events;
  }
  function updateDays(previousDays, current) {
    const rows = Array.isArray(previousDays) ? [...previousDays] : [];
    if (current.progress && !current.progress_error) {
      const date = localDay(current.checked_at);
      const summary = {};
      for (const key of ['libraries','shaders']) summary[key] = metric(current.progress[key]);
      const row = {date, at:current.checked_at, summary};
      const index = rows.findIndex(item => item.date === date);
      if (index >= 0) rows[index] = row; else rows.push(row);
    }
    return rows.sort((a,b) => a.date.localeCompare(b.date)).slice(-180);
  }
  function dailyPoints(current, days) {
    const today = localDay(current.checked_at);
    const points = new Map();
    for (const row of days || []) if (row.date <= today) points.set(row.date, {...row, source:row.date === today ? 'Hoje · parcial' : 'Local'});
    for (const row of current.official_history || []) if (row.date <= today && (row.date < today || !points.has(row.date))) points.set(row.date, {date:row.date, summary:{libraries:row.libraries}, source:current.history_error ? 'Oficial (salvo)' : 'Oficial'});
    return Array.from(points.values()).sort((a,b) => a.date.localeCompare(b.date));
  }
  function yesterdayRecord(current, days) {
    const date = new Date(current.checked_at);
    date.setDate(date.getDate()-1);
    const yesterday = localDay(date);
    const official = (current.official_history || []).find(row => row.date === yesterday);
    if (official) return {date:yesterday, stat:official.libraries, official:true};
    const local = (days || []).find(row => row.date === yesterday);
    return local ? {date:yesterday, stat:local.summary.libraries, official:false} : null;
  }
  function chartScale(points) {
    let maximum = 0;
    for (const row of points) maximum = Math.max(maximum, row.summary.libraries.done, row.summary.libraries.total);
    const rough = Math.max(1, maximum/4);
    const magnitude = 10 ** Math.floor(Math.log10(rough));
    const step = [1,2,5,10].find(factor => factor*magnitude >= rough)*magnitude;
    return {ceiling:Math.max(step, Math.ceil(maximum/step)*step), step};
  }
  function renderChart(allPoints) {
    const points = allPoints.slice(-60);
    if (points.length < 2) return '<div class="empty chart-empty">O gráfico aparece quando houver dados de pelo menos dois dias.<br><span>As consultas do mesmo dia são agrupadas em um único ponto.</span></div>';
    const start = Date.parse(points[0].date), span = Date.parse(points[points.length-1].date)-start;
    const {ceiling,step} = chartScale(points);
    const coords = points.map(row => ({...row, x:58+686*(Date.parse(row.date)-start)/span,
      y:198-176*row.summary.libraries.done/ceiling, declaredY:198-176*row.summary.libraries.total/ceiling}));
    const path = coords.map(row => row.x.toFixed(2)+','+row.y.toFixed(2)).join(' ');
    const declaredPath = coords.map(row => row.x.toFixed(2)+','+row.declaredY.toFixed(2)).join(' ');
    let grid = '';
    for (let value=0; value<=ceiling; value+=step) {
      const y = 198-176*value/ceiling;
      grid += '<line x1="58" y1="'+y.toFixed(2)+'" x2="744" y2="'+y.toFixed(2)+'" class="gridline"/><text x="46" y="'+(y+4).toFixed(2)+'" text-anchor="end">'+number(value)+'</text>';
    }
    const dots = coords.map(row => '<circle cx="'+row.x.toFixed(2)+'" cy="'+row.y.toFixed(2)+'" r="4" class="chart-dot"><title>'+dayLabel(row.date)+' · '+row.source+': '+number(row.summary.libraries.done)+' implementadas · '+number(row.summary.libraries.total)+' declaradas</title></circle>').join('');
    const last = points[points.length-1];
    return '<svg class="history-chart" viewBox="0 0 776 234" role="img" aria-labelledby="chart-title chart-description"><title id="chart-title">Evolução da quantidade de funções das bibliotecas PS5</title><desc id="chart-description">Quantidade diária de funções implementadas, em linha contínua, e declaradas, em linha tracejada. Escala comum a partir de zero, ajustada ao maior total. Um ponto por dia; hoje é parcial. Valores e fontes na tabela diária.</desc>'+grid+'<polygon points="58,198 '+path+' 744,198" class="chart-area"/><polyline points="'+declaredPath+'" class="chart-declared-line"/><polyline points="'+path+'" class="chart-line"/>'+dots+'<text x="58" y="225">'+dayLabel(points[0].date)+'</text><text x="744" y="225" text-anchor="end">'+dayLabel(last.date)+'</text></svg><div class="chart-summary"><span>Implementadas <strong class="green">'+number(last.summary.libraries.done)+'</strong></span><span>Declaradas <strong>'+number(last.summary.libraries.total)+'</strong></span><small>'+dayLabel(last.date)+'</small></div>';
  }
  function renderValues(current, previous, days, events) {
    const libs = current.progress.libraries, gpu = current.progress.shaders;
    const points = dailyPoints(current, days);
    const baseline = yesterdayRecord(current, days);
    let delta = '<span class="muted">Sem medição do dia anterior</span>';
    if (baseline) {
      const value = libs.done-baseline.stat.done;
      const source = baseline.official ? 'histórico oficial'+(current.history_error ? ' (salvo)' : '') : 'histórico local';
      delta = '<span title="'+escape(dayLabel(baseline.date)+' · '+number(baseline.stat.done)+' funções')+'"><span class="'+(value<0 ? 'rose' : value>0 ? 'delta' : 'muted')+'">'+signed(value)+' funções</span><span class="muted"> vs. dia anterior · '+(baseline.official ? '<a href="'+BASE+'/history.html">'+source+' ↗</a>' : source)+'</span></span>';
    }
    let insight = 'Esta é a primeira leitura neste celular. As próximas consultas mostrarão as mudanças.';
    if (previous && previous.progress) {
      const before = previous.progress.libraries, doneDelta = libs.done-before.done, totalDelta = libs.total-before.total;
      insight = signed(doneDelta)+' implementadas e '+signed(totalDelta)+' declaradas desde a checagem anterior. A cobertura variou '+(libs.percent-before.percent).toFixed(2).replace('.', ',')+' p.p.';
      if (doneDelta > 0 && libs.percent < before.percent) insight += ' O total declarado cresceu mais que as implementações; a queda percentual não significa perda de funções.';
    }
    if (current.progress_error) { delta = '<span class="muted">Dados salvos; a coleta de progresso está indisponível.</span>'; insight = 'Exibindo a última leitura salva. Tente atualizar novamente quando houver conexão.'; }
    const groups = libs.groups || {};
    const ordered = PRIORITY.filter(name => groups[name]).concat(Object.keys(groups).filter(name => !PRIORITY.includes(name)).sort());
    const rows = ordered.map(name => {
      const stat = groups[name], value = stat.total ? 100*stat.done/stat.total : 0;
      const level = stat.total && stat.done === stat.total ? 'complete' : 'pending';
      const tone = value>=90 ? 'green' : value>=50 ? 'amber' : 'rose';
      return '<tr data-priority="'+PRIORITY.includes(name)+'" data-level="'+level+'" data-percent="'+value.toFixed(4)+'" data-name="'+escape(name.toLowerCase())+'"'+(!PRIORITY.includes(name) ? ' hidden' : '')+'><th scope="row"><span class="lib-name">'+escape(name)+'</span><span class="lib-area">'+(AREAS[name] || 'Biblioteca do sistema')+'</span></th><td>'+number(stat.done)+'<span class="of-total"> / '+number(stat.total)+'</span></td><td>'+number(stat.total-stat.done)+'</td><td><div class="coverage '+tone+'"><span>'+(stat.total ? percent(value) : '—')+'</span><div class="mini-track" aria-hidden="true"><i style="width:'+width(value)+'%"></i></div></div></td></tr>';
    }).join('');
    const eventRows = events.map(event => '<li data-kind="'+escape(event.kind)+'"><span class="event-mark '+escape(event.kind)+'" aria-hidden="true">'+(event.kind === 'commit' ? '↗' : '+')+'</span><div><span class="event-kind">'+KINDS[event.kind]+'</span><a href="'+safeURL(event.url)+'" rel="noopener noreferrer">'+escape(event.text)+' <span class="external" aria-hidden="true">↗</span></a></div></li>').join('');
    const filters = Object.entries(KINDS).map(([kind,label]) => '<button type="button" data-filter="'+kind+'" aria-pressed="false">'+label+' <span>'+events.filter(event => event.kind === kind).length+'</span></button>').join('');
    const historyRows = [...points.slice(-60)].reverse().map(row => '<tr><th scope="row">'+dayLabel(row.date)+'<span class="lib-area">'+row.source+'</span></th><td>'+number(row.summary.libraries.done)+'</td><td>'+number(row.summary.libraries.total)+'</td><td>'+percent(row.summary.libraries.percent,2)+'</td></tr>').join('');
    return {
      checked_at:escape(current.progress_as_of || current.checked_at), checked_label:escape(dateLabel(current.progress_as_of || current.checked_at)),
      status_class:current.errors.length ? 'amber' : 'green', status:current.progress_error ? 'Dados salvos · coleta indisponível' : current.errors.length ? 'Coleta com avisos' : 'Última coleta concluída',
      lib_done:number(libs.done), lib_total:number(libs.total), lib_percent:percent(libs.percent,2), lib_width:width(libs.percent), remaining:number(libs.total-libs.done), delta, insight:escape(insight),
      gpu_percent:percent(gpu.percent,2), gpu_done:number(gpu.done), gpu_total:number(gpu.total), gpu_width:width(gpu.percent),
      release:escape(current.release ? current.release.tag : 'Sem registro'), release_url:safeURL(current.release ? current.release.url : REPO+'/releases'),
      chart:renderChart(points), history_rows:historyRows, history_count:String(points.length), library_count:String(ordered.length), priority_count:String(PRIORITY.filter(name => groups[name]).length), library_rows:rows,
      event_count:String(events.length), event_filters:filters, event_rows:eventRows, event_empty_hidden:events.length ? ' hidden' : '',
      errors:current.errors.length ? '<aside class="collection-warning" role="status"><strong>Avisos da coleta</strong><ul>'+current.errors.map(error => '<li>'+escape(error)+'</li>').join('')+'</ul></aside>' : '',
    };
  }
  async function start() {
    let cache = {};
    try { cache = JSON.parse(window.localStorage.getItem(CACHE_KEY) || '{}') || {}; } catch {}
    window.TrackerLastRequestAt = Date.now();
    try {
      const previous = cache.snapshot && cache.snapshot.progress ? cache.snapshot : null;
      const current = await collectSnapshot(previous, window.fetch.bind(window));
      if (!current.progress) throw new Error('Conecte o celular à internet para carregar o progresso pela primeira vez.');
      const days = updateDays(cache.days, current);
      const events = eventsBetween(previous, current);
      try { window.localStorage.setItem(CACHE_KEY, JSON.stringify({snapshot:current, days})); } catch {}
      const values = renderValues(current, previous, days, events);
      document.body.innerHTML = window.TrackerConfig.body.replace(/\{\{(\w+)\}\}/g, (match,key) => {
        if (!(key in values)) throw new Error('Campo ausente: '+key);
        return values[key];
      });
      const controls = document.createElement('script');
      controls.src = 'controls.js';
      document.body.appendChild(controls);
    } catch (error) {
      document.body.innerHTML = '<main style="max-width:540px;margin:14vh auto;padding:24px"><div class="eyebrow">AnyPS5 Tracker</div><h1>Não foi possível carregar.</h1><p class="muted">'+escape(error.message)+'</p><button class="more-button" style="margin-top:24px" onclick="location.reload()">Tentar novamente</button></main>';
    }
  }
  const exported = {compactProgress, compactHistory, collectSnapshot, eventsBetween, updateDays, dailyPoints, yesterdayRecord, chartScale, renderChart, renderValues, localDay, escape};
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else { window.TrackerMobile = exported; start(); }
})();
