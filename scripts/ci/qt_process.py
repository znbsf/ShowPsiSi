"""Tear down only a test-owned Qt process (and its Windows descendants)."""
import os
import subprocess


def stop_qt_process(process):
    if process.poll() is None:
        if os.name == 'nt':
            # TerminateProcess alone skips Qt's backend destructor. Descendants
            # can retain inherited log handles after the direct child is reaped.
            # Target the still-live process we launched, never an image name.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           check=True, capture_output=True, text=True, timeout=10)
        else:
            process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
