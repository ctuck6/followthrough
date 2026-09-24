"""Run an isolated Followthrough window and stop its servers when it closes."""

import fcntl
import json
import os
import platform
from pathlib import Path
import shutil
import signal
import subprocess
import time
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
STATE = Path.home() / 'Library/Application Support/Followthrough'
URL = 'http://localhost:5174'
PROCESSES: list[subprocess.Popen] = []


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.read()


def stop() -> None:
    for process in reversed(PROCESSES):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in reversed(PROCESSES):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def launch(args: list[str], cwd: Path, log: object, env: dict) -> subprocess.Popen:
    process = subprocess.Popen(
        args, cwd=cwd, stdout=log, stderr=log, env=env, start_new_session=True
    )
    PROCESSES.append(process)
    return process


def select_node() -> str:
    """Select a runtime that can load the installed native frontend dependencies."""
    candidates = [
        str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime'
            / 'dependencies/node/bin/node'),
        '/opt/homebrew/bin/node',
        shutil.which('node'),
        '/usr/local/bin/node',
    ]
    errors = []
    for candidate in dict.fromkeys(candidates):
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run(
                [candidate, '--input-type=module', '-e',
                 "await import('vite'); await import('rollup');"],
                cwd=ROOT / 'frontend', capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return candidate
            errors.append(f'{candidate}: {result.stderr.strip()}')
        except (OSError, subprocess.TimeoutExpired) as error:
            errors.append(f'{candidate}: {error}')
    raise RuntimeError(
        'No compatible Node.js runtime could load the frontend dependencies.\n'
        + '\n'.join(errors)
    )


def chrome_command() -> list[str]:
    """Avoid inheriting Finder's Rosetta architecture preference."""
    architecture = platform.machine()
    if architecture == 'arm64':
        return ['/usr/bin/arch', '-arm64', str(CHROME)]
    return [str(CHROME)]


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'launcher.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        # Import from the script directory both for direct launch and test imports.
        sys.path.insert(0, str(ROOT / 'scripts'))
        from git_update import update_checkout

        if os.environ.pop('FOLLOWTHROUGH_UPDATE_CHECKED', '') != '1':
            with (STATE / 'launcher.log').open('a') as log:
                changed = update_checkout(ROOT, log)
            if changed:
                # Reload the newly pulled launcher code. The lock closes on exec.
                os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve())],
                          dict(os.environ, FOLLOWTHROUGH_UPDATE_CHECKED='1'))
        node = select_node()
        profile = STATE / 'Chrome'
        profile.mkdir(exist_ok=True)
        port_file = profile / 'DevToolsActivePort'
        port_file.unlink(missing_ok=True)
        env = dict(os.environ, FOLLOWTHROUGH_BACKEND='http://127.0.0.1:8001')
        with (STATE / 'launcher.log').open('a') as log:
            subprocess.run([str(ROOT / 'backend/.venv/bin/python'), 'manage.py', 'migrate', '--noinput', '--settings=config.settings.desktop'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, check=True)
            backend = launch([
                str(ROOT / 'backend/.venv/bin/python'), 'manage.py', 'runserver',
                '127.0.0.1:8001', '--noreload', '--settings=config.settings.desktop',
            ], ROOT / 'backend', log, env)
            frontend = launch([
                node, 'node_modules/vite/bin/vite.js', '--host', 'localhost',
                '--port', '5174', '--strictPort',
            ], ROOT / 'frontend', log, env)
            deadline = time.monotonic() + 40
            while True:
                if backend.poll() is not None or frontend.poll() is not None:
                    raise RuntimeError('A server could not start. See launcher.log.')
                try:
                    fetch('http://127.0.0.1:8001/api/state/')
                    fetch('http://127.0.0.1:8001/api/accounts/')
                    fetch(URL)
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() > deadline:
                        raise RuntimeError('Servers took too long to start.')
                    time.sleep(0.25)
            chrome = launch(chrome_command() + [ f'--user-data-dir={profile}', '--remote-debugging-port=0',
                '--no-first-run', '--no-default-browser-check',
                '--disable-background-mode', f'--app={URL}',
            ], ROOT, log, env)
            deadline = time.monotonic() + 90
            while not port_file.exists():
                if chrome.poll() is not None:
                    return
                if time.monotonic() > deadline:
                    raise RuntimeError('Chrome did not open its application window.')
                time.sleep(0.25)
            port = int(port_file.read_text().splitlines()[0])
            seen_page = False
            missing_since = None
            while chrome.poll() is None:
                try:
                    targets = json.loads(fetch(f'http://127.0.0.1:{port}/json/list'))
                    pages = any(target.get('type') == 'page' for target in targets)
                    if pages:
                        seen_page = True
                        missing_since = None
                    elif seen_page:
                        missing_since = missing_since or time.monotonic()
                        if time.monotonic() - missing_since > 2:
                            return
                    elif time.monotonic() > deadline:
                        raise RuntimeError('Chrome did not create an application page.')
                except (OSError, urllib.error.URLError):
                    missing_since = missing_since or time.monotonic()
                    if time.monotonic() - missing_since > 5:
                        return
                time.sleep(0.5)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: exit(0))
    signal.signal(signal.SIGINT, lambda *_: exit(0))
    try:
        main()
    except Exception as error:
        stop()
        STATE.mkdir(parents=True, exist_ok=True)
        with (STATE / 'launcher.log').open('a') as log:
            log.write(f'Launcher error: {error}\n')
        subprocess.run([
            '/usr/bin/osascript', '-e',
            'display alert "Followthrough could not start" message '
            + json.dumps(str(error) + '\nLog: ' + str(STATE / 'launcher.log')),
        ], check=False)
    finally:
        stop()
