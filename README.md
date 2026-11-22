# US/DE layout (Omarchy plugin)

Toggle the Hyprland keyboard layout between **US** and **German**. Made for a
German laptop plus a ZSA Voyager that is programmed as US QWERTY.

The bar shows `US` or `DE`. Click it to switch. The last selected layout is saved
in `$XDG_STATE_HOME/omarchy/rafi.kb-layout/layout.json` (default:
`~/.local/state/omarchy/rafi.kb-layout/layout.json`) and restored on shell startup,
after suspend/resume, and after a Hyprland configuration reload. Restoration is
silent. Your saved choice remains authoritative until you switch through the
bar, keybind, or plugin IPC. Reset and hotplug events never overwrite it;
reconnected keyboards receive the same saved layout. Hyprland events trigger
checks (debounced by 100 ms), with a check every two seconds as a fallback for
missing events and delayed resets, including display sleep without system
suspend. The plugin never rewrites Hyprland configuration: only keyboards
configured with both `us` and `de` are switched, using each device's own layout
order. Missing layouts and failed commands are reported in the tooltip.

A layout switched by anything other than this plugin (Omarchy's `SUPER + I`,
its keyboard layout widget, `hyprctl switchxkblayout`) is treated like a reset
and undone, which is why the install below replaces both.

## Install

```bash
omarchy plugin add https://github.com/rafiistcool/omarchy-kb-layout.git --enable --yes
```

Hyprland must list both layouts, US first. Pick `English (US)` and then
`German` in Omarchy's keyboard setup:

```bash
omarchy setup keyboard
```

It saves the choice to `~/.config/omarchy/keyboard-layouts`:

```
XKBLAYOUT=us,de
XKBVARIANT=,
```

Setting `kb_layout = "us,de"` in `~/.config/hypr/input.lua` works too.

Then swap Omarchy's own keyboard layout widget for this one, in the same spot:

```bash
omarchy plugin enable rafi.kb-layout --after omarchy.keyboard-layout
omarchy plugin disable omarchy.keyboard-layout
```

### Super + I

Omarchy binds `SUPER + I` and `SUPER + SHIFT + I` to `omarchy-input-method cycle`.
With a single Fcitx input method that cycles the Hyprland layouts directly, and
the plugin puts its saved layout back within two seconds. Route both keys
through the plugin in `~/.config/hypr/bindings.lua`:

```lua
hl.unbind("SUPER + I")
hl.unbind("SUPER + SHIFT + I")
o.bind("SUPER + I", "Toggle US/DE keyboard layout", "omarchy-shell rafi.kb-layout toggle")
o.bind("SUPER + SHIFT + I", "Toggle US/DE keyboard layout", "omarchy-shell rafi.kb-layout toggle")
```

Then check the config:

```bash
hyprctl reload && hyprctl configerrors
```

## Use

| Action | Result |
|---|---|
| Click the bar label | Toggle US ↔ DE |
| `SUPER + I` | Same toggle, with an OSD (after the rebind above) |
| `omarchy-shell rafi.kb-layout toggle` | Toggle from a script or Voyager key |
| `omarchy-shell rafi.kb-layout use us` | Force US |
| `omarchy-shell rafi.kb-layout use de` | Force German |
| `omarchy-shell rafi.kb-layout status` | JSON snapshot |

## Update and validation

```bash
omarchy plugin update rafi.kb-layout
```

`omarchy update` reloads plugins; it does not pull third-party Git repositories.
Requires Hyprland, Quickshell, Bash, GNU `timeout`, and `dbus-monitor` (standard on Omarchy).

From a development checkout:

```bash
node tests/model.test.cjs
python3 -m unittest discover -s tests -v
omarchy plugin validate .
```

The QML test runs with a simulated keyboard and never changes real layouts.

## Why US is first

Hyprland matches keybinds against the **first** layout in `kb_layout`, not the
one currently active. Leading with `us` keeps Super+letter shortcuts on the
Voyager’s QWERTY positions while you type German.

## License

MIT
