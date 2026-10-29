// 执行真实 SFC 状态和处理函数；IPC 替身仅在测试进程内，不进入生产入口。
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const ts = require('typescript');
const { ref, computed, h } = require('vue');
const source = fs.readFileSync('src/components/ControllerDiscovery.vue', 'utf8').split('<script setup lang="ts">')[1].split('</script>')[0];
const ast = ts.createSourceFile('discovery.ts', source, ts.ScriptTarget.Latest, true);
const body = ast.statements.filter(n => !ts.isImportDeclaration(n)).map(n => n.getText(ast)).join('\n');
const code = ts.transpileModule(body, { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText;
function setup(overrides = {}) {
  let mounted;
  let event;
  let sequence = 0;
  const calls = [];
  const scope = { ref, computed, h, NButton: 'button', console,
    useI18n: () => ({ t: x => x, te: () => true }), useMessage: () => ({ error() {} }),
    defineEmits: () => (...args) => calls.push(['emit', ...args]),
    onMounted: fn => { mounted = fn; }, onUnmounted() {},
    listen: async (_, fn) => { event = fn; return () => {}; },
    crypto: { randomUUID: () => `scan-${++sequence}` },
    checkControllerDiscovery: async () => ({ status: 'ready', interfaces: [{ id: 'wifi', name: 'WiFi', mac: '02:11:22:33:44:55' }], warnings: [] }),
    startControllerDiscovery: async (...args) => calls.push(['start', ...args]),
    cancelControllerDiscovery: async id => calls.push(['cancel', id]),
    openNpcapDownload: async () => {}, ...overrides };
  vm.createContext(scope);
  const state = vm.runInContext(code + '\n;({prepare,onEvent,leave,stop,rows,stage,error,check,warnings,columns,addressConflict,incompleteIdentity})', scope);
  return { state, calls, scope, mount: () => mounted(), event: payload => event({ payload }) };
}
const device = (key, mac = '02:11:22:33:44:55', ids = ['usb']) => ({ key, ip: '10.0.0.2', mac, macStatus: mac ? 'valid' : 'missing', connectable: true, interfaceIds: ids });

test('entry and every rescan start automatically without adapter arguments', async () => {
  const x = setup(); await x.mount(); await x.state.prepare();
  assert.deepEqual(x.calls.filter(c => c[0] === 'start'), [['start', 'scan-1'], ['start', 'scan-2']]);
});
test('scan inventory includes new USB adapter and clears stale precheck warnings', async () => {
  const x = setup(); await x.mount();
  x.state.warnings.value = [{ code: 'unavailable', interfaceId: 'usb' }];
  x.event({ scanId: 'scan-1', kind: 'interfaces', interfaces: [{ id: 'usb', name: 'USB Ethernet', mac: '02:11:22:33:44:55' }] });
  assert.equal(x.state.check.value.interfaces[0].name, 'USB Ethernet');
  assert.equal(x.state.warnings.value.length, 0);
  x.event({ scanId: 'scan-1', kind: 'warning', code: 'permission', interfaceId: 'usb' });
  assert.equal(x.state.warnings.value.length, 1);
});
test('missing adapters can recover on retry without manual selection', async () => {
  let ready = false;
  const x = setup({ checkControllerDiscovery: async () => ({ status: ready ? 'ready' : 'no_interfaces', interfaces: [], warnings: [] }) });
  await x.mount(); assert.equal(x.state.stage.value, 'failed');
  ready = true; await x.state.prepare();
  assert.equal(x.state.stage.value, 'scanning');
  assert.equal(x.calls.filter(c => c[0] === 'start').length, 1);
});
test('late previous scan events cannot change current rows or status', async () => {
  const x = setup(); await x.mount(); await x.state.prepare();
  x.event({ scanId: 'scan-1', kind: 'device', device: device('old') });
  x.event({ scanId: 'scan-1', kind: 'finished', reason: 'timeout' });
  assert.equal(x.state.rows.value.length, 0); assert.equal(x.state.stage.value, 'scanning');
});
test('invalid MAC identities stay separate; valid duplicates merge and conflicts remain visible', async () => {
  const x = setup(); await x.mount();
  for (const row of [device('a', '', ['a']), device('b', '', ['b']), device('valid'), device('valid', undefined, ['usb', 'wifi'])]) {
    x.event({ scanId: 'scan-1', kind: 'device', device: row });
  }
  assert.equal(x.state.rows.value.length, 3);
  assert.equal(x.state.rows.value[2].interfaceIds.length, 2);
  assert.equal(x.state.incompleteIdentity.value, true);
  assert.equal(x.state.addressConflict.value, false);
  x.event({ scanId: 'scan-1', kind: 'device', device: device('other', '02:11:22:33:44:66') });
  assert.equal(x.state.addressConflict.value, true);
});
test('using an IP cancels search before emitting only the IP', async () => {
  const x = setup(); await x.mount(); await x.state.leave('10.0.0.2');
  assert.deepEqual(x.calls.slice(-2), [['cancel', 'scan-1'], ['emit', 'select', '10.0.0.2']]);
});
test('IPv6 is displayed with disabled connection action', async () => {
  const x = setup(); await x.mount();
  const row = { ...device('v6'), ip: 'fe80::1234', connectable: false };
  const button = x.state.columns.value.at(-1).render(row);
  assert.equal(button.props.disabled, true); button.props.onClick();
  assert.equal(x.calls.filter(c => c[0] === 'emit').length, 0);
});
test('rapid stop waits for the pending start before cancelling', async () => {
  let finish;
  const order = [];
  const x = setup({ startControllerDiscovery: () => new Promise(resolve => { finish = () => { order.push('start'); resolve(); }; }), cancelControllerDiscovery: async () => order.push('cancel') });
  const mounting = x.mount();
  while (!finish) await new Promise(resolve => setImmediate(resolve));
  const stopping = x.state.stop();
  assert.equal(order.length, 0); finish(); await mounting; await stopping;
  assert.deepEqual(order, ['start', 'cancel']);
});
test('all five locales have matching discovery keys', () => {
  const scope = { exports: {} };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/locales/discovery.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, scope);
  const all = Object.values(scope.exports);
  for (const locale of all.slice(1)) {
    assert.deepEqual(Object.keys(locale).sort(), Object.keys(all[0]).sort());
    assert.deepEqual(Object.keys(locale.errors).sort(), Object.keys(all[0].errors).sort());
  }
});
