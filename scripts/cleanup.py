"""Scoped scratch-file lifecycle. This helper is NOT an OS security boundary."""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid

MARKER = '{"format": "safe-ai-cleanup-v1"}\n'
RETENTION = 7 * 86400


def plain(path, directory=False):
    s = path.lstat()
    if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024:
        raise ValueError(f'Link/reparse point refused: {path}')
    if directory != stat.S_ISDIR(s.st_mode):
        raise ValueError(f'Unexpected file type: {path}')
    if not directory and (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1):
        raise ValueError(f'Nonregular or hard-linked file refused: {path}')


def absolute(path):
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts or str(p).startswith(('\\\\', '//')):
        raise ValueError('Use an absolute local path without parent traversal')
    for parent in reversed((p, *p.parents)):
        plain(parent, True)
    return p


def write_json(path, obj):
    if os.path.lexists(path):
        plain(path)
    # Exclusive temporary file and atomic replace prevent partial manifests.
    temp = path.with_name('state-new.json')
    with temp.open('x', encoding='utf-8') as f:
        json.dump(obj, f)
    os.replace(temp, path)


def record(root, token):
    if not re.fullmatch('[0-9a-f]{32}', token):
        raise ValueError('Invalid artifact ID')
    folder = root / token
    plain(folder, True)
    if {p.name for p in folder.iterdir()} != {'state.json', 'payload'}:
        raise ValueError('Unexpected artifact contents; preserve for manual review')
    plain(folder / 'state.json')
    plain(folder / 'payload')
    data = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
    if data['status'] not in ('active', 'released', 'quarantined'):
        raise ValueError('Invalid lifecycle state')
    if data['status'] == 'quarantined':
        stamp = data['quarantined_at']
        if not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or stamp < 0 or stamp > time.time():
            raise ValueError('Invalid quarantine timestamp')
    digest = hashlib.sha256((folder / 'payload').read_bytes()).hexdigest()
    if digest != data['sha256']:
        raise ValueError('Content changed; preserve for manual review')
    return folder, data


def run(args):
    policy_path = Path(__file__).parent.parent / 'references' / 'cleanup-policy.json'
    plain(policy_path)
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    if policy.get('format') != 'safe-ai-cleanup-policy-v1' or not isinstance(policy.get('allowed_projects'), list):
        raise ValueError('Invalid cleanup policy')
    # No CLI override: enrollment is an administrator/user policy edit.
    allowed = policy['allowed_projects']
    if not all(isinstance(p, str) and Path(p).is_absolute() and '..' not in Path(p).parts for p in allowed):
        raise ValueError('Invalid allowed project path')
    if os.path.normcase(str(Path(args.project))) not in {os.path.normcase(str(Path(p))) for p in allowed}:
        raise ValueError('Project is not enrolled in the cleanup policy')
    project = absolute(args.project)
    root = project / '.ai-scratch'
    if args.command == 'init':
        # Never adopt an existing directory, even if it looks temporary.
        root.mkdir()
        (root / 'scope.json').write_text(MARKER, encoding='utf-8')
        print(f'Enabled scratch lifecycle at {root}; OS isolation is separate.')
        return
    absolute(str(root))
    plain(root / 'scope.json')
    if (root / 'scope.json').read_text(encoding='utf-8') != MARKER:
        raise ValueError('Missing or invalid scope marker')
    lock = root / '.lock'
    lock.mkdir()  # Fail closed on concurrent operations or a stale lock.
    try:
        audit = root / 'audit.jsonl'
        if os.path.lexists(audit):
            plain(audit)
        def log(action, token):
            with audit.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'time': time.time(), 'action': action, 'id': token}) + '\n')
        if args.command == 'create':
            if not args.reason.strip():
                raise ValueError('A disposable-file purpose is required')
            content = sys.stdin.buffer.read()
            if args.base64:
                content = base64.b64decode(content, validate=True)
            token = uuid.uuid4().hex
            folder = root / token
            folder.mkdir()
            (folder / 'payload').write_bytes(content)
            write_json(folder / 'state.json', {'status': 'active', 'reason': args.reason,
                       'sha256': hashlib.sha256(content).hexdigest()})
            log('create', token)
            print(json.dumps({'id': token, 'path': str(folder / 'payload')}))
        elif args.command == 'preview':
            for folder in root.iterdir():
                if not re.fullmatch('[0-9a-f]{32}', folder.name):
                    continue
                try:
                    _, data = record(root, folder.name)
                    print(json.dumps({'id': folder.name, **data}))
                except (ValueError, OSError, KeyError, TypeError) as e:
                    print(json.dumps({'id': folder.name, 'preserved': str(e)}))
        else:
            folder, data = record(root, args.id)
            action = args.command
            if action == 'release':
                if data['status'] != 'active':
                    raise ValueError('Only active artifacts can be released')
                data['status'] = 'released'
            elif action == 'quarantine':
                if data['status'] != 'released':
                    raise ValueError('Release only after all consumers have finished')
                data.update(status='quarantined', quarantined_at=time.time())
            elif action == 'restore':
                if data['status'] != 'quarantined':
                    raise ValueError('Only quarantined artifacts can be restored')
                data['status'] = 'active'
                data.pop('quarantined_at', None)
            elif action == 'purge':
                if data['status'] != 'quarantined' or time.time() - data['quarantined_at'] < RETENTION:
                    raise ValueError('Purge requires at least seven days in quarantine')
                # Revalidate immediately; no recursive deletion and no wildcard targets.
                record(root, args.id)
                log('purge-intent', args.id)
                (folder / 'payload').unlink()
                (folder / 'state.json').unlink()
                folder.rmdir()
                log('purged', args.id)
                print(f'Purged {args.id}')
                return
            write_json(folder / 'state.json', data)
            log(action, args.id)
            print(f'{action}: {args.id}')
    finally:
        lock.rmdir()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', required=True)
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('init', 'preview'):
        sub.add_parser(command)
    create = sub.add_parser('create')
    create.add_argument('--reason', required=True)
    create.add_argument('--base64', action='store_true')
    for command in ('release', 'quarantine', 'restore', 'purge'):
        sub.add_parser(command).add_argument('id')
    try:
        run(p.parse_args())
    except (OSError, ValueError, KeyError, TypeError) as e:
        p.exit(1, f'Refused: {e}\n')


if __name__ == '__main__':
    main()
