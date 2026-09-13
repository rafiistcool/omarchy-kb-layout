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
  property bool applyPending: false
  property string pendingCode: ""

  readonly property string layoutLabel: LayoutModel.labelFor(layoutCode)
  readonly property string nextCode: LayoutModel.otherCode(layoutCode)

  function refresh() {
    if (queryProc.running) {
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
      icon: "keyboard",
      message: name,
      duration: 1200
    })])
  }

  function applyCode(code) {
    if (code !== "us" && code !== "de") return
    var command = LayoutModel.switchCommand(root.typedKeyboards, code)
    if (!command) {
      if (!ensureProc.running) ensureProc.running = true
      pendingCode = code
      applyPending = true
      return
    }
    if (applyProc.running) {
      pendingCode = code
      applyPending = true
      return
    }
    root.layoutCode = code
    root.layoutFull = LayoutModel.fullName(code)
    applyProc.command = ["bash", "-lc", command]
    applyProc.running = true
    root.showOsd(code)
  }

  function toggle() {
    root.applyCode(root.nextCode)
  }

  function setLayout(code) {
    root.applyCode(String(code || "").toLowerCase())
  }

  Component.onCompleted: refresh()

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (!event || !event.name) return
      var name = String(event.name)
      if (name === "activelayout") {
        const named = LayoutModel.eventKeyboardName(event)
        if (named) root.typedKeyboardName = named
      }
      if (name.indexOf("activelayout") !== -1 || name === "configreloaded") root.refresh()
    }
  }

  Process {
    id: queryProc
    command: ["hyprctl", "-j", "devices"]
    onRunningChanged: {
      if (running) {
        stallTimer.restart()
        return
      }
      stallTimer.stop()
      if (root.refreshPending) root.refresh()
    }
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        let listed
        try {
          listed = JSON.parse(text || "{}").keyboards
        } catch (e) {
          return
        }
        if (!Array.isArray(listed)) return

        const typed = listed.filter(function (keyboard) {
          return LayoutModel.isTypedKeyboard(keyboard && keyboard.name)
        })
        root.typedKeyboards = typed

        const keyboard = LayoutModel.selectKeyboard(typed, root.typedKeyboardName)
        if (!keyboard || !keyboard.active_keymap) {
          if (typed.length === 0) {
            root.layoutCode = ""
            root.layoutFull = ""
            root.keyboardName = ""
          }
          return
        }

        root.keyboardName = String(keyboard.name || "")
        root.layoutCode = LayoutModel.currentCode(keyboard)
        root.layoutFull = String(keyboard.active_keymap || LayoutModel.fullName(root.layoutCode))

        if (!LayoutModel.hasUsAndDe(keyboard) && !ensureProc.running)
          ensureProc.running = true
      }
    }
  }

  Process {
    id: ensureProc
    command: ["hyprctl", "keyword", "input:kb_layout", "us,de"]
    onExited: refreshTimer.restart()
  }

  Process {
    id: applyProc
    onExited: function() {
      if (root.applyPending) {
        root.applyPending = false
        var code = root.pendingCode
        root.pendingCode = ""
        root.applyCode(code)
        return
      }
      refreshTimer.restart()
    }
  }

  Timer {
    id: refreshTimer
    interval: 600
    onTriggered: root.refresh()
  }

  Timer {
    id: stallTimer
    interval: 5000
    onTriggered: {
      queryProc.running = false
      refreshTimer.restart()
    }
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
        layout: root.layoutCode,
        label: root.layoutLabel,
        keymap: root.layoutFull,
        keyboard: root.keyboardName
      })
    }
  }
}
