"""FFmpeg operations. Commands are argv lists, never shell strings."""
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from core import read, save, resolve, number, ident, sha, now


def run(args, cwd=None):
    proc = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, encoding='utf8', errors='replace')
    if proc.returncode:
        raise RuntimeError(proc.stderr[-2500:])
    return proc.stdout


def probe(file):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', file]))
    if not any(s['codec_type'] == 'video' for s in data['streams']):
        raise ValueError('文件没有视频轨')
    return data


def decode(file):
    run(['ffmpeg', '-v', 'error', '-xerror', '-i', file, '-f', 'null', '-'])


def enc():
    return ['-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart']


def ff(args, cwd=None):
    return run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y'] + args, cwd)


def protect(out):
    if out.exists():
        raise ValueError('输出已存在，请换版本文件名：' + str(out))
    out.parent.mkdir(parents=True, exist_ok=True)


def finish(temp, out):
    decode(temp)
    temp.replace(out)
    return out


def join(inputs, out, width=720, height=1280, fps=24):
    protect(out)
    with tempfile.TemporaryDirectory(dir=out.parent) as work:
        normalized = []
        for i, source in enumerate(inputs):
            dest = Path(work) / f'{i:04}.mp4'
            clip(source, dest, 0, float(probe(source)['format']['duration']), 1, width, height, fps)
            normalized.append(dest)
        listing = Path(work) / 'list.txt'
        listing.write_text('\n'.join(f"file '{f.name}'" for f in normalized), 'utf8')
        temp = Path(work) / 'joined.mp4'
        ff(['-f', 'concat', '-safe', '1', '-i', 'list.txt', '-c', 'copy', '-movflags', '+faststart', temp], work)
        return finish(temp, out)


def clip(source, out, start, end, speed=1, width=720, height=1280, fps=24):
    info = probe(source)
    duration = float(info['format']['duration'])
    start = number(start, 0, duration)
    end = number(end, start + .001, duration + .05)
    speed = number(speed, .5, 2)
    vf = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,setpts=(PTS-STARTPTS)/{speed},fps={fps}'
    args = ['-ss', start, '-t', end-start, '-i', source]
    has_audio = any(s['codec_type'] == 'audio' for s in info['streams'])
    if not has_audio:
        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    args += ['-map', '0:v:0', '-map', '0:a:0' if has_audio else '1:a:0', '-vf', vf,
             '-af', f'asetpts=PTS-STARTPTS,atempo={speed}', '-t', (end-start)/speed, *enc(), out]
    ff(args)


def ass_time(t):
    n = round(t * 100)
    return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'


def ass_text(t):
    return str(t).replace('\\', '＼').replace('{', '（').replace('}', '）').replace('\n', r'\N')


def ass_header(width, height, font):
    if any(c in font for c in ',\r\n'):
        raise ValueError('字体名不能含逗号或换行')
    size = round(width / 20)
    return f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,40,40,100,1
Style: Title,{font},{round(size*.8)},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,1,0,7,35,35,40,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''


def render(p, timeline_file):
    t = read(timeline_file)
    cfg = read(p / 'project.json')['output']
    width, height, fps = [int(number(cfg[k], 1, 8192)) for k in ('width', 'height', 'fps')]
    if width % 2 or height % 2:
        raise ValueError('输出尺寸需为偶数')
    out = resolve(p, t['output']); protect(out)
    with tempfile.TemporaryDirectory(dir=out.parent) as work:
        w = Path(work); offset = 0; captions = []
        for i, c in enumerate(t['clips']):
            speed = number(c.get('speed', 1), .5, 2)
            source = resolve(p, c['source'])
            clip(source, w / f'{i:04}.mp4', c['in'], c['out'], speed, width, height, fps)
            length = (c['out']-c['in'])/speed
            for sub in c.get('subtitles', []):
                # Caption positions are original source seconds, before trim/speed.
                a = max(c['in'], sub['start']); b = min(c['out'], sub['end'])
                if b > a:
                    captions.append((offset+(a-c['in'])/speed, offset+(b-c['in'])/speed, sub['text']))
            offset += length
        if not t['clips']:
            raise ValueError('空时间线')
        (w/'list.txt').write_text('\n'.join(f"file '{i:04}.mp4'" for i in range(len(t['clips']))), 'utf8')
        ff(['-f','concat','-safe','1','-i','list.txt','-c','copy','base.mp4'],w)
        ass = ass_header(width,height,cfg['font'])
        if t.get('title'):
            ass += f'Dialogue: 0,0:00:00.00,{ass_time(min(3,offset))},Title,,0,0,0,,{ass_text(t["title"])}\n'
        for a,b,text in captions:
            ass+=f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{ass_text(text)}\n'
        (w/'subtitles.ass').write_text(ass,'utf-8-sig')
        args=['-i','base.mp4']; music=t.get('music',[])
        filters=[]; labels=['[0:a]']
        for i,m in enumerate(music,1):
            source=resolve(p,m['source']); start=number(m['start'],0,offset); end=number(m['end'],start+.01,offset)
            gain=number(m.get('gain_db',-22),-60,0)
            args+=['-i',source]
            duration=end-start; fade=min(.5,duration/2)
            filters.append(f'[{i}:a]atrim=start={m.get("source_in",0)}:duration={duration},asetpts=PTS-STARTPTS,volume={gain}dB,afade=t=in:st=0:d={fade},afade=t=out:st={duration-fade}:d={fade},adelay={round(start*1000)}:all=1[m{i}]')
            labels.append(f'[m{i}]')
        rate=number(t.get('speed',1),.5,2)
        if music:
            filters.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=first:normalize=0,alimiter=limit=0.95,atempo={rate}[a]')
        else:
            filters.append(f'[0:a]atempo={rate}[a]')
        vf=f'ass=subtitles.ass,setpts=(PTS-STARTPTS)/{rate},fps={fps}'
        args+=['-filter_complex',';'.join(filters),'-map','0:v','-map','[a]','-vf',vf,*enc(),'result.mp4']
        ff(args,w)
        finish(w/'result.mp4',out)
    save(out.with_suffix('.render.json'),{'timeline':t,'output_config':cfg,'sha256':sha(out),'at':now()})
    return out


