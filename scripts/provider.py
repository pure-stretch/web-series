"""Atlas adapter: persist intent before POST, never silently resubmit."""
import base64
import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from core import read, save, now, resolve, fingerprint, approved, shots, env_key, number

BASE = 'https://api.atlascloud.ai'


def request(method, path, body=None):
    key = env_key()
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            result = json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'供应商HTTP {e.code}；查看控制台，日志不保存响应正文') from None
    except (OSError, ValueError):
        raise RuntimeError('网络或响应解析失败；若是提交请求，结果未知，禁止自动重发') from None
    if result.get('code', 200) not in (0, 200):
        raise RuntimeError('供应商返回非成功状态；检查控制台')
    return result.get('data', result)


@contextmanager
def lock(p):
    path = p / 'tasks' / 'submit.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x') as f:
            f.write(f'pid={os.getpid()} at={now()}')
    except FileExistsError:
        raise ValueError('有提交锁：先检查另一进程是否仍运行；崩溃后核对任务再手动移走锁') from None
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def plan(p, ids):
    cfg = read(p / 'project.json')['video']
    if cfg.get('provider') != 'atlas' or cfg.get('model') != 'bytedance/seedance-2.0-mini/image-to-video':
        raise ValueError('当前适配器仅验证Atlas Mini；其他模型先核实参数并扩展适配器')
    if not cfg.get('price_checked_at'):
        raise ValueError('先核实当前价格并记录price_checked_at')
    price = Decimal(str(number(cfg['usd_per_second'], 0.000001, 100)))
    margin = Decimal(str(number(cfg.get('cost_margin', 1.3), 1, 10)))
    all_shots = {s['id']: s for s in shots(p)}
    if not ids or len(ids) != len(set(ids)) or not set(ids) <= all_shots.keys():
        raise ValueError('请指定不重复的有效镜号')
    result = []
    for key in ids:
        s = all_shots[key]
        d = number(s['duration'], 4, 15)
        if int(d) != d:
            raise ValueError('Mini时长应为4—15的整数')
        if not s.get('prompt', '').strip():
            raise ValueError('缺少独立完整的视频提示词')
        result.append({'id': key, 'fingerprint': fingerprint(p, s, 'generation'),
                       'reserve_usd': float(price * Decimal(str(d)) * margin)})
    return result


def authorize(p, ids, limit, evidence):
    if not evidence.strip():
        raise ValueError('缺少用户明确付费授权依据')
    rows = plan(p, ids)
    limit = number(limit, 0.01, 100000)
    if sum(r['reserve_usd'] for r in rows) > limit:
        raise ValueError('首轮估算已超过预算')
    for s in shots(p):
        if s['id'] in ids and (not approved(p, s, 'image') or not approved(p, s, 'generation')):
            raise ValueError(f'{s["id"]}首帧或生成方案未经最新批准')
    # Every authorization is immutable. A new authorization is a new user-approved budget.
    with lock(p):
        existing = [int(f.stem[1:]) for f in (p / 'budgets').glob('B*.json')
                    if f.stem[1:].isdigit()]
        name = f'B{max(existing, default=0)+1:04d}'
        save(p / 'budgets' / (name + '.json'), {'id': name, 'limit_usd': limit,
             'items': rows, 'evidence': evidence, 'at': now()})
    return name


def task_path(p, row):
    return p / 'tasks' / (row['id'] + '-' + row['fingerprint'] + '.json')


def image_data(p, file):
    path = resolve(p, file)
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in ('image/png', 'image/jpeg', 'image/webp') or path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError('首帧必须为PNG/JPEG/WebP且小于30MiB')
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def submit(p, budget_id):
    from core import ident
    budget = read(p / 'budgets' / (ident(budget_id) + '.json'))
    cfg = read(p / 'project.json')['video']
    current = {s['id']: s for s in shots(p)}
    with lock(p):
        for row in budget['items']:
            s = current[row['id']]
            path = task_path(p, row)
            if path.exists():
                print('SKIP existing/unknown', s['id'])
                continue
            if fingerprint(p, s, 'generation') != row['fingerprint']:
                raise ValueError('批准后输入已改动，请重新审阅当前版本')
            if not approved(p, s, 'image') or not approved(p, s, 'generation'):
                raise ValueError('首帧/生成方案批准已失效')
            used = sum(Decimal(str(read(f)['reserve_usd'])) for f in (p / 'tasks').glob('*.json')
                       if read(f).get('budget') == budget_id)
            if used + Decimal(str(row['reserve_usd'])) > Decimal(str(budget['limit_usd'])):
                raise ValueError('预算占用已满；失败/未知提交也占额度，不能自动释放')
            payload = {'model': cfg['model'], 'duration': s['duration'],
                       'resolution': cfg['resolution'], 'ratio': cfg.get('ratio', 'adaptive'),
                       'generate_audio': s.get('audio', True), 'watermark': False,
                       'prompt': s['prompt'], 'image': image_data(p, s['image'])}
            if s.get('last_image'):
                payload['last_image'] = image_data(p, s['last_image'])
            if 'seed' in s:
                payload['seed'] = s['seed']
            env_key()  # Missing key is not an unknown provider submission.
            state = dict(row, budget=budget_id, status='submitting', at=now())
            save(path, state)
            try:
                data = request('POST', '/api/v1/model/generateVideo', payload)
                task_id = str(data['id'])
                if not task_id:
                    raise ValueError('empty id')
                state.update(task_id=task_id, status='submitted')
                save(path, state)
                print('SUBMITTED', s['id'], task_id)
            except Exception:
                state['status'] = 'unknown'
                save(path, state)
                raise RuntimeError('提交结果不确定；已保留记录。去供应商控制台查任务，不能重发。') from None


def attach_task(p, path, task_id, evidence):
    state = read(path)
    if state['status'] not in ('unknown', 'submitting') or not evidence.strip():
        raise ValueError('仅可为核实后的未知提交补任务ID')
    state.update(task_id=task_id, status='submitted', reconciliation=evidence)
    save(path, state)


def poll(p):
    from media import probe
    for path in sorted((p / 'tasks').glob('*.json')):
        state = read(path)
        if state.get('status') == 'downloaded':
            if resolve(p, state['video']).exists():
                continue
        if not state.get('task_id'):
            print('UNKNOWN', state['id'])
            continue
        data = request('GET', '/api/v1/model/prediction/' + urllib.parse.quote(state['task_id'], safe=''))
        state['status'] = data.get('status', 'unknown')
        save(path, state)
        print(state['id'], state['status'])
        if state['status'] in ('completed', 'succeeded'):
            url = data['outputs'][0]
            if urllib.parse.urlparse(url).scheme != 'https':
                raise ValueError('下载地址不是HTTPS，需核实供应商输出')
            target = p / 'videos' / (path.stem + '.mp4')
            target.parent.mkdir(exist_ok=True)
            part = target.with_suffix('.part')
            # Signed output URL is used only in memory, not stored in logs/reviews.
            with urllib.request.urlopen(url, timeout=180) as src, part.open('wb') as dst:
                import shutil
                shutil.copyfileobj(src, dst)
            probe(part)
            part.replace(target)
            state.update(status='downloaded', video=target.relative_to(p).as_posix())
            save(path, state)
            print('SAVED', state['video'])
