"""Bounded, failure-safe retention of explicitly named Qt test artifacts.

Keep this context inside TemporaryDirectory and outside process cleanup, open
logs, and assertions (including assertions comparing multiple runs). For example:

    with TemporaryDirectory() as temporary:
        directory = Path(temporary)
        with retain_qt_evidence(evidence_root / test_name, [
            directory / 'result.json', directory / 'ui.log',
            directory / 'screen.png', directory / 'trace.jsonl',
        ]):
            run_and_check_qt(directory)

The caller chooses the destination, file names, and retention scope. Retention
does not parse reports or decide whether a run passed; incomplete JSON and logs
are useful evidence too. Pass None as the destination to disable retention.
"""
from contextlib import contextmanager
from pathlib import Path
import stat


MAX_EVIDENCE_BYTES = 5 * 1024 * 1024


def _retain_files(destination, sources):
    destination.mkdir(parents=True, exist_ok=True)
    errors = []
    for source in sources:
        try:
            # Do not recurse into directories or block reading a named pipe.
            # A bounded read also enforces the cap if the file grows after stat.
            try:
                info = source.stat()
            except FileNotFoundError:
                continue  # A failed run need not have produced every artifact.
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_EVIDENCE_BYTES:
                continue
            with source.open('rb') as stream:
                content = stream.read(MAX_EVIDENCE_BYTES + 1)
            if len(content) > MAX_EVIDENCE_BYTES:
                continue
            (destination / source.name).write_bytes(content)
        except OSError as error:
            errors.append((source, error))
            # One inaccessible artifact must not prevent retaining the others.
    if errors:
        details = '; '.join(f'{source.name}: {error}' for source, error in errors)
        raise OSError(f'Could not retain Qt evidence at {destination}: {details}') from errors[0][1]


@contextmanager
def retain_qt_evidence(destination, sources):
    """Retain named files on every exit without replacing a run's exception.

    Existing regular files of at most 5 MiB are copied byte-for-byte by basename.
    Missing, nonregular, and oversized files are skipped. Sources are explicit
    paths, not directory globs; no unrelated files are collected. Use a distinct
    destination for each test/run whose evidence must remain distinguishable.

    Retention errors fail an otherwise successful scope. If the body already
    failed, its original exception and traceback propagate instead, with an
    explanatory exception note when supported. Process ownership, shutdown,
    log flushing, and report validation remain the caller's responsibility.
    """
    sources = tuple(Path(source) for source in sources)
    destination = Path(destination) if destination is not None else None
    original_error = None
    try:
        yield
    except BaseException as error:
        original_error = error
        raise
    finally:
        if destination is not None:
            try:
                _retain_files(destination, sources)
            except Exception as error:
                if original_error is None:
                    raise
                # Diagnostics must not turn a failed retention into a new error,
                # even for custom exceptions or Python without add_note.
                try:
                    original_error.add_note(f'Qt evidence retention also failed: {error}')
                except Exception:
                    pass
