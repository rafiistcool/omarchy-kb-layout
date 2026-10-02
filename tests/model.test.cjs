const test = require('node:test');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const model = require('../LayoutModel.js');
const keyboard = (name, layout='us,de', index=0) => ({name, layout, active_layout_index:index});

test('keeps real Dell keyboards while excluding non-typing devices', () => {
  assert.equal(model.isTypedKeyboard('dell-usb-keyboard'), true);
  for (const name of ['', 'power-button', 'dell-wmi-hotkeys', 'dell-privacy-driver', 'voyager-consumer-control', 'hl-virtual-keyboard'])
    assert.equal(model.isTypedKeyboard(name), false, name);
});
test('prefers the event keyboard, then the main keyboard, regardless of layout index', () => {
  const main = {...keyboard('main'), main:true};
  const other = keyboard('other', 'us,de', 1);
  assert.equal(model.selectKeyboard([other, main], ''), main);
  assert.equal(model.selectKeyboard([main, other], 'other'), other);
  assert.equal(model.selectKeyboard([], ''), undefined);
});
test('uses each keyboard layout ordering and preserves unrelated configurations', () => {
  assert.equal(model.switchCommand([keyboard('first'), keyboard('second', 'de,us'), keyboard('third', 'fr,de')], 'de'),
    "hyprctl switchxkblayout 'first' 1 && hyprctl switchxkblayout 'second' 0");
  assert.equal(model.switchCommand([keyboard('french', 'fr')], 'de'), '');
});
test('quotes keyboard names without executing their contents', () => {
  const name = "keyboard'$(echo INJECTED)";
  const command = 'hyprctl() { printf "%s\\n" "$@"; }; ' + model.switchCommand([keyboard(name)], 'de');
  const result = spawnSync('bash', ['-c', command], {encoding:'utf8'});
  assert.equal(result.status, 0);
  assert.equal(result.stdout, `switchxkblayout\n${name}\n1\n`);
});
test('does not report success when an earlier keyboard switch fails', () => {
  const command = 'hyprctl() { return 7; }; ' + model.switchCommand([keyboard('a'), keyboard('b')], 'de');
  assert.equal(spawnSync('bash', ['-c', command]).status, 7);
});
test('recognizes active map and reversed configured order', () => {
  assert.equal(model.currentCode({...keyboard('a'), active_keymap:'German'}), 'de');
  assert.equal(model.currentCode(keyboard('a', 'de,us', 1)), 'us');
});
test('ignores layout events from non-typing devices', () => {
  for (const name of ['power-button', 'sdca-hid:04-consumer-control', 'hl-virtual-keyboard'])
    assert.equal(model.eventKeyboardName({data: name + ',English (US)'}), '');
  assert.equal(model.eventKeyboardName({data: 'at-translated-set-2-keyboard,German'}), 'at-translated-set-2-keyboard');
});
