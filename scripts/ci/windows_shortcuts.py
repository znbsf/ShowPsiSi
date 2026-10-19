"""Unicode Shell-link identity checks with retained diagnostics, never execution."""
import argparse
import contextlib
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


@contextlib.contextmanager
def shell_link():
    if os.name != 'nt':
        raise RuntimeError('Native Shell-link checks require Windows')
    # IShellLinkW, not the encoding-neutral/ANSI interface. Methods follow the
    # Windows SDK shobjidl_core.h and objidl.h COM vtables.
    from ctypes import wintypes
    class GUID(ctypes.Structure):
        _fields_ = [('data', ctypes.c_ubyte * 16)]
    def guid(value):
        return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)
    def checked(result):
        if result < 0:
            raise OSError(f'Shell-link HRESULT 0x{result & 0xffffffff:08x}')
    def call(pointer, index, result, arguments, *values):
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *arguments)(vtable[index])(pointer, *values)
    ole = ctypes.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = (ctypes.c_void_p, wintypes.DWORD)
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoCreateInstance.argtypes = (ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
    ole.CoCreateInstance.restype = ctypes.c_long
    ole.CoUninitialize.argtypes = ()
    ole.CoUninitialize.restype = None
    checked(ole.CoInitializeEx(None, 2))  # COINIT_APARTMENTTHREADED
    link, persist = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        checked(ole.CoCreateInstance(ctypes.byref(guid('00021401-0000-0000-C000-000000000046')),
                None, 1, ctypes.byref(guid('000214F9-0000-0000-C000-000000000046')), ctypes.byref(link)))
        checked(call(link, 0, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
                     ctypes.byref(guid('0000010B-0000-0000-C000-000000000046')), ctypes.byref(persist)))
        def load(path):
            checked(call(persist, 5, ctypes.c_long, (wintypes.LPCWSTR, wintypes.DWORD), str(path), 0))
        def target():
            buffer = ctypes.create_unicode_buffer(32768)
            checked(call(link, 3, ctypes.c_long,
                         (wintypes.LPWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD),
                         buffer, len(buffer), None, 4))  # SLGP_RAWPATH; no search/Resolve
            if not buffer.value:
                raise RuntimeError('Shell link has no filesystem target')
            return buffer.value
        def save(path, destination):
            checked(call(link, 20, ctypes.c_long, (wintypes.LPCWSTR,), str(destination)))
            checked(call(persist, 6, ctypes.c_long, (wintypes.LPCWSTR, wintypes.BOOL), str(path), True))
        yield load, target, save
    finally:
        for pointer in (persist, link):
            if pointer:
                call(pointer, 2, ctypes.c_ulong, ())
        ole.CoUninitialize()


def read_target(path):
    with shell_link() as (load, target, _):
        load(path)
        return target()


def legacy_diagnostic(path):
    """Retain the former reader's bytes, only to diagnose transport/API differences."""
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; $s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:SHOWPSISI_SMOKE_LINK); $s.TargetPath"
    try:
        result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', command],
                                env=dict(os.environ, SHOWPSISI_SMOKE_LINK=str(path)), timeout=30,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        raw, stderr = result.stdout, result.stderr
        record = {'exit_code': result.returncode}
    except subprocess.TimeoutExpired as error:
        raw, stderr = error.stdout or b'', error.stderr or b''
        record = {'exit_code': None, 'timeout': True}
    record.update(stdout_hex=raw.hex(), stderr_hex=stderr.hex())
    try:
        record['decoded_utf8'] = raw.decode('utf-8').strip()
    except UnicodeDecodeError as error:
        record['utf8_decode_error'] = str(error)
    return record


def verify(path, expected, evidence):
    evidence.mkdir(parents=True, exist_ok=False)
    record = {'shortcut': str(path), 'expected': str(expected), 'passed': False}
    try:
        shutil.copyfile(path, evidence / 'shortcut.lnk')  # retain before any cleanup
        try:
            record['legacy_wscript'] = legacy_diagnostic(path)
        except Exception as error:
            record['legacy_diagnostic_error'] = str(error)
        record['target'] = read_target(path)
        record['resolved_expected'] = str(expected.resolve(strict=True))
        record['resolved_target'] = str(Path(record['target']).resolve(strict=True))
        record['resolved_equal'] = Path(record['resolved_target']) == Path(record['resolved_expected'])
        record['same_file'] = Path(record['target']).samefile(expected)
        # Preserve exact resolved-target comparison and additionally require the
        # OS to identify the same file. Equal contents alone are insufficient.
        if not record['resolved_equal'] or not record['same_file']:
            raise RuntimeError(f'Unexpected shortcut target: {record["target"]!r}; expected {str(expected)!r}')
        record['passed'] = True
        return record
    except Exception as error:
        record['error'] = str(error)
        raise
    finally:
        (evidence / 'target.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def probe(artifacts):
    if os.name != 'nt':
        raise RuntimeError('Native Shell-link probe requires Windows')
    with tempfile.TemporaryDirectory(prefix='ShowPsiSi shortcut 测试 ') as directory:
        root = Path(directory)
        expected = root / 'Application 空间' / 'target 文件.txt'
        expected.parent.mkdir()
        expected.write_text('Shortcut fixture only; never executed.', encoding='utf-8')
        link = root / 'shortcut 测试.lnk'
        with shell_link() as (_, _, save):
            save(link, expected)
        print(json.dumps(verify(link, expected, artifacts), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    probe(parser.parse_args().artifacts)
