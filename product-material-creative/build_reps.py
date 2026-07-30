# -*- coding: utf-8 -*-
"""选每类目代表作(Top1-2按消耗),映射关键帧路径,检查帧就绪状态。"""
import csv, sys, io, os, re, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TOP20 = Path("out/material_top20.csv")
ANA = Path(r"C:\Users\johnsywang\Downloads\商品素材_analysis")
FRAMES = ANA / "frames"

def safe(s):
    return re.sub(r'[\\/:*?"<>|]', '_', str(s))

rows = list(csv.DictReader(open(TOP20, encoding='utf-8-sig')))
# 按类目分组
from collections import defaultdict
by_cat = defaultdict(list)
for r in rows:
    by_cat[r['类目']].append(r)

reps = []
for cat, items in by_cat.items():
    items.sort(key=lambda x: float(x['消耗(元)']), reverse=True)
    # 大类目(>=10素材)取Top2, 小类目取Top1
    n = 2 if len(items) >= 10 else 1
    for it in items[:n]:
        fn = safe(it['建议文件名'])
        stem = Path(fn).stem
        vid_dir = FRAMES / safe(cat) / stem
        # 找该视频的帧(每视频独立子目录)
        frame_files = []
        if vid_dir.exists():
            frame_files = sorted([str(p) for p in vid_dir.glob("*.jpg")])
        reps.append({
            'cat': cat, 'rank': it['类目内排名'], 'cost': float(it['消耗(元)']),
            'ctr': it['ctr(%)'], 'file': fn, 'stem': stem,
            'n_frames': len(frame_files), 'frames': frame_files,
        })

reps.sort(key=lambda x: (-x['cost']))
Path("out").mkdir(exist_ok=True)
json.dump(reps, open("out/representatives.json", 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

ready = [r for r in reps if r['n_frames'] > 0]
print(f"代表作总数: {len(reps)}  (来自 {len(by_cat)} 个类目)")
print(f"帧已就绪: {len(ready)}  帧未就绪: {len(reps)-len(ready)}")
print("--- 消耗Top15代表作 ---")
for r in reps[:15]:
    print(f"  {r['cat'][:14]:16s} rank{r['rank']} 消耗{r['cost']/10000:.1f}万 ctr{r['ctr']}% 帧{r['n_frames']}")
