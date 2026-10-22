"""Run with Python 3; all mutations use a disposable test project."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).with_name('cleanup.py')


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cleanup-test-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        self.outside = Path(self.temp.name) / 'sentinel.txt'
        self.outside.write_text('KEEP')
        package = Path(self.temp.name) / 'skill'
        (package / 'scripts').mkdir(parents=True)
        (package / 'references').mkdir()
        self.script = package / 'scripts/cleanup.py'
        shutil.copyfile(SCRIPT, self.script)
        (package / 'references/cleanup-policy.json').write_text(json.dumps({
            'format': 'safe-ai-cleanup-policy-v1', 'allowed_projects': [str(self.project)]}))
        self.call('init')

    def call(self, *args, content=b'', ok=True):
        result = subprocess.run([sys.executable, '-B', str(self.script), '--project', str(self.project), *args],
                                input=content, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stderr.decode())
        self.assertEqual(self.outside.read_text(), 'KEEP')
        return result.stdout.decode()

    def create(self):
        return json.loads(self.call('create', '--reason', 'test-only scratch', content=b'TEMP'))

    def test_lifecycle_and_retention(self):
        item = self.create()
        token = item['id']
        self.call('purge', token, ok=False)
        self.call('quarantine', token, ok=False)
        self.call('release', token)
        self.call('quarantine', token)
        self.call('purge', token, ok=False)
        self.call('restore', token)
        self.assertEqual(Path(item['path']).read_bytes(), b'TEMP')
        self.call('release', token)
        self.call('quarantine', token)
        state = Path(item['path']).with_name('state.json')
        data = json.loads(state.read_text())
        data['quarantined_at'] = time.time() - 8 * 86400
        state.write_text(json.dumps(data))
        self.call('purge', token)
        self.assertFalse(Path(item['path']).parent.exists())
        self.assertIn('purged', (self.project / '.ai-scratch/audit.jsonl').read_text())

    def test_changed_or_unknown_files_preserved(self):
        item = self.create()
        Path(item['path']).write_bytes(b'USER EDIT')
        self.call('release', item['id'], ok=False)
        unknown = self.project / '.ai-scratch/notes.txt'
        unknown.write_text('KEEP')
        self.call('preview')
        self.assertEqual(unknown.read_text(), 'KEEP')
        self.call('release', '../sentinel.txt', ok=False)
        self.call('init', ok=False)

    def test_unenrolled_project_denied(self):
        other = Path(self.temp.name) / 'other'
        other.mkdir()
        result = subprocess.run([sys.executable, '-B', str(self.script), '--project', str(other), 'init'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((other / '.ai-scratch').exists())

    def test_links_extra_contents_corruption_and_lock(self):
        item = self.create()
        payload = Path(item['path'])
        payload.unlink()
        os.link(self.outside, payload)
        self.call('release', item['id'], ok=False)
        payload.unlink()
        payload.write_bytes(b'TEMP')
        extra = payload.with_name('unknown')
        extra.write_text('KEEP')
        self.call('release', item['id'], ok=False)
        extra.unlink()
        state = payload.with_name('state.json')
        state.write_text('{broken')
        self.call('release', item['id'], ok=False)
        (self.project / '.ai-scratch/.lock').mkdir()
        self.call('preview', ok=False)

    def test_windows_junction_escape(self):
        if os.name != 'nt':
            self.skipTest('Windows junction test')
        item = self.create()
        folder = Path(item['path']).parent
        Path(item['path']).unlink()
        (folder / 'state.json').unlink()
        folder.rmdir()
        result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(folder), str(self.outside.parent)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        try:
            self.call('release', item['id'], ok=False)
        finally:
            folder.rmdir()  # Remove junction itself, never its destination.


if __name__ == '__main__':
    unittest.main()
