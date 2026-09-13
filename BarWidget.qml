import QtQuick
import qs.Ui
import qs.Commons
import "LayoutModel.js" as LayoutModel

BarWidget {
  id: root
  moduleName: "rafi.kb-layout"

  property var kbService: null

  readonly property string layoutCode: kbService ? kbService.layoutCode : ""
  readonly property string layoutFull: kbService ? kbService.layoutFull : ""
  readonly property string layoutLabel: LayoutModel.labelFor(layoutCode)
  readonly property string nextCode: LayoutModel.otherCode(layoutCode)

  function bindService() {
    if (kbService) return
    if (bar && bar.shell && typeof bar.shell.serviceFor === "function")
      kbService = bar.shell.serviceFor("rafi.kb-layout")
  }

  function toggle() {
    if (kbService && typeof kbService.toggle === "function") kbService.toggle()
  }

  Component.onCompleted: bindService()
  onBarChanged: bindService()

  Timer {
    interval: 250
    running: kbService === null
    repeat: true
    triggeredOnStart: true
    onTriggered: root.bindService()
  }

  visible: layoutLabel !== ""
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.layoutLabel
    fontSize: Style.font.caption
    horizontalMargin: 6
    tooltipText: root.layoutFull
      ? (root.layoutFull + " · click to switch to " + LayoutModel.labelFor(root.nextCode))
      : "Toggle US/DE layout"
    onPressed: function() { root.toggle() }
  }
}
