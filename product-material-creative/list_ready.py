# -*- coding: utf-8 -*-
"""输出已就绪代表作的分析清单:类目/消耗/ctr/帧路径(取4张:首中中尾)/ASR是否就绪。按消耗降序。"""
import json, sys, io, re
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = Path.home() / 'Downloads' / '商品素材_analysis'
TR = BASE / 'transcripts'
def safe(s): return re.sub(r'[\\/:*?"<>|]', '_', str(s))
reps = json.load(open('out/representatives.json', encoding='utf-8'))

ready = [r for r in reps if r['n_frames'] >= 4]
print(f"帧就绪代表作: {len(ready)}/{len(reps)}\n")
out = []
for r in ready:
    frames = r['frames']
    # 取4张:首、1/3、2/3、尾
    n = len(frames)
    pick = [frames[0], frames[n//3], frames[2*n//3], frames[-1]]
    stem = r['stem']; cat = r['cat']
    tr = TR / safe(cat) / f"{stem}.json"
    out.append({'cat':cat,'rank':r['rank'],'cost':r['cost'],'ctr':r['ctr'],
                'stem':stem,'pick_frames':pick,'asr_ready':tr.exists()})
json.dump(out, open('out/ready_analysis.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
for r in out[:40]:
    print(f"{r['cost']/10000:6.1f}万 ctr{r['ctr']:>7}% {'ASR✓' if r['asr_ready'] else 'ASR×'} {r['cat']}/{r['stem']}")
