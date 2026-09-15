import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PreserveDatabaseTest(unittest.TestCase):
    def test_preserves_corrupt_database_and_sidecars_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'data'
            source.mkdir()
            expected = {'digital-life.db': b'corrupt bytes',
                        'digital-life.db-wal': b'pending writes',
                        'digital-life.db-shm': b'coordination'}
            for name, data in expected.items():
                (source / name).write_bytes(data)
            target = root / 'quarantine'
            result = subprocess.run(['python3', str(ROOT / 'scripts/preserve-database.py'),
                                     str(source), str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name, data in expected.items():
                self.assertEqual((target / name).read_bytes(), data)
                self.assertEqual((source / name).read_bytes(), data)

    def test_refuses_to_overwrite_existing_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'data'
            source.mkdir()
            (source / 'digital-life.db').write_bytes(b'new')
            target = root / 'existing'
            target.mkdir()
            (target / 'digital-life.db').write_bytes(b'original')
            result = subprocess.run(['python3', str(ROOT / 'scripts/preserve-database.py'),
                                     str(source), str(target)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((target / 'digital-life.db').read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
