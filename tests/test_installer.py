import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest

import install


def write_minimal_asar(path, package=None):
    package = package or {'name': 'openai-codex-electron', 'version': 'test'}
    data = json.dumps(package, separators=(',', ':')).encode()
    header = {'files': {'package.json': {'size': len(data), 'offset': '0'}}}
    raw = json.dumps(header, separators=(',', ':')).encode()
    payload = struct.pack('<I', len(raw)) + raw
    payload += b'\0' * ((-len(payload)) % 4)
    pickle = struct.pack('<I', len(payload)) + payload
    path.write_bytes(struct.pack('<II', 4, len(pickle)) + pickle + data)
    return hashlib.sha256(raw).hexdigest()


class InstallerTests(unittest.TestCase):
    def test_distribution_checksums(self):
        self.assertIn('install.py', install.verify_bundle())

    def test_asar_header_hash_matches_electron_integrity_value(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'app.asar'
            expected = write_minimal_asar(path)
            self.assertEqual(install.asar_header_sha(path), expected)
            self.assertEqual(json.loads(install.Asar(path).read('package.json'))['version'], 'test')

    def test_runtime_placeholders_are_bound_for_every_build(self):
        for spec in install.BUILD_SPECS:
            with self.subTest(spec=spec['id']):
                loader = install.render_runtime('animation-loader.js', spec)
                runtime = install.render_runtime('animation-runtime.js', spec)
                self.assertNotIn('__NF_', loader + runtime)
                self.assertIn(spec['safe_join'] + '(platform, directory', loader)
                self.assertIn(spec['react'] + '.createElement', runtime)
        linux = install.BUILD_SPECS[0]
        self.assertEqual(
            hashlib.sha256(install.render_runtime('animation-loader.js', linux).encode()).hexdigest(),
            '0ac19d05d0ff8edafedb990f6c2ddb65ec4aa41594a54bd11cdb6aa7d3c6907f')
        self.assertEqual(
            hashlib.sha256(install.render_runtime('animation-runtime.js', linux).encode()).hexdigest(),
            'cb68e4ee77c4bca3c4e9a58105b08a6f54749add51bcae6e8b5f109c688b90bf')

    def test_specs_are_platform_and_fingerprint_specific(self):
        for spec in install.BUILD_SPECS:
            with self.subTest(spec=spec['id']):
                self.assertIs(install.spec_for(spec['version'], spec['original'], spec['platform']), spec)
                other = 'darwin' if spec['platform'] == 'linux' else 'linux'
                self.assertIsNone(install.spec_for(spec['version'], spec['original'], other))
                self.assertIsNone(install.spec_for(spec['version'], '0' * 64, spec['platform']))

    def test_mac_integrity_update_and_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / 'ChatGPT Test.app'
            resources = bundle / 'Contents/Resources'
            resources.mkdir(parents=True)
            asar = resources / 'app.asar'
            expected = write_minimal_asar(asar)
            plist_path = bundle / 'Contents/Info.plist'
            with plist_path.open('wb') as stream:
                plistlib.dump({
                    'CFBundleDisplayName': 'ChatGPT',
                    'ElectronAsarIntegrity': {'Resources/app.asar': {'algorithm': 'SHA256', 'hash': 'old'}},
                }, stream)
            actual = install.update_mac_integrity(bundle, 'ChatGPT 奶蛙')
            self.assertEqual(actual, expected)
            self.assertTrue(install.verify_mac_bundle(bundle, install.sha(asar), expected,
                                                       verify_signature=False))
            with plist_path.open('rb') as stream:
                updated = plistlib.load(stream)
            self.assertEqual(updated['CFBundleDisplayName'], 'ChatGPT 奶蛙')

    def test_mac_bundle_paths_fail_closed(self):
        good = Path('/Applications/ChatGPT.app/Contents/Resources/app.asar')
        self.assertEqual(install.mac_bundle_for_asar(good), Path('/Applications/ChatGPT.app'))
        with self.assertRaises(install.InstallError):
            install.mac_bundle_for_asar(Path('/tmp/app.asar'))
        with self.assertRaises(install.InstallError):
            install.mac_target_path(Path('/Applications/ChatGPT.app'),
                                    '/Applications/ChatGPT.app')

    @unittest.skipUnless(os.environ.get('NAIFROG_TEST_MAC_APP'),
                         'set NAIFROG_TEST_MAC_APP to exercise a real supported macOS app')
    def test_real_mac_fixture_rebuild_is_deterministic(self):
        source = install.app_asar(os.environ['NAIFROG_TEST_MAC_APP'])
        report = install.inspect(source, 'darwin')
        self.assertTrue(report['supported'])
        self.assertFalse(report['alreadyPatched'])
        spec = next(item for item in install.BUILD_SPECS if item['id'] == report['build'])
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / 'first.asar'
            second = Path(folder) / 'second.asar'
            install.build_archive(source, first, spec)
            install.build_archive(source, second, spec)
            self.assertEqual(install.sha(first), spec['patched'])
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == '__main__':
    unittest.main()
