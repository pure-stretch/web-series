#!/usr/bin/env python3
"""Run from repository root: uv run python scripts/ws.py --help."""
import argparse
import json
import platform
import shutil
import sys
from pathlib import Path
from core import ROOT, read, save, ident, resolve, project, shots, approve, sha, now
import media
import provider
import review


def doctor():
    result={'python':platform.python_version(),'os':platform.system(),'ffmpeg':shutil.which('ffmpeg'),
            'ffprobe':shutil.which('ffprobe'),'key_present':False}
    try:
        from core import env_key
        env_key();result['key_present']=True
    except ValueError:pass
    if result['ffmpeg']:
        result['subtitles_filter']='subtitles' in media.run(['ffmpeg','-hide_banner','-filters'])
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('中文字体：Windows可选Microsoft YaHei，macOS可选PingFang SC；跨机一致请安装同款Noto Sans CJK SC并填project.json。')
    if not result['ffmpeg'] or not result['ffprobe'] or not result.get('subtitles_filter'):
        raise ValueError('缺少FFmpeg/ffprobe/libass；先安装再剪辑')


def init(name,title):
    p=ROOT/'projects'/ident(name)
    if p.exists():raise ValueError('项目已存在，禁止覆盖')
    for folder in ['images','videos','edits','reviews','tasks','budgets','references','covers','publish']:
        (p/folder).mkdir(parents=True,exist_ok=True)
    for file in ['project.json','shots.json','bible.json','timeline.json','credits.json','delivery.json']:
        shutil.copy2(ROOT/'templates'/file,p/file)
    data=read(p/'project.json');data['title']=title
    if platform.system()=='Windows':data['output']['font']='Microsoft YaHei'
    elif platform.system()=='Darwin':data['output']['font']='PingFang SC'
    save(p/'project.json',data);save(p/'approvals.json',{})
    (p/'STATUS.md').write_text('# 当前制作状态\n\n阶段：1 项目建立\n已确认：无\n待确认：G1项目简报\n下一步：盘点inbox并读剧本\n','utf8')
    print(p)


def inventory(p):
    rows=[]
    for file in sorted((ROOT/'inbox').rglob('*')):
        if file.is_file() and file.name!='README.txt':
            rows.append({'path':file.relative_to(ROOT).as_posix(),'bytes':file.stat().st_size,'sha256':sha(file)})
    save(p/'inventory.json',{'at':now(),'files':rows});print(len(rows),'files')


def main():
    ap=argparse.ArgumentParser(description='网剧制作工具：所有批准必须来源于用户。')
    sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('doctor')
    q=sub.add_parser('init');q.add_argument('project');q.add_argument('--title',required=True)
    for cmd in ['inventory','validate','poll','balance']:
        q=sub.add_parser(cmd);q.add_argument('project')
    q=sub.add_parser('review');q.add_argument('project');q.add_argument('stage',choices=['image','video'])
    q=sub.add_parser('import-review');q.add_argument('project');q.add_argument('file')
    q=sub.add_parser('approve');q.add_argument('project');q.add_argument('stage',choices=['image','generation','video']);q.add_argument('ids',nargs='+');q.add_argument('--evidence',required=True)
    q=sub.add_parser('plan');q.add_argument('project');q.add_argument('ids',nargs='+')
    q=sub.add_parser('authorize');q.add_argument('project');q.add_argument('ids',nargs='+');q.add_argument('--limit',type=float,required=True);q.add_argument('--evidence',required=True)
    q=sub.add_parser('submit');q.add_argument('project');q.add_argument('budget')
    q=sub.add_parser('attach-task');q.add_argument('project');q.add_argument('record');q.add_argument('task_id');q.add_argument('--evidence',required=True)
    for cmd in ['render','card','package']:
        q=sub.add_parser(cmd);q.add_argument('project');q.add_argument('file')
    q=sub.add_parser('join');q.add_argument('project');q.add_argument('output');q.add_argument('inputs',nargs='+')
    q=sub.add_parser('inspect');q.add_argument('project');q.add_argument('file');q.add_argument('output')
    a=ap.parse_args()
    if a.cmd=='doctor':return doctor()
    if a.cmd=='init':return init(a.project,a.title)
    p=project(a.project)
    if a.cmd=='inventory':return inventory(p)
    if a.cmd=='validate':
        rows=shots(p)
        for s in rows:
            from core import fingerprint
            fingerprint(p,s,'image')
        print('镜号与首帧通过',len(rows));return
    if a.cmd=='review':return print(review.build(p,a.stage))
    if a.cmd=='import-review':return review.import_review(p,Path(a.file))
    if a.cmd=='approve':return approve(p,a.ids,a.stage,a.evidence)
    if a.cmd=='plan':return print(json.dumps(provider.plan(p,a.ids),ensure_ascii=False,indent=2))
    if a.cmd=='authorize':return print(provider.authorize(p,a.ids,a.limit,a.evidence))
    if a.cmd=='submit':return provider.submit(p,a.budget)
    if a.cmd=='poll':return provider.poll(p)
    if a.cmd=='balance':return print(json.dumps(provider.request('GET','/public/v1/balance'),ensure_ascii=False))
    if a.cmd=='attach-task':return provider.attach_task(p,resolve(p,a.record),a.task_id,a.evidence)
    if a.cmd=='render':return print(media.render(p,resolve(p,a.file)))
    if a.cmd=='card':return print(media.card(p,resolve(p,a.file)))
    if a.cmd=='join':
        cfg=read(p/'project.json')['output']
        return print(media.join([resolve(p,f) for f in a.inputs],resolve(p,a.output),cfg['width'],cfg['height'],cfg['fps']))
    if a.cmd=='inspect':return media.inspect(resolve(p,a.file),resolve(p,a.output))
    if a.cmd=='package':return print(media.package(p,resolve(p,a.file),ROOT/'deliveries'))


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,KeyError,TypeError,FileNotFoundError) as e:
        print('停止：'+str(e),file=sys.stderr);sys.exit(1)
