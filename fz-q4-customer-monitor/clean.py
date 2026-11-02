"""源表清洗：服饰Q4客户&商品盘点.xlsx -> data/clean.json + 品类地图图片。

清洗规则详见 README.md「清洗规则」章节，修改规则时两边同步。
"""
import argparse
import base64
import datetime as dt
import io
import json
import math
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

from python_calamine import CalamineWorkbook

import config as C

INF = math.inf
NUM = r"\d+(?:\.\d+)?"
issues = []  # 数据质量问题：{industry, customer, field, raw, msg}


def note(ind, cust, field, raw, msg, level="warn"):
    """level: warn=需人工确认；info=已按规则自动解析，仅留痕。"""
    issues.append({"industry": ind, "customer": cust, "field": field, "raw": s(raw), "msg": msg, "level": level})


def s(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (dt.date, dt.datetime)):
        return f"{v.month}月{v.day}日"
    return str(v).strip()


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------- 数值解析
def parse_amount(v):
    """金额（万元）：数值直接用；文本提取数字，区间/多个数字取最大值。'w'/'万' 均视为万元。"""
    if is_num(v):
        return float(v)
    t = s(v)
    nums = [float(x) for x in re.findall(NUM, t)]
    return max(nums) if nums else None


def parse_yoy(v):
    """年同比 -> 小数（0.05=+5%）；+∞ 用 INF；无法解析返回 None。"""
    if is_num(v):
        return float(v)
    t = s(v).replace(" ", "")
    if not t or t in {"/", "-", "—"}:
        return None
    if "∞" in t:
        return INF
    m = re.search(rf"(增长|上涨|提升|下滑|下跌|下降)({NUM})(?:[-~～]({NUM}))?%", t)
    if m:
        val = float(m.group(3) or m.group(2)) / 100
        return -val if m.group(1) in ("下滑", "下跌", "下降") else val
    if "持平" in t:
        return 0.0
    if re.search(r"没怎么做|没有怎么搞|挂机|基本为0", t):
        return INF  # 去年基数≈0，视为从无到有
    m = re.fullmatch(rf"([+-]?{NUM})%\+?", t)
    if m:
        return float(m.group(1)) / 100
    return None


def yoy_label(x):
    if x is None:
        return ""
    if x == INF:
        return "+∞"
    if abs(x) < 1e-9:
        return "持平"
    return f"{x * 100:+.0f}%"


def parse_ratio(v):
    """占比类（视频号占比/TR）：数值直接用，文本不可解析 -> None。"""
    if is_num(v):
        return float(v)
    t = s(v)
    m = re.fullmatch(rf"({NUM})%", t)
    return float(m.group(1)) / 100 if m else None


# ---------------------------------------------------------------- 人力：adq 专职投手数
def parse_adq_fulltime(desc):
    """仅当描述含「独立」或「专职」时计数，否则 0。返回 (数量, 说明)。"""
    t = s(desc).lower()
    if not t or not ("独立" in t or "专职" in t):
        return 0, ""
    pats = [
        (rf"({NUM})\s*组独立", "按独立组数计"),
        (rf"({NUM})\s*个组是独立", "按独立组数计"),
        (rf"adq\s*({NUM})\s*人", ""),
        (rf"({NUM})\s*个?\s*(?:投手)?\s*(?:专职)?\s*adq", ""),
        (rf"({NUM})\s*个投手专职", ""),
        (rf"({NUM})\s*(?:人|个)", "按团队人数计"),
    ]
    for p, msg in pats:
        m = re.search(p, t)
        if m:
            n = float(m.group(1))
            return (int(n) if n.is_integer() else n), msg
    return 1, "独立团队未注明人数，暂按 1 计"


