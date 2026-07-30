# -*- coding: utf-8 -*-
import csv, io, sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r"C:/Users/johnsywang/Downloads/商品素材.csv"

rows = []
with open(path, encoding='utf-8-sig') as f:
    r = csv.reader(f)
    header = next(r)
    for line in r:
        if not line or len(line) < 4:
            continue
        rows.append(line)

print("表头:", header)
print("总数据行:", len(rows))

cat = defaultdict(lambda: {"n":0, "url":0, "nourl":0, "cost":0.0})
total_cost = 0.0
for c, url, cost, ctr in [(x[0], x[1], x[2], x[3]) for x in rows]:
    try:
        cost_v = float(cost)
    except:
        cost_v = 0.0
    d = cat[c]
    d["n"] += 1
    d["cost"] += cost_v
    if url and url.strip() and url.strip() != "空":
        d["url"] += 1
    else:
        d["nourl"] += 1

print("\n类目数(含整体):", len(cat))
print(f"\n{'类目':<16}{'素材数':>6}{'有URL':>7}{'无URL':>7}{'消耗(万元)':>14}")
for c, d in sorted(cat.items(), key=lambda kv: -kv[1]['cost']):
    print(f"{c:<16}{d['n']:>6}{d['url']:>7}{d['nourl']:>7}{d['cost']/1e4:>14.1f}")
