# -*- coding: utf-8 -*-
import csv, io, sys, os, hashlib
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

src = r"C:/Users/johnsywang/Downloads/商品素材.csv"
outdir = r"C:/Users/johnsywang/CodeBuddy/20260730115254/out"
os.makedirs(outdir, exist_ok=True)

rows = []
with open(src, encoding='utf-8-sig') as f:
    r = csv.reader(f)
    header = next(r)
    for line in r:
        if not line or len(line) < 4:
            continue
        cat, url, cost, ctr = line[0], line[1], line[2], line[3]
        if cat in ("整体", "空"):
            continue
        url = (url or "").strip()
        has_url = bool(url) and url != "空" and url.startswith("http")
        try:
            cost_v = float(cost)
        except:
            cost_v = 0.0
        try:
            ctr_v = float(ctr)
        except:
            ctr_v = 0.0
        rows.append((cat, url, has_url, cost_v, ctr_v))

by_cat = defaultdict(list)
for cat, url, has_url, cost_v, ctr_v in rows:
    if has_url:
        by_cat[cat].append((url, cost_v, ctr_v))

# 每类目按消耗降序取 Top20（仅可下载视频）
top20 = {}
for cat, lst in by_cat.items():
    lst.sort(key=lambda x: -x[1])
    top20[cat] = lst[:20]

# 明细清单
detail_path = os.path.join(outdir, "material_top20.csv")
total_dl = 0
with open(detail_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["类目", "类目内排名", "消耗(元)", "ctr(%)", "建议文件名", "素材URL"])
    for cat in sorted(top20.keys()):
        for i, (url, cost_v, ctr_v) in enumerate(top20[cat], 1):
            md5 = hashlib.md5(url.encode()).hexdigest()[:8]
            fn = f"{cat}_{i:02d}_{md5}.mp4"
            w.writerow([cat, i, round(cost_v, 2), round(ctr_v, 4), fn, url])
            total_dl += 1

# 类目汇总
summary_path = os.path.join(outdir, "category_summary.csv")
with open(summary_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["类目", "可下载素材总数", "Top20实际数", "Top20消耗合计(万元)", "Top20平均ctr(%)"])
    agg = []
    for cat, lst in by_cat.items():
        t = top20[cat]
        s = sum(x[1] for x in t)
        avg_ctr = sum(x[2] for x in t) / len(t) if t else 0
        agg.append((cat, len(lst), len(t), s / 1e4, avg_ctr))
    agg.sort(key=lambda x: -x[3])
    for cat, n, tn, s, ac in agg:
        w.writerow([cat, n, tn, round(s, 1), round(ac, 3)])

print("有效可下载素材类目数:", len(by_cat))
print("Top20清单需下载视频总数:", total_dl)
print("\n各类目可下载素材数 >=10 的（重点类目）:")
big = [(cat, len(lst)) for cat, lst in by_cat.items() if len(lst) >= 10]
big.sort(key=lambda x: -x[1])
for cat, n in big:
    print(f"  {cat:<18} 可下载{n:>4}  取Top20={min(n,20)}")
print("\n可下载素材数 <10 的类目数:", sum(1 for _, lst in by_cat.items() if len(lst) < 10))
print("清单已输出:", detail_path)
print("汇总已输出:", summary_path)
