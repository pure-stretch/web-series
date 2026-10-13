"""Optional local transcription. It does not judge pronunciation or change subtitles."""
import argparse
from pathlib import Path
from core import save

def main():
    p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('output');p.add_argument('--model',default='base');p.add_argument('--download',action='store_true');a=p.parse_args()
    from faster_whisper import WhisperModel
    model=WhisperModel(a.model,device='cpu',compute_type='int8',local_files_only=not a.download)
    segments,info=model.transcribe(a.video,language='zh',word_timestamps=True,condition_on_previous_text=False)
    rows=[{'start':s.start,'end':s.end,'text':s.text,'words':[{'text':w.word,'start':w.start,'end':w.end} for w in s.words or []]} for s in segments]
    save(Path(a.output),{'source':Path(a.video).name,'segments':rows,'note':'识别仅供定位，同音字需听辨，不自动覆盖剧本台词'})

if __name__=='__main__':main()
