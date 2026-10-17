"""Strict native CI runner with persistent loader, Qt smoke, and test evidence.

The regular test files remain the source of assertions. This wrapper additionally
rejects zero/skip-only coverage and retains a real Qt smoke's screenshot/trace.
It never treats a build or a simulated UI as a successful native regression.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from qt_result import wait_for_qt_result

ROOT = Path(__file__).resolve().parents[2]


def required_binary(variable):
    value = os.environ.get(variable)
    if not value or not Path(value).is_file():
        raise RuntimeError(f"{variable} must name an existing native executable: {value!r}")
    return Path(value).resolve()


def engine_probe(artifacts, variable="SHOWPSISI_CORE", prefix="engine-probe"):
    """Catch Windows DLL startup failures before they become JSON/pipe errors."""
    binary = required_binary(variable)
    completed = subprocess.run(
        [str(binary), "--root", str(ROOT)], cwd=ROOT,
        input='{"id":1,"method":"capabilities","params":{}}\n',
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    (artifacts / f"{prefix}.stdout.jsonl").write_text(completed.stdout, encoding="utf-8")
    (artifacts / f"{prefix}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    status = {
        "binary": str(binary), "exit_code": completed.returncode,
        "exit_hex": f"0x{completed.returncode & 0xFFFFFFFF:08X}",
    }
    (artifacts / f"{prefix}-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print("Native startup:", status, flush=True)
    if completed.returncode:
        raise RuntimeError(
            f"Native startup failed ({status['exit_hex']}). "
            "On Windows, 0xC0000135 means a missing DLL; 0xC000007B an invalid architecture. "
            f"See {prefix}.stderr.log and Diagnostics.log's dumpbin dependencies.\n"
            + completed.stderr
        )
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    if not any(item.get("id") == 1 and "result" in item for item in responses):
        raise RuntimeError(f"Engine did not answer capabilities: {responses!r}")


def run_suite(pattern, artifacts):
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
    with (artifacts / f"{Path(pattern).stem}.log").open("w", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    text = (artifacts / f"{Path(pattern).stem}.log").read_text(encoding="utf-8")
    print(text, flush=True)
    # The large, separately sourced French recording is deliberately untracked.
    # Permit only its existing absence skip; never hide a missing native binary,
    # unavailable protocol fixture, changed reason, or another skipped test.
    allowed_skips = [
        (test.id(), reason) for test, reason in result.skipped
        if test.id() == "test_engine.EngineTests.test_real_stream_baseline"
        and reason == "Optional real sample missing"
        and not (ROOT / "samples/real/tnt-uhf22-2019.ts").exists()
    ]
    unexpected_skips = [
        (test.id(), reason) for test, reason in result.skipped
        if (test.id(), reason) not in allowed_skips
    ]
    summary = {
        "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": [(test.id(), reason) for test, reason in result.skipped],
        "allowed_skips": allowed_skips, "unexpected_skips": unexpected_skips,
        "unexpected_successes": len(result.unexpectedSuccesses),
        "expected_failures": len(result.expectedFailures),
    }
    (artifacts / f"{Path(pattern).stem}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # Qt tests normally skip when the executable is absent; this CI job must fail.
    if allowed_skips:
        print("Optional real-stream recording absent; no real-recording coverage claimed.", flush=True)
    return result.wasSuccessful() and result.testsRun > len(result.skipped) and not unexpected_skips


def qt_smoke(artifacts):
    """Keep one smoke run's actual output even when a later unittest fails."""
    binary = required_binary("SHOWPSISI_QT")
    output = artifacts / "qt-smoke"
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "result.json"
    # Each CI invocation gets a fresh directory; refuse stale success evidence.
    if report_path.exists():
        raise RuntimeError(f"Remove the old CI artifacts before rerunning: {report_path}")
    env = os.environ.copy()
    env.update(
        SHOWPSISI_AUTO="1", SHOWPSISI_SCRIPT="smoke", SHOWPSISI_STANDARDS="dvb",
        SHOWPSISI_SAMPLE=str(ROOT / "samples/generated/lab.ts"),
        SHOWPSISI_TEST_RESULT=str(report_path), SHOWPSISI_SCREENSHOT=str(output / "screen.png"),
        SHOWPSISI_TRACE=str(output / "trace.jsonl"), SHOWPSISI_ARTIFACT_DIR=str(output),
        QT_DEBUG_PLUGINS="1", QT_FORCE_STDERR_LOGGING="1",
    )
    with (output / "ui.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([str(binary)], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            report = wait_for_qt_result(report_path, process, 60)
            original_returncode = process.poll()
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    diagnostics = (output / "ui.log").read_text(encoding="utf-8", errors="replace")
    if "QFontDatabase: Cannot find font directory" in diagnostics:
        raise RuntimeError("Qt offscreen cannot load fonts; screenshot text would be unreadable. See qt-smoke/ui.log.")
    if not report_path.is_file():
        print(diagnostics, flush=True)
        code = None if original_returncode is None else f"0x{original_returncode & 0xFFFFFFFF:08X}"
        raise RuntimeError(f"Qt smoke did not produce a report (exit={code}). See qt-smoke/ui.log and trace.jsonl.")
    print("Retained Qt smoke:", json.dumps(report, ensure_ascii=False), flush=True)
    screenshot = output / "screen.png"
    if not report.get("passed") or not screenshot.is_file() or screenshot.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Native Qt smoke failed or screenshot missing; see qt-smoke evidence.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--engine", action="store_true")
    mode.add_argument("--qt", action="store_true")
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    engine_probe(artifacts)
    # The deterministic cancellation seam is a separate opt-in executable.
    # Ordinary tests and the retained UI smoke must keep using production core.
    engine_probe(artifacts, "SHOWPSISI_TEST_CORE", "cancellation-helper-probe")
    if args.qt:
        qt_smoke(artifacts)
        patterns = ["test_qt_ui.py", "test_qt_resource_paths.py"]
    else:
        patterns = ["test_engine.py", "test_protocol_coverage.py", "test_sdk_migration.py", "test_cloud_preview.py",
                    "test_cancellation.py", "test_mcp_cancellation.py", "test_portable_package.py"]
    results = [run_suite(pattern, artifacts) for pattern in patterns]
    if not all(results):
        raise SystemExit("Native regression failed, discovered zero executable tests, or unexpectedly skipped coverage. See logs above.")


if __name__ == "__main__":
    main()