def card(p, file):
    c=read(file); cfg=read(p/'project.json')['output']; out=resolve(p,c['output']);protect(out)
    seconds=number(c.get('seconds',10),1,60);width=cfg['width'];height=cfg['height']
    with tempfile.TemporaryDirectory(dir=out.parent) as work:
        w=Path(work);ass=ass_header(width,height,cfg['font'])
        lines=[c['title'],'']+c['lines']+['',c['closing']]
        text=ass_text('\n'.join(lines))
        ass+=f'Dialogue: 0,0:00:00.00,{ass_time(seconds)},Default,,0,0,0,,{{\\an5\\pos({width//2},{height//2})\\fad(400,800)}}{text}\n'
        (w/'subtitles.ass').write_text(ass,'utf-8-sig')
        args=['-f','lavfi','-i',f'color=c=0x111b18:s={width}x{height}:r={cfg["fps"]}:d={seconds}']
        if c.get('music'):
            args+=['-i',resolve(p,c['music']),'-af',f'volume=-22dB,afade=t=out:st={max(0,seconds-1.5)}:d=1.5']
        else:
            args+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
        ff(args+['-t',seconds,'-map','0:v','-map','1:a','-vf','ass=subtitles.ass',*enc(),'card.mp4'],w)
        return finish(w/'card.mp4',out)


def inspect(file, out):
    out.mkdir(parents=True,exist_ok=True);info=probe(file);decode(file)
    d=float(info['format']['duration'])
    for i,t in enumerate([min(.2,d/4),d/2,max(0,d-.2)]):
        ff(['-ss',t,'-i',file,'-frames:v','1',out/f'frame-{i}.png'])
    save(out/'probe.json',info)


def package(p, manifest_file, destination):
    m=read(manifest_file); ident(m['name']);out=destination/(m['name']+'.zip');protect(out)
    with tempfile.TemporaryDirectory(dir=out.parent) as work:
        root=Path(work);entries=[]
        for folder, rows in [('01_分集发布',m['episodes']),('02_合集发布',[m['collection']])]:
            for row in rows:
                stem=ident(row['id']);d=root/folder;d.mkdir(exist_ok=True)
                for field,suffix in [('video','.mp4'),('cover','_封面.png')]:
                    source=resolve(p,row[field]);target=d/(stem+suffix)
                    if target.exists():raise ValueError('交付ID重复')
                    if field=='video':decode(source)
                    elif source.suffix.lower()!='.png':raise ValueError('交付封面需PNG')
                    shutil.copy2(source,target)
                    entries.append({'file':target.relative_to(root).as_posix(),'sha256':sha(target)})
                (d/(stem+'_简介.txt')).write_text(row['description']+'\n','utf-8-sig')
        shutil.copy2(resolve(p,m['tutorial']),root/'00_发布教程.txt')
        temp=root/'bundle.zip'
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
            for f in sorted(root.rglob('*')):
                if f.is_file() and f!=temp:z.write(f,f.relative_to(root))
        with zipfile.ZipFile(temp) as z:
            if z.testzip():raise ValueError('ZIP校验失败')
        temp.replace(out)
    save(out.with_suffix('.checks.json'),{'at':now(),'sha256':sha(out),'files':entries})
    return out
