#!/usr/bin/env python3
"""Bounded client for an explicitly enabled ShowPsiSi UI diagnostic session."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid


def request(directory, method, params=None, timeout=15):
    directory = Path(directory).resolve(strict=True)
    session = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
    if session.get('schema_version') != 1 or method not in session.get('methods', []):
        raise ValueError('Unsupported UI session or method')
    request_id = uuid.uuid4().hex
    temporary = directory / (request_id + '.pending')
    destination = directory / (request_id + '.request.json')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump({'id': request_id, 'method': method, 'params': params or {}}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.rename(destination)
    response = directory / (request_id + '.response.json')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if response.exists():
            envelope = json.loads(response.read_text(encoding='utf-8'))
            if envelope.get('id') != request_id or not isinstance(envelope.get('ok'), bool):
                raise ValueError('Invalid response envelope')
            if not envelope['ok']:
                raise RuntimeError(envelope.get('result', {}).get('error', 'UI request failed'))
            return envelope['result']
        time.sleep(.05)
    raise TimeoutError(f'UI response timed out: {request_id}; inspect session before retrying actions')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('method', choices=['snapshot', 'capture', 'action'])
    parser.add_argument('--params', default='{}', help='JSON object for the named UI action')
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error('timeout must be in (0, 60] seconds')
    params = json.loads(args.params)
    if not isinstance(params, dict):
        parser.error('params must be an object')
    print(json.dumps(request(args.session, args.method, params, args.timeout), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
