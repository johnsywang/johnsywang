# -*- coding: utf-8 -*-
"""只对 83 个代表作优先抽帧(每视频8帧,比全量更密以便精拆分镜)。已抽的skip。"""
import sys, io, json, time
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
import av
from PIL import Image

BASE = Path.home() / 'Downloads' / '商品素材_analysis'
VIDEO_DIR = BASE / 'videos'
FRAMES_DIR = BASE / 'frames'
import re
def safe(s): return re.sub(r'[\\/:*?"<>|]', '_', str(s))

reps = json.load(open('out/representatives.json', encoding='utf-8'))
N = 8

def extract(video_path: Path, out_dir: Path, n):
    existing = sorted(out_dir.glob('*.jpg')) if out_dir.exists() else []
    if len(existing) >= n:
        return 'skip', len(existing)
    container = av.open(str(video_path))
    stream = container.streams.video[0]
    dur = float(container.duration) / 1_000_000 if container.duration else 30
    times = [dur * (0.04 + 0.92 * i / (n - 1)) for i in range(n)]
    out_dir.mkdir(parents=True, exist_ok=True)
    # 清旧帧(数量不足则重抽)
    for f in existing: 
        try: f.unlink()
        except: pass
    it = iter(times); target = next(it); saved = []; idx = 1
    container.seek(0)
    try:
        for frame in container.decode(stream):
            if frame.time is None: continue
            if frame.time >= target:
                img = frame.to_image(); w, h = img.size
                if max(w, h) > 768:
                    s = 768 / max(w, h); img = img.resize((int(w*s), int(h*s)), Image.LANCZOS)
                fp = out_dir / f'f{idx}_t{round(frame.time,1)}s.jpg'
                img.save(fp, format='JPEG', quality=82)
                saved.append({'idx': idx, 'time': round(frame.time,1), 'file': fp.name}); idx += 1
                try: target = next(it)
                except StopIteration: break
    finally:
        container.close()
    (out_dir/'meta.json').write_text(json.dumps({'video':video_path.name,'duration':round(dur,1),'frames':saved},ensure_ascii=False,indent=2),encoding='utf-8')
    return 'ok', len(saved)

ok=skip=err=0; t0=time.time()
for i, r in enumerate(reps, 1):
    cat = r['cat']; fn = r['file']; stem = r['stem']
    vp = VIDEO_DIR / safe(cat) / fn
    od = FRAMES_DIR / safe(cat) / stem
    if not vp.exists():
        err += 1; print(f'  MISS {cat}/{fn}'); continue
    try:
        st, n = extract(vp, od, N)
        if st=='ok': ok+=1
        else: skip+=1
    except Exception as e:
        err+=1; print(f'  ERR {fn}: {e}')
    if i % 20 == 0: print(f'  [{i}/{len(reps)}] ok={ok} skip={skip} err={err} {time.time()-t0:.0f}s')
print(f'完成 ok={ok} skip={skip} err={err} 用时{time.time()-t0:.0f}s')
