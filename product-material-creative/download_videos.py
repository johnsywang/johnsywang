# -*- coding: utf-8 -*-
"""S1: 按 out/material_top20.csv 并发下载 512 个视频，按类目分子目录。"""
import csv, os, sys, io, ssl, time, hashlib, re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

ROOT = Path(r'c:/Users/johnsywang/CodeBuddy/20260730115254')
LIST = ROOT / 'out' / 'material_top20.csv'
BASE = Path(os.path.expandvars(r'%USERPROFILE%')) / 'Downloads' / '商品素材_analysis'
VIDEO_DIR = BASE / 'videos'
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

def safe(s):
    return re.sub(r'[\\/:*?"<>|\r\n\t]', '_', s).strip()

def load_list():
    items = []
    with open(LIST, encoding='utf-8-sig') as f:
        r = csv.DictReader(f)
        for row in r:
            items.append(row)
    return items

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def download_one(item):
    cat = item['类目']
    url = item['素材URL']
    fn = safe(item['建议文件名'])
    cat_dir = VIDEO_DIR / safe(cat)
    cat_dir.mkdir(parents=True, exist_ok=True)
    fp = cat_dir / fn
    if fp.exists() and fp.stat().st_size > 50*1024:
        return ('skip', fn, fp.stat().st_size)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=90, context=ctx) as resp, open(fp, 'wb') as out:
                while True:
                    chunk = resp.read(128*1024)
                    if not chunk: break
                    out.write(chunk)
            sz = fp.stat().st_size
            if sz < 50*1024:
                raise IOError(f'too small {sz}')
            return ('ok', fn, sz)
        except Exception as e:
            if attempt == 2:
                return ('fail', fn, str(e))
            time.sleep(1.5)
    return ('fail', fn, 'unknown')

def main():
    items = load_list()
    print(f'待下载: {len(items)} 个视频')
    ok = skip = fail = 0
    fails = []
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(download_one, it): it for it in items}
        for fu in as_completed(futs):
            status, fn, info = fu.result()
            done += 1
            if status == 'ok':
                ok += 1
            elif status == 'skip':
                skip += 1
            else:
                fail += 1
                fails.append((fn, info))
            if done % 20 == 0 or done == len(items):
                print(f'  进度 {done}/{len(items)}  ok={ok} skip={skip} fail={fail}  用时{time.time()-t0:.0f}s')
    print(f'\n完成: ok={ok} skip={skip} fail={fail}  总用时{time.time()-t0:.0f}s')
    if fails:
        print('失败清单:')
        for fn, info in fails[:50]:
            print(f'  {fn}: {info}')
        (ROOT / 'out' / 'download_fails.txt').write_text(
            '\n'.join(f'{fn}\t{info}' for fn, info in fails), encoding='utf-8')

if __name__ == '__main__':
    main()
