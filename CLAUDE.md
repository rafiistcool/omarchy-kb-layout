# rafi.kb-layout

Omarchy shell plugin (Quickshell/QML) that toggles Hyprland between US and German.

## Commands

```bash
node tests/model.test.cjs                    # LayoutModel.js, fast
python3 -m unittest discover -s tests -v     # real QML service against a fake hyprctl; ~70 s, needs qs
omarchy plugin validate .                    # manifest schema
```

No build and no linter. Run all three before committing.

## Not obvious from the code

- `LayoutModel.js` stays Qt-free so node can test it. Logic goes there, QML only wires it up.
- The saved layout (`$XDG_STATE_HOME/omarchy/rafi.kb-layout/layout.json`) only changes on an explicit
  switch through the plugin (bar click, IPC). Every other layout change is treated as a reset and undone
  by the 2 s reconcile timer. That is deliberate: wake and hotplug resets arrive late and without events.
  Consequence: Omarchy's own switchers (`SUPER + I` via `omarchy-input-method cycle`, the built-in
  `omarchy.keyboard-layout` widget) fight the plugin, so users rebind/disable them (see README).
- The plugin never writes Hyprland config. Since Omarchy 4, `kb_layout` comes from
  `~/.config/omarchy/keyboard-layouts` (`omarchy setup keyboard`), read by `default/hypr/input.lua`.
- `isTypedKeyboard` filters non-keyboards (power button, `hl-virtual-keyboard*`, ...). Omarchy keeps its own
  list in `$OMARCHY_PATH/shell/plugins/bar/widgets/KeyboardLayoutModel.js`; compare when devices misbehave.
- `omarchy agent look plugin .` renders an empty strip: the widget gets its label from the service, which
  the preview doesn't start. Check the real bar instead.

## Git

Forgejo (`ssh://git@privat.lan:2222/rafiistcool/omarchy-kb-layout.git`) is the source of truth; the GitHub
copy is a push mirror. PRs go through `fj`. Installed copy: `~/.config/omarchy/plugins/rafi.kb-layout`
(`omarchy plugin update rafi.kb-layout`).
