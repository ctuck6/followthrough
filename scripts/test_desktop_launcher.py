"""Exercise launcher lifecycle without starting servers or touching journal data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    'launcher', Path(__file__).with_name('desktop_launcher.py')
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_window_close_finishes_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            launched = []

            def launch(args, cwd, log, env):
                process = MagicMock()
                process.poll.return_value = None
                launched.append(args)
                if len(launched) == 3:
                    (state / 'Chrome/DevToolsActivePort').write_text('9222\n')
                return process

            responses = [b'{}', b'ok', b'[{"type":"page"}]', b'[]', b'[]']
            with patch.dict(launcher.os.environ, {'FOLLOWTHROUGH_UPDATE_CHECKED': '1'}), patch.object(launcher, 'STATE', state), patch.object(
                launcher, 'launch', side_effect=launch
            ), patch.object(launcher, 'fetch', side_effect=responses), patch.object(
                launcher, 'select_node', return_value='/node'
            ), patch.object(launcher.time, 'sleep'), patch.object(
                launcher.time, 'monotonic', side_effect=[0, 0, 1, 2, 5]
            ):
                launcher.main()
            self.assertEqual(len(launched), 3)
            self.assertIn('--port', launched[1])
            self.assertIn('--app=http://localhost:5174', launched[2])

    def test_runtime_falls_back_when_native_dependencies_fail(self) -> None:
        with patch.object(launcher.Path, 'is_file', return_value=True), patch.object(
            launcher.subprocess, 'run', side_effect=[
                MagicMock(returncode=1, stderr='Wrong architecture'),
                MagicMock(returncode=0),
            ]
        ) as run:
            self.assertEqual(launcher.select_node(), '/opt/homebrew/bin/node')
            self.assertEqual(run.call_count, 2)

    def test_chrome_uses_native_apple_silicon(self) -> None:
        with patch.object(launcher.platform, 'machine', return_value='arm64'):
            self.assertEqual(launcher.chrome_command(), [
                '/usr/bin/arch', '-arm64', str(launcher.CHROME)
            ])

    def test_cleanup_stops_only_owned_process_groups(self) -> None:
        process = MagicMock(pid=123)
        process.poll.return_value = None
        with patch.object(launcher, 'PROCESSES', [process]), patch.object(
            launcher.os, 'killpg'
        ) as kill:
            launcher.stop()
            kill.assert_called_once_with(123, launcher.signal.SIGTERM)
            process.wait.assert_called_once_with(timeout=5)


if __name__ == '__main__':
    unittest.main()
