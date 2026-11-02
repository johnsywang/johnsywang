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


def alias_index(data):
    idx = {}
    for ind in data["industries"]:
        for c in ind["customers"]:
            for a in dict.fromkeys(x.strip() for x in c["aliases"] + [c["name"]]):
                if c not in idx.setdefault(a, []):
                    idx[a].append(c)
    return idx


def find_book(arg):
    if arg:
        return Path(arg)
    for d in (C.INPUT_DIR, C.DESKTOP):
        fs = [p for p in d.glob(C.PERF_BOOK_GLOB) if not p.name.startswith("~$")] if d.exists() else []
        if fs:
            return max(fs, key=lambda p: p.stat().st_mtime)
    return None


def book_date(p: Path):
    """文件名「客户数据11.1」-> 2026-11-01（Q4 内月份取 Q_START 的年份，跨年月份顺延一年）。"""
    m = re.search(r"(\d{1,2})[.\-_月](\d{1,2})", p.stem)
    if not m:
        return None
    mo, d = int(m.group(1)), int(m.group(2))
    y = C.Q_START.year + (1 if mo < C.Q_START.month else 0)
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def book_num(v):
    """BI 导出：「~」= 该期无数据，按 0 计（这样汇总时本期/对比期都能正常加总）；「+∞」等非数值忽略。"""
    if isinstance(v, str) and v.strip() == "~":
        return 0.0
    return to_num(v)


