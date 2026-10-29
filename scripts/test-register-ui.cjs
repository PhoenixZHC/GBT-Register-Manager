// 隔离执行真实页面处理函数，不调用 IPC 或机器人。
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const { test } = require('node:test');
const source = fs.readFileSync('src/App.vue', 'utf8').split('<script setup lang="ts">')[1].split('</script>')[0];
const ast = ts.createSourceFile('app.ts', source, ts.ScriptTarget.Latest, true);
const names = new Set(['onCreateRegisters', 'buildCreateRows', 'onApplyIO', 'collectImportRowIds', 'onImportExcel', 'onReadPreviewIO', 'confirmPointWriteResult']);
const functions = ast.statements.filter(n => ts.isFunctionDeclaration(n) && names.has(n.name.text)).map(n => n.getText(ast)).join('\n');
const validation = ts.transpileModule(fs.readFileSync('src/utils/registerValidation.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const validateScope = { exports: {} };
vm.runInNewContext(validation, validateScope);
const validateRegisterRows = validateScope.exports.validateRegisterRows;

function context() {
  const state = { isConnected: { value: true }, createStartId: { value: 1 }, createCount: { value: 1 }, createType: { value: 'R' }, createProgramName: { value: '' }, needProgramForCreate: { value: false }, createLoading: { value: false }, createDetails: { value: [] },
    ioType: { value: 'R' }, ioProgramName: { value: '' }, ioRows: { value: [{ ID: 1, value: 5 }] }, needProgramForIO: { value: false }, ioApplyLoading: { value: false }, ioDetails: { value: [] }, loading: { value: false },
    ioReadLoading: { value: false }, ioMode: { value: 'range' }, ioStartId: { value: 1 }, ioEndId: { value: 2 },
    ExcelUserError: class extends Error {}, parseExcelForPreview: async () => [],
    message: { warning() {}, info() {}, error() {}, success() {} }, t: x => x, beginProgressOp: () => 1, endProgressOp() {}, robotSessionId: () => 7, finishRegisterProgress() {}, formatIpcError: String, applyResultMessage: () => '', validateRegisterRows,
    readRegisters: async () => [], applyRegisters: async () => ({ ok: true }) };
  vm.createContext(state);
  vm.runInContext(ts.transpileModule(functions, { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText, state);
  return state;
}
test('create target remains fixed across preflight await', async () => {
  const s = context(); let request;
  s.readRegisters = async () => { s.createType.value = 'P'; s.createProgramName.value = 'Other'; return []; };
  s.applyRegisters = async req => { request = req; return { ok: true }; };
  await s.onCreateRegisters();
  assert.equal(request.registerType, 'R'); assert.equal(request.programName, undefined); assert.equal(request.rows[0].type, 'R');
});
test('import rows and target remain fixed across preflight await', async () => {
  const s = context(); let request;
  s.readRegisters = async () => { s.ioType.value = 'P'; s.ioRows.value[0].value = 999; return []; };
  s.applyRegisters = async req => { request = req; return { ok: true }; };
  await s.onApplyIO();
  assert.equal(request.registerType, 'R'); assert.equal(request.rows[0].value, 5);
});
test('bad imported data never starts preflight or write', async () => {
  const s = context(); let calls = 0;
  s.ioRows.value = [{ ID: 1, value: 5 }, { ID: 2, value: 'NaN' }];
  s.readRegisters = s.applyRegisters = async () => { calls++; return []; };
  await s.onApplyIO(); assert.equal(calls, 0);
});
test('fractional, duplicate and oversized ID ranges are rejected', () => {
  for (const rows of [[{ ID: 1.5, value: 5 }], [{ ID: 1, value: 1 }, { ID: 1, value: 2 }], [{ ID: 0, value: 1 }, { ID: 10000, value: 2 }]]) {
    assert.throws(() => validateRegisterRows('R', rows), /GBT_INVALID_REGISTER_DATA/);
  }
});
test('Excel parsing preserves fractional IDs for validation', async () => {
  const XLSX = require('xlsx');
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['type', 'ID', 'value'], ['R', 1.0001, 5]]), 'R');
  const data = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' });
  class FileReader {
    readAsArrayBuffer() { this.result = data; this.onload(); }
  }
  const scope = { exports: {}, require, FileReader };
  const code = ts.transpileModule(fs.readFileSync('src/utils/excel.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  vm.runInNewContext(code, scope);
  const rows = await scope.exports.parseExcelForPreview({ size: data.byteLength }, 'R');
  assert.equal(rows[0].ID, 1.0001);
  assert.throws(() => validateRegisterRows('R', rows), /GBT_INVALID_REGISTER_DATA/);
});

test('failed replacement import clears old data and prevents writes', async () => {
  const s = context(); let writes = 0;
  s.ioDetails.value = ['old failure'];
  s.parseExcelForPreview = async () => { assert.equal(s.ioRows.value.length, 0); throw new Error('bad workbook'); };
  s.applyRegisters = async () => { writes++; };
  await s.onImportExcel({ target: { files: [{}], value: 'new.xlsx' } });
  await s.onApplyIO();
  assert.equal(s.ioRows.value.length, 0); assert.equal(s.ioDetails.value.length, 0);
  assert.equal(writes, 0); assert.equal(s.loading.value, false);
});
test('failed replacement read clears previous preview', async () => {
  const s = context();
  s.ioDetails.value = ['old failure'];
  s.readRegisters = async () => { assert.equal(s.ioRows.value.length, 0); throw new Error('disconnected'); };
  await s.onReadPreviewIO();
  assert.equal(s.ioRows.value.length, 0); assert.equal(s.ioDetails.value.length, 0);
  assert.equal(s.ioReadLoading.value, false); assert.equal(s.loading.value, false);
});
test('cancelled file picker preserves preview; successful import replaces it', async () => {
  const s = context(); const original = s.ioRows.value;
  await s.onImportExcel({ target: { files: [] } });
  assert.equal(s.ioRows.value, original);
  const replacement = [{ ID: 2, value: 10 }];
  s.parseExcelForPreview = async () => replacement;
  await s.onImportExcel({ target: { files: [{}], value: 'new.xlsx' } });
  assert.equal(s.ioRows.value, replacement);
});

for (const kind of ['P', 'PR']) {
  test(`Python-exported mixed ${kind} workbook retains types and values in frontend`, async () => {
    const data = fs.readFileSync(`.local-testing/pose-${kind}.xlsx`);
    const expected = JSON.parse(fs.readFileSync(`.local-testing/pose-${kind}.json`, 'utf8'));
    class FileReader { readAsArrayBuffer() { this.result = data; this.onload(); } }
    const scope = { exports: {}, require, FileReader };
    vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/utils/excel.ts', 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
    }).outputText, scope);
    const rows = await scope.exports.parseExcelForPreview({ size: data.length }, kind);
    validateRegisterRows(kind, rows);
    assert.equal(rows.length, 2);
    for (let i = 0; i < rows.length; i++) {
      for (const [key, value] of Object.entries(expected[i])) {
        if (value == null) assert.equal(rows[i][key] ?? null, null);
        else if (typeof value === 'number') assert.ok(Math.abs(rows[i][key] - value) < 1e-10, key);
        else assert.equal(rows[i][key], value, key);
      }
    }
    assert.equal(rows[0].PoseType, 'CART'); assert.equal(rows[1].PoseType, 'JOINT');
    for (const change of [{ PoseType: '' }, { PoseType: 'bad' }, { J9: null }, { X: 5 }, { Turn1: 1.5 }]) {
      assert.throws(() => validateRegisterRows(kind, [{ ...rows[1], ...change }]), /GBT_INVALID_REGISTER_DATA/);
    }
  });
}

