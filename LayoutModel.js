// US/DE layout helpers. Qt-free so the mapping can be checked under node.

var UNTYPED_KEYBOARDS = /^(hl-virtual-keyboard|power-button|sleep-button|lid-switch|video-bus|intel-hid|dell-)/
var UNTYPED_SUFFIX = /-(consumer-control|system-control)$/

function isTypedKeyboard(name) {
  var value = String(name || "")
  return !UNTYPED_KEYBOARDS.test(value) && !UNTYPED_SUFFIX.test(value)
}

function eventKeyboardName(event) {
  var parts

  try {
    if (event && event.parse) parts = event.parse(2)
  } catch (error) {
  }

  if (!parts) parts = String(event && event.data ? event.data : "").split(",")

  var name = String(parts[0] || "")
  return name.indexOf("hl-virtual-keyboard") === 0 ? "" : name
}

function layoutIndex(keyboard) {
  return (keyboard && keyboard.active_layout_index) || 0
}

function selectKeyboard(typed, namedByEvent) {
  var keyboards = typed || []

  return keyboards.find(function (keyboard) {
    return keyboard.name === namedByEvent
  }) || keyboards.reduce(function (furthest, keyboard) {
    return layoutIndex(keyboard) > layoutIndex(furthest) ? keyboard : furthest
  }, keyboards[0])
}

function layoutCodes(keyboard) {
  return String(keyboard && keyboard.layout || "")
    .split(",")
    .map(function (code) { return code.trim() })
    .filter(Boolean)
}

function codeFromKeymap(keymap) {
  var text = String(keymap || "").toLowerCase()
  if (!text) return ""
  if (text.indexOf("german") !== -1 || text === "de") return "de"
  if (text.indexOf("english (us)") !== -1 || text === "english" || text === "us") return "us"
  return ""
}

function currentCode(keyboard) {
  if (!keyboard) return ""
  var fromKeymap = codeFromKeymap(keyboard.active_keymap)
  if (fromKeymap) return fromKeymap
  var codes = layoutCodes(keyboard)
  return codes[layoutIndex(keyboard)] || ""
}

function indexForCode(keyboard, code) {
  return layoutCodes(keyboard).indexOf(code)
}

function hasUsAndDe(keyboard) {
  var codes = layoutCodes(keyboard)
  return codes.indexOf("us") !== -1 && codes.indexOf("de") !== -1
}

function otherCode(code) {
  return code === "de" ? "us" : "de"
}

function labelFor(code) {
  return String(code || "").toUpperCase()
}

function fullName(code) {
  if (code === "de") return "German"
  if (code === "us") return "English (US)"
  return ""
}

function shellQuote(value) {
  return "'" + String(value || "").replace(/'/g, "'\\''") + "'"
}

function switchCommand(keyboards, code) {
  var parts = []
  ;(keyboards || []).forEach(function (keyboard) {
    if (!isTypedKeyboard(keyboard && keyboard.name)) return
    var index = indexForCode(keyboard, code)
    if (index < 0) return
    parts.push("hyprctl switchxkblayout " + shellQuote(keyboard.name) + " " + index)
  })
  return parts.join("; ")
}

if (typeof module !== "undefined") {
  module.exports = {
    codeFromKeymap: codeFromKeymap,
    currentCode: currentCode,
    eventKeyboardName: eventKeyboardName,
    fullName: fullName,
    hasUsAndDe: hasUsAndDe,
    indexForCode: indexForCode,
    isTypedKeyboard: isTypedKeyboard,
    labelFor: labelFor,
    layoutCodes: layoutCodes,
    otherCode: otherCode,
    selectKeyboard: selectKeyboard,
    switchCommand: switchCommand
  }
}
