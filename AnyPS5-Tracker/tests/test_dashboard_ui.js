// Verifica o JavaScript gerado sem navegador nem dependências externas.
// Executar: node tests/test_dashboard_ui.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'painel-template.html'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
function element(dataset = {}) {
  return {
    dataset, hidden: false, value: '', textContent: '', listeners: {}, attributes: {},
    addEventListener(type, handler) { this.listeners[type] = handler; },
    setAttribute(name, value) { this.attributes[name] = value; },
    fire(type) { this.listeners[type](); },
  };
}
const ids = Object.fromEntries([
  'library-search', 'library-scope', 'library-sort', 'library-count', 'library-empty',
  'more-events', 'event-count', 'event-empty', 'refresh-interval', 'refresh-summary', 'refresh-status',
].map(id => ['#' + id, element()]));
const libraries = [
  element({ name: 'libsceagc', priority: 'true', level: 'pending', percent: '90' }),
  element({ name: 'libscepad', priority: 'true', level: 'pending', percent: '14' }),
  element({ name: 'libscenet', priority: 'false', level: 'complete', percent: '100' }),
];
const body = { rows: [...libraries], appendChild(row) {
  this.rows = this.rows.filter(item => item !== row).concat(row);
}};
ids['#library-rows'] = body;
ids['#library-scope'].value = 'priority';
ids['#library-sort'].value = 'default';
const events = Array.from({ length: 111 }, (_, index) => element({ kind: index < 72 ? 'group' : 'commit' }));
const filters = ['all', 'group', 'commit', 'release'].map(filter => element({ filter }));
const storage = new Map();
const preferences = new Map();
const timers = new Map();
let reloads = 0;
let refresh;
let timerId = 0;
const browser = {
  location: { pathname: '/painel.html', reload() { reloads++; timers.clear(); } },
  scrollY: 640,
  scrollTo(x, y) { this.scrollY = y; },
  sessionStorage: {
    getItem(key) { return storage.get(key) || null; },
    setItem(key, value) { storage.set(key, value); },
    removeItem(key) { storage.delete(key); },
  },
  localStorage: {
    getItem(key) { return preferences.get(key) || null; },
    setItem(key, value) { preferences.set(key, value); },
  },
  setTimeout(handler, milliseconds) {
    const id = ++timerId;
    timers.set(id, { handler, milliseconds });
    refresh = handler;
    return id;
  },
  clearTimeout(id) { assert.ok(timers.has(id)); timers.delete(id); },
};
const context = { window: browser, document: {
  querySelector(selector) { assert.ok(ids[selector], selector); return ids[selector]; },
  querySelectorAll(selector) {
    if (selector === '#event-list li') return events;
    if (selector === '[data-filter]') return filters;
    if (selector === '.nav-link') return [];
    throw new Error('Seletor inesperado: ' + selector);
  },
}};
function loadPanel() {
  timers.clear();
  vm.runInNewContext(script, context);
}
loadPanel();
assert.equal([...timers.values()][0].milliseconds, 300000);
assert.equal(ids['#refresh-interval'].value, '5');
const visible = rows => rows.filter(row => !row.hidden);
assert.equal(visible(libraries).length, 2);
assert.equal(visible(events).length, 8);
ids['#library-search'].value = '  LibSceNet  ';
ids['#library-search'].fire('input');
assert.equal(ids['#library-scope'].value, 'all');
assert.equal(visible(libraries).length, 1);
assert.equal(visible(libraries)[0].dataset.name, 'libscenet');
ids['#library-search'].value = 'não existe';
ids['#library-search'].fire('input');
assert.equal(visible(libraries).length, 0);
assert.equal(ids['#library-empty'].hidden, false);
ids['#library-search'].value = '';
ids['#library-scope'].value = 'pending';
ids['#library-sort'].value = 'low';
ids['#library-sort'].fire('change');
assert.deepEqual(visible(body.rows).map(row => row.dataset.name), ['libscepad', 'libsceagc']);
ids['#library-scope'].value = 'complete';
ids['#library-scope'].fire('change');
assert.deepEqual(visible(body.rows).map(row => row.dataset.name), ['libscenet']);
filters.find(button => button.dataset.filter === 'commit').fire('click');
assert.equal(visible(events).length, 8);
assert.ok(visible(events).every(row => row.dataset.kind === 'commit'));
ids['#more-events'].fire('click');
assert.equal(visible(events).length, 16);
filters.find(button => button.dataset.filter === 'release').fire('click');
assert.equal(visible(events).length, 0);
assert.equal(ids['#more-events'].hidden, true);
assert.equal(ids['#event-empty'].hidden, false);
filters.find(button => button.dataset.filter === 'all').fire('click');
for (let page = 0; page < 14; page++) ids['#more-events'].fire('click');
assert.equal(visible(events).length, 111);
assert.equal(ids['#more-events'].hidden, true);
assert.equal(ids['#event-count'].textContent, '111 de 111 alterações');
refresh();
assert.equal(reloads, 1);
const saved = JSON.parse(storage.get('anyps5-panel:/painel.html'));
assert.equal(saved.scope, 'complete');
assert.equal(saved.sort, 'low');
assert.equal(saved.scrollY, 640);
assert.equal(saved.limit, 120);
// Simula o carregamento seguinte para verificar a restauracao dos controles.
ids['#library-search'].value = 'reset';
ids['#library-scope'].value = 'priority';
ids['#library-sort'].value = 'default';
browser.scrollY = 0;
loadPanel();
assert.equal(ids['#library-search'].value, '');
assert.equal(ids['#library-scope'].value, 'complete');
assert.equal(ids['#library-sort'].value, 'low');
assert.equal(browser.scrollY, 640);
assert.equal(visible(events).length, 111);
// Cada uma das sete opcoes substitui o timer anterior imediatamente.
const preferenceKey = 'anyps5-panel:/painel.html:refresh-minutes';
const options = source.match(/<select id="refresh-interval"[^>]*>([\s\S]*?)<\/select>/)[1];
assert.deepEqual([...options.matchAll(/value="(\d+)"/g)].map(match => match[1]), ['5', '15', '30', '60', '120', '180', '360']);
for (const minutes of ['5', '15', '30', '60', '120', '180', '360']) {
  ids['#refresh-interval'].value = minutes;
  ids['#refresh-interval'].fire('change');
  assert.equal(timers.size, 1);
  assert.equal([...timers.values()][0].milliseconds, Number(minutes) * 60000);
  assert.equal(preferences.get(preferenceKey), minutes);
  assert.ok(ids['#refresh-status'].textContent.startsWith('Próxima recarga:'));
}
assert.equal(ids['#refresh-summary'].textContent, '↻ Painel: a cada 6 h');
storage.clear();
loadPanel();
assert.equal(ids['#refresh-interval'].value, '360');
assert.equal([...timers.values()][0].milliseconds, 21600000);
preferences.set(preferenceKey, 'intervalo inválido');
loadPanel();
assert.equal(ids['#refresh-interval'].value, '5');
browser.localStorage.getItem = () => { throw new Error('Storage bloqueado'); };
browser.localStorage.setItem = () => { throw new Error('Storage bloqueado'); };
storage.set(preferenceKey, '120');
loadPanel();
assert.equal(ids['#refresh-interval'].value, '120');
assert.equal([...timers.values()][0].milliseconds, 7200000);
// Armazenamento bloqueado nao impede filtros nem recarregamento automatico.
browser.sessionStorage.getItem = () => { throw new Error('Storage bloqueado'); };
browser.sessionStorage.setItem = () => { throw new Error('Storage bloqueado'); };
loadPanel();
assert.equal(ids['#refresh-interval'].value, '5');
ids['#refresh-interval'].value = '30';
ids['#refresh-interval'].fire('change');
assert.equal([...timers.values()][0].milliseconds, 1800000);
refresh();
assert.equal(reloads, 2);
console.log('OK: filtros, paginação, sete intervalos, persistência e restauração de estado.');
