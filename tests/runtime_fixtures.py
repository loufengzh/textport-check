"""Execute only our generated, fixed, benign fixtures. Never user inputs."""
import errno
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        if os.name == 'nt':
            powershell = shutil.which('powershell.exe')
            assert powershell, 'Windows PowerShell 5.1 is required'
            version = subprocess.check_output([powershell, '-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()'], text=True).strip()
            assert version.startswith('5.1.'), version
            # Compare code points via ASCII output to avoid console encoding effects.
            source = '$s = "你好ПриветGrüße"; (($s.ToCharArray() | ForEach-Object { [int]$_ }) -join ",")\r\n'
            expected = ','.join(str(ord(c)) for c in '你好ПриветGrüße')
            for name, data, answer in [('ascii.ps1', b'Write-Output "ascii-ok"\r\n', 'ascii-ok'), ('unicode.ps1', b'\xef\xbb\xbf' + source.encode('utf-8'), expected)]:
                path = root / name
                path.write_bytes(data)
                result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(path)], capture_output=True, text=True, timeout=20)
                assert result.returncode == 0, result.stderr
                assert result.stdout.strip() == answer, result.stdout
            # BOM-less behavior depends on system ANSI code page; record, do not
            # assume the machine cannot use UTF-8 as its configured code page.
            path = root / 'no-bom.ps1'
            path.write_bytes(source.encode())
            result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(path)], capture_output=True, text=True, timeout=20)
            print('PowerShell', version, 'BOM-less non-ASCII preserved:', result.returncode == 0 and result.stdout.strip() == expected)
            print('PASS: native Windows PowerShell 5.1 ASCII and multilingual UTF-8 BOM fixtures')
        else:
            for name, data, works in [('lf', b'#!/bin/sh\nprintf "fixture-ok\\n"\n', True), ('bom', b'\xef\xbb\xbf#!/bin/sh\nprintf "fixture-ok\\n"\n', False), ('crlf', b'#!/bin/sh\r\nprintf "fixture-ok\\n"\n', False)]:
                path = root / name
                path.write_bytes(data)
                path.chmod(0o700)
                try:
                    result = subprocess.run([str(path)], capture_output=True, timeout=10, check=False)
                except OSError as exc:
                    assert not works and exc.errno in (errno.ENOEXEC, errno.ENOENT), exc
                else:
                    assert works and result.returncode == 0 and result.stdout == b'fixture-ok\n', result
            print('PASS: native direct Linux shebang LF/BOM/CRLF fixtures (no shell fallback)')


if __name__ == '__main__':
    main()
