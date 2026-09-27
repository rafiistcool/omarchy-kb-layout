import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import qs.Commons
import "LayoutModel.js" as LayoutModel

Item {
  id: root

  property var shell: null
  property var settings: ({})
  property string layoutCode: ""
  property string layoutFull: ""
  property string keyboardName: ""
  property string typedKeyboardName: ""
  property var typedKeyboards: []
  property bool refreshPending: false
  property string pendingCode: ""
  property string applyingCode: ""
  property string lastError: ""

  readonly property string layoutLabel: LayoutModel.labelFor(layoutCode)
  readonly property string nextCode: LayoutModel.otherCode(pendingCode || applyingCode || layoutCode)

  function refresh() {
    if (queryProc.running || applyProc.running) {
      refreshPending = true
      return
    }
    refreshPending = false
    queryProc.running = true
  }

  function showOsd(code) {
    var name = LayoutModel.fullName(code) || LayoutModel.labelFor(code)
    if (!name) return
    Util.execArgv(["omarchy-shell", "-q", "osd", "show", JSON.stringify({
      icon: "keyboard", message: name, duration: 1200
    })])
  }

  function applyCode(code) {
    if (code !== "us" && code !== "de") return
    pendingCode = code
    refresh()
  }

  function applyQueued() {
    if (!pendingCode || applyProc.running) return
    var code = pendingCode
    pendingCode = ""
    var command = LayoutModel.switchCommand(typedKeyboards, code)
    if (!command) {
      lastError = "Configure kb_layout = us,de for the keyboard in Hyprland first."
      return
    }
    applyingCode = code
    lastError = ""
    applyProc.command = ["timeout", "--kill-after=1s", "10s", "bash", "-c", command]
    applyProc.running = true
  }

  function toggle() { applyCode(nextCode) }
  function setLayout(code) { applyCode(String(code || "").toLowerCase()) }

  Component.onCompleted: refresh()

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (!event || !event.name) return
      var name = String(event.name)
      if (name === "activelayout") {
        var named = LayoutModel.eventKeyboardName(event)
        if (named) root.typedKeyboardName = named
      }
      if (name === "activelayout" || name === "configreloaded") refreshTimer.restart()
    }
  }

  Process {
    id: queryProc
    command: ["timeout", "--kill-after=1s", "3s", "hyprctl", "-j", "devices"]
    stdout: StdioCollector { id: devicesOutput; waitForEnd: true }
    onExited: function(exitCode) {
      var listed = null
      try { listed = JSON.parse(devicesOutput.text || "{}").keyboards } catch (error) {}
      if (exitCode !== 0 || !Array.isArray(listed)) {
        root.lastError = "Could not read Hyprland keyboards"
        root.pendingCode = ""
        return
      }
      root.typedKeyboards = listed.filter(function(keyboard) {
        return LayoutModel.isTypedKeyboard(keyboard && keyboard.name)
      })
      var keyboard = LayoutModel.selectKeyboard(root.typedKeyboards, root.typedKeyboardName)
      root.keyboardName = keyboard ? String(keyboard.name || "") : ""
      root.layoutCode = LayoutModel.currentCode(keyboard)
      root.layoutFull = keyboard ? String(keyboard.active_keymap || LayoutModel.fullName(root.layoutCode)) : ""
      root.applyQueued()
      if (root.refreshPending) refreshTimer.restart()
    }
  }

  Process {
    id: applyProc
    onExited: function(exitCode) {
      var code = root.applyingCode
      root.applyingCode = ""
      if (exitCode === 0) root.showOsd(code)
      else root.lastError = "Could not switch the keyboard layout"
      root.refresh()
    }
  }

  Timer {
    id: refreshTimer
    interval: 100
    onTriggered: root.refresh()
  }

  // Hyprland does not emit a layout event for every device hotplug.
  // Discover it without changing either its layout or global configuration.
  Timer {
    interval: 60000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  IpcHandler {
    target: "rafi.kb-layout"
    function toggle(): string {
      var next = root.nextCode
      root.toggle()
      return next
    }
    function use(code: string): string {
      var layout = String(code || "").toLowerCase()
      if (layout !== "us" && layout !== "de") return root.layoutCode
      root.setLayout(layout)
      return layout
    }
    function status(): string {
      return JSON.stringify({
        layout: root.layoutCode, label: root.layoutLabel,
        keymap: root.layoutFull, keyboard: root.keyboardName,
        pending: root.pendingCode || root.applyingCode, error: root.lastError
      })
    }
  }
}
