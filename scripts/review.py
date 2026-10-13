import html
import json
import os
from pathlib import Path
from urllib.parse import quote
from core import read, save, shots, fingerprint, now, resolve, digest


def build(p, stage):
    if stage not in ('image', 'video'):
        raise ValueError('评审页只支持image或video')
    items = []
    cards = []
    for s in shots(p):
        media = resolve(p, s[stage])
        fp = fingerprint(p, s, stage)
        items.append({'id': s['id'], 'fingerprint': fp, 'status': 'pending', 'comment': ''})
        url = quote('../' + media.relative_to(p).as_posix(), safe='/')
        tag = f'<img src="{url}" alt="{html.escape(s["id"])}">' if stage == 'image' else f'<video src="{url}" controls preload="metadata" playsinline></video>'
        text = '\n'.join(str(s.get(k, '')) for k in ('design', 'line', 'prompt'))
        cards.append(f'<article data-id="{s["id"]}"><h2>{s["id"]}</h2>{tag}<pre>{html.escape(text)}</pre>'
                     '<select><option value="pending">待审</option><option value="approved">通过</option>'
                     '<option value="changes">需修改</option></select><textarea placeholder="写具体意见"></textarea></article>')
    report = {'project': p.name, 'stage': stage, 'items': items}
    version = digest(report)[:12]
    report['version'] = version
    data = json.dumps(report, ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>逐镜评审</title><style>body{background:#16211d;color:#edf2eb;font:16px/1.7 sans-serif;margin:24px}header{position:sticky;top:0;background:#16211d;padding:12px;z-index:2}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:20px}article{background:#27372d;padding:18px;border-radius:10px}img,video{width:100%;max-height:60vh;object-fit:contain}pre{white-space:pre-wrap;font:inherit;font-size:14px}textarea{width:100%;height:100px}button,select{font:inherit;padding:8px}p{color:#bbcbbb}</style>
<header><h1>逐镜评审</h1><p>意见自动保存在本浏览器。完成后点“导出意见”，把JSON交给agent；单纯关闭页面不会传回意见。</p><button id="export">导出意见</button> <label>视频试听速度 <select id="rate"><option>1</option><option>1.1</option><option>1.15</option><option>1.2</option></select></label><span id="notice"></span></header><main>'''+''.join(cards)+'''</main><script>
const report=DATA;const key='review:'+report.project+':'+report.stage+':'+report.version;
try{const saved=JSON.parse(localStorage.getItem(key));if(saved&&saved.version===report.version)report.items=saved.items}catch{}
function persist(){try{localStorage.setItem(key,JSON.stringify(report))}catch{document.querySelector('#notice').textContent='本地保存不可用，请及时导出'}}
for(const item of report.items){const el=document.querySelector(`[data-id="${item.id}"]`),sel=el.querySelector('select'),txt=el.querySelector('textarea');sel.value=item.status;txt.value=item.comment;sel.onchange=()=>{item.status=sel.value;persist()};txt.oninput=()=>{item.comment=txt.value;persist()}}
document.querySelector('#rate').onchange=e=>{document.querySelectorAll('video').forEach(v=>{v.playbackRate=Number(e.target.value);v.preservesPitch=true})};
document.querySelector('#export').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));a.download=report.project+'-'+report.stage+'-'+report.version+'-意见.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
</script>'''.replace('DATA', data)
    out = p / 'reviews' / f'{stage}-{version}.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, 'utf8')
    save(out.with_suffix('.json'), report)
    return out


def import_review(p, file):
    report = read(file)
    if report['project'] != p.name or report['stage'] not in ('image', 'video'):
        raise ValueError('评审项目或阶段不匹配')
    rows = {s['id']: s for s in shots(p)}
    items = report['items']
    if len({x['id'] for x in items}) != len(items):
        raise ValueError('评审镜号重复')
    # Validate the entire export before mutating any approvals.
    for x in items:
        if x['id'] not in rows or x['fingerprint'] != fingerprint(p, rows[x['id']], report['stage']):
            raise ValueError('旧版意见不能应用到新版素材：' + x['id'])
        if x['status'] not in ('pending', 'approved', 'changes'):
            raise ValueError('未知评审状态')
    data = read(p / 'approvals.json')
    for x in items:
        data.setdefault(report['stage'], {})[x['id']] = dict(x, evidence=Path(file).name, at=now())
    save(p / 'approvals.json', data)
    save(p / 'reviews' / ('import-' + digest(report)[:16] + '.json'), report)
