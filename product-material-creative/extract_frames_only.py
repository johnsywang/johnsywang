# -*- coding: utf-8 -*-
"""本地关键帧抽取（无需任何 API）。每视频抽 5 帧存 jpg，用于分镜拆解与报告展示。
videos/<类目>/*.mp4 -> frames/<类目>/<name>/f1..f5.jpg"""
import sys, io, time, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

BASE = Path.home() / 'Downloads' / '商品素材_analysis'
VIDEO_DIR = BASE / 'videos'
FRAMES_DIR = BASE / 'frames'
FRAMES_DIR.mkdir(parents=True, exist_ok=True)
N = 5

import av
from PIL import Image

def extract(video_path: Path, out_dir: Path):
    meta = out_dir / 'meta.json'
    if meta.exists():
        return 'skip', 0
    container = av.open(str(video_path))
    stream = container.streams.video[0]
    dur = float(container.duration) / 1_000_000 if container.duration else 30
    times = [dur * (0.06 + 0.88 * i / (N - 1)) for i in range(N)]
    out_dir.mkdir(parents=True, exist_ok=True)
    it = iter(times); target = next(it); saved = []
    idx = 1
    container.seek(0)
    try:
        for frame in container.decode(stream):
            if frame.time is None: continue
            if frame.time >= target:
                img = frame.to_image()
                w, h = img.size
                if max(w, h) > 720:
                    s = 720 / max(w, h); img = img.resize((int(w*s), int(h*s)), Image.LANCZOS)
                fp = out_dir / f'f{idx}_t{round(frame.time,1)}s.jpg'
                img.save(fp, format='JPEG', quality=80)
                saved.append({'idx': idx, 'time': round(frame.time,1), 'file': fp.name})
                idx += 1
                try: target = next(it)
                except StopIteration: break
    finally:
        container.close()
    meta.write_text(json.dumps({'video': video_path.name, 'duration': round(dur,1), 'frames': saved},
                               ensure_ascii=False, indent=2), encoding='utf-8')
    return 'ok', len(saved)

def main():
    videos = sorted(VIDEO_DIR.rglob('*.mp4'))
    print(f'共 {len(videos)} 视频抽帧')
    ok = skip = err = 0; t0 = time.time()
    for i, v in enumerate(videos, 1):
        rel = v.relative_to(VIDEO_DIR)
        out_dir = FRAMES_DIR / rel.parent / v.stem
        try:
            st, n = extract(v, out_dir)
            if st == 'ok': ok += 1
            else: skip += 1
        except Exception as e:
            err += 1; print(f'  ERR {v.name}: {e}')
        if i % 40 == 0:
            print(f'  [{i}/{len(videos)}] ok={ok} skip={skip} err={err} 用时{time.time()-t0:.0f}s')
    print(f'\n完成 ok={ok} skip={skip} err={err} 用时{time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
