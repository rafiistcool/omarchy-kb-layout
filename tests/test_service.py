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
        self.run_service(request='de', expected='de')

    def test_restores_saved_layout_before_observing_startup_default(self):
        self.run_service(saved='de', expected='de')

    def test_resume_restores_layout_and_handles_delayed_device_reset(self):
        self.run_service(saved='de', expected='de', resume=True)

    def test_invalid_state_falls_back_to_current_layout(self):
        self.run_service(saved='invalid', expected='us')

    def test_failed_switch_does_not_overwrite_saved_layout(self):
        self.run_service(saved='us', request='de', expected='us', fail=True)

    def run_service(self, saved=None, request=None, expected='de', resume=False, fail=False):
        with tempfile.TemporaryDirectory(prefix='kb-qml-') as temp:
            root = Path(temp)
            for name in ('Kb', 'Commons', 'bin', 'runtime'):
                (root / name).mkdir(mode=0o700)
            for name in ('Service.qml', 'LayoutModel.js'):
                shutil.copy2(ROOT / name, root / 'Kb' / name)
            state_dir = root / 'persistent/omarchy/rafi.kb-layout'
            state_dir.mkdir(parents=True)
            if saved:
                (state_dir / 'layout.json').write_text(json.dumps({'layout': saved}))
            (root / 'Commons/qmldir').write_text('module qs.Commons\nsingleton Util 1.0 Util.qml\n')
            (root / 'Commons/Util.qml').write_text('pragma Singleton\nimport QtQml\nQtObject { function execArgv(argv) {} }\n')
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "Kb" as Kb
ShellRoot {
  Kb.Service { id: service }
  property double settledAt: 0
  Component.onCompleted: REQUEST
  Timer {
    interval: 50; running: true; repeat: true
    onTriggered: {
      if (service.stateReady && service.layoutCode === "EXPECTED" && service.pendingCode === "" && service.applyingCode === "") {
        if (settledAt === 0) settledAt = Date.now()
        if (Date.now() - settledAt > 5600) { console.log("KB_TEST_PASS"); Qt.quit() }
      }
    }
  }
}
'''.replace('REQUEST', 'service.setLayout(' + json.dumps(request) + ')' if request else '{}')
                .replace('EXPECTED', expected))
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
 if os.environ.get('KB_TEST_FAIL') == '1': raise SystemExit(7)
 state.write_text(args[2])
else: raise SystemExit(99)
''')
            fake.chmod(0o755)
            monitor = root / 'bin/dbus-monitor'
            monitor.write_text('''#!/usr/bin/env python3
import os, time
from pathlib import Path
if os.environ.get('KB_TEST_RESUME') == '1':
 time.sleep(.7)
 print('   boolean true', flush=True)
 time.sleep(.2)
 (Path(os.environ['KB_TEST_ROOT']) / 'state').write_text('0')
 print('   boolean false', flush=True)
 time.sleep(1.5)
 (Path(os.environ['KB_TEST_ROOT']) / 'state').write_text('0')
time.sleep(30)
''')
            monitor.chmod(0o755)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(root / 'runtime'),
                       XDG_STATE_HOME=str(root / 'persistent'), KB_TEST_RESUME='1' if resume else '0',
                       KB_TEST_FAIL='1' if fail else '0',
                       KB_TEST_ROOT=str(root), PATH=str(root / 'bin') + os.pathsep + os.environ['PATH'],
                       HYPRLAND_INSTANCE_SIGNATURE='')
            result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('KB_TEST_PASS', result.stdout + result.stderr)
            calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
            switches = calls.count(['switchxkblayout', 'test-keyboard', '1'])
            if expected == 'de' or fail:
                self.assertGreaterEqual(switches, 3 if resume else 1, calls)
            else:
                self.assertEqual(switches, 0, calls)
            self.assertFalse(any('keyword' in args for args in calls))
            self.assertLessEqual(calls.count(['-j', 'devices']), 12 if saved == 'de' else 3, calls)
            self.assertEqual(json.loads((state_dir / 'layout.json').read_text())['layout'], expected)

if __name__ == '__main__': unittest.main()
