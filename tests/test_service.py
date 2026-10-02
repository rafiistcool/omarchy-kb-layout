"""Run the real QML service against a fake compositor, without a desktop."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
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

    def test_english_is_restored_too(self):
        self.run_service(saved='us', expected='us', initial='de', resume=True)

    def test_explicit_switch_to_english_replaces_saved_german(self):
        self.run_service(saved='de', request='us', expected='us', initial='de')

    def test_late_layout_event_does_not_replace_saved_german(self):
        self.run_service(saved='de', expected='de', reset_after=6, event=True)

    def test_late_layout_event_does_not_replace_saved_english(self):
        self.run_service(saved='us', expected='us', reset_after=6, event=True)

    def test_reset_without_sleep_or_layout_event_is_repaired(self):
        self.run_service(saved='de', expected='de', reset_after=1)

    def test_english_reset_without_events_is_repaired(self):
        self.run_service(saved='us', expected='us', initial='de', reset_after=1)

    def test_missing_resume_signal_does_not_disable_reconciliation(self):
        self.run_service(saved='de', expected='de', reset_after=1, lost_resume=True)

    def test_returning_keyboard_keeps_saved_layout(self):
        self.run_service(saved='de', expected='de', reappear=True)

    def test_failed_restoration_retries_without_overwriting_choice(self):
        self.run_service(saved='de', expected='us', fail=True)

    def test_selection_survives_an_actual_service_restart(self):
        self.run_service(request='de', expected='de', restart=True)

    def test_invalid_state_falls_back_to_current_layout(self):
        self.run_service(saved='invalid', expected='us')

    def test_failed_switch_does_not_overwrite_saved_layout(self):
        self.run_service(saved='us', request='de', expected='us', fail=True)

    def run_service(self, saved=None, request=None, expected='de', resume=False, fail=False,
                    initial='us', reset_after=0, event=False, reappear=False, restart=False,
                    lost_resume=False):
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
            (root / 'state').write_text('1' if initial == 'de' else '0')
            duration = reset_after + 3 if reset_after else 5 if resume or fail else 3
            (root / 'Commons/qmldir').write_text('module qs.Commons\nsingleton Util 1.0 Util.qml\n')
            (root / 'Commons/Util.qml').write_text('pragma Singleton\nimport QtQml\nQtObject { function execArgv(argv) { console.log("KB_OSD") } }\n')
            (root / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "Kb" as Kb
ShellRoot {
  Kb.Service { id: service }
  property double startedAt: Date.now()
  Component.onCompleted: REQUEST
  Timer {
    interval: 50; running: true; repeat: true
    onTriggered: {
      if (Date.now() - startedAt > DURATION) {
        console.log("KB_TEST_RESULT " + JSON.stringify({
          layout: service.layoutCode, saved: service.savedCode, error: service.lastError,
          pending: service.pendingCode || service.applyingCode, keyboards: service.typedKeyboards
        }))
        Qt.quit()
      }
    }
  }
}
'''.replace('REQUEST', 'service.setLayout(' + json.dumps(request) + ')' if request else '{}')
                .replace('DURATION', str(duration * 1000)))
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
 keyboards = [{'name':'test-keyboard', 'layout':'us,de', 'main':True, 'active_layout_index':index, 'active_keymap':'German' if index else 'English (US)'}]
 if (root / 'absent').exists(): keyboards = []
 print(json.dumps({'keyboards':keyboards}))
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
root = Path(os.environ['KB_TEST_ROOT'])
opposite = '0' if os.environ['KB_TEST_EXPECTED'] == 'de' else '1'
def reset():
 (root / 'state.new').write_text(opposite)
 (root / 'state.new').replace(root / 'state')
 (root / 'event').write_text('reset')
if os.environ.get('KB_TEST_REAPPEAR') == '1':
 (root / 'absent').touch()
 time.sleep(1)
 (root / 'absent').unlink()
if os.environ.get('KB_TEST_RESUME') == '1':
 time.sleep(.7)
 print('   boolean true', flush=True)
 time.sleep(.2)
 reset()
 print('   boolean false', flush=True)
 time.sleep(1.5)
 reset()
elif float(os.environ.get('KB_TEST_RESET_AFTER', '0')):
 time.sleep(float(os.environ['KB_TEST_RESET_AFTER']))
 if os.environ.get('KB_TEST_LOST_RESUME') == '1': print('   boolean true', flush=True)
 reset()
time.sleep(30)
''')
            monitor.chmod(0o755)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(root / 'runtime'),
                       XDG_STATE_HOME=str(root / 'persistent'), KB_TEST_RESUME='1' if resume else '0',
                       KB_TEST_FAIL='1' if fail else '0',
                       KB_TEST_EXPECTED=expected, KB_TEST_RESET_AFTER=str(reset_after),
                       KB_TEST_REAPPEAR='1' if reappear else '0',
                       KB_TEST_LOST_RESUME='1' if lost_resume else '0',
                       KB_TEST_ROOT=str(root), PATH=str(root / 'bin') + os.pathsep + os.environ['PATH'],
                       HYPRLAND_INSTANCE_SIGNATURE='')
            received = []
            finished = threading.Event()
            if event:
                # Feed a real Hyprland socket event into the native QML singleton.
                socket_dir = root / 'runtime/hypr/kb-test'
                socket_dir.mkdir(parents=True)
                server = socket.socket(socket.AF_UNIX)
                server.bind(str(socket_dir / '.socket2.sock'))
                server.listen(1)
                server.settimeout(10)
                env['HYPRLAND_INSTANCE_SIGNATURE'] = 'kb-test'

                def emit_event():
                    try:
                        connection, _ = server.accept()
                        with connection:
                            while not finished.wait(.02):
                                if (root / 'event').exists():
                                    keymap = 'English (US)' if expected == 'de' else 'German'
                                    connection.sendall(('activelayout>>test-keyboard,' + keymap + '\n').encode())
                                    received.append(True)
                                    break
                    except (OSError, TimeoutError):
                        pass

                thread = threading.Thread(target=emit_event, daemon=True)
                thread.start()
            try:
                result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                                        capture_output=True, text=True, timeout=duration + 5)
            finally:
                finished.set()
                if event:
                    server.close()
                    thread.join(timeout=1)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = result.stdout + result.stderr
            snapshots = [json.loads(line.split('KB_TEST_RESULT ', 1)[1])
                         for line in output.splitlines() if 'KB_TEST_RESULT ' in line]
            self.assertEqual(len(snapshots), 1, output)
            self.assertEqual(snapshots[0]['layout'], expected, output)
            self.assertEqual(snapshots[0]['pending'], '', output)
            if event:
                self.assertTrue(received, output)
            calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
            switches = [args for args in calls if args[0] == 'switchxkblayout']
            if request or saved == 'de' or resume or reset_after or fail:
                self.assertGreaterEqual(len(switches), 2 if resume else 1, calls)
            if fail:
                self.assertTrue(snapshots[0]['error'], output)
            else:
                self.assertEqual(snapshots[0]['error'], '', output)
                self.assertEqual((root / 'state').read_text(), '1' if expected == 'de' else '0')
            self.assertFalse(any('keyword' in args for args in calls))
            self.assertLessEqual(calls.count(['-j', 'devices']), duration + 6, calls)
            remembered = saved if fail else expected
            self.assertEqual(json.loads((state_dir / 'layout.json').read_text())['layout'], remembered)
            self.assertEqual(output.count('KB_OSD'), 1 if request and not fail else 0, output)
            if restart:
                # Reset the compositor default, keep the actual file produced above.
                (root / 'state').write_text('0' if expected == 'de' else '1')
                shell_file = root / 'shell.qml'
                shell_file.write_text(shell_file.read_text().replace('service.setLayout(' + json.dumps(request) + ')', '{}'))
                result = subprocess.run(['qs', '-p', str(root), '--no-color'], env=env,
                                        capture_output=True, text=True, timeout=duration + 5)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((root / 'state').read_text(), '1' if expected == 'de' else '0')
                self.assertEqual(json.loads((state_dir / 'layout.json').read_text())['layout'], expected)

if __name__ == '__main__': unittest.main()
