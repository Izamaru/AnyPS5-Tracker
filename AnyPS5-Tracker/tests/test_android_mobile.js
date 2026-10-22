// Coleta móvel, cache offline e renderização sem dependências externas.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const androidDir = path.resolve(__dirname, '../../android');
const mobile = require(path.join(androidDir, 'mobile.js'));

function rawProgress(done=2, total=3, names=['a','b']) {
  return {
    libraries:{done,total,groups:[{name:'libSceAgc',done,todo:total-done,done_names:names}]},
    shaders:{done:2,total:2,groups:[{name:'DS',done:2,todo:0,done_names:['DS_A','DS_B']}]},
  };
}
function day(date, done=2, total=3) {
  return {date, libraries:{done,total}, shaders:{done:2,total:2}};
}
function responses(url) {
  if (url.endsWith('/progress.json')) return rawProgress();
  if (url.endsWith('/history.json')) return [day('2026-10-18')];
  if (url.includes('/releases?')) return [{tag_name:'v1',html_url:'https://github.com/example/release'}];
  if (url.includes('/commits?')) return [{sha:'abc',commit:{message:'Shader cache fix'},html_url:'https://github.com/example/abc'}];
  throw new Error('URL inesperada: '+url);
}
async function main() {
  assert.equal(mobile.compactProgress(rawProgress()).libraries.percent, 66.67);
  assert.throws(() => mobile.compactProgress(rawProgress(4,3)));
  assert.throws(() => mobile.compactHistory([day('2026-02-31')]));
  assert.throws(() => mobile.compactHistory([day('2026-10-18'), day('2026-10-18')]));
  assert.equal(mobile.compactHistory([day('2026-10-18')])[0].libraries.percent, 66.67);
  const calls = [];
  const current = await mobile.collectSnapshot(null, async (url,options) => {
    calls.push(url);
    assert.equal(options.cache, 'no-store');
    return {ok:true,json:async () => responses(url)};
  });
  assert.equal(calls.length, 4);
  assert.equal(current.errors.length, 0);
  assert.equal(current.progress.libraries.done, 2);
  assert.equal(current.progress_as_of, current.checked_at);
  assert.deepEqual(mobile.eventsBetween(null,current), []);
  const offline = await mobile.collectSnapshot(current, async () => { throw new Error('offline'); });
  assert.equal(offline.errors.length, 4);
  assert.equal(offline.progress_as_of, current.progress_as_of);
  assert.equal(offline.progress.libraries.done, 2);
  assert.deepEqual(offline.official_history, current.official_history);
  const days = mobile.updateDays([], current);
  assert.equal(days.length, 1);
  const repeated = mobile.updateDays(days, {...current,progress:mobile.compactProgress(rawProgress(3,3))});
  assert.equal(repeated.length, 1);
  assert.equal(repeated[0].summary.libraries.done, 3);
  assert.deepEqual(mobile.updateDays(repeated, offline), repeated);
  const previous = {...current,commit_shas:['abc']};
  const changed = {...current,progress:mobile.compactProgress(rawProgress(3,3,['a','b','c'])),
    commits:[{sha:'new',body:'Fix shader GPU cache',message:'<script>alert(1)</script>',url:'javascript:alert(1)'}]};
  const events = mobile.eventsBetween(previous, changed);
  assert.equal(events.filter(event => event.kind === 'commit').length, 1);
  assert.ok(events.some(event => event.text.includes('novas: c')));
  const fixed = {...changed,checked_at:'2026-10-19T17:00:00Z',progress_as_of:'2026-10-19T17:00:00Z',
    official_history:mobile.compactHistory([day('2026-10-18',2,3),day('2026-10-19',2,3),day('2026-10-20',3,3)])};
  const localDays = [{date:'2026-10-18',summary:{libraries:{done:1,total:3,percent:33.33}}},
                     {date:'2026-10-19',summary:{libraries:fixed.progress.libraries}}];
  const points = mobile.dailyPoints(fixed, localDays);
  assert.equal(points.length,2);
  assert.equal(points[0].summary.libraries.done,2);
  assert.equal(points[1].summary.libraries.done,3);
  assert.equal(points[1].source,'Hoje · parcial');
  const numericPoints = [
    {date:'2026-10-19',source:'Oficial',summary:{libraries:{done:4000,total:4000,percent:100}}},
    {date:'2026-10-20',source:'Hoje · parcial',summary:{libraries:{done:4000,total:6600,percent:60.61}}},
  ];
  const chart = mobile.renderChart(numericPoints);
  function heights(markup, className) {
    const path = markup.match(new RegExp('<polyline points="([^"]+)" class="'+className+'"'))[1];
    return path.split(' ').map(pair => Number(pair.split(',')[1]));
  }
  assert.deepEqual(mobile.chartScale(numericPoints),{ceiling:8000,step:2000});
  const implemented = heights(chart,'chart-line');
  const declared = heights(chart,'chart-declared-line');
  assert.equal(implemented[0],implemented[1]);
  assert.ok(declared[1] < declared[0]);
  assert.ok(chart.includes('8.000</text>'));
  assert.ok(chart.includes('6.600 declaradas'));
  assert.ok(!chart.includes('%'));
  const zeroPoints = numericPoints.map(row => ({...row,summary:{libraries:{done:0,total:0}}}));
  assert.deepEqual(heights(mobile.renderChart(zeroPoints),'chart-line'),[198,198]);
  const revised = numericPoints.map((row,index) => ({...row,summary:{libraries:{done:index ? 3 : 5,total:8}}}));
  const revisedHeights = heights(mobile.renderChart(revised),'chart-line');
  assert.ok(revisedHeights[1] > revisedHeights[0]);
  const values = mobile.renderValues(fixed,previous,localDays,events);
  const base = new Date('2026-10-22T17:00:00Z');
  const dated = offset => new Date(base.getTime()+offset*86400000).toISOString().slice(0,10);
  const longCurrent = {...fixed,checked_at:base.toISOString(),
    official_history:mobile.compactHistory(Array.from({length:40},(_,index) => day(dated(index-40))))};
  let longDays = [];
  for (const advance of [0,1]) {
    longCurrent.checked_at = new Date(base.getTime()+advance*86400000).toISOString();
    longDays = mobile.updateDays(longDays,longCurrent);
    const window = mobile.renderValues(longCurrent,previous,longDays,[]);
    const label = offset => dated(offset).split('-').reverse().join('/');
    assert.equal(window.history_count,'30');
    assert.equal((window.chart.match(/class="chart-dot"/g) || []).length,30);
    assert.equal((window.history_rows.match(/<tr>/g) || []).length,30);
    for (const markup of [window.chart,window.history_rows]) {
      assert.ok(markup.includes(label(advance-29)));
      assert.ok(!markup.includes(label(advance-30)));
    }
  }
  assert.equal(longCurrent.official_history.length,40);
  assert.ok(values.delta.includes('+1 funções'));
  assert.ok(values.delta.includes('histórico oficial'));
  assert.ok(values.event_rows.includes('&lt;script&gt;'));
  assert.ok(!values.event_rows.includes('javascript:'));
  assert.ok(!values.event_rows.includes('<script>'));
  const configPath = path.join(androidDir,'build/assets/config.js');
  assert.ok(fs.existsSync(configPath),'Execute ../android/prepare_assets.py a partir da pasta AnyPS5-Tracker antes deste teste.');
  const context = {window:{}};
  vm.runInNewContext(fs.readFileSync(configPath,'utf8'),context);
  const body = context.window.TrackerConfig.body;
  assert.ok(body.includes('últimos 30 dias com registro'));
  assert.ok(body.includes('<main id="conteudo">'));
  assert.ok(body.includes('Atualizar agora'));
  for (const match of body.matchAll(/\{\{(\w+)\}\}/g)) assert.ok(match[1] in values,match[1]);
  assert.ok(!body.includes('INICIAR.bat'));
  assert.ok(!body.includes('INSTALAR-BOT'));
  assert.ok(!body.includes('target="_blank"'));
  const offlineValues = mobile.renderValues(offline,current,days,[]);
  assert.equal(offlineValues.lib_done,'2');
  assert.ok(offlineValues.status.includes('Dados salvos'));
  console.log('OK: coleta Android, cache offline, gráfico quantitativo, histórico diário, links e template.');
}
main().catch(error => { console.error(error); process.exitCode=1; });
