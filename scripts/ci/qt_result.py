"""Wait for a complete Qt test result before stopping its producing process."""
import json
import time


def wait_for_qt_result(path, process, timeout, on_running=None):
    # QFile creates the path before its buffered JSON is flushed. Existence alone
    # is not publication: terminating the writer at that point can truncate it.
    deadline = time.monotonic() + timeout
    content = None
    while True:
        try:
            content = path.read_text(encoding="utf-8")
            report = json.loads(content)
            assert isinstance(report, dict), f"Qt result must be an object: {content!r}"
            return report
        except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as error:
            last_error = error
        exit_code = process.poll()
        if exit_code is not None:
            # The writer may have flushed between our read and observing exit.
            try:
                content = path.read_text(encoding="utf-8")
                report = json.loads(content)
                assert isinstance(report, dict), f"Qt result must be an object: {content!r}"
                return report
            except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as error:
                last_error = error
        if exit_code is not None or time.monotonic() >= deadline:
            raise AssertionError(
                f"Qt did not publish complete JSON at {path} "
                f"(exit={exit_code}, timeout={timeout}s, content={content!r}): {last_error}"
            ) from last_error
        if on_running:
            on_running(process)
        time.sleep(0.1)