# ---------------------------------------------------------------- 微信豆 / ADQ 份额
def parse_dou(v):
    """统一为「微信豆xx%，adqxx%」。返回 (dou%, adq%, 规范文本, ROI备注, 问题说明)。"""
    if is_num(v):
        return None, None, "", "", f"仅填写数字「{s(v)}」，无法判断含义"
    raw = s(v)
    t = raw.replace(" ", "").replace("：", ":").replace("，", ",")
    tl = t.lower()
    roi = []
    m1 = re.search(rf"微信豆[^●\n]*?roi({NUM})", tl)
    m2 = re.search(rf"adq[^●\n]*?roi({NUM})", tl)
    if m1:
        roi.append(f"豆ROI {m1.group(1)}")
    if m2:
        roi.append(f"ADQ ROI {m2.group(1)}")
    roi = "｜".join(roi)
    dou = adq = None
    if not t:
        return None, None, "", "", "未填写"
    if re.search(r"全(部)?adq|几乎全adq|豆子不怎么投", tl) or re.fullmatch(r"adq=1", tl):
        dou, adq = 0, 1
    elif (m := re.search(rf"adq与微信豆消耗占比:?({NUM})%,({NUM})%", tl)):
        adq, dou = float(m.group(1)), float(m.group(2))
    elif (m := re.search(rf"adq:微信豆约?({NUM}):({NUM})", tl)):
        adq, dou = float(m.group(1)), float(m.group(2))
    elif (m := re.search(rf"微信豆:adq=?约?({NUM}):({NUM})", tl)):
        dou, adq = float(m.group(1)), float(m.group(2))
    elif "消耗" in tl:
        md = re.search(rf"微信豆消耗({NUM})(?:[-~～]({NUM}))?", tl)
        ma = re.search(rf"adq消耗({NUM})(?:[-~～]({NUM}))?", tl)
        if md and ma:
            dou = float(md.group(2) or md.group(1))
            adq = float(ma.group(2) or ma.group(1))
        else:
            return None, None, "", roi, "微信豆或ADQ消耗金额缺失，无法计算份额"
    elif (md := re.search(rf"微信豆({NUM})%?", tl)) and (ma := re.search(rf"adq({NUM})%?", tl)):
        dou, adq = float(md.group(1)), float(ma.group(1))
    if dou is None or adq is None or dou + adq == 0:
        return None, None, "", roi, "无法识别格式"
    dp = round(dou / (dou + adq) * 100)
    return dp, 100 - dp, f"微信豆{dp}%，adq{100 - dp}%", roi, ""


# ---------------------------------------------------------------- 双十一字段
def norm_stock(v):
    t = s(v)
    if t in ("是", "充足"):
        return "充足"
    if t in ("否", "不足"):
        return "不足"
    return t or "未填写"


