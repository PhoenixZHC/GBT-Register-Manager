// 隔离执行真实页面处理函数，不调用 IPC 或机器人。
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const { test } = require('node:test');
const source = fs.readFileSync('src/App.vue', 'utf8').split('<script setup lang="ts">')[1].split('</script>')[0];
const ast = ts.createSourceFile('app.ts', source, ts.ScriptTarget.Latest, true);
const names = new Set(['onCreateRegisters', 'buildCreateRows', 'onApplyIO', 'collectImportRowIds']);
const functions = ast.statements.filter(n => ts.isFunctionDeclaration(n) && names.has(n.name.text)).map(n => n.getText(ast)).join('\n');
const validation = ts.transpileModule(fs.readFileSync('src/utils/registerValidation.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const validateScope = { exports: {} };
vm.runInNewContext(validation, validateScope);
const validateRegisterRows = validateScope.exports.validateRegisterRows;

function context() {
  const state = { isConnected: { value: true }, createStartId: { value: 1 }, createCount: { value: 1 }, createType: { value: 'R' }, createProgramName: { value: '' }, needProgramForCreate: { value: false }, createLoading: { value: false }, createDetails: { value: [] },
    ioType: { value: 'R' }, ioProgramName: { value: '' }, ioRows: { value: [{ ID: 1, value: 5 }] }, needProgramForIO: { value: false }, ioApplyLoading: { value: false }, ioDetails: { value: [] }, loading: { value: false },
    message: { warning() {}, info() {}, error() {} }, t: x => x, beginProgressOp: () => 1, endProgressOp() {}, robotSessionId: () => 7, finishRegisterProgress() {}, formatIpcError: String, applyResultMessage: () => '', validateRegisterRows,
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
