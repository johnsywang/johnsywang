# -*- coding: utf-8 -*-
"""S3: 关键帧抽取 + 混元 vision 画面分析。
遍历 videos/<类目>/*.mp4 → 抽帧 → hunyuan-vision 描述 → vision/<类目>/<name>.json
Token 预算控制：按累计 token 动态限流；分级抽帧。"""
import sys, io, json, base64, time, argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

ROOT = Path(r'c:/Users/johnsywang/CodeBuddy/20260730115254')
BASE = Path.home() / 'Downloads' / '商品素材_analysis'
VIDEO_DIR = BASE / 'videos'
FRAMES_DIR = BASE / 'frames'
VISION_DIR = BASE / 'vision'
VISION_DIR.mkdir(parents=True, exist_ok=True)
CFG = json.loads((Path(r'C:/Users/johnsywang/CodeBuddy/20260513225710/.api-config.json')).read_text(encoding='utf-8'))

TOKEN_BUDGET = 900_000       # 免费包 100w，留 10w 余量
_token_used_file = ROOT / 'out' / 'vision_token_used.txt'

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
import av
from PIL import Image

cred = credential.Credential(CFG['secret_id'], CFG['secret_key'])
http = HttpProfile(); http.endpoint = 'hunyuan.tencentcloudapi.com'; http.reqTimeout = 60
cp = ClientProfile(); cp.httpProfile = http
client = hunyuan_client.HunyuanClient(cred, 'ap-guangzhou', cp)

def extract_frames(video_path: Path, n_frames):
    container = av.open(str(video_path))
    stream = container.streams.video[0]
    duration_s = float(container.duration) / 1_000_000 if container.duration else 30
    if n_frames == 1:
        times = [duration_s * 0.4]
    else:
        times = [duration_s * (0.05 + 0.9 * i / (n_frames - 1)) for i in range(n_frames)]
    frames = []
    it = iter(times); target = next(it)
    container.seek(0)
    try:
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            if frame.time >= target:
                img = frame.to_image()
                w, h = img.size
                if max(w, h) > 768:
                    s = 768 / max(w, h)
                    img = img.resize((int(w*s), int(h*s)), Image.LANCZOS)
                buf = io.BytesIO(); img.save(buf, format='JPEG', quality=75)
                frames.append({'time': round(frame.time, 1), 'jpeg': buf.getvalue()})
                try: target = next(it)
                except StopIteration: break
    finally:
        container.close()
    return frames

PROMPT = '''你是短视频广告创意分析师。用中文简洁分析此视频画面（第{idx}/{total}帧，第{time}s处）。严格按格式，每点1句、总共不超过80字：
人物:(几人/性别/年龄/穿着) 动作:(在做什么) 产品:(可见产品/包装/特写) 字幕:(精确摘录关键字幕文字,无则写无) 场景:(家/直播间/户外/厨房/卫浴等)'''

def analyze_frame(jpeg, idx, total, t):
    b64 = base64.b64encode(jpeg).decode('ascii')
    req = models.ChatCompletionsRequest()
    payload = {'Model':'hunyuan-vision','Stream':False,'Messages':[{'Role':'user','Contents':[
        {'Type':'text','Text':PROMPT.format(idx=idx,total=total,time=t)},
        {'Type':'image_url','ImageUrl':{'Url':f'data:image/jpeg;base64,{b64}'}}]}]}
    req.from_json_string(json.dumps(payload))
    resp = client.ChatCompletions(req)
    d = json.loads(resp.to_json_string())
    return d['Choices'][0]['Message']['Content'], d.get('Usage',{}).get('TotalTokens',0)

def n_frames_for(category, big_cats):
    return 6 if category in big_cats else 4

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--big-threshold', type=int, default=10)
    args = ap.parse_args()

    # 读类目汇总判断大类目
    import csv
    big_cats = set()
    with open(ROOT/'out'/'category_summary.csv', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if int(row['可下载素材总数']) >= args.big_threshold:
                big_cats.add(row['类目'].replace('/', '_'))

    videos = sorted(VIDEO_DIR.rglob('*.mp4'))
    print(f'共 {len(videos)} 视频；大类目(6帧): {len(big_cats)} 个，其余 4 帧')
    token_used = 0
    if _token_used_file.exists():
        try: token_used = int(_token_used_file.read_text().strip())
        except: token_used = 0
    print(f'已用 token(累计记录): {token_used}')
    ok = skip = err = 0
    degraded = False
    t0 = time.time()
    for i, v in enumerate(videos, 1):
        rel = v.relative_to(VIDEO_DIR)
        cat = rel.parent.name
        out_json = VISION_DIR / rel.parent / (v.stem + '.json')
        if out_json.exists():
            skip += 1; continue
        # 预算控制：接近上限降级为 1 帧
        n = n_frames_for(cat, big_cats)
        if token_used > TOKEN_BUDGET:
            n = 1
            if not degraded:
                print(f'  !! token 超预算 {token_used}，降级为每视频 1 帧'); degraded = True
        try:
            frames = extract_frames(v, n)
        except Exception as e:
            err += 1; print(f'  抽帧失败 {v.name}: {e}'); continue
        fa = []
        for fidx, fr in enumerate(frames, 1):
            try:
                desc, tok = analyze_frame(fr['jpeg'], fidx, len(frames), fr['time'])
                token_used += tok
                fa.append({'frame_idx':fidx,'time_s':fr['time'],'description':desc,'tokens':tok})
            except Exception as e:
                fa.append({'frame_idx':fidx,'time_s':fr['time'],'error':str(e)})
                time.sleep(1)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps({'video':v.name,'category':cat,'frames':fa},
                                       ensure_ascii=False, indent=2), encoding='utf-8')
        ok += 1
        _token_used_file.write_text(str(token_used))
        if ok % 10 == 0:
            print(f'  [{i}/{len(videos)}] ok={ok} skip={skip} err={err} token={token_used} 用时{time.time()-t0:.0f}s')
    print(f'\n完成: ok={ok} skip={skip} err={err} 总token={token_used} 用时{time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
