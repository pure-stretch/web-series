"""Offline integration: synthetic clips -> captions/music -> credits -> join -> ZIP."""
import json
import platform
import tempfile
import zipfile
from pathlib import Path
from core import save
import media
import review


def main():
    with tempfile.TemporaryDirectory(prefix='web-series-中文-') as temp:
        p=Path(temp)/'demo';p.mkdir();(p/'edits').mkdir()
        font={'Windows':'Microsoft YaHei','Darwin':'PingFang SC'}.get(platform.system(),'DejaVu Sans')
        save(p/'project.json',{'output':{'width':180,'height':320,'fps':24,'font':font}})
        media.ff(['-f','lavfi','-i','color=c=blue:s=180x320:r=24:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-shortest',*media.enc(),p/'a.mp4'])
        media.ff(['-f','lavfi','-i','color=c=green:s=180x320:r=24:d=2','-an','-c:v','libx264',p/'b.mp4'])
        media.ff(['-i',p/'a.mp4','-frames:v',1,p/'cover.png'])
        timeline={'title':'DEMO','output':'edits/E01.mp4','speed':1.1,'clips':[
            {'source':'a.mp4','in':.1,'out':1.8,'speed':1.15,'subtitles':[{'start':.2,'end':1,'text':'TEST'}]},
            {'source':'b.mp4','in':0,'out':1.5,'speed':1,'subtitles':[]}],
            'music':[{'source':'a.mp4','start':1,'end':2,'gain_db':-25}]}
        save(p/'timeline.json',timeline);episode=media.render(p,p/'timeline.json')
        duration=float(media.probe(episode)['format']['duration']);assert abs(duration-((1.7/1.15+1.5)/1.1))<.15
        save(p/'credits.json',{'title':'DEMO','lines':['DIRECTOR | TEST'],'closing':'THANKS','seconds':1,'output':'edits/credits.mp4'})
        credits=media.card(p,p/'credits.json');combined=media.join([episode,credits],p/'edits/all.mp4',180,320,24)
        assert abs(float(media.probe(combined)['format']['duration'])-duration-1)<.2
        media.inspect(combined,p/'checks')
        save(p/'shots.json',[{'id':'E01-S01','image':'cover.png','video':'edits/E01.mp4','line':'TEST'}]);save(p/'approvals.json',{})
        assert review.build(p,'video').exists()
        (p/'tutorial.txt').write_text('Publish instructions','utf8')
        save(p/'delivery.json',{'name':'smoke-v1','tutorial':'tutorial.txt','episodes':[{'id':'E01','video':'edits/E01.mp4','cover':'cover.png','description':'正文 #话题'}],
            'collection':{'id':'ALL','video':'edits/all.mp4','cover':'cover.png','description':'全集 #话题'}})
        output=media.package(p,p/'delivery.json',p/'delivery')
        with zipfile.ZipFile(output) as z:
            assert len(z.namelist())==7 and z.testzip() is None
            assert z.read('01_分集发布/E01_简介.txt').decode('utf-8-sig').strip()=='正文 #话题'
        print('PASS: trim/speed + silent clip + captions + music + credits + concat + review + ZIP')

if __name__=='__main__':main()
