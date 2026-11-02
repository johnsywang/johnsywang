"""一键生成客户监控看板：清洗源表 -> 合并消耗数据（如有）-> 输出 HTML + 清洗结果 Excel。

用法：
  python build.py                       # 自动取桌面最新「服饰Q4客户&商品盘点*.xlsx」，数据日期=昨天
  python build.py --src <xlsx> --date 2026-10-31
"""
import argparse
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

import config as C
import clean


def find_input(pattern):
    if not C.INPUT_DIR.exists():
        return None
    fs = [p for p in C.INPUT_DIR.glob(pattern) if p.suffix.lower() in (".csv", ".xlsx", ".xls") and not p.name.startswith("~$")]
    return max(fs, key=lambda p: p.stat().st_mtime) if fs else None


def read_table(p: Path):
    import pandas as pd
    if p.suffix.lower() == ".csv":
        for enc in ("utf-8-sig", "gbk"):
            try:
                return pd.read_csv(p, encoding=enc)
            except UnicodeDecodeError:
                continue
    return pd.read_excel(p)


def to_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)
    t = re.sub(r"[,，\s%]", "", str(v))
    try:
        return float(t)
    except ValueError:
        return None


def load_perf(pattern, colmap, data, tag):
    """读分客户消耗数据，按客户简称（含别名）匹配，同一客户多行加总。"""
    p = find_input(pattern)
    if not p:
        return None
    df = read_table(p)
    cols = {}
    for k, aliases in colmap.items():
        hit = next((a for a in aliases if a in df.columns), None)
        if hit:
            cols[k] = hit
    if "name" not in cols:
        raise ValueError(f"{p.name} 未找到客户列，请在 config.py 的列名映射中补充别名；现有列：{list(df.columns)}")
    idx = {}
    for ind in data["industries"]:
        for c in ind["customers"]:
            for a in dict.fromkeys(x.strip() for x in c["aliases"] + [c["name"]]):
                if c not in idx.setdefault(a, []):
                    idx[a].append(c)
    unmatched = set()
    for _, r in df.iterrows():
        nm = str(r[cols["name"]]).strip()
        targets = idx.get(nm)
        if not targets:
            unmatched.add(nm)
            continue
        for c in targets:
            perf = c.setdefault("perf", {})
            for k, col in cols.items():
                if k == "name":
                    continue
                v = to_num(r[col])
                if v is not None:
                    perf[k] = perf.get(k, 0) + v
    for nm in sorted(unmatched):
        data["issues"].append({"industry": "", "customer": nm, "field": f"{tag}数据", "raw": p.name, "msg": "消耗数据中的客户未在盘点表中找到，未计入", "level": "warn"})
    return p.name


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--date", help="数据日期（昨日），YYYY-MM-DD")
    a = ap.parse_args()
    src = Path(a.src) if a.src else clean.latest_src()
    ddate = dt.date.fromisoformat(a.date) if a.date else C.default_data_date()

    data = clean.run(src)
    C.DATA_DIR.mkdir(exist_ok=True)
    C.OUTPUT_DIR.mkdir(exist_ok=True)
    (C.DATA_DIR / "clean.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    yfile = load_perf(C.YDAY_FILE_GLOB, C.YDAY_COLS, data, "昨日")
    dfile = load_perf(C.D11_FILE_GLOB, C.D11_COLS, data, "双十一期间")

    elapsed = max(0, min((ddate - C.D11_START).days + 1, C.D11_TOTAL_DAYS))
    ctypes = C.CTYPES[:-1] + sorted({c["ctype"] for i in data["industries"] for c in i["customers"]} - set(C.CTYPES)) + C.CTYPES[-1:]
    data["meta"] = {
        "source": data["source"], "source_mtime": data["source_mtime"],
        "built_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_date": ddate.isoformat(), "d11_start": C.D11_START.isoformat(), "d11_end": C.D11_END.isoformat(),
        "d11_total": C.D11_TOTAL_DAYS, "d11_elapsed": elapsed, "cost_div": C.COST_UNIT_DIVISOR,
        "ctypes": ctypes, "yday_file": yfile, "d11_file": dfile,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = C.TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out = C.OUTPUT_DIR / "客户监控看板.html"
    out.write_text(html, encoding="utf-8")
    clean.export_excel(data, C.OUTPUT_DIR / "清洗结果.xlsx")

    n = sum(len(i["customers"]) for i in data["industries"])
    print(f"源表: {src.name} | 客户 {n} 家 | 数据日期 {ddate} | 双十一已过 {elapsed}/{C.D11_TOTAL_DAYS} 天")
    print(f"昨日数据: {yfile or '未提供'} | 双十一数据: {dfile or '未提供'}")
    print(f"看板: {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"清洗结果: {C.OUTPUT_DIR / '清洗结果.xlsx'}")


if __name__ == "__main__":
    main()