def load_book(p: Path, data):
    """读多 sheet 客户数据：每个 sheet 对应 昨日 / 双十一期间 / QTD，指标列的下一列为对比值。
    只取客户行的本期值和对比期值；汇总层的同环比由看板先加总再计算，不使用单客户变化率。"""
    from python_calamine import CalamineWorkbook
    wb = CalamineWorkbook.from_path(str(p))
    idx = alias_index(data)
    norm = lambda h: re.sub(r"\s", "", str(h or "")).lower()
    seen, tags = set(), []
    for sn in wb.sheet_names:
        spec = next((v for k, v in C.PERF_BOOK_SHEETS.items() if k.lower() in sn.lower()), None)
        if not spec:
            data["issues"].append({"industry": "", "customer": "", "field": "客户数据", "raw": f"{p.name}/{sn}", "msg": "未识别的 sheet，已跳过", "level": "warn"})
            continue
        tag, metrics = spec
        rows = wb.get_sheet_by_name(sn).to_python()
        hdr = [norm(h) for h in rows[0]]
        name_col = next((j for j, h in enumerate(hdr) if h in ("客户简称", "主计客户简称", "客户")), None)
        if name_col is None:
            raise ValueError(f"{p.name}/{sn} 未找到客户简称列；表头：{rows[0]}")
        cols = {}
        for j, h in enumerate(hdr):
            if "对比" in h or "变化" in h:
                continue
            for pre, (ck, pk) in metrics.items():
                if h.startswith(norm(pre)) and ck not in cols:
                    cols[ck] = j
                    if j + 1 < len(hdr) and "对比值" in hdr[j + 1]:
                        cols[pk] = j + 1
        miss = [pre for pre, (ck, pk) in metrics.items() if ck not in cols or pk not in cols]
        if miss:
            raise ValueError(f"{p.name}/{sn} 缺少指标列或对比值列：{miss}；表头：{rows[0]}")
        total, sums, unmatched = None, {k: 0.0 for k in cols}, []
        for r in rows[1:]:
            nm = str(r[name_col] if name_col < len(r) else "").strip()
            if not nm:
                continue
            vals = {k: book_num(r[j]) if j < len(r) else None for k, j in cols.items()}
            if nm == C.PERF_BOOK_TOTAL_ROW:
                total = vals
                continue
            targets = idx.get(nm)
            if not targets:
                unmatched.append(nm)
                continue
            for k, v in vals.items():
                if v is None:
                    continue
                sums[k] += v
                for c in targets:
                    perf = c.setdefault("perf", {})
                    perf[k] = perf.get(k, 0) + v
            for c in targets:
                seen.add((tag, id(c)))
        for nm in unmatched:
            data["issues"].append({"industry": "", "customer": nm, "field": f"{tag}数据", "raw": f"{p.name}/{sn}", "msg": "客户数据中的客户未在盘点表中找到，未计入", "level": "warn"})
        if total:
            for k, t in total.items():
                if t is not None and abs(sums[k] - t) > max(1.0, abs(t) * 1e-4):
                    why = ("客户数据全部已匹配，差异来自 BI 整体汇总行的去重统计口径；看板按客户加总" if not unmatched
                           else "已匹配客户加总与 BI 整体汇总行不一致（有客户未匹配）")
                    data["issues"].append({"industry": "", "customer": "", "field": f"{tag}数据/{k}", "raw": f"客户加总 {sums[k]:,.2f} vs 整体 {t:,.2f}", "msg": why, "level": "info" if not unmatched else "warn"})
        tags.append(f"{sn}(匹配{sum(1 for (t, _) in seen if t == tag)}家)")
    for ind in data["industries"]:
        for c in ind["customers"]:
            lost = [t for t in {v[0] for v in C.PERF_BOOK_SHEETS.values()} if (t, id(c)) not in seen]
            if lost:
                data["issues"].append({"industry": c.get("industry", ""), "customer": c["name"], "field": "客户数据", "raw": p.name, "msg": f"客户数据中没有该客户的 {'/'.join(sorted(lost))} 数据，看板显示待补充", "level": "warn"})
    return f"{p.name}：" + "、".join(tags)


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
    idx = alias_index(data)
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
    ap.add_argument("--date", help="数据日期（昨日），YYYY-MM-DD；不填时优先取客户数据文件名中的日期")
    ap.add_argument("--perf", help="多 sheet 客户数据 xlsx（默认 input/ 或桌面最新「客户数据*.xlsx」）")
    a = ap.parse_args()
    src = Path(a.src) if a.src else clean.latest_src()
    book = find_book(a.perf)
    ddate = dt.date.fromisoformat(a.date) if a.date else (book and book_date(book)) or C.default_data_date()

    data = clean.run(src)
    C.DATA_DIR.mkdir(exist_ok=True)
    C.OUTPUT_DIR.mkdir(exist_ok=True)
    (C.DATA_DIR / "clean.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    if book:
        yfile = dfile = qfile = load_book(book, data)
    else:
        yfile = load_perf(C.YDAY_FILE_GLOB, C.YDAY_COLS, data, "昨日")
        dfile = load_perf(C.D11_FILE_GLOB, C.D11_COLS, data, "双十一期间")
        qfile = load_perf(C.QTD_FILE_GLOB, C.QTD_COLS, data, "QTD")
    perf_src = yfile if book else " / ".join(x for x in (yfile, dfile, qfile) if x)

    elapsed = max(0, min((ddate - C.D11_START).days + 1, C.D11_TOTAL_DAYS))
    q_days = max(0, (ddate - C.Q_START).days + 1)
    # QTD 日耗：优先用直接提供的日耗，否则 累计消耗 ÷ QTD天数；去年同期按相同天数换算
    for ind in data["industries"]:
        for c in ind["customers"]:
            p = c.get("perf")
            if not p or not q_days:
                continue
            for day_k, cost_k in (("q_day", "q_cost"), ("q_day_ly", "q_cost_ly")):
                if day_k not in p and cost_k in p:
                    p[day_k] = p[cost_k] / q_days
    used = {c["ctype"] for i in data["industries"] for c in i["customers"]}
    # 「未标注」默认不展示，仅在确有客户未填写客户类型时才出现，避免这些客户在分类汇总中被漏掉
    ctypes = [t for t in C.CTYPES if t != C.CTYPE_EMPTY] + sorted(used - set(C.CTYPES))
    if C.CTYPE_EMPTY in used:
        ctypes.append(C.CTYPE_EMPTY)
    data["meta"] = {
        "source": data["source"], "source_mtime": data["source_mtime"],
        "built_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_date": ddate.isoformat(), "d11_start": C.D11_START.isoformat(), "d11_end": C.D11_END.isoformat(),
        "d11_total": C.D11_TOTAL_DAYS, "d11_elapsed": elapsed,
        "q_start": C.Q_START.isoformat(), "q_days": q_days, "qtd_file": qfile, "cost_div": C.COST_UNIT_DIVISOR,
        "ctypes": ctypes, "yday_file": yfile, "d11_file": dfile, "perf_src": perf_src, "playbook": C.CT_PLAYBOOK,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = C.TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out = C.OUTPUT_DIR / "客户监控看板.html"
    out.write_text(html, encoding="utf-8")
    clean.export_excel(data, C.OUTPUT_DIR / "清洗结果.xlsx")

    n = sum(len(i["customers"]) for i in data["industries"])
    print(f"源表: {src.name} | 客户 {n} 家 | 数据日期 {ddate} | 双十一已过 {elapsed}/{C.D11_TOTAL_DAYS} 天")
    if book:
        print(f"客户数据: {yfile}")
    else:
        print(f"昨日数据: {yfile or '未提供'} | 双十一数据: {dfile or '未提供'} | QTD数据: {qfile or '未提供（或已含在昨日文件中）'}")
    print(f"看板: {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"清洗结果: {C.OUTPUT_DIR / '清洗结果.xlsx'}")


if __name__ == "__main__":
    main()
