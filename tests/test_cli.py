import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from textport_check.cli import main
from textport_check.io import InputError, safe_read


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_deterministic_read_only(self):
        file = self.root / '中文.ps1'
        file.write_bytes('你好'.encode())
        before = file.read_bytes(), file.stat().st_mtime_ns
        args = ('--root', str(self.root), '--profile', 'powershell51-script', '--profile', 'utf8-no-bom', '--format', 'json', file.name, './' + file.name)
        one = self.call(*args)
        self.assertEqual(one, self.call(*args))
        self.assertEqual(one[0], 1)
        doc = json.loads(one[1])
        self.assertEqual(len(doc['files']), 1)
        self.assertEqual(doc['schema_version'], 1)
        self.assertNotIn('你好', one[1])
        self.assertEqual(before, (file.read_bytes(), file.stat().st_mtime_ns))

    def test_config(self):
        (self.root / 'a').write_bytes(b'ok')
        config = self.root / 'check.json'
        config.write_text(json.dumps({'version': 1, 'files': [{'path': 'a', 'profiles': ['utf8-no-bom']}]}))
        self.assertEqual(self.call('--config', str(config))[0], 0)
        self.assertEqual(self.call('--config', str(config), '--profile', 'utf8-no-bom')[0], 2)
        config.write_text('{"version":1,"version":1,"files":[]}')
        self.assertEqual(self.call('--config', str(config))[0], 2)

    def test_bad_config(self):
        config = self.root / 'check.json'
        for data in (b'\xff', b'{}', b'[]', b'{"version":true,"files":[]}', b'{"version":1,"files":[{"path":"../x","profiles":["utf8-no-bom"]}]}'):
            config.write_bytes(data)
            self.assertEqual(self.call('--config', str(config))[0], 2)

    def test_excessive_config_nesting(self):
        config = self.root / 'deep.json'
        config.write_bytes(b'[' * 100000 + b']' * 100000)
        code, output, error = self.call('--config', str(config))
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('nesting', error)
        self.assertNotIn('Traceback', error)

    def test_paths_limits_and_missing(self):
        (self.root / 'a').write_bytes(b'xx')
        for name in ('../a', str(self.root / 'a'), r'C:a', r'\a', 'a:stream', r'..\a'):
            self.assertEqual(self.call('--root', str(self.root), '--profile', 'utf8-no-bom', name)[0], 2)
        self.assertEqual(self.call('--root', str(self.root), '--profile', 'utf8-no-bom', '--max-bytes', '1', 'a')[0], 3)
        self.assertEqual(self.call('--root', str(self.root), '--profile', 'utf8-no-bom', 'missing')[0], 3)
        self.assertEqual(self.call('--root', str(self.root), '--profile', 'utf8-no-bom', '.')[0], 3)
        self.assertEqual(self.call('--max-bytes', '0')[0], 2)
        with patch('textport_check.cli.safe_read', side_effect=PermissionError()):
            self.assertEqual(self.call('--root', str(self.root), '--profile', 'utf8-no-bom', 'a')[0], 3)

    def test_unknown_precedes_incompatible(self):
        (self.root / 'a').write_bytes(b'\xff')
        code, text, _ = self.call('--root', str(self.root), '--profile', 'utf8-no-bom', '--profile', 'powershell51-script', '--format', 'json', 'a')
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(text)['summary'], {'compatible': 0, 'incompatible': 1, 'unknown': 1})

    def test_symlink_and_parent_symlink(self):
        (self.root / 'a').write_bytes(b'ok')
        try:
            (self.root / 'link').symlink_to(self.root / 'a')
            (self.root / 'dirlink').symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest('host does not permit symlinks')
        for name in ('link', 'dirlink/a'):
            with self.assertRaises((OSError, InputError)):
                safe_read(self.root, name, 10)
        with self.assertRaises((OSError, InputError)):
            safe_read(self.root / 'dirlink', 'a', 10)

    @unittest.skipUnless(os.name == 'posix', 'POSIX FIFO only')
    def test_fifo_not_opened_blocking(self):
        os.mkfifo(self.root / 'fifo')
        with self.assertRaises(InputError):
            safe_read(self.root, 'fifo', 10)

    @unittest.skipUnless(os.name == 'posix', 'control characters in filename')
    def test_terminal_safe_filename(self):
        (self.root / '\x1b[31m').write_bytes(b'ok')
        _, output, _ = self.call('--root', str(self.root), '--profile', 'utf8-no-bom', '\x1b[31m')
        self.assertNotIn('\x1b', output)