def norm_dates(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return f"{v.month}月{v.day}日"
    if is_num(v):
        return f"{int(v)}日"
    return s(v) or "未填写"


# ---------------------------------------------------------------- 商品拆分
SPLIT_CHARS = set("\n、，,；;/ \t")
EMPTY_ITEMS = {"", "/", "无", "-", "暂无", "—"}


def split_items(v):
    """按 换行/、/，/;/斜杠/空格 拆分（括号内不拆），返回 [{name, n}]，n 为「（N款）」款数，默认 1。"""
    t = s(v)
    out, buf, depth = [], "", 0
    for ch in t + "\n":
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(depth - 1, 0)
        if ch in SPLIT_CHARS and depth == 0:
            if buf.strip() not in EMPTY_ITEMS:
                out.append(buf.strip())
            buf = ""
        else:
            buf += ch
    res = []
    for name in out:
        m = re.search(r"[（(](\d+)款[）)]", name)
        res.append({"name": name, "n": int(m.group(1)) if m else 1})
    return res


# ---------------------------------------------------------------- 客户分类
def norm_ctype(v):
    """直接使用源表「客户类型」列，只做写法归一。返回 (标准类型, 原文说明, 是否识别)。
    标准类型见 config.CTYPES；空值 -> 未标注；无法归入 4 类的保留原文。"""
    raw = s(v)
    t = re.sub(r"^\s*\d+\s*[、.．]\s*", "", raw).replace(" ", "")
    if not t:
        return C.CTYPE_EMPTY, "", True
    tl = t.lower()
    if "挤压" in tl:
        std = "adq被豆子挤压"
    elif "均下跌" in tl or ("微信豆" in tl and "adq" in tl and "下跌" in tl):
        std = "视频号微信豆和adq均下跌"
    elif "全平台" in tl and ("下跌" in tl or "下滑" in tl):
        std = "全平台生意下跌"
    elif "视频号" in tl and "增长" in tl:
        std = "视频号生意增长"
    else:
        return raw, f"原文：{raw}", False
    return std, ("" if t == std else f"原文：{raw}"), True


# ---------------------------------------------------------------- 读表
def find_header(rows):
    for i, r in enumerate(rows):
        if r and s(r[0]).startswith("主计客户简称"):
            return i
    raise ValueError("未找到「主计客户简称」表头行")


def build_colmap(rows, h):
    """用表头文字定位列，避免列顺序变化导致错位。重复的「年同比」以前一列名前缀区分。"""
    sub, sub2 = rows[h + 1], rows[h + 2]
    cmap, prev, month = {}, "", ""
    for j in range(len(sub)):
        name = s(sub[j])
        if re.fullmatch(r"\d+月", name):
            month = name
        if month and s(sub2[j]) in ("季节品", "常规品"):
            cmap[f"{month}_{s(sub2[j])}"] = j
            continue
        if not name:
            continue
        if name.startswith("客户类型"):
            name = "客户类型"  # 表头内含 1~4 类说明的多行文字，只取前缀
        key = f"{prev}_年同比" if name == "年同比" else name
        cmap[key] = j
        if name != "年同比":
            prev = name
    for j, v in enumerate(rows[h]):
        if s(v) == "销售":
            cmap["销售"] = j
    return cmap


COLS = {
    "gmv_all": "全平台日均GMV（万元）",
    "gmv_all_yoy": "全平台日均GMV（万元）_年同比",
    "gmv_vx": "视频号日均GMV（万元）",
    "gmv_vx_yoy": "视频号日均GMV（万元）_年同比",
    "vx_share": "视频号占比",
    "vx_tr": "视频号TR",
    "ams": "ams日耗（万元）",
    "ams_yoy": "ams日耗（万元）_年同比",
    "ctype": "客户类型",
    "adq_desc": "adq投手情况盘点",
    "dou": "微信豆投放摸底",
    "signup": "双十一小店活动报名情况",
    "big_dates": "双11大场规划日期（单场gmv＞50万）",
    "stock": "双11微信小店现货库存是否充足",
    "cost_target": "双11期间日均消耗目标（万元）",
    "gmv_target": "双11期间日均GMV目标（万元）",
    "sales": "销售",
}
MONTHS = ["10月", "11月", "12月"]


def sheet_images(z):
    """sheet 名 -> 图片 bytes（解析 workbook/sheet/drawing 三层 rels）。"""
    def rels(path):
        p = PurePosixPath(path)
        rp = f"{p.parent}/_rels/{p.name}.rels"
        if rp not in z.namelist():
            return {}
        xml = z.read(rp).decode("utf-8")
        out = {}
        for m in re.finditer(r'<Relationship[^>]*?Id="([^"]+)"[^>]*?Target="([^"]+)"', xml):
            out[m.group(1)] = str(PurePosixPath(p.parent, m.group(2)))
        for m in re.finditer(r'<Relationship[^>]*?Target="([^"]+)"[^>]*?Id="([^"]+)"', xml):
            out[m.group(2)] = str(PurePosixPath(p.parent, m.group(1)))
        return out

    def norm(p):
        parts = []
        for x in p.split("/"):
            if x == "..":
                parts.pop()
            elif x and x != ".":
                parts.append(x)
        return "/".join(parts)

    wb_xml = z.read("xl/workbook.xml").decode("utf-8")
    wb_rels = rels("xl/workbook.xml")
    res = {}
    for m in re.finditer(r'<sheet [^>]*?name="([^"]+)"[^>]*?r:id="([^"]+)"', wb_xml):
        name, rid = m.group(1), m.group(2)
        sp = norm(wb_rels.get(rid, ""))
        imgs = []
        for _, dp in rels(sp).items():
            dp = norm(dp)
            if "drawing" not in dp:
                continue
            for _, ip in rels(dp).items():
                ip = norm(ip)
                if ip in z.namelist() and re.search(r"\.(png|jpe?g|gif|bmp)$", ip, re.I):
                    imgs.append(z.read(ip))
        res[name] = imgs
    return res


def to_jpeg_b64(data, max_w=2000):
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


YOY_KEYS = ("gmv_all_yoy", "gmv_vx_yoy", "ams_yoy")


def yoy_scales(rows, h, cmap):
    """按 sheet 判断各年同比列的数值口径：列内数值的绝对值中位数 > 5 视为百分数（-89.59 = -89.59%），需 ÷100；
    否则为小数口径（1.082 = +108.2%）。源表不同 sheet 口径可能不一致（如内衣 ams 年同比为百分数）。"""
    out = {}
    for k in YOY_KEYS:
        j = cmap.get(COLS[k])
        vals = sorted(abs(r[j]) for r in rows[h + 3:] if j is not None and j < len(r) and is_num(r[j]) and r[j] != 0)
        out[k] = 100 if vals and vals[len(vals) // 2] > 5 else 1
    return out


def clean_customer(ind, r, cmap, scales=None):
    scales = scales or {}
    g = lambda k: r[cmap[COLS[k]]] if COLS[k] in cmap and cmap[COLS[k]] < len(r) else ""
    name = s(r[0])
    aliases = [a.strip() for a in re.split(r"[\n、/，,]", name) if a.strip()]
    c = {"industry": ind, "name": aliases[0] if aliases else name, "aliases": aliases, "sales": s(g("sales"))}

    biz = {}
    for k in ("gmv_all", "gmv_vx", "ams"):
        raw = g(k)
        val = parse_amount(raw)
        biz[k] = {"raw": s(raw), "val": val}
        if s(raw) and val is None:
            note(ind, c["name"], COLS[k], raw, "无法解析为数值")
        elif s(raw) and not is_num(raw):
            note(ind, c["name"], COLS[k], raw, f"文本已解析为 {val:g} 万元（区间/多值取最大）", "info")
    for k in YOY_KEYS:
        raw = g(k)
        val = parse_yoy(raw)
        if is_num(raw) and scales.get(k, 1) != 1:
            val = raw / scales[k]
        biz[k] = {"raw": s(raw), "val": None if val is None else ("inf" if val == INF else val), "label": yoy_label(val)}
        if is_num(val) and val != INF and abs(val) > 50:
            note(ind, c["name"], COLS[k], raw, f"年同比 {yoy_label(val)} 异常偏大，请核对源表口径（小数/百分数）")
        if s(raw) and val is None:
            note(ind, c["name"], COLS[k], raw, "年同比无法解析")
        elif s(raw) and not is_num(raw) and s(raw).strip() not in ("+∞", "持平"):
            note(ind, c["name"], COLS[k], raw, f"文本已解析为 {yoy_label(val)}", "info")
    for k in ("vx_share", "vx_tr"):
        raw = g(k)
        val = parse_ratio(raw)
        biz[k] = {"raw": s(raw), "val": val}
        if s(raw) and val is None:
            note(ind, c["name"], COLS[k], raw, "非数值，已保留原文")
    if "抖音" in biz["gmv_all"]["raw"]:
        biz["gmv_all"]["note"] = "抖音口径"
    c["biz"] = biz

    adq_desc = s(g("adq_desc"))
    n, n_note = parse_adq_fulltime(adq_desc)
    dp, ap, dtxt, roi, dmsg = parse_dou(g("dou"))
    if dmsg and dmsg != "未填写":
        note(ind, c["name"], COLS["dou"], g("dou"), dmsg)
    if n_note:
        note(ind, c["name"], "adq专职投手数量", adq_desc, f"计 {n}：{n_note}")
    c["staff"] = {"adq_desc": adq_desc, "adq_fulltime": n, "adq_fulltime_note": n_note,
                  "dou_raw": s(g("dou")), "dou_text": dtxt, "dou_pct": dp, "adq_pct": ap,
                  "roi_note": roi, "dou_msg": dmsg}

    ctype, creason, known = norm_ctype(g("ctype"))
    c["ctype"], c["ctype_reason"] = ctype, creason
    if not known:
        note(ind, c["name"], "客户类型", g("ctype"), "无法归入 4 类标准类型，已按原文单独成类")
    elif ctype == C.CTYPE_EMPTY:
        note(ind, c["name"], "客户类型", "", "客户类型未填写")
    elif creason:
        note(ind, c["name"], "客户类型", g("ctype"), f"写法已归一为「{ctype}」", "info")

    ct_raw, gt_raw = g("cost_target"), g("gmv_target")
    c["d11"] = {
        "signup": s(g("signup")) or "未填写",
        "big_dates": norm_dates(g("big_dates")),
        "stock": norm_stock(g("stock")),
        "cost_target_raw": s(ct_raw), "cost_target": parse_amount(ct_raw),
        "gmv_target_raw": s(gt_raw), "gmv_target": parse_amount(gt_raw),
    }

    goods, q4 = {}, {"季节品": {}, "常规品": {}}
    for mo in MONTHS:
        goods[mo] = {}
        for tp in ("季节品", "常规品"):
            key = f"{mo}_{tp}"
            items = split_items(r[cmap[key]]) if key in cmap and cmap[key] < len(r) else []
            goods[mo][tp] = items
            for it in items:
                q4[tp].setdefault(it["name"], it["n"])
    c["goods"] = goods
    c["q4_season"] = sum(q4["季节品"].values())
    c["q4_regular"] = sum(q4["常规品"].values())
    c["q4_season_items"] = list(q4["季节品"])
    c["q4_regular_items"] = list(q4["常规品"])
    return c


def merge_dup(a, b):
    """同名客户合并：空值用后者补；两者都有且不同的文本以「；」拼接；商品取并集。"""
    def m(x, y):
        if isinstance(x, dict):
            return {k: m(x.get(k), y.get(k)) for k in x}
        if x in (None, "", "未填写"):
            return y
        if y in (None, "", "未填写") or x == y:
            return x
        if isinstance(x, str) and isinstance(y, str):
            return f"{x}；{y}"
        return x
    out = m(a, b)
    src = a if a["ctype"] != C.CTYPE_EMPTY or b["ctype"] == C.CTYPE_EMPTY else b
    out["ctype"], out["ctype_reason"] = src["ctype"], src["ctype_reason"]
    for k in ("dou_pct", "adq_pct", "adq_fulltime"):
        out["staff"][k] = a["staff"][k] if a["staff"][k] not in (None, 0) else b["staff"][k]
    for mo in MONTHS:
        for tp in ("季节品", "常规品"):
            seen = {i["name"] for i in a["goods"][mo][tp]}
            out["goods"][mo][tp] = a["goods"][mo][tp] + [i for i in b["goods"][mo][tp] if i["name"] not in seen]
    for tp, k in (("季节品", "q4_season"), ("常规品", "q4_regular")):
        allit = {}
        for mo in MONTHS:
            for it in out["goods"][mo][tp]:
                allit.setdefault(it["name"], it["n"])
        out[k] = sum(allit.values())
        out[f"{k}_items"] = list(allit)
    return out


def run(src: Path):
    issues.clear()
    wb = CalamineWorkbook.from_path(str(src))
    z = zipfile.ZipFile(src)
    imgs = sheet_images(z)
    industries = []
    for ind in wb.sheet_names:
        rows = wb.get_sheet_by_name(ind).to_python()
        h = find_header(rows)
        cmap = build_colmap(rows, h)
        miss = [v for v in COLS.values() if v not in cmap]
        for v in miss:
            note(ind, "", v, "", "表头未找到该列")
        scales = yoy_scales(rows, h, cmap)
        for k, sc in scales.items():
            if sc != 1:
                note(ind, "（整列）", COLS[k], "", "该列数值为百分数口径（如 -89.59 表示 -89.59%），已统一 ÷100 换算为小数", "info")
        custs = {}
        for i in range(h + 3, len(rows)):
            r = rows[i]
            if not any(s(x) for x in r):
                continue
            if not s(r[0]):
                note(ind, f"第{i + 1}行", "主计客户简称", "", "客户名为空，整行已跳过")
                continue
            c = clean_customer(ind, r, cmap, scales)
            if c["name"] in custs:
                note(ind, c["name"], "主计客户简称", c["name"], f"同名客户重复（第{i + 1}行），已合并为一行")
                custs[c["name"]] = merge_dup(custs[c["name"]], c)
            else:
                custs[c["name"]] = c
        maps = [to_jpeg_b64(b) for b in imgs.get(ind, [])]
        industries.append({"name": ind, "maps": maps, "customers": list(custs.values())})
    return {
        "source": src.name,
        "source_mtime": dt.datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        "cleaned_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "industries": industries,
        "issues": issues[:],
    }


def latest_src():
    cands = sorted(C.DESKTOP.glob(C.SRC_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        raise FileNotFoundError(f"桌面未找到 {C.SRC_GLOB}")
    return cands[0]


def export_excel(data, path):
    import pandas as pd
    rows, goods = [], []
    for ind in data["industries"]:
        for c in ind["customers"]:
            b, st, d = c["biz"], c["staff"], c["d11"]
            rows.append({
                "行业": ind["name"], "客户": c["name"], "销售": c["sales"], "客户类型": c["ctype"], "客户类型备注": c["ctype_reason"],
                "全平台日均GMV(万)": b["gmv_all"]["val"], "全平台年同比": b["gmv_all_yoy"]["label"],
                "视频号日均GMV(万)": b["gmv_vx"]["val"], "视频号年同比": b["gmv_vx_yoy"]["label"],
                "视频号占比": b["vx_share"]["val"], "视频号TR": b["vx_tr"]["val"],
                "AMS日耗(万)": b["ams"]["val"], "AMS年同比": b["ams_yoy"]["label"],
                "adq投手情况盘点": st["adq_desc"], "adq专职投手数量": st["adq_fulltime"],
                "微信豆投放(清洗后)": st["dou_text"] or st["dou_msg"], "ROI备注": st["roi_note"], "微信豆投放(原文)": st["dou_raw"],
                "双十一报名": d["signup"], "大场规划日期": d["big_dates"], "现货库存": d["stock"],
                "日均消耗目标(万)": d["cost_target"], "日均消耗目标(原文)": d["cost_target_raw"],
                "日均GMV目标(万)": d["gmv_target"], "日均GMV目标(原文)": d["gmv_target_raw"],
                "Q4季节品数": c["q4_season"], "Q4常规品数": c["q4_regular"],
            })
            for mo in MONTHS:
                for tp in ("季节品", "常规品"):
                    for it in c["goods"][mo][tp]:
                        goods.append({"行业": ind["name"], "客户": c["name"], "月份": mo, "类型": tp, "商品": it["name"], "款数": it["n"]})
    with pd.ExcelWriter(path) as w:
        pd.DataFrame(rows).to_excel(w, sheet_name="客户盘点_清洗后", index=False)
        pd.DataFrame(goods).to_excel(w, sheet_name="商品上新明细", index=False)
        pd.DataFrame(data["issues"]).rename(columns={"industry": "行业", "customer": "客户", "field": "字段", "raw": "原值", "msg": "处理说明", "level": "级别"}).to_excel(w, sheet_name="数据质量清单", index=False)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    a = ap.parse_args()
    src = Path(a.src) if a.src else latest_src()
    data = run(src)
    C.DATA_DIR.mkdir(exist_ok=True)
    (C.DATA_DIR / "clean.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"源表: {src}")
    for ind in data["industries"]:
        print(ind["name"], len(ind["customers"]), "客户", len(ind["maps"]), "张地图")
    print("数据质量问题", len(data["issues"]))
