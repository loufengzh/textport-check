import unittest
from textport_check.core import analyze, inspect, evaluate, PROFILES


class ByteTests(unittest.TestCase):
    def check(self, data, profile, status, code):
        result = evaluate(inspect(data), profile)
        self.assertEqual((result['status'], result['diagnostic_id']), (status, code))

    def test_ascii(self):
        for p in ('powershell51-script', 'utf8-no-bom'):
            self.assertEqual(evaluate(inspect(b'hello'), p)['status'], 'compatible')

    def test_multilingual(self):
        for text in ('你好', 'Привет', 'Grüße', '🙂'):
            data = text.encode()
            self.check(data, 'powershell51-script', 'incompatible', 'TPC201')
            self.check(b'\xef\xbb\xbf' + data, 'powershell51-script', 'compatible', 'TPC200')
            self.check(data, 'utf8-no-bom', 'compatible', 'TPC100')
            self.check(b'\xef\xbb\xbf' + data, 'utf8-no-bom', 'incompatible', 'TPC101')

    def test_bom_variants(self):
        for codec, bom in [('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff'), ('utf-32-le', b'\xff\xfe\0\0'), ('utf-32-be', b'\0\0\xfe\xff')]:
            data = bom + '你好'.encode(codec)
            facts = inspect(data)
            self.assertEqual(facts['bom'], codec)
            self.assertTrue(facts['valid_encoding'])
            self.check(data, 'powershell51-script', 'unknown', 'TPC205')

    def test_malformed(self):
        for data, offset in [(b'a\xff', 1), (b'a\xe2\x82', 1), (b'\xef\xbb\xbf\xff', 3), (b'\xff\xfe\x00', 2), (b'\0\0\xfe\xff\x00', 4)]:
            self.assertEqual(inspect(data)['invalid_byte_offset'], offset)
        self.check(b'\xff', 'powershell51-script', 'unknown', 'TPC203')
        self.check(b'\xef\xbb\xbf\xff', 'powershell51-script', 'incompatible', 'TPC203')

    def test_empty_and_nul(self):
        self.check(b'', 'utf8-no-bom', 'compatible', 'TPC100')
        self.check(b'\0', 'utf8-no-bom', 'compatible', 'TPC100')
        self.check(b'\0', 'powershell51-script', 'unknown', 'TPC204')
        self.check(b'', 'posix-direct-script', 'incompatible', 'TPC302')

    def test_shebang(self):
        p = 'posix-direct-script'
        self.check(b'#!/bin/sh\necho ok\n', p, 'compatible', 'TPC300')
        self.check(b'\xef\xbb\xbf#!/bin/sh\n', p, 'incompatible', 'TPC301')
        self.check(b'#!/bin/sh\r\n', p, 'incompatible', 'TPC303')
        for data in (b'#!/bin/sh', b'#! \n', '#!/路径\n'.encode()):
            self.check(data, p, 'unknown', 'TPC304')
        self.check(b'#!/bin/sh\n\0', p, 'unknown', 'TPC305')
        self.check(b'#!/bin/sh\n\xff', p, 'unknown', 'TPC306')

    def test_conflicts(self):
        self.assertEqual(analyze('你好'.encode(), list(PROFILES))['conflicts'][0]['diagnostic_id'], 'TPC400')
        self.assertEqual(analyze(b'#!/bin/sh\n', list(PROFILES))['conflicts'], [])
        self.assertEqual(analyze(b'\xff', list(PROFILES))['conflicts'], [])
        self.assertEqual(analyze(b'\xef\xbb\xbfhello', list(PROFILES))['conflicts'], [])

    def test_profile_sort_and_unique(self):
        report = analyze(b'hello', ['utf8-no-bom', 'powershell51-script', 'utf8-no-bom'])
        self.assertEqual([r['profile'] for r in report['results']], ['powershell51-script', 'utf8-no-bom'])
