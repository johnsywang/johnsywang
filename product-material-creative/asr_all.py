# -*- coding: utf-8 -*-
"""S2: 批量 ASR 口播转写（faster-whisper small, cpu/int8）。
遍历 videos/<类目>/*.mp4 → transcripts/<类目>/<name>.json"""
import sys, io, json, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

ROOT = Path(r'c:/Users/johnsywang/CodeBuddy/20260730115254')
BASE = Path.home() / 'Downloads' / '商品素材_analysis'
VIDEO_DIR = BASE / 'videos'
TRANS_DIR = BASE / 'transcripts'
TRANS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR = str(Path(r'C:/Users/johnsywang/CodeBuddy/20260513225710/models/faster-whisper-small'))

_model = None
def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f'加载 whisper small (cpu/int8): {MODEL_DIR}')
        _model = WhisperModel(MODEL_DIR, device='cpu', compute_type='int8')
    return _model

def transcribe(video_path: Path, out_json: Path):
    if out_json.exists():
        return 'skip', None
    model = get_model()
    t0 = time.time()
    try:
        segments, info = model.transcribe(
            str(video_path), language='zh', beam_size=5,
            vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
            initial_prompt='以下是普通话商品广告口播。',
        )
        segs, full = [], []
        for s in segments:
            segs.append({'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip()})
            full.append(s.text.strip())
        text = ' '.join(full).strip()
        result = {
            'video': video_path.name,
            'category': video_path.parent.name,
            'duration': round(info.duration, 2),
            'segments': segs, 'text': text,
            'asr_cost_seconds': round(time.time()-t0, 1),
        }
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return 'ok', result
    except Exception as e:
        return 'err', str(e)

def main():
    videos = sorted(VIDEO_DIR.rglob('*.mp4'))
    print(f'共 {len(videos)} 个视频待转写')
    ok = skip = err = 0
    t0 = time.time()
    for i, v in enumerate(videos, 1):
        rel = v.relative_to(VIDEO_DIR)
        out_json = TRANS_DIR / rel.parent / (v.stem + '.json')
        status, r = transcribe(v, out_json)
        if status == 'ok':
            ok += 1
            if ok % 10 == 0:
                print(f'  [{i}/{len(videos)}] ok={ok} skip={skip} err={err}  用时{time.time()-t0:.0f}s')
        elif status == 'skip':
            skip += 1
        else:
            err += 1
            print(f'  ERR {v.name}: {r}')
    print(f'\n完成: ok={ok} skip={skip} err={err}  总用时{time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
