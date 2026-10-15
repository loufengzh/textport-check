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

    def test_root_parent_components_are_checked_before_normalization(self):
        (self.root / 'a').write_bytes(b'ok')
        (self.root / 'directory').mkdir()
        # A real directory followed by '..' is supported. Missing/non-directory
        # components must not disappear merely because '..' follows them.
        valid = self.root / 'directory' / '..'
        self.assertEqual(safe_read(valid, 'a', 10), b'ok')
        self.assertEqual(self.call('--root', str(valid), '--profile', 'utf8-no-bom', 'a')[0], 0)
        for name in ('missing', 'a'):
            root = self.root / name / '..'
            with self.subTest(root=str(root)):
                with self.assertRaises((OSError, InputError)):
                    safe_read(root, 'a', 10)
                code, output, error = self.call('--root', str(root), '--profile', 'utf8-no-bom', '--format', 'json', 'a')
                self.assertEqual(code, 3)
                report = json.loads(output)
                self.assertEqual(report['summary'], {'compatible': 0, 'incompatible': 0, 'unknown': 1})
                self.assertEqual(report['files'][0]['error']['diagnostic_id'], 'TPC900')
                self.assertNotIn(str(self.root), output + error)

    def test_config_parent_components_are_checked_before_normalization(self):
        (self.root / 'a').write_bytes(b'ok')
        (self.root / 'directory').mkdir()
        config = self.root / 'check.json'
        config.write_text(json.dumps({'version': 1, 'files': [{'path': 'a', 'profiles': ['utf8-no-bom']}]}))
        self.assertEqual(self.call('--config', str(self.root / 'directory' / '..' / config.name))[0], 0)
        for name in ('missing', 'a'):
            path = self.root / name / '..' / config.name
            with self.subTest(path=str(path)):
                code, output, error = self.call('--config', str(path), '--format', 'json')
                self.assertEqual(code, 2)
                self.assertEqual(output, '')
                self.assertNotIn(str(self.root), error)

    def test_symlink_parent_cannot_audit_different_file(self):
        (self.root / 'a').write_bytes(b'ok')
        (self.root / 'actual' / 'child').mkdir(parents=True)
        (self.root / 'actual' / 'a').write_bytes(b'\xff')
        config_data = json.dumps({'version': 1, 'files': [{'path': 'a', 'profiles': ['utf8-no-bom']}]})
        (self.root / 'check.json').write_text(config_data)
        (self.root / 'actual' / 'check.json').write_text(config_data)
        try:
            (self.root / 'link').symlink_to(self.root / 'actual' / 'child', target_is_directory=True)
        except OSError:
            self.skipTest('host does not permit symlinks')
        root = self.root / 'link' / '..'
        with self.assertRaisesRegex(InputError, 'Symlinks and reparse points'):
            safe_read(root, 'a', 10)
        code, output, error = self.call('--root', str(root), '--profile', 'utf8-no-bom', 'a', '--format', 'json')
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output)['files'][0]['error']['diagnostic_id'], 'TPC900')
        self.assertNotIn(str(self.root), output + error)
        code, output, error = self.call('--config', str(root / 'check.json'), '--format', 'json')
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertNotIn(str(self.root), error)
        self.assertEqual(self.call('--root', str(self.root / 'actual'), '--profile', 'utf8-no-bom', 'a')[0], 1)

    def test_relative_parent_root_and_config_preserve_components(self):
        (self.root / 'a').write_bytes(b'ok')
        (self.root / 'directory').mkdir()
        (self.root / 'check.json').write_text(json.dumps({'version': 1, 'files': [{'path': 'a', 'profiles': ['utf8-no-bom']}]}))
        previous = Path.cwd()
        try:
            os.chdir(self.root / 'directory')
            self.assertEqual(safe_read(Path('..'), 'a', 10), b'ok')
            self.assertEqual(self.call('--root', '..', '--profile', 'utf8-no-bom', 'a')[0], 0)
            self.assertEqual(self.call('--config', str(Path('..') / 'check.json'))[0], 0)
            with self.assertRaises((OSError, InputError)):
                safe_read(Path('missing') / '..' / '..', 'a', 10)
        finally:
            os.chdir(previous)

    def test_portable_fallback_preserves_root_parent_checks(self):
        (self.root / 'a').write_bytes(b'ok')
        (self.root / 'directory').mkdir()
        with patch('textport_check.io.os.supports_dir_fd', set()):
            self.assertEqual(safe_read(self.root / 'directory' / '..', 'a', 10), b'ok')
            for name in ('missing', 'a'):
                with self.subTest(component=name), self.assertRaises((OSError, InputError)):
                    safe_read(self.root / name / '..', 'a', 10)

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
