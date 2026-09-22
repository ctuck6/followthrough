"""Test updates against temporary local repositories, without GitHub access."""

import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from git_update import update_checkout


class UpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.remote = root / 'remote'
        self.local = root / 'local'
        self.remote.mkdir()
        self.git(self.remote, 'init', '-b', 'main')
        self.configure(self.remote)
        self.commit(self.remote, 'initial')
        self.git(root, 'clone', str(self.remote), str(self.local))
        self.configure(self.local)
        self.log = io.StringIO()

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(
            ['/usr/bin/git', *args], cwd=cwd, check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    def configure(self, repo: Path) -> None:
        self.git(repo, 'config', 'user.name', 'Test')
        self.git(repo, 'config', 'user.email', 'test@example.invalid')
        self.git(repo, 'config', 'commit.gpgsign', 'false')

    def commit(self, repo: Path, content: str) -> None:
        (repo / 'app.txt').write_text(content)
        self.git(repo, 'add', 'app.txt')
        self.git(repo, 'commit', '-m', content)

    def test_clean_checkout_fast_forwards(self) -> None:
        self.commit(self.remote, 'updated')
        self.assertTrue(update_checkout(self.local, self.log))
        self.assertEqual((self.local / 'app.txt').read_text(), 'updated')
        self.assertFalse(update_checkout(self.local, self.log))

    def test_dirty_checkout_preserves_changes(self) -> None:
        self.commit(self.remote, 'updated')
        (self.local / 'app.txt').write_text('unsaved work')
        self.assertFalse(update_checkout(self.local, self.log))
        self.assertEqual((self.local / 'app.txt').read_text(), 'unsaved work')

    def test_divergent_history_is_untouched(self) -> None:
        self.commit(self.remote, 'remote work')
        self.commit(self.local, 'local work')
        before = self.git(self.local, 'rev-parse', 'HEAD')
        self.assertFalse(update_checkout(self.local, self.log))
        self.assertEqual(before, self.git(self.local, 'rev-parse', 'HEAD'))
        self.assertFalse(self.git(self.local, 'status', '--porcelain'))

    def test_unavailable_remote_uses_local_version(self) -> None:
        self.git(self.local, 'remote', 'set-url', 'origin', '/nonexistent/remote.git')
        self.assertFalse(update_checkout(self.local, self.log))
        self.assertIn('opening the local version', self.log.getvalue())
