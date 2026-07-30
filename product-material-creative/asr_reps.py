# -*- coding: utf-8 -*-
"""只转写 83 个代表作的口播(优先级最高)。已转写的skip。"""
import sys, io, json, time, re
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

BASE = Path.home() / 'Downloads' / '商品素材_analysis'
VIDEO_DIR = BASE / 'videos'
TR_DIR = BASE / 'transcripts'
TR_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR = r"C:\Users\johnsywang\CodeBuddy\20260513225710\models\faster-whisper-small"
def safe(s): return re.sub(r'[\\/:*?"<>|]', '_', str(s))

from faster_whisper import WhisperModel
print("加载模型...")
model = WhisperModel(MODEL_DIR, device="cpu", compute_type="int8")
print("模型就绪")

reps = json.load(open('out/representatives.json', encoding='utf-8'))
ok=skip=err=0; t0=time.time()
for i, r in enumerate(reps, 1):
    cat=r['cat']; fn=r['file']; stem=r['stem']
    vp = VIDEO_DIR / safe(cat) / fn
    od = TR_DIR / safe(cat); od.mkdir(parents=True, exist_ok=True)
    outp = od / f"{stem}.json"
    if outp.exists():
        skip+=1; continue
    if not vp.exists():
        err+=1; print(f"  MISS {cat}/{fn}"); continue
    try:
        segs, info = model.transcribe(str(vp), language="zh", beam_size=5, vad_filter=True)
        segments=[]; full=[]
        for s in segs:
            segments.append({'start':round(s.start,1),'end':round(s.end,1),'text':s.text.strip()})
            full.append(s.text.strip())
        outp.write_text(json.dumps({'video':fn,'duration':round(info.duration,1),
            'text':''.join(full),'segments':segments}, ensure_ascii=False, indent=2), encoding='utf-8')
        ok+=1
        print(f"  [{i}/{len(reps)}] OK {cat[:12]} {stem[-8:]} {info.duration:.0f}s 累计{ok}")
    except Exception as e:
        err+=1; print(f"  ERR {fn}: {e}")
print(f"完成 ok={ok} skip={skip} err={err} 用时{time.time()-t0:.0f}s")
