import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from core import save,read,approve,approved,fingerprint,resolve
import provider
import review


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'demo';self.p.mkdir();(self.p/'image.png').write_bytes(b'image-v1')
        self.s={'id':'E01-S01','image':'image.png','line':'测试','design':'坐着','prompt':'具体动作','duration':5,'revision':1}
        self.cfg={'video':{'provider':'atlas','model':'bytedance/seedance-2.0-mini/image-to-video','resolution':'720p','usd_per_second':.03,'cost_margin':1.3,'price_checked_at':'2026-10-13'}}
        save(self.p/'shots.json',[self.s]);save(self.p/'project.json',self.cfg);save(self.p/'approvals.json',{})

    def authorize(self):
        approve(self.p,['E01-S01'],'image','用户确认该图')
        approve(self.p,['E01-S01'],'generation','用户确认台词与生成方案')
        return provider.authorize(self.p,['E01-S01'],1,'用户允许本轮一美元')

    def test_image_change_invalidates(self):
        self.authorize();self.assertTrue(approved(self.p,self.s,'image'))
        (self.p/'image.png').write_bytes(b'image-v2')
        self.assertFalse(approved(self.p,self.s,'image'))

    def test_prompt_change_invalidates_generation_only(self):
        self.authorize();s=dict(self.s,prompt='different')
        self.assertTrue(approved(self.p,s,'image'));self.assertFalse(approved(self.p,s,'generation'))

    def test_missing_approval_and_budget(self):
        with self.assertRaises(ValueError):provider.authorize(self.p,['E01-S01'],1,'用户授权')
        self.authorize()
        with self.assertRaises(ValueError):provider.authorize(self.p,['E01-S01'],.01,'用户授权')

    def test_unknown_submission_not_retried(self):
        b=self.authorize()
        with patch('provider.env_key',return_value='test'),patch('provider.request',side_effect=RuntimeError('timeout')) as req:
            with self.assertRaises(RuntimeError):provider.submit(self.p,b)
            provider.submit(self.p,b)
            self.assertEqual(req.call_count,1)
        self.assertEqual(read(next((self.p/'tasks').glob('*.json')))['status'],'unknown')

    def test_stale_budget_stops_before_post(self):
        b=self.authorize();s=dict(self.s,duration=6);save(self.p/'shots.json',[s])
        with patch('provider.request') as req:
            with self.assertRaises(ValueError):provider.submit(self.p,b)
            req.assert_not_called()

    def test_stale_review_is_atomic(self):
        export=self.p/'feedback.json';save(export,{'project':'demo','stage':'image','items':[{'id':self.s['id'],'fingerprint':'old','status':'approved'}]})
        with self.assertRaises(ValueError):review.import_review(self.p,export)
        self.assertEqual(read(self.p/'approvals.json'),{})

    def test_review_escape_and_import(self):
        self.s['design']='</script><img src=x onerror=alert(1)>';save(self.p/'shots.json',[self.s])
        page=review.build(self.p,'image');self.assertNotIn('<img src=x',page.read_text('utf8'))
        report=read(page.with_suffix('.json'));report['items'][0]['status']='approved';save(self.p/'feedback.json',report)
        review.import_review(self.p,self.p/'feedback.json');self.assertTrue(approved(self.p,self.s,'image'))

    def test_path_escape(self):
        for name in ('../.env','/tmp/file','C:/Users/key','images\\bad.png'):
            with self.assertRaises(ValueError):resolve(self.p,name)

    def test_price_required(self):
        self.cfg['video']['usd_per_second']=None;save(self.p/'project.json',self.cfg)
        with self.assertRaises((TypeError,ValueError)):provider.plan(self.p,['E01-S01'])

    def test_success_task_no_duplicate_new_budget(self):
        b=self.authorize()
        with patch('provider.env_key',return_value='test'),patch('provider.request',return_value={'id':'task-1'}) as req:
            provider.submit(self.p,b)
            b2=provider.authorize(self.p,['E01-S01'],1,'再次预算也不应重复同输入')
            provider.submit(self.p,b2);self.assertEqual(req.call_count,1)

if __name__=='__main__':unittest.main()
