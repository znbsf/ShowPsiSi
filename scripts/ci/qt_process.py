"""Tear down only a test-owned Qt process (and its Windows descendants)."""
import os
import subprocess
import sys


def stop_qt_process(process):
    if process.poll() is None:
        if os.name == 'nt':
            # TerminateProcess alone skips Qt's backend destructor. Descendants
            # can retain inherited log handles after the direct child is reaped.
            # Target the still-live process we launched, never an image name.
            try:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               check=True, capture_output=True, text=True, timeout=10)
            except subprocess.CalledProcessError as error:
                # A close-test can publish its report just before normal exit.
                # Never infer that race from taskkill's code alone.
                exit_code = process.poll()
                diagnostic = (f'Owned Qt cleanup: taskkill={error.returncode}, '
                              f'Qt exit={exit_code}, stdout={error.stdout!r}, stderr={error.stderr!r}')
                print(diagnostic, file=sys.stderr)
                if error.returncode != 128 or exit_code != 0:
                    raise RuntimeError(diagnostic) from error
        else:
            process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
