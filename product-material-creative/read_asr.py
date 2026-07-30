# -*- coding: utf-8 -*-
"""读取指定重点代表作的ASR口播文本(用于框架分析)。"""
import json, sys, io, re
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
TR = Path.home() / 'Downloads' / '商品素材_analysis' / 'transcripts'
def safe(s): return re.sub(r'[\\/:*?"<>|]', '_', str(s))

targets = [
    ("饮料冲调","饮料冲调_01_8a03fdad"),
    ("休闲食品","休闲食品_01_4a237b6c"),
    ("保健滋补","保健滋补_01_99089b61"),
    ("传统滋补品","传统滋补品_01_12cefd30"),
    ("内衣裤袜/睡衣/家居服","内衣裤袜_睡衣_家居服_01_2328bd3f"),
    ("个护健康","个护健康_01_12621ef3"),
    ("传统滋补品","传统滋补品_02_84d2d58c"),
    ("休闲食品","休闲食品_02_10809823"),
]
for cat, stem in targets:
    p = TR / safe(cat) / f"{stem}.json"
    if p.exists():
        d = json.load(open(p, encoding='utf-8'))
        t = d.get('text','')
        print(f"\n=== {cat} / {stem} (时长{d.get('duration')}s) ===")
        print(t[:700])
    else:
        print(f"\n=== {cat}/{stem}  [ASR未就绪] ===")
# 统计已完成ASR总数
allc = len(list(TR.rglob('*.json')))
print(f"\n\n[ASR已完成总数: {allc}]")