test('blank modern pose type is not displayed as legacy CART', () => {
  const declaration = ast.statements.filter(ts.isVariableStatement)
    .flatMap(s => [...s.declarationList.declarations]).find(d => d.name.getText(ast) === 'ioColumns');
  const scope = { computed: f => f(), ioType: { value: 'P' }, expectedHeaders: () => ['PoseType'] };
  vm.runInNewContext(ts.transpileModule(`const columns = ${declaration.initializer.getText(ast)}; globalThis.result = columns;`,
    { compilerOptions: { target: ts.ScriptTarget.ES2020 } }).outputText, scope);
  assert.equal(scope.result[0].render({}), 'CART');
  assert.equal(scope.result[0].render({ PoseType: undefined }), '');
  assert.equal(scope.result[0].render({ PoseType: 'JOINT' }), 'JOINT');
});

function pointDialogContext() {
  const s = context();
  s.h = (tag, props, children) => ({ tag, children: children === undefined ? props : children });
  s.te = () => true;
  s.t = (key, params) => `${key} ${params ? JSON.stringify(params) : ''}`;
  s.dialog = { create(options) { s.openDialog = options; } };
  return s;
}
test('P result dialog lists failed IDs and cannot dismiss without acknowledgement', async () => {
  const s = pointDialogContext(); let acknowledged = false;
  const pending = s.confirmPointWriteResult({ ok: false, stats: { success: 2, skipped: 1, failed: 2,
    failures: [{ id: 3, outcome: 'unknown', reason: 'GBT_P_WRITE_UNKNOWN' }, { id: 5, outcome: 'failed', reason: 'GBT_P_READ_FAILED' }] } }, 'A1')
    .then(() => { acknowledged = true; });
  await Promise.resolve();
  assert.equal(acknowledged, false);
  assert.equal(s.openDialog.closable, false); assert.equal(s.openDialog.maskClosable, false); assert.equal(s.openDialog.closeOnEsc, false);
  const text = JSON.stringify(s.openDialog.content());
  assert.ok(text.includes('ID=3')); assert.ok(text.includes('ID=5')); assert.ok(text.includes('GBT_P_WRITE_UNKNOWN'));
  assert.ok(text.includes('A1')); assert.ok(text.includes('success'));
  s.openDialog.onPositiveClick(); await pending;
  assert.equal(acknowledged, true);
});
for (const operation of ['onApplyIO', 'onCreateRegisters']) {
  test(`${operation} holds P controls until result is confirmed`, async () => {
    const s = pointDialogContext();
    s.ioType.value = s.createType.value = 'P';
    s.ioProgramName.value = s.createProgramName.value = 'A1';
    s.ioRows.value = [{ ID: 1, X: 0, Y: 0, Z: 0, A: 0, B: 0, C: 0, TF: 0, UF: 0, Coord: 'L' }];
    s.applyRegisters = async () => ({ ok: true, stats: { success: 1, skipped: 0, failed: 0 } });
    let completed = false;
    const pending = s[operation]().then(() => { completed = true; });
    for (let i = 0; i < 8; i++) await Promise.resolve();
    assert.ok(s.openDialog); assert.equal(s.loading.value, true); assert.equal(completed, false);
    s.openDialog.onPositiveClick(); await pending;
    assert.equal(s.loading.value, false); assert.equal(completed, true);
  });
}
test('P transport failure requests confirmation without fabricating counts', async () => {
  const s = pointDialogContext();
  s.createType.value = 'P'; s.createProgramName.value = 'A1';
  s.applyRegisters = async () => { throw new Error('process lost'); };
  const pending = s.onCreateRegisters();
  for (let i = 0; i < 8; i++) await Promise.resolve();
  const text = JSON.stringify(s.openDialog.content());
  assert.ok(text.includes('writeResult.noResult')); assert.ok(!text.includes('writeResult.summary'));
  s.openDialog.onPositiveClick(); await pending;
});
