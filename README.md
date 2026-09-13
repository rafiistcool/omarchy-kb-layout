# US/DE layout (Omarchy plugin)

Toggle the Hyprland keyboard layout between **US** and **German**. Made for a
German laptop plus a ZSA Voyager that is programmed as US QWERTY.

The bar shows `US` or `DE`. Click it to switch. There is no automatic
switching when a keyboard is plugged in.

## Install

```bash
omarchy plugin add git@github.com:rafiistcool/omarchy-kb-layout.git --enable --yes
```

Hyprland must list both layouts. In `~/.config/hypr/input.lua`:

```lua
hl.config({
  input = {
    -- US first so Super+letter binds keep matching the Voyager.
    kb_layout = "us,de",
  },
})
```

Then reload:

```bash
hyprctl reload
```

Optional keybind in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + K", "Toggle US/DE keyboard layout", "omarchy-shell rafi.kb-layout toggle")
```

## Use

| Action | Result |
|---|---|
| Click the bar label | Toggle US ↔ DE |
| `SUPER + SHIFT + K` | Same toggle, with an OSD |
| `omarchy-shell rafi.kb-layout toggle` | Toggle from a script or Voyager key |
| `omarchy-shell rafi.kb-layout use us` | Force US |
| `omarchy-shell rafi.kb-layout use de` | Force German |
| `omarchy-shell rafi.kb-layout status` | JSON snapshot |

## Why US is first

Hyprland matches keybinds against the **first** layout in `kb_layout`, not the
one currently active. Leading with `us` keeps Super+letter shortcuts on the
Voyager’s QWERTY positions while you type German.

## License

MIT
