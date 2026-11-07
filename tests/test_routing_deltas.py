import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('routing_deltas',
    Path(__file__).resolve().parents[1] / '.github/create-routing-deltas.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def release(tag, date, *assets, **flags):
    return {'tag_name': tag, 'published_at': date, 'assets': list(assets), **flags}


def asset(name, valid=True):
    return {'name': name, 'size': 100, 'digest': 'sha256:' + ('a' * 64 if valid else 'bad')}


class RoutingDeltasTest(unittest.TestCase):
    def test_previous_version_is_selected_per_region(self):
        a = asset('valhalla_tiles_bremen.tar')
        b = asset('valhalla_tiles_berlin_brandenburg.tar')
        releases = [release('tiles-20261001T000000Z', '2026-10-01', a, b),
                    release('tiles-20261101T000000Z', '2026-11-01', a),
                    release('tiles-20261102T000000Z', '2026-11-02', b, draft=True),
                    release('latest', '2026-11-03', b)]
        bases = mod.bases(releases)
        self.assertEqual(bases['bremen'][0], 'tiles-20261101T000000Z')
        self.assertEqual(bases['berlin_brandenburg'][0], 'tiles-20261001T000000Z')

    def test_unknown_digest_is_not_a_delta_base(self):
        r = release('tiles-20261101T000000Z', '2026-11-01',
                    asset('valhalla_tiles_bremen.tar', False),
                    asset('valhalla_tiles_bremen.tar.zst'))
        self.assertEqual(mod.bases([r]), {})

    def test_real_generator_with_partial_releases(self):
        encoder = os.environ.get('HDIFFZ')
        if not encoder or not Path(encoder).is_file():
            self.skipTest('Set HDIFFZ for real patch generation')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / 'old.tar'; old.write_bytes(b'a' * 50000)
            artifacts = root / 'artifacts' / 'bremen'; artifacts.mkdir(parents=True)
            target = artifacts / 'valhalla_tiles_bremen.tar'; target.write_bytes(b'a' * 25000 + b'b' * 25000)
            target.with_name(target.name + '.zst').write_bytes(b'x' * 10000)
            base = {'name': target.name, 'size': old.stat().st_size, 'digest': 'sha256:' + mod.sha256(old)}
            releases = [[release('tiles-20261001T000000Z', '2026-10-01', base)]]
            real_run = mod.subprocess.run
            def run(args, **kwargs):
                if args[:3] == ['gh', 'release', 'download']:
                    shutil.copyfile(old, Path(args[-1]) / target.name)
                    return None
                return real_run(args, **kwargs)
            with mock.patch.object(mod.subprocess, 'check_output', return_value=json.dumps(releases).encode()), \
                 mock.patch.object(mod.subprocess, 'run', side_effect=run), \
                 mock.patch.object(mod.sys, 'argv', ['generator', str(root / 'artifacts')]), \
                 mock.patch.dict(os.environ, {'PATH': str(Path(encoder).parent) + ':' + os.environ['PATH']}):
                mod.main()
            patch = artifacts / 'valhalla_tiles_bremen.from-tiles-20261001T000000Z.hdelta'
            self.assertTrue(patch.is_file())
            self.assertLess(patch.stat().st_size, 10000)

    def test_workflow_keeps_full_and_compressed_assets(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/action.yml').read_text()
        self.assertIn('artifacts/**/*.tar\n', workflow)
        self.assertIn('artifacts/**/*.tar.zst', workflow)
        self.assertIn('artifacts/**/*.hdelta', workflow)
        self.assertIn('628963bf2ee9108a97260fa5eef44acd9ec94369b76090a957c9182b3abbb558', workflow)


if __name__ == '__main__':
    unittest.main()
