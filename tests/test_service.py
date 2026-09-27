"""Run the real QML service against a fake compositor, without a desktop."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('qs'), 'requires Quickshell')
class ServiceTests(unittest.TestCase):
    def test_first_request_waits_for_discovery_and_never_reconfigures_hyprland(self):
        with tempfile.TemporaryDirectory(prefix='kb-qml-') as temp:
            root = Path(temp)
            for name in ('Kb', 'Commons', 'bin', 'runtime'):
                (root / name).mkdir(mode=0o700)
            for name in ('Service.qml', 'LayoutModel.js'):
                shutil.copy2(ROOT / name, root / 'Kb' / name)
            (root / 'Commons/qmldir').write_text('module qs.Commons\nsingleton Util 1.0 Util.qml\n')
            (root / 'Commons/Util.qml').write_text('pragma Singleton\nimport QtQml\nQtObject { function execArgv(argv) {} }\n')
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "Kb" as Kb
ShellRoot {
  Kb.Service { id: service }
  Component.onCompleted: service.setLayout("de")
  Timer {
    interval: 50; running: true; repeat: true
    onTriggered: {
      if (service.layoutCode === "de" && service.pendingCode === "" && service.applyingCode === "") {
        console.log("KB_TEST_PASS")
        Qt.quit()
      }
    }
  }
}
''')
            fake = root / 'bin/hyprctl'
            fake.write_text('''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
root = Path(os.environ['KB_TEST_ROOT'])
args = sys.argv[1:]
with (root / 'calls').open('a') as f: f.write(json.dumps(args) + '\\n')
state = root / 'state'
if args == ['-j', 'devices']:
 time.sleep(.1)
 index = int(state.read_text()) if state.exists() else 0
 print(json.dumps({'keyboards':[{'name':'test-keyboard', 'layout':'us,de', 'main':True, 'active_layout_index':index, 'active_keymap':'German' if index else 'English (US)'}]}))
elif args[:2] == ['switchxkblayout', 'test-keyboard']:
 state.write_text(args[2])
else: raise SystemExit(99)
''')
            fake.chmod(0o755)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(root / 'runtime'),
                       KB_TEST_ROOT=str(root), PATH=str(root / 'bin') + os.pathsep + os.environ['PATH'],
                       HYPRLAND_INSTANCE_SIGNATURE='')
            result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                                    capture_output=True, text=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('KB_TEST_PASS', result.stdout + result.stderr)
            calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
            self.assertIn(['switchxkblayout', 'test-keyboard', '1'], calls)
            self.assertFalse(any('keyword' in args for args in calls))

if __name__ == '__main__': unittest.main()
