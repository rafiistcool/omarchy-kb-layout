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
  property string persistenceError: ""
  property string savedCode: ""
  property bool stateReady: false
  property bool stateWritable: false
  property bool pendingSilent: false
  property bool applyingSilent: false
  property double retryAfter: 0
  readonly property string stateDir: (Quickshell.env("XDG_STATE_HOME") ||
    Quickshell.env("HOME") + "/.local/state") + "/omarchy/rafi.kb-layout"

  readonly property string layoutLabel: LayoutModel.labelFor(layoutCode)
  readonly property string nextCode: LayoutModel.otherCode(pendingCode || applyingCode || savedCode || layoutCode)

  function refresh() {
    if (!stateReady) return
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
    pendingSilent = false
    retryAfter = 0
    refresh()
  }

  function remember(code) {
    if (code !== "us" && code !== "de") return
    if (savedCode === code) return
    savedCode = code
    if (stateWritable) stateFile.setText(JSON.stringify({layout: code}) + "\n")
  }

  function loadState(raw) {
    if (stateReady) return
    try {
      var code = JSON.parse(raw).layout
      if (code === "us" || code === "de") savedCode = code
    } catch (error) {}
    stateReady = true
    if (pendingCode) refresh()
    else restoreSaved()
  }

  function restoreSaved() {
    if (!stateReady) return
    retryAfter = 0
    refresh()
  }

  function prepareForSleep(asleep) {
    // Reconciliation also runs without a resume signal. Timers naturally pause
    // during system suspend; a lost DBus signal must not disable the fallback.
    if (!asleep) restoreSaved()
  }

  function applyQueued() {
    if (!pendingCode || applyProc.running) return
    var code = pendingCode
    pendingCode = ""
    var silent = pendingSilent
    pendingSilent = false
    var keyboards = silent ? typedKeyboards.filter(function(device) {
      return LayoutModel.currentCode(device) !== code
    }) : typedKeyboards
    var command = LayoutModel.switchCommand(keyboards, code)
    if (!command) {
      lastError = "Configure kb_layout = us,de for the keyboard in Hyprland first."
      return
    }
    applyingCode = code
    applyingSilent = silent
    lastError = ""
    applyProc.command = ["timeout", "--kill-after=1s", "10s", "bash", "-c", command]
    applyProc.running = true
  }

  function toggle() { applyCode(nextCode) }
  function setLayout(code) { applyCode(String(code || "").toLowerCase()) }

  Component.onCompleted: ensureStateDir.running = true

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (!event || !event.name) return
      var name = String(event.name)
      if (name === "activelayout") {
        var named = LayoutModel.eventKeyboardName(event)
        if (named) root.typedKeyboardName = named
      }
      if (name === "configreloaded") root.restoreSaved()
      else if (name === "activelayout") refreshTimer.restart()
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
      // Only an explicit, successful plugin switch changes the saved choice.
      // Wake/hotplug layout events can arrive late or without a sleep signal.
      if (!root.pendingCode) {
        if (!root.savedCode) root.remember(root.layoutCode)
        if (root.savedCode && Date.now() >= root.retryAfter) {
          var needsRestore = root.typedKeyboards.some(function(device) {
            return LayoutModel.hasUsAndDe(device) && LayoutModel.currentCode(device) !== root.savedCode
          })
          if (needsRestore) {
            root.pendingCode = root.savedCode
            root.pendingSilent = true
          }
        }
      }
      root.applyQueued()
      if (root.refreshPending) refreshTimer.restart()
    }
  }

  Process {
    id: applyProc
    onExited: function(exitCode) {
      var code = root.applyingCode
      root.applyingCode = ""
      if (exitCode === 0) {
        if (!root.applyingSilent) {
          root.remember(code)
          root.showOsd(code)
        }
      } else {
        root.lastError = "Could not switch the keyboard layout"
        root.retryAfter = Date.now() + 3000
      }
      root.applyingSilent = false
      root.refresh()
    }
  }

  Process {
    id: ensureStateDir
    command: ["mkdir", "-p", root.stateDir]
    onExited: function(exitCode) {
      root.stateWritable = exitCode === 0
      if (exitCode !== 0) root.persistenceError = "Could not create keyboard layout state directory"
      stateFile.path = root.stateDir + "/layout.json"
    }
  }

  FileView {
    id: stateFile
    atomicWrites: true
    blockWrites: true
    printErrors: false
    onLoaded: root.loadState(text())
    onLoadFailed: root.loadState("")
    onSaveFailed: root.persistenceError = "Could not save keyboard layout"
    onSaved: root.persistenceError = ""
  }

  Process {
    id: sleepMonitor
    running: true
    command: ["dbus-monitor", "--system",
      "type='signal',sender='org.freedesktop.login1',path='/org/freedesktop/login1',interface='org.freedesktop.login1.Manager',member='PrepareForSleep'"]
    stdout: SplitParser {
      onRead: function(line) {
        var value = String(line).trim()
        if (value === "boolean true") root.prepareForSleep(true)
        else if (value === "boolean false") root.prepareForSleep(false)
      }
    }
    onExited: monitorRetry.restart()
  }

  Timer {
    id: monitorRetry
    interval: 5000
    onTriggered: sleepMonitor.running = true
  }

  Timer {
    id: refreshTimer
    interval: 100
    onTriggered: root.refresh()
  }

  // Keep reconciling for resets that arrive without a usable wake/layout event,
  // including display sleep and devices that reconnect long after resume.
  Timer {
    interval: 2000
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
        pending: root.pendingCode || root.applyingCode, error: root.lastError || root.persistenceError,
        saved: root.savedCode
      })
    }
  }
}
