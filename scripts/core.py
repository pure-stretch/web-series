"""Small cross-platform primitives; every persistent path is project-relative."""
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        name = f.name
    os.replace(name, path)


def ident(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value):
        raise ValueError('ID只能包含字母数字、下划线和短横线')
    return value


def resolve(base, relative):
    base = Path(base).resolve()
    if not relative or Path(relative).is_absolute() or '\\' in relative or ':' in relative:
        raise ValueError('请使用项目内相对路径和正斜杠')
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError('路径超出项目目录')
    return path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def number(value, low, high):
    n = float(value)
    if not math.isfinite(n) or not low <= n <= high:
        raise ValueError(f'数值应在 {low} 至 {high} 内')
    return n


def project(name):
    p = ROOT / 'projects' / ident(name)
    read(p / 'project.json')
    return p


def shots(p):
    rows = read(p / 'shots.json')
    ids = [ident(s['id']) for s in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('镜号重复')
    return rows


def fingerprint(p, shot, stage):
    if stage == 'image':
        return digest({'id': shot['id'], 'image': sha(resolve(p, shot['image'])),
                       'last_image': sha(resolve(p, shot['last_image'])) if shot.get('last_image') else None,
                       'design': shot.get('design', ''), 'line': shot.get('line', '')})
    if stage == 'generation':
        cfg = read(p / 'project.json')['video']
        return digest({'shot': shot, 'image': fingerprint(p, shot, 'image'), 'video_config': cfg})
    if stage == 'video':
        return digest({'id': shot['id'], 'video': sha(resolve(p, shot['video'])),
                       'line': shot.get('line', '')})
    raise ValueError('stage需为image、generation或video')


def approved(p, shot, stage):
    data = read(p / 'approvals.json')
    entry = data.get(stage, {}).get(shot['id'], {})
    return entry.get('fingerprint') == fingerprint(p, shot, stage) and entry.get('status') == 'approved'


def approve(p, ids, stage, evidence):
    if not evidence.strip():
        raise ValueError('必须记录用户原话或评审文件依据，不能自批')
    rows = {s['id']: s for s in shots(p)}
    if not set(ids) <= rows.keys():
        raise ValueError('不存在的镜号')
    data = read(p / 'approvals.json')
    for key in ids:
        data.setdefault(stage, {})[key] = {'fingerprint': fingerprint(p, rows[key], stage),
            'status': 'approved', 'evidence': evidence, 'at': now()}
    save(p / 'approvals.json', data)


def env_key():
    key = os.environ.get('ATLASCLOUD_API_KEY', '').strip()
    if not key and (ROOT / '.env').exists():
        for line in (ROOT / '.env').read_text('utf-8-sig').splitlines():
            if line.strip().startswith('ATLASCLOUD_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('\"\'')
    if not key:
        raise ValueError('未配置ATLASCLOUD_API_KEY；请填本地.env或环境变量')
    return key
