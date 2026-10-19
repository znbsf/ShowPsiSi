"""Fail-closed same-release source tests; tiny archive pins exist only in fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('corresponding_source', ROOT / 'scripts/ci/corresponding_source.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
REAL_PINS = copy.deepcopy(source.QT_ARCHIVES)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, indent=2).encode('utf-8')


class CorrespondingSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        self.sources = self.root / 'original-sources'
        self.sources.mkdir()
        shutil.copytree(ROOT / 'scripts/portable-licenses', self.package)
        (self.package / 'vc-runtime-pin.json').unlink(missing_ok=True)
        self.payloads = {pin['filename']: ('fixture-only original archive ' + pin['module']).encode() for pin in REAL_PINS}
        self.pins = tuple(dict(pin, bytes=len(self.payloads[pin['filename']]), sha256=sha(self.payloads[pin['filename']])) for pin in REAL_PINS)
        self.patcher = mock.patch.object(source, 'QT_ARCHIVES', self.pins)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        records = [dict(pin, url='https://download.qt.io/archive/qt/6.7/6.7.3/submodules/' + pin['filename'], publisher_checksum_verified=True) for pin in self.pins]
        for name, data in self.payloads.items():
            (self.sources / name).write_bytes(data)
        self.index = source.read_json(self.package / 'source-index.json')
        self.index['corresponding_source'] = dict(source.POLICY)
        self.index['qt_source_archives'] = records
        self.write_json('source-index.json', self.index)
        attr = source.read_json(self.package / 'licenses/qt/source-attributions.json')
        attr['archives'] = records
        self.write_json('licenses/qt/source-attributions.json', attr)
        (self.package / 'SOURCE_INFORMATION.txt').write_text(
            'Read SOURCE_DOWNLOAD.txt for the exact free same-release Qt source.\n'
            'Original archives retain Qt build scripts; use qt_build_configuration.\n')
        (self.package / 'LICENSE').write_bytes((ROOT / 'LICENSE').read_bytes())
        (self.package / 'bin').mkdir()
        (self.package / 'bin/Qt6Core.dll').write_bytes(b'unchanged fixture QtCore')
        (self.package / 'bin/showpsisi-qt.exe').write_bytes(b'fixture executable')
        config = {'mkspecs/qconfig.pri': 'QT_CONFIG += shared\nQT_VERSION = 6.7.3\n',
                  'mkspecs/qmodule.pri': 'QT.global_private.enabled_features = gui relocatable shared\n',
                  'include/QtCore/qconfig.h': '#define QT_FEATURE_shared 1\n#define QT_FEATURE_static -1\n#define QT_VERSION_STR "6.7.3"\n'}
        core = source.digest(self.package / 'bin/Qt6Core.dll')
        self.build = {'application_version': '0.3.0', 'source_commit': 'a' * 40,
                      'qt_version': '6.7.3', 'qt_source_archives': records,
                      'qt_build_configuration': {name: {'content': text, 'sha256': sha(text.encode())} for name, text in config.items()},
                      'qt_core_relocation': {'installed_kit_sha256': core, 'deployed_sha256': core}}
        self.write_json('build-information.json', self.build)
        source.stamp(self.package)
        self.build = source.read_json(self.package / 'build-information.json')
        self.review()
        self.output = self.root / source.asset_name(self.build['application_version'])

    def write_json(self, name, value):
        (self.package / name).write_bytes(encoded(value))

    def manifest(self):
        self.write_json('manifest.json', {'schema_version': 1, 'build': source.read_json(self.package / 'build-information.json'),
                                         'files': source.inventory(self.package, exclude=('manifest.json',))})

    def review(self):
        value = {'build': source.read_json(self.package / 'build-information.json'), 'files': source.inventory(self.package, exclude=('manifest.json',))}
        self.write_json('redistribution-review.json', {'schema_version': 1, 'review_complete': True,
                                                      'reviewed_files': source.review_inventory(value)})
        self.manifest()

    def archive(self):
        return source.build_archive(self.package, self.sources, self.output)

    def mutate_zip(self, changes=None, remove=(), extra=(), regenerate=False, compression=zipfile.ZIP_STORED):
        changes = changes or {}
        with zipfile.ZipFile(self.output) as archive:
            entries = {item.filename.removeprefix(source.ZIP_ROOT): archive.read(item) for item in archive.infolist()}
        for name in remove:
            del entries[name]
        entries.update(changes)
        if regenerate:
            files = {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in entries.items() if name != source.MANIFEST}
            build = source.decode_json(entries['build-information.json'])
            entries[source.MANIFEST] = encoded(source._source_manifest(build, files))
        with warnings.catch_warnings(), zipfile.ZipFile(self.output, 'w', compression=compression) as archive:
            warnings.simplefilter('ignore', UserWarning)
            for name, data in entries.items():
                archive.writestr(source.ZIP_ROOT + name, data)
            for name, data in extra:
                archive.writestr(name, data)
        self.output.with_suffix('.zip.sha256').write_text(f'{source.digest(self.output)}  {self.output.name}\n')

    def test_production_pins_are_exact_reviewed_originals(self):
        self.assertEqual(sum(pin['bytes'] for pin in REAL_PINS), 86882732)
        self.assertEqual([pin['sha256'] for pin in REAL_PINS], [
            '8ccbb9ab055205ac76632c9eeddd1ed6fc66936fc56afc2ed0fd5d9e23da3097',
            '937b70e441abf5bc4e50d44d26610e2714a28514acf3885cd36116cd610b9875',
            '40142cb71fb1e07ad612bc361b67f5d54cd9367f9979ae6b86124a064deda06b'])

    def test_asset_name_and_exact_url_contract(self):
        self.assertEqual(self.output.name, 'ShowPsiSi-0.3.0-corresponding-source.zip')
        self.assertEqual(self.build['corresponding_source']['url'],
                         'https://github.com/znbsf/ShowPsiSi/releases/download/v0.3.0/' + self.output.name)
        for version in (None, 'v0.3.0', '0.3', '00.3.0', '0.3.0-rc1', '../0.3.0'):
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                source.asset_name(version)
        for commit in ('fixture', 'A' * 40, 'a' * 39, 'a' * 40 + '/x', None):
            with self.subTest(commit=commit), self.assertRaises(RuntimeError):
                source.delivery_contract(dict(self.build, source_commit=commit))

    def test_stamping_never_rewrites_reviewed_static_materials(self):
        before = {name: (self.package / name).read_bytes() for name in ('SOURCE_INFORMATION.txt', 'source-index.json', 'redistribution-review.json')}
        source.stamp(self.package)
        for name, data in before.items():
            self.assertEqual((self.package / name).read_bytes(), data)
        self.assertIn('/tree/' + 'a' * 40, (self.package / 'SOURCE_DOWNLOAD.txt').read_text())

    def test_roundtrip_preserves_every_original_byte_and_full_review(self):
        result = self.archive()
        self.assertEqual(source.verify_archive(self.output, self.package, 'a' * 40, '0.3.0'), result)
        self.assertEqual(source.verify_archive(self.output), result)
        self.assertEqual(result['qt_source_archives'], list(self.pins))
        with zipfile.ZipFile(self.output) as archive:
            for info in archive.infolist():
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
            for name, data in self.payloads.items():
                self.assertEqual(archive.read(source.ZIP_ROOT + 'sources/' + name), data)
            for name in source.RETAINED:
                self.assertEqual(archive.read(source.ZIP_ROOT + name), (self.package / name).read_bytes())
            self.assertNotIn(source.ZIP_ROOT + 'bin/Qt6Core.dll', archive.namelist())
        review = source.read_json(self.package / 'redistribution-review.json')['reviewed_files']
        for pin in self.pins:
            self.assertEqual(review['sources/' + pin['filename']], pin['sha256'])
        self.assertFalse((self.package / 'sources').exists())
        self.assertEqual(self.output.with_suffix('.zip.sha256').read_text(), f'{source.digest(self.output)}  {self.output.name}\n')

    def test_missing_wrong_and_extra_source_inputs_fail_before_output(self):
        target = self.sources / self.pins[0]['filename']
        original = target.read_bytes()
        for data in (None, b'wrong original source'):
            with self.subTest(data=data):
                if data is None:
                    target.unlink()
                else:
                    target.write_bytes(data)
                with self.assertRaisesRegex(RuntimeError, 'input set/bytes/hash'):
                    self.archive()
                self.assertFalse(self.output.exists())
                target.write_bytes(original)
        (self.sources / 'unreviewed.tar.xz').write_bytes(b'extra')
        with self.assertRaisesRegex(RuntimeError, 'input set/bytes/hash'):
            self.archive()

    def test_wrong_inner_source_rejected_after_all_outer_hashes_regenerated(self):
        self.archive()
        self.mutate_zip({'sources/' + self.pins[0]['filename']: b'wrong archive'}, regenerate=True)
        with self.assertRaisesRegex(RuntimeError, 'Reviewed source/notice|Pinned Qt source'):
            source.verify_archive(self.output, self.package)

    def test_wrong_inner_source_and_forged_review_cannot_override_pins(self):
        self.archive()
        name = 'sources/' + self.pins[0]['filename']
        review = source.read_json(self.package / 'redistribution-review.json')
        review['reviewed_files'][name] = sha(b'wrong archive')
        self.mutate_zip({name: b'wrong archive', 'redistribution-review.json': encoded(review)}, regenerate=True)
        with self.assertRaisesRegex(RuntimeError, 'Pinned Qt source'):
            source.verify_archive(self.output)

    def test_missing_inner_source_rejected_after_manifest_regeneration(self):
        self.archive()
        self.mutate_zip(remove=['sources/' + self.pins[0]['filename']], regenerate=True)
        with self.assertRaisesRegex(RuntimeError, 'Reviewed source/notice'):
            source.verify_archive(self.output)

    def test_wrong_archive_source_record_rejected_even_when_outer_manifest_matches(self):
        self.archive()
        build = copy.deepcopy(self.build)
        build['qt_source_archives'][0]['sha256'] = 'f' * 64
        self.mutate_zip({'build-information.json': encoded(build)}, regenerate=True)
        with self.assertRaisesRegex(RuntimeError, 'reviewed pins'):
            source.verify_archive(self.output)

    def test_missing_full_license_rejected_even_when_forged_review_drops_it(self):
        self.archive()
        name = 'licenses/qt/qtbase/LICENSES/LGPL-3.0-only.txt'
        review = source.read_json(self.package / 'redistribution-review.json')
        del review['reviewed_files'][name]
        self.mutate_zip({'redistribution-review.json': encoded(review)}, remove=[name], regenerate=True)
        with self.assertRaisesRegex(RuntimeError, 'Required full Qt license'):
            source.verify_archive(self.output)

    def test_missing_source_family_notice_rejected_even_when_forged_review_drops_it(self):
        self.archive()
        name = 'licenses/qt/qtbase/src/3rdparty/zlib/LICENSE'
        review = source.read_json(self.package / 'redistribution-review.json')
        del review['reviewed_files'][name]
        self.mutate_zip({'redistribution-review.json': encoded(review)}, remove=[name], regenerate=True)
        with self.assertRaisesRegex(RuntimeError, 'source-family notice'):
            source.verify_archive(self.output)

    def test_non_source_payload_is_rejected_even_with_regenerated_manifest(self):
        self.archive()
        self.mutate_zip({'bin/unreviewed.dll': b'bad'}, regenerate=True)
        with self.assertRaisesRegex(RuntimeError, 'Unexpected or missing'):
            source.verify_archive(self.output)

    def test_version_and_commit_must_match_paired_request(self):
        self.archive()
        for kwargs in ({'expected_source': 'b' * 40}, {'expected_version': '0.4.0'}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(RuntimeError, 'differs from binary/request'):
                source.verify_archive(self.output, **kwargs)

    def test_separately_valid_source_for_other_commit_cannot_pair(self):
        self.archive()
        build = copy.deepcopy(self.build)
        build['source_commit'] = 'b' * 40
        build['corresponding_source'] = source.delivery_contract(build)
        self.mutate_zip({'build-information.json': encoded(build),
                         'SOURCE_DOWNLOAD.txt': source.download_information(build).encode()}, regenerate=True)
        self.assertEqual(source.verify_archive(self.output)['source_commit'], 'b' * 40)
        with self.assertRaisesRegex(RuntimeError, 'Paired source/binary build identity'):
            source.verify_archive(self.output, self.package)

    def test_paired_metadata_compares_exact_bytes_not_only_json_values(self):
        self.archive()
        data = json.dumps(self.build, separators=(',', ':')).encode()
        self.mutate_zip({'build-information.json': data}, regenerate=True)
        self.assertTrue(source.verify_archive(self.output))
        with self.assertRaisesRegex(RuntimeError, 'Paired source/binary material'):
            source.verify_archive(self.output, self.package)

    def test_build_feature_content_hash_and_shared_mechanism_are_required(self):
        for mutation in ('hash', 'missing', 'static', 'relocatable', 'version', 'patch'):
            with self.subTest(mutation=mutation):
                build = copy.deepcopy(self.build)
                if mutation == 'hash':
                    build['qt_build_configuration']['mkspecs/qconfig.pri']['content'] += 'tampered'
                elif mutation == 'missing':
                    del build['qt_build_configuration']['mkspecs/qconfig.pri']
                elif mutation == 'patch':
                    build['qt_source_patches'] = ['local.patch']
                else:
                    name = 'mkspecs/qmodule.pri' if mutation == 'relocatable' else 'include/QtCore/qconfig.h'
                    text = build['qt_build_configuration'][name]['content']
                    text = text.replace('relocatable', 'fixed') if mutation == 'relocatable' else text.replace('QT_FEATURE_shared 1', 'QT_FEATURE_shared -1') if mutation == 'static' else text.replace('6.7.3', '6.8.0')
                    build['qt_build_configuration'][name] = {'content': text, 'sha256': sha(text.encode())}
                with self.assertRaises(RuntimeError):
                    source.validate_build(build)

    def test_unmodified_qtcore_binding_is_required(self):
        build = copy.deepcopy(self.build)
        build['qt_core_relocation']['installed_kit_sha256'] = 'f' * 64
        with self.assertRaisesRegex(RuntimeError, 'QtCore was modified'):
            source.validate_build(build)
        (self.package / 'bin/Qt6Core.dll').write_bytes(b'changed')
        self.manifest()
        with self.assertRaisesRegex(RuntimeError, 'redistribution inventory mismatch'):
            source.validate_package(self.package)

    def test_wrong_source_link_cannot_be_silently_repointed(self):
        for key, value in (('url', 'https://example.org/source.zip'), ('filename', '../source.zip'),
                           ('source_commit', 'b' * 40), ('application_version', '0.4.0')):
            with self.subTest(key=key):
                build = copy.deepcopy(self.build)
                build['corresponding_source'][key] = value
                with self.assertRaisesRegex(RuntimeError, 'declaration mismatch'):
                    source.validate_build(build)
        (self.package / 'SOURCE_DOWNLOAD.txt').write_text('See latest sources online')
        self.manifest()
        with self.assertRaisesRegex(RuntimeError, 'download information mismatch'):
            source.validate_package(self.package)

    def test_static_notice_must_point_to_generated_exact_download_information(self):
        (self.package / 'SOURCE_INFORMATION.txt').write_text('Use upstream Qt sources')
        with self.assertRaisesRegex(RuntimeError, 'download directions'):
            source.validate_metadata(self.package)

    def test_review_switch_and_any_inventory_reduction_fail_closed(self):
        review = source.read_json(self.package / 'redistribution-review.json')
        review['review_complete'] = False
        self.write_json('redistribution-review.json', review)
        self.manifest()
        with self.assertRaisesRegex(RuntimeError, 'review is incomplete'):
            self.archive()
        review['review_complete'] = True
        del review['reviewed_files']['sources/' + self.pins[0]['filename']]
        self.write_json('redistribution-review.json', review)
        self.manifest()
        with self.assertRaisesRegex(RuntimeError, 'Pinned Qt source'):
            self.archive()

    def test_binary_with_embedded_sources_cannot_claim_sidecar_layout(self):
        (self.package / 'sources').mkdir()
        (self.package / 'sources' / self.pins[0]['filename']).write_bytes(self.payloads[self.pins[0]['filename']])
        self.manifest()
        with self.assertRaisesRegex(RuntimeError, 'must not embed'):
            source.validate_package(self.package)

    def test_manifest_tampering_and_stale_package_fail(self):
        (self.package / 'LICENSE').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'manifest/build mismatch'):
            self.archive()

    def test_no_overwrite_and_output_outside_inputs(self):
        self.output.write_bytes(b'preserve me')
        with self.assertRaisesRegex(RuntimeError, 'existing/stale'):
            self.archive()
        self.assertEqual(self.output.read_bytes(), b'preserve me')
        for directory in (self.package, self.sources):
            with self.subTest(directory=directory), self.assertRaisesRegex(RuntimeError, 'outside input'):
                source.build_archive(self.package, self.sources, directory / self.output.name)

    def test_wrong_filename_is_rejected_for_build_and_verify(self):
        wrong = self.root / 'ShowPsiSi-0.4.0-corresponding-source.zip'
        with self.assertRaisesRegex(RuntimeError, 'filename/version mismatch'):
            source.build_archive(self.package, self.sources, wrong)
        self.archive()
        self.output.rename(wrong)
        with self.assertRaisesRegex(RuntimeError, 'filename/version mismatch'):
            source.verify_archive(wrong)

    def test_duplicate_and_case_alias_zip_members_are_rejected(self):
        self.archive()
        self.mutate_zip(extra=[(source.ZIP_ROOT + 'LICENSE', b'duplicate')])
        with self.assertRaisesRegex(RuntimeError, 'Duplicate/aliased'):
            source.verify_archive(self.output)
        self.mutate_zip(extra=[(source.ZIP_ROOT + 'license', b'case alias')])
        with self.assertRaisesRegex(RuntimeError, 'Duplicate/aliased'):
            source.verify_archive(self.output)

    def test_path_traversal_absolute_ads_and_windows_aliases_are_rejected(self):
        self.archive()
        for name in ('../outside', '/absolute', 'a//b', 'a/./b', 'a/../b', 'a\\b', 'C:/x', 'file:stream', 'NUL', 'CON.txt', 'tail.', 'space '):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'Unsafe source path'):
                source.safe_name(name)
        self.mutate_zip(extra=[(source.ZIP_ROOT + '../outside', b'bad')])
        with self.assertRaisesRegex(RuntimeError, 'Unsafe source path'):
            source.verify_archive(self.output)
        self.assertFalse((self.root / 'outside').exists())

    def test_symlink_archive_and_input_files_are_rejected(self):
        self.archive()
        with zipfile.ZipFile(self.output, 'a') as archive:
            info = zipfile.ZipInfo(source.ZIP_ROOT + 'link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, '/tmp/outside')
        with self.assertRaisesRegex(RuntimeError, 'Nonregular'):
            source.verify_archive(self.output)
        (self.sources / 'link').symlink_to(self.sources / self.pins[0]['filename'])
        with self.assertRaisesRegex(RuntimeError, 'Symlinks'):
            source.inventory(self.sources)

    def test_recompressed_zip_is_rejected(self):
        self.archive()
        self.mutate_zip(compression=zipfile.ZIP_DEFLATED)
        with self.assertRaisesRegex(RuntimeError, 'store unencrypted'):
            source.verify_archive(self.output)

    def test_duplicate_json_fields_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Duplicate JSON'):
            source.decode_json(b'{"schema_version":1,"schema_version":2}')
        self.archive()
        self.mutate_zip({'build-information.json': b'{"source_commit":"a","source_commit":"b"}'})
        with self.assertRaisesRegex(RuntimeError, 'Duplicate JSON'):
            source.verify_archive(self.output)

    def test_boolean_float_and_nonfinite_schema_aliases_are_rejected(self):
        for alias in (True, 1.0):
            with self.subTest(alias=alias):
                build = copy.deepcopy(self.build)
                build['corresponding_source']['schema_version'] = alias
                with self.assertRaisesRegex(RuntimeError, 'declaration mismatch'):
                    source.validate_build(build)
                index = copy.deepcopy(self.index)
                index['corresponding_source']['schema_version'] = alias
                with self.assertRaisesRegex(RuntimeError, 'policy mismatch'):
                    source._validate_metadata(self.build, index, b'SOURCE_DOWNLOAD.txt',
                                              source.download_information(self.build).encode())
        for number in ('NaN', 'Infinity', '-Infinity', '1e999', '-1e999'):
            with self.subTest(number=number), self.assertRaisesRegex(RuntimeError, 'Invalid source JSON'):
                source.decode_json(('{"schema_version":' + number + '}').encode())
        self.assertFalse(source.strict_equal({'bytes': True}, {'bytes': 1}))
        self.assertFalse(source.strict_equal({'bytes': 1.0}, {'bytes': 1}))
        self.assertFalse(source.strict_equal({'bytes': float('nan')}, {'bytes': float('nan')}))

    def test_source_manifest_schema_float_is_rejected(self):
        self.archive()
        with zipfile.ZipFile(self.output) as archive:
            manifest = source.decode_json(archive.read(source.ZIP_ROOT + source.MANIFEST))
        manifest['schema_version'] = 1.0
        self.mutate_zip({source.MANIFEST: encoded(manifest)})
        with self.assertRaisesRegex(RuntimeError, 'manifest identity/files mismatch'):
            source.verify_archive(self.output)

    def test_binary_manifest_size_and_schema_aliases_are_rejected(self):
        manifest = source.read_json(self.package / 'manifest.json')
        manifest['schema_version'] = True
        self.write_json('manifest.json', manifest)
        with self.assertRaisesRegex(RuntimeError, 'manifest/build mismatch'):
            source.validate_package(self.package)
        manifest['schema_version'] = 1
        item = manifest['files']['LICENSE']
        item['bytes'] = float(item['bytes'])
        self.write_json('manifest.json', manifest)
        with self.assertRaisesRegex(RuntimeError, 'manifest/build mismatch'):
            source.validate_package(self.package)

    def test_bounded_archive_and_metadata_sizes(self):
        self.archive()
        with mock.patch.object(source, 'MAX_TOTAL', 10), self.assertRaisesRegex(RuntimeError, 'oversized'):
            source.verify_archive(self.output)
        with mock.patch.object(source, 'MAX_FILES', 2), self.assertRaisesRegex(RuntimeError, 'member count'):
            source.verify_archive(self.output)
        with mock.patch.object(source, 'MAX_JSON', 4), self.assertRaisesRegex(RuntimeError, 'bounded size'):
            source.decode_json(b'{"abc":1}')

    def legacy(self):
        build = copy.deepcopy(self.build)
        del build['corresponding_source']
        index = copy.deepcopy(self.index)
        del index['corresponding_source']
        self.write_json('build-information.json', build)
        self.write_json('source-index.json', index)
        shutil.copytree(self.sources, self.package / 'sources')
        self.review()

    def test_legacy_requires_complete_original_bundled_sources(self):
        self.legacy()
        self.assertEqual(len(source.verify_bundled_sources(self.package)), 3)
        (self.package / 'sources' / self.pins[0]['filename']).unlink()
        self.review()
        with self.assertRaisesRegex(RuntimeError, 'Bundled source archive'):
            source.verify_bundled_sources(self.package)

    def test_sidecar_cannot_fall_back_to_legacy(self):
        with self.assertRaisesRegex(RuntimeError, 'cannot fall back'):
            source.verify_bundled_sources(self.package)

    def test_legacy_wrong_archives_cannot_be_approved_by_regenerated_review(self):
        self.legacy()
        (self.package / 'sources' / self.pins[0]['filename']).write_bytes(b'wrong')
        self.review()
        with self.assertRaisesRegex(RuntimeError, 'Bundled source archive'):
            source.verify_bundled_sources(self.package)


if __name__ == '__main__':
    unittest.main()
