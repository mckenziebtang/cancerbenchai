const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag = 'div') { this.tag = tag; this.children = []; this.style = {}; this.events = {}; this.value = ''; this.hidden = false; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, fn) { this.events[name] = fn; }
  setAttribute(name, value) { this[name] = value; }
}

async function workspace(extraFetch) {
  const nodes = new Map();
  const context = vm.createContext({
    document: { getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); }, createElement: (tag) => new Element(tag) },
    Option: function(text, value) { return { textContent: text, value }; },
    fetch: extraFetch || (async () => new Response(JSON.stringify({ cell_line_ids: ['SIDM00001'], drug_names: ['Cisplatin'] }))),
    AbortSignal, TextDecoder, console,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8'), context);
  await new Promise(setImmediate);
  return { context, nodes };
}

const result = {
  prediction: { prediction: 3.2, cell_line_id: 'SIDM00001', drug_name: 'Cisplatin', model_version: 'xgb_v1' },
  answer: '<script>untrusted</script>', explanation_status: 'completed', explanation_cache_hit: true,
  top_features: [{ name: 'TP53', contribution: -0.5 }],
  citations: [{ pmid: '12345678', title: '<img src=x onerror=alert(1)>', snippet: 'Fixture', year: 2024 }],
  limitations: ['Fixture limitation'], trace_id: 'a'.repeat(32),
};

test('catalog loads supported identifiers and enables submission', async () => {
  const { nodes } = await workspace();
  assert.equal(nodes.get('submit').disabled, false);
  assert.equal(nodes.get('drug').value, 'Cisplatin');
});

test('catalog outage disables submission and offers retry', async () => {
  const { nodes } = await workspace(async () => new Response('', { status: 503 }));
  assert.equal(nodes.get('submit').disabled, true);
  assert.equal(nodes.get('retry-catalog').hidden, false);
});

test('render treats source markup as text and builds canonical PMID links', async () => {
  const { context, nodes } = await workspace();
  context.render(result);
  assert.equal(nodes.get('answer').textContent, result.answer);
  const link = nodes.get('citations').children[0].children[1].children[0];
  assert.equal(link.textContent, result.citations[0].title);
  assert.equal(link.href, 'https://pubmed.ncbi.nlm.nih.gov/12345678/');
  assert.equal(nodes.get('cache-status').textContent, 'Cache hit');
  assert.equal(nodes.get('output').hidden, false);
});

test('empty evidence gets an explicit partial result state', async () => {
  const { context, nodes } = await workspace();
  context.render({ ...result, citations: [], top_features: [], explanation_status: 'timed_out' });
  assert.equal(nodes.get('result-state').textContent, 'Partial evidence');
  assert.match(nodes.get('features').children[0].textContent, /timed_out/);
});

test('stream parser handles records split across chunks', async () => {
  const { context, nodes } = await workspace();
  const data = JSON.stringify({ event: 'progress', stage: 'prediction', status: 'completed' }) + '\n' + JSON.stringify({ event: 'result', data: result }) + '\n';
  const bytes = new TextEncoder().encode(data);
  const body = new ReadableStream({ start(controller) { controller.enqueue(bytes.slice(0, 11)); controller.enqueue(bytes.slice(11)); controller.close(); } });
  await context.consume(new Response(body));
  assert.equal(nodes.get('progress-prediction').textContent, 'Prediction · completed');
  assert.equal(nodes.get('trace-id').textContent, result.trace_id);
});

test('stream errors and interrupted responses are surfaced', async () => {
  const { context } = await workspace();
  await assert.rejects(context.consume(new Response('{"event":"error","message":"Service unavailable"}\n')), /Service unavailable/);
  await assert.rejects(context.consume(new Response('')), /connection ended/);
});
