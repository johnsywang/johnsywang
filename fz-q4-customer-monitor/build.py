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


def nkey(s):
    """客户名匹配键：去空白、不区分大小写（SIINSIIN = siinsiin）。"""
    return re.sub(r"\s", "", str(s or "")).lower()


def alias_index(data):
    idx = {}
    for ind in data["industries"]:
        for c in ind["customers"]:
            for a in dict.fromkeys(nkey(x) for x in c["aliases"] + [c["name"]]):
                if c not in idx.setdefault(a, []):
                    idx[a].append(c)
    return idx


def _blank_customer(name, industry, ctype):
    """盘点表中没有的手动补充客户：盘点类字段全部按「未填写」处理，结构与 clean.py 输出一致。"""
    E = lambda: {"raw": "", "val": None}
    Y = lambda: {"raw": "", "val": None, "label": None}
    return {
        "industry": industry, "name": name, "aliases": [name], "sales": "",
        "biz": {"gmv_all": E(), "gmv_vx": E(), "ams": E(), "gmv_all_yoy": Y(), "gmv_vx_yoy": Y(), "ams_yoy": Y(), "vx_share": E(), "vx_tr": E()},
        "staff": {"adq_desc": "", "adq_fulltime": 0, "adq_fulltime_note": "", "dou_raw": "", "dou_text": "", "dou_pct": None, "adq_pct": None, "roi_note": "", "dou_msg": "未填写"},
        "ctype": ctype, "ctype_reason": "",
        "d11": {"signup": "未填写", "big_dates": "未填写", "stock": "未填写", "cost_target_raw": "", "cost_target": None, "gmv_target_raw": "", "gmv_target": None},
        "goods": {m: {"季节品": [], "常规品": []} for m in ("10月", "11月", "12月")},
        "q4_season": 0, "q4_regular": 0, "q4_season_items": [], "q4_regular_items": [],
        "manual": True,
    }


def apply_scope(data):
    """按 config.KEEP_CUSTOMERS 收窄客户范围，并补充 EXTRA_CUSTOMERS（盘点表中没有的客户）。"""
    inds = {i["name"]: i for i in data["industries"]}
    for e in C.EXTRA_CUSTOMERS:
        if nkey(e["name"]) in alias_index(data):
            continue
        ind = inds.get(e["industry"])
        if ind is None:
            ind = inds[e["industry"]] = {"name": e["industry"], "maps": [], "customers": []}
            data["industries"].append(ind)
        ind["customers"].append(_blank_customer(e["name"], e["industry"], e.get("ctype") or C.CTYPE_EMPTY))
        data["issues"].append({"industry": e["industry"], "customer": e["name"], "field": "客户范围", "raw": "config.EXTRA_CUSTOMERS",
                               "msg": f"盘点表中无该客户，按配置手动新增（客户类型：{e.get('ctype') or C.CTYPE_EMPTY}）；盘点类信息待补充", "level": "info"})
    if C.KEEP_CUSTOMERS is None:
        return
    keep = {nkey(x): x for x in C.KEEP_CUSTOMERS}
    hit = set()
    for ind in data["industries"]:
        kept = []
        for c in ind["customers"]:
            ks = {nkey(x) for x in c["aliases"] + [c["name"]]} & keep.keys()
            if ks:
                kept.append(c)
                hit |= ks
        ind["customers"] = kept
    data["industries"] = [i for i in data["industries"] if i["customers"]]
    names = {nkey(c["name"]) for i in data["industries"] for c in i["customers"]}
    data["issues"] = [x for x in data["issues"] if not x.get("customer") or nkey(x["customer"]) in names]
    for k in keep.keys() - hit:
        data["issues"].append({"industry": "", "customer": keep[k], "field": "客户范围", "raw": "config.KEEP_CUSTOMERS",
                               "msg": "保留名单中的客户在盘点表中找不到，也未在 EXTRA_CUSTOMERS 中配置，未展示", "level": "warn"})


def find_book(arg):
    """客户数据：--perf 指定 > input/ 与桌面中文件名日期最新的一份（同日期取修改时间最新）。"""
    if arg:
        return Path(arg)
    fs = [p for d in (C.INPUT_DIR, C.DESKTOP) if d.exists() for p in d.glob(C.PERF_BOOK_GLOB) if not p.name.startswith("~$")]
    if not fs:
        return None
    return max(fs, key=lambda p: (book_date(p) or dt.date.min, p.stat().st_mtime))


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
        if not cols:
            raise ValueError(f"{p.name}/{sn} 未找到任何指标列（{list(metrics)}）；表头：{rows[0]}")
        for pre, (ck, pk) in metrics.items():
            if ck in cols and pk not in cols:
                data["issues"].append({"industry": "", "customer": "", "field": f"{tag}数据/{ck}", "raw": f"{p.name}/{sn}", "msg": f"「{pre}」后没有对比值列，同环比显示待补充", "level": "warn"})
        total, sums, unmatched = None, {k: 0.0 for k in cols}, []
        for r in rows[1:]:
            nm = str(r[name_col] if name_col < len(r) else "").strip()
            if not nm:
                continue
            vals = {k: book_num(r[j]) if j < len(r) else None for k, j in cols.items()}
            if nm == C.PERF_BOOK_TOTAL_ROW:
                total = vals
                continue
            targets = idx.get(nkey(nm))
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
            data["issues"].append({"industry": "", "customer": nm, "field": f"{tag}数据", "raw": f"{p.name}/{sn}", "msg": "客户数据中的客户不在看板客户范围内，未计入", "level": "warn"})
        n_all = sum(len(i["customers"]) for i in data["industries"])
        n_hit = sum(1 for (t, _) in seen if t == tag)
        if total:
            for k, t in total.items():
                if t is not None and abs(sums[k] - t) > max(1.0, abs(t) * 1e-4):
                    if unmatched:
                        why, lv = "已匹配客户加总与 BI 整体汇总行不一致（有客户未匹配）", "warn"
                    elif n_hit < n_all and abs(sums[k] - t) > abs(t) * 0.01:
                        why, lv = f"该 sheet 只列出 {n_hit}/{n_all} 家客户，整体汇总行含未列出客户；看板按已列出客户加总，未列出客户显示待补充", "warn"
                    else:
                        why, lv = "客户全部已匹配，差异来自 BI 整体汇总行的去重统计口径；看板按客户加总", "info"
                    data["issues"].append({"industry": "", "customer": "", "field": f"{tag}数据/{k}", "raw": f"客户加总 {sums[k]:,.2f} vs 整体 {t:,.2f}", "msg": why, "level": lv})
        tags.append(f"{sn}(匹配{n_hit}/{n_all}家)")
    present = {v[0] for k, v in C.PERF_BOOK_SHEETS.items() if any(k.lower() in sn.lower() for sn in wb.sheet_names)}
    for ind in data["industries"]:
        for c in ind["customers"]:
            lost = [t for t in present if (t, id(c)) not in seen]
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
        targets = idx.get(nkey(nm))
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
    apply_scope(data)
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
    # QTD：日耗与累计消耗互推（日耗 = 累计 ÷ QTD天数；累计 = 日耗 × QTD天数），去年同期按相同天数换算
    for ind in data["industries"]:
        for c in ind["customers"]:
            p = c.get("perf")
            if not p or not q_days:
                continue
            for day_k, cost_k in (("q_day", "q_cost"), ("q_day_ly", "q_cost_ly")):
                if day_k not in p and cost_k in p:
                    p[day_k] = p[cost_k] / q_days
                elif cost_k not in p and day_k in p:
                    p[cost_k] = p[day_k] * q_days
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
