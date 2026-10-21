"""Bounded, reproducible synthetic analysis/transport benchmark.

This is not a disk, GUI, real EPG or Windows interaction benchmark. Wall times
include process startup and client JSON decoding. Compact runs consume all result
pages, so terminal latency alone cannot conceal work deferred to hydration.
Run the same fixture/arguments with a baseline legacy core and a candidate compact
core. Keep source/build identities and individual rounds; do not infer a universal
speedup from one run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

from make_fixture import section, word

COLLECTIONS = (
    "tables", "services", "events", "history", "table_history",
    "diagnostics", "density", "table_groups",
)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def generate(path, kind, mib, unique):
    packets = mib * 1024 * 1024 // 188
    if kind == "null":
        block = (b"\x47\x1f\xff\x10" + b"\xff" * 184) * 8192
        with path.open("wb") as stream:
            while packets:
                count = min(packets, 8192)
                stream.write(block[:count * 188])
                packets -= count
        return
    if kind == "pat":
        sections = [section(0, 1, 1, word(1) + word(0xE100))]
        pid = 0
    else:
        # Empty EIT event loops: stress unique table/result cardinality, NOT
        # realistic event decoding or broadcast completeness.
        sections = [
            section(0x4E, index + 1, 1, word(1) + word(1) + b"\x00\x4e")
            for index in range(unique)
        ]
        pid = 0x12
    with path.open("wb") as stream:
        buffer = bytearray()
        for index in range(packets):
            raw = sections[index % len(sections)]
            buffer.extend(bytes((0x47, 0x40 | (pid >> 8), pid & 255,
                                 0x10 | (index & 15))))
            buffer.extend(b"\x00" + raw + b"\xff" * (183 - len(raw)))
            if len(buffer) >= 1024 * 1024:
                stream.write(buffer)
                buffer.clear()
        stream.write(buffer)


def run(core, root, source, mode, timeout):
    started = time.perf_counter()
    proc = subprocess.Popen(
        [str(core), "--root", str(root)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    lines = queue.Queue()
    errors = []

    def read_output():
        try:
            for line in proc.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    def drain_errors():
        for line in proc.stderr:
            if sum(map(len, errors)) < 65536:
                errors.append(line)

    reader = threading.Thread(target=read_output, daemon=True)
    stderr_reader = threading.Thread(target=drain_errors, daemon=True)
    reader.start()
    stderr_reader.start()
    stats = dict(messages=0, progress_messages=0, wire_bytes=0,
                 max_message_bytes=0, max_progress_bytes=0,
                 first_progress_wall_ms=None, pages=0, item_counts={})
    request_id = 0
    deadline = started + timeout

    def request(method, params):
        nonlocal request_id
        request_id += 1
        expected = request_id
        proc.stdin.write((json.dumps(dict(id=expected, method=method,
                                         params=params)) + "\n").encode())
        proc.stdin.flush()
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError("Benchmark exceeded its total deadline")
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty as error:
                raise TimeoutError("No complete response before deadline") from error
            if line is None:
                raise RuntimeError("Core exited before response: " +
                                   b"".join(errors).decode(errors="replace"))
            stats["messages"] += 1
            stats["wire_bytes"] += len(line)
            stats["max_message_bytes"] = max(stats["max_message_bytes"], len(line))
            value = json.loads(line)
            if value.get("event") == "progress":
                stats["progress_messages"] += 1
                stats["max_progress_bytes"] = max(stats["max_progress_bytes"], len(line))
                if stats["first_progress_wall_ms"] is None:
                    stats["first_progress_wall_ms"] = (time.perf_counter() - started) * 1000
                continue
            if value.get("id") != expected:
                raise AssertionError("Unexpected response identity")
            if "error" in value:
                raise RuntimeError(json.dumps(value["error"]))
            return value["result"]

    try:
        params = dict(path=str(source), standards="dvb")
        if mode == "compact":
            params["response_mode"] = "compact"
        result = request("analyze", params)
        stats["analyze_terminal_wall_ms"] = (time.perf_counter() - started) * 1000
        stats["backend_metrics"] = result.get("metrics", {})
        stats["analysis_revision"] = result.get("analysis_revision")
        stats["observations"] = result.get("observations")
        if mode == "compact":
            for collection in COLLECTIONS:
                offset = 0
                count = 0
                total = None
                while True:
                    page = request("query_result", dict(
                        analysis_revision=result["analysis_revision"],
                        collection=collection, offset=offset, limit=200,
                    ))
                    if (page.get("analysis_revision") != result["analysis_revision"]
                            or page.get("collection") != collection
                            or page.get("at_packet") is not None):
                        raise AssertionError("Result page identity/cutoff mismatch")
                    items = page.get("items")
                    page_total = page.get("total")
                    if (not isinstance(items, list) or len(items) > 200
                            or type(page_total) is not int or page_total < 0):
                        raise AssertionError("Invalid result page shape")
                    if total is None:
                        total = page_total
                    if page_total != total:
                        raise AssertionError("Result total changed during hydration")
                    end = offset + len(items)
                    if end > total:
                        raise AssertionError("Result page exceeds its collection")
                    count += len(items)
                    stats["pages"] += 1
                    next_offset = page.get("next_offset")
                    if next_offset is None:
                        if end != total:
                            raise AssertionError("Result page ended prematurely")
                        break
                    if (type(next_offset) is not int or next_offset != end
                            or next_offset <= offset or next_offset >= total):
                        raise AssertionError("Invalid result page cursor")
                    offset = next_offset
                if count != total:
                    raise AssertionError(f"{collection}: incomplete hydration")
                stats["item_counts"][collection] = count
        else:
            stats["item_counts"] = {
                key: len(result.get(key, [])) for key in COLLECTIONS
            }
        stats["fully_consumed_wall_ms"] = (time.perf_counter() - started) * 1000
        proc.stdin.close()
        proc.wait(timeout=max(1, deadline - time.perf_counter()))
        if proc.returncode:
            raise RuntimeError(f"Core exit status {proc.returncode}")
        return stats
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        reader.join(timeout=2)
        stderr_reader.join(timeout=2)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream and not stream.closed:
                stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--response-mode", choices=("legacy", "compact"), default="compact")
    parser.add_argument("--fixture", choices=("null", "pat", "many-eit"), default="many-eit")
    parser.add_argument("--mib", type=int, default=8)
    parser.add_argument("--unique-sections", type=int, default=5000)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.mib <= 512 or not 1 <= args.unique_sections <= 20000:
        parser.error("Use 1–512 MiB and 1–20000 unique sections")
    if not 1 <= args.rounds <= 10 or not 1 <= args.timeout <= 600:
        parser.error("Use 1–10 rounds and a 1–600 second per-round deadline")
    args.core = args.core.resolve(strict=True)
    args.root = args.root.resolve(strict=True)
    report = dict(
        core_sha256=digest(args.core), core=str(args.core), root=str(args.root),
        source_main_cpp_sha256=digest(args.root / "core/main.cpp"),
        mode=args.response_mode, fixture=args.fixture,
        unique_sections=args.unique_sections if args.fixture == "many-eit" else None,
        platform=os.name, runs=[],
        limitations="Synthetic CLI; startup and client decoding included; warm-cache "
                    "effects uncontrolled; not HDD/GUI/real EPG acceptance.",
    )
    try:
        report["checkout_head"] = subprocess.check_output(
            ["git", "-C", str(args.root), "rev-parse", "HEAD"], text=True,
        ).strip()
        report["checkout_dirty"] = bool(subprocess.check_output(
            ["git", "-C", str(args.root), "status", "--porcelain"], text=True,
        ).strip())
    except (OSError, subprocess.CalledProcessError):
        report["checkout_head"] = None
        report["checkout_dirty"] = None
    with tempfile.TemporaryDirectory(prefix="showpsisi-analysis-benchmark-") as directory:
        source = Path(directory) / "synthetic.ts"
        generate(source, args.fixture, args.mib, args.unique_sections)
        report.update(source_bytes=source.stat().st_size, source_sha256=digest(source))
        for _ in range(args.rounds):
            report["runs"].append(run(args.core, args.root, source,
                                      args.response_mode, args.timeout))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
