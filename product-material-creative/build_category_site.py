# -*- coding: utf-8 -*-
"""生成 65 个类目独立页面的商品素材创意深度分析站点。"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
BASE = Path.home() / "Downloads" / "商品素材_analysis"
TRANSCRIPTS = BASE / "transcripts"
FRAMES = BASE / "frames"
SITE = ROOT / "category_site"
ASSETS = SITE / "assets"
CATEGORIES_DIR = SITE / "categories"
FRAMES_OUT = ASSETS / "frames"

FORM_MAP = {
    "A 食补滋补冲调": ["饮料冲调", "传统滋补品", "保健滋补", "普通膳食营养食品", "海外膳食营养补充食品", "茗茶"],
    "B 护肤美妆个护": ["面部洗护", "彩妆", "防晒", "身体洗护", "女性护理", "香水/香水用品", "足部洗护", "美妆工具", "个护健康", "成人护理"],
    "C 零食生鲜食品": ["休闲食品", "方便速食", "生肉/肉制品", "海鲜/水产制品", "新鲜水果", "调味品/果酱/沙拉", "粮油米面/南北干货", "白酒", "烘焙原辅料/半成品/食品添加剂"],
    "D 家清口腔清洁": ["洗护清洁/除臭剂/纸品", "口腔洗护", "头发洗护/造型", "清洁工具", "生活用品", "收纳整理"],
    "E 服饰鞋包家纺": ["内衣裤袜/睡衣/家居服", "婴童服/婴童用品", "男装", "女装", "男鞋", "女鞋", "家纺", "箱包皮具", "时尚饰品", "家居饰品", "户外服装/运动服装", "童装/亲子装"],
    "F 家电数码智能": ["生活电器", "厨房用具", "电脑及周边", "影音娱乐", "智能设备", "手机", "3C数码配件", "手机配件", "汽车内饰品"],
    "G 医药健身其他": ["医药非药械类", "外用贴膏或凝胶", "中小型健身器材", "运动装备", "运动/休闲玩具", "益智玩具", "眼镜及配件", "电子教育产品", "人文社科", "日常学习用品", "宠物营养品", "露营/野炊/旅行装备", "计生用品"],
}
CAT_TO_FORM = {cat: form for form, cats in FORM_MAP.items() for cat in cats}

FORM_STRATEGY = {
    "A 食补滋补冲调": {
        "formula": "反常识/体感问题钩子 → 原料产地与人物背书 → 成分数字与冲泡演示 → 家庭关怀 + 限时促销",
        "visual": "人物观点开场、原料/产地/工厂实拍、粉体或冲泡特写、包装与到手量感",
        "upgrade": "前 5 秒只保留一个强问题；中段用原料、工艺和检测信息替代泛功效；结尾把到手数量与价格机制一次说清。",
    },
    "B 护肤美妆个护": {
        "formula": "人群痛点/素颜冲突 → 成分或配方解释 → 真人使用过程 → 效果观感 + 备案/品牌信任",
        "visual": "面部或局部痛点特写、质地/上脸过程、前后状态对照、成分与备案信息",
        "upgrade": "把产品质地和使用动作前置；减少绝对效果承诺；用真实肤质、适用人群和使用方法提高可信度。",
    },
    "C 零食生鲜食品": {
        "formula": "食欲特写/反差剧情 → 原料配料与口感证明 → 试吃反馈 → 箱装量感 + 多件促销",
        "visual": "开袋、拉丝、爆汁或热气特写，配料与制作过程，真人试吃，整箱堆叠",
        "upgrade": "前 3 秒直接给最强食欲镜头；中段展示配料表和实际规格；促销表达避免反复，突出单件到手成本。",
    },
    "D 家清口腔清洁": {
        "formula": "脏污/异味/白发等问题特写 → 使用实测 → 原理或成分解释 → 前后对比 + 促销",
        "visual": "问题局部特写、操作过程、泡沫/溶解/清洁变化、使用前后同机位对照",
        "upgrade": "采用同机位、同光线的可验证对比；标注加速演示；先展示结果再解释原理，提高首屏信息效率。",
    },
    "E 服饰鞋包家纺": {
        "formula": "场景/身材需求钩子 → 真人上身 → 面料工艺与功能点 → 尺码建议 + 组合优惠",
        "visual": "全身上身效果、局部面料和走线、不同角度与动作测试、尺码/颜色卡",
        "upgrade": "减少纯口播卖点堆叠，增加不同体型和动作实测；尺码、材质、厚薄与适用季节保持常驻可见。",
    },
    "F 家电数码智能": {
        "formula": "结果先行/低价反差 → 核心功能实测 → 参数与场景解释 → 同类对比 + 售后保障",
        "visual": "产品全貌、关键功能实操、效果近景、参数字幕、家庭或办公场景",
        "upgrade": "避免只念参数；每个核心参数必须绑定一个可视化场景；补充安装、续航、噪音和售后等决策信息。",
    },
    "G 医药健身其他": {
        "formula": "明确人群问题 → 场景演示/知识解释 → 材质资质或专业背书 → 使用方法 + 风险提示",
        "visual": "使用场景、动作步骤、结构或材质细节、资质/说明书、适用边界",
        "upgrade": "先明确适用与不适用人群；功效表达回到产品功能和体验；用规范演示与风险提示提升信任。",
    },
}

TAG_RULES = {
    "痛点直击": ["痛", "斑", "臭", "脏", "白发", "油", "胖", "冒汗", "下垂", "外扩", "不会"],
    "促销转化": ["直播间", "拍一", "到手", "半价", "周年庆", "限时", "优惠", "立减", "赠", "发六", "划算"],
    "成分配方": ["成分", "配方", "原料", "蛋白", "毫克", "草本", "植物", "添加", "精选"],
    "信任背书": ["研究", "专家", "研发", "老师傅", "传承", "源头", "厂家", "备案", "专利", "认证"],
    "场景人群": ["孩子", "父母", "老人", "姐妹", "宝妈", "上班", "夏天", "睡觉", "家庭", "学生"],
    "演示实测": ["试试", "冲泡", "打开", "使用", "对比", "测试", "一分钟", "效果", "清洁", "上脸"],
    "稀缺催单": ["错过", "没有了", "赶快", "最后", "库存", "等好久", "马上", "趁现在"],
    "情绪价值": ["孝顺", "心疼", "喜欢", "惊喜", "幸福", "送给", "一定要", "爱吃"],
}

RISK_RULES = {
    "医疗/功效暗示": ["治疗", "治好", "晚期", "药", "病", "腰椎", "血糖", "血压", "消炎"],
    "绝对化承诺": ["一定", "百分百", "最", "彻底", "永久", "全网第一", "没有之一"],
    "价格稀缺表述": ["最低价", "最后一天", "错过没有", "马上恢复原价", "仅此一次"],
}


def safe(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", str(s))


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def trunc(s: str, n: int = 150) -> str:
    s = re.sub(r"\s+", "", s or "")
    return s if len(s) <= n else s[:n] + "…"


def https_url(url: str) -> str:
    return re.sub(r"^http://", "https://", url.strip(), flags=re.I)


def fmt_money(v: float) -> str:
    return f"{v / 10000:.1f}万" if v >= 10000 else f"{v:,.0f}元"


def phase_text(segments, start: float, end: float, limit=150) -> str:
    texts = [x.get("text", "") for x in segments if float(x.get("end", 0)) >= start and float(x.get("start", 0)) <= end]
    return trunc("".join(texts), limit) or "该时段暂无可用口播转写。"


def detect_labels(text: str, rules: dict, fallback: str) -> list[str]:
    labels = [name for name, words in rules.items() if any(w in text for w in words)]
    return labels or [fallback]


def material_analysis(item: dict, cat_items: list[dict], transcript: dict | None) -> dict:
    cost = item["cost"]
    ctr = item["ctr"]
    total_cost = sum(x["cost"] for x in cat_items)
    avg_ctr = statistics.mean(x["ctr"] for x in cat_items)
    median_ctr = statistics.median(x["ctr"] for x in cat_items)
    share = cost / total_cost * 100 if total_cost else 0
    ctr_delta = ctr - avg_ctr
    ctr_position = "高于类目均值" if ctr_delta >= 0 else "低于类目均值"
    ctr_level = "强点击" if ctr >= avg_ctr * 1.25 else "稳健" if ctr >= avg_ctr * 0.85 else "点击承压"
    rank = int(item["rank"])
    cost_level = "核心放量" if rank == 1 else "主力素材" if rank <= 3 else "补充素材"

    text = transcript.get("text", "") if transcript else ""
    duration = float(transcript.get("duration", 0)) if transcript else 0
    segments = transcript.get("segments", []) if transcript else []
    speech_end = max((float(x.get("end", 0)) for x in segments), default=duration)
    tags = detect_labels(text, TAG_RULES, "数据表现")
    risks = detect_labels(text, RISK_RULES, "未检出高风险关键词") if text else ["无口播转写，需人工复核合规"]
    if transcript and speech_end:
        opening = phase_text(segments, 0, min(15, speech_end * .18), 130)
        middle = phase_text(segments, speech_end * .28, speech_end * .66, 180)
        closing = phase_text(segments, max(0, speech_end - 22), speech_end + 1, 150)
    else:
        opening = middle = closing = "暂无 ASR 转写；页面仍保留视频，可直接播放人工核看。"

    strengths = []
    if ctr >= avg_ctr:
        strengths.append(f"CTR {ctr:.2f}% 高于类目均值 {avg_ctr:.2f}%，开场或人群指向具备点击优势")
    else:
        strengths.append(f"消耗占比 {share:.1f}% 说明具备投放承接能力，但 CTR 较类目均值低 {abs(ctr_delta):.2f}pp")
    if "促销转化" in tags:
        strengths.append("口播包含明确到手机制或直播间指令，转化路径较完整")
    elif "演示实测" in tags:
        strengths.append("包含使用或实测表达，能够把抽象卖点转化为可感知证据")
    else:
        strengths.append("素材已进入类目消耗 Top，核心表达具备继续拆分测试的价值")

    improvements = []
    if ctr < median_ctr:
        improvements.append("重做前 3–5 秒：结果前置、缩短背景铺垫，并把核心人群直接写进首屏字幕")
    else:
        improvements.append("保留当前高效钩子，复制 3 个变量版本：人物、首句和首帧分别单变量测试")
    if duration > 90:
        improvements.append("视频时长偏长，建议剪出 30–45 秒短版，仅保留钩子、两项证据和一次 CTA")
    else:
        improvements.append("中段每 5–8 秒补一次画面变化或证据点，避免同景口播造成信息疲劳")
    if any(r != "未检出高风险关键词" for r in risks):
        improvements.append("复核功效、绝对化及价格稀缺措辞；增加适用边界和效果因人而异提示")
    else:
        improvements.append("促销口径与资质信息保持同屏可验证，结尾只保留一个明确行动指令")

    return {
        "share": share, "avg_ctr": avg_ctr, "ctr_delta": ctr_delta,
        "ctr_position": ctr_position, "ctr_level": ctr_level, "cost_level": cost_level,
        "tags": tags, "risks": risks, "opening": opening, "middle": middle, "closing": closing,
        "strengths": strengths, "improvements": improvements, "duration": duration,
        "full_text": trunc(text, 1800) if text else "暂无 ASR 转写。",
    }


def read_data():
    rows = []
    with open(OUT / "material_top20.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["rank"] = int(r["类目内排名"])
            r["cost"] = float(r["消耗(元)"])
            r["ctr"] = float(r["ctr(%)"])
            r["filename"] = safe(r["建议文件名"])
            r["stem"] = Path(r["filename"]).stem
            r["video_url"] = https_url(r["素材URL"])
            rows.append(r)
    summary = {}
    with open(OUT / "category_summary.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            summary[r["类目"]] = r
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["类目"]].append(r)
    for items in grouped.values():
        items.sort(key=lambda x: x["rank"])
    return grouped, summary


def load_transcript(cat: str, stem: str):
    p = TRANSCRIPTS / safe(cat) / f"{stem}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_frames(cat: str, stem: str, out_slug: str) -> list[dict]:
    src_dir = FRAMES / safe(cat) / stem
    if not src_dir.exists():
        return []
    files = sorted(src_dir.glob("*.jpg"))
    if not files:
        return []
    # 每条代表素材取 4 张等距关键帧，控制站点体积。
    idxs = sorted(set([0, round((len(files)-1)/3), round((len(files)-1)*2/3), len(files)-1]))
    chosen = [files[i] for i in idxs]
    target = FRAMES_OUT / out_slug / stem
    target.mkdir(parents=True, exist_ok=True)
    result = []
    for i, src in enumerate(chosen, 1):
        dst = target / src.name
        shutil.copy2(src, dst)
        m = re.search(r"_t([\d.]+)s", src.stem)
        t = float(m.group(1)) if m else 0
        result.append({"src": f"../assets/frames/{out_slug}/{stem}/{src.name}", "time": t, "idx": i})
    return result


def category_slug(index: int, cat: str) -> str:
    short = safe(cat).replace(" ", "-")
    return f"{index:02d}-{short}-{hashlib.md5(cat.encode()).hexdigest()[:5]}.html"


CSS = r"""
:root{--ink:#172033;--muted:#667085;--line:#e7eaf0;--bg:#f3f5f9;--purple:#6d28d9;--pink:#db2777;--blue:#0284c7;--green:#059669;--orange:#d97706}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg);line-height:1.65}a{color:inherit;text-decoration:none}.container{max-width:1280px;margin:auto;padding:0 26px}.topbar{position:sticky;top:0;z-index:50;background:rgba(15,18,32,.94);backdrop-filter:blur(10px);color:#fff}.topbar .container{height:58px;display:flex;align-items:center;justify-content:space-between;gap:16px}.brand{font-weight:850}.navlinks{display:flex;gap:14px;font-size:13px;color:#cbd5e1}.navlinks a:hover{color:#fff}.hero{background:linear-gradient(135deg,#4c1d95,#7c3aed 48%,#db2777);color:#fff;padding:54px 0 46px}.eyebrow{font-size:13px;letter-spacing:2px;opacity:.8;font-weight:750}.hero h1{font-size:44px;line-height:1.16;margin:10px 0 12px}.hero p{margin:0;max-width:940px;color:#eee7ff;font-size:16px}.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:28px}.kpi{padding:16px 14px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:14px}.kpi strong{font-size:27px;display:block}.kpi span{font-size:12px;opacity:.78}.section{padding:34px 0}.section h2{margin:0 0 5px;font-size:26px}.desc{color:var(--muted);font-size:14px;margin-bottom:20px}.panel{background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 5px 22px rgba(26,32,44,.05)}.toolbar{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}.input,.select{height:42px;border:1px solid #d8dce5;border-radius:10px;padding:0 13px;background:#fff;color:var(--ink)}.input{min-width:280px;flex:1}.cat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.cat-card{display:block;background:#fff;border:1px solid var(--line);border-radius:15px;padding:17px;transition:.2s;position:relative;overflow:hidden}.cat-card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(#7c3aed,#db2777)}.cat-card:hover{transform:translateY(-3px);box-shadow:0 12px 28px rgba(76,29,149,.12);border-color:#d8b4fe}.cat-card h3{font-size:16px;margin:0 0 8px}.mini{display:flex;gap:12px;font-size:12px;color:var(--muted)}.mini b{color:var(--purple)}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:3px 9px;background:#f3e8ff;color:#6b21a8;font-weight:750;font-size:11px}.badge.hot{background:#fce7f3;color:#be185d}.badge.blue{background:#e0f2fe;color:#0369a1}.badge.green{background:#d1fae5;color:#047857}.bread{font-size:13px;margin-bottom:12px;color:#ddd6fe}.category-hero h1{font-size:40px}.category-hero .kpis{grid-template-columns:repeat(4,1fr)}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.metric-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:17px}.metric-card .num{font-size:25px;font-weight:850;color:var(--purple)}.metric-card .label{font-size:12px;color:var(--muted)}.formula{background:linear-gradient(120deg,#faf5ff,#fff1f8);border:1px dashed #c4b5fd;border-radius:14px;padding:16px;color:#5b21b6;font-weight:750}.bullet{padding-left:19px;margin:8px 0}.bullet li{margin:6px 0}.rep{background:#fff;border:1px solid var(--line);border-radius:20px;overflow:hidden;margin-bottom:24px;box-shadow:0 6px 24px rgba(26,32,44,.06)}.rep-head{background:#17152f;color:#fff;padding:16px 20px;display:flex;align-items:center;justify-content:space-between;gap:14px}.rep-title{font-size:19px;font-weight:850}.rep-body{padding:20px}.video-layout{display:grid;grid-template-columns:390px 1fr;gap:20px}.video-box{background:#0b1020;border-radius:14px;overflow:hidden;align-self:start}.video-box video{width:100%;max-height:580px;display:block;background:#000}.video-note{padding:9px 12px;color:#aeb7c8;font-size:11px}.perf-row{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px}.perf{background:#f8fafc;border-radius:10px;padding:10px}.perf strong{display:block;font-size:18px;color:#5b21b6}.perf span{font-size:11px;color:var(--muted)}.analysis-box{border-top:1px solid var(--line);padding-top:14px;margin-top:14px}.analysis-box h4{margin:0 0 7px;font-size:15px;color:#34255f}.quote-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.quote{background:#f8fafc;border-radius:10px;padding:10px;font-size:12px;color:#475467}.quote b{display:block;color:#7c3aed;margin-bottom:4px}.tags{display:flex;flex-wrap:wrap;gap:6px}.storyboard{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.frame{background:#101426;border-radius:11px;overflow:hidden;color:#fff}.frame img{width:100%;aspect-ratio:9/16;object-fit:cover;display:block}.frame div{font-size:11px;padding:7px 8px;color:#cbd5e1}.detail{margin-top:12px;border:1px solid var(--line);border-radius:10px;padding:10px 12px}.detail summary{cursor:pointer;font-weight:750;color:#5b21b6}.transcript{font-size:12px;color:#475467;margin-top:8px;white-space:pre-wrap}.rank-table{width:100%;border-collapse:collapse;font-size:13px}.rank-table th{background:#f8fafc;color:#667085;text-align:left;padding:10px;border-bottom:1px solid var(--line)}.rank-table td{padding:11px 10px;border-bottom:1px solid #eef0f4}.rank-table tr:hover td{background:#fcfaff}.rank{font-weight:850;color:#7c3aed}.watch{display:inline-block;background:#ede9fe;color:#6d28d9;border-radius:7px;padding:4px 8px;font-weight:750}.watch:hover{background:#6d28d9;color:#fff}.prevnext{display:flex;justify-content:space-between;gap:16px;margin:26px 0}.prevnext a{background:#fff;border:1px solid var(--line);border-radius:11px;padding:10px 14px;color:#5b21b6;font-weight:750}.footer{padding:26px;color:#98a2b3;background:#111427;text-align:center;font-size:12px}.empty{padding:30px;text-align:center;color:var(--muted)}
@media(max-width:900px){.cat-grid{grid-template-columns:1fr 1fr}.kpis{grid-template-columns:repeat(2,1fr)}.video-layout{grid-template-columns:1fr}.video-box{max-width:520px}.grid3,.quote-grid{grid-template-columns:1fr}.storyboard{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.container{padding:0 15px}.hero{padding:36px 0}.hero h1,.category-hero h1{font-size:30px}.cat-grid,.grid2{grid-template-columns:1fr}.category-hero .kpis,.perf-row{grid-template-columns:repeat(2,1fr)}.rank-table{min-width:760px}.table-scroll{overflow:auto}.navlinks{display:none}}
"""

JS = r"""
function filterCats(){const q=(document.getElementById('q')?.value||'').toLowerCase();const f=document.getElementById('form')?.value||'';const sort=document.getElementById('sort')?.value||'cost';const grid=document.getElementById('catGrid');if(!grid)return;const cards=[...grid.querySelectorAll('.cat-card')];cards.forEach(c=>c.style.display=((!q||c.dataset.name.toLowerCase().includes(q))&&(!f||c.dataset.form===f))?'block':'none');cards.sort((a,b)=>sort==='ctr'?+b.dataset.ctr-+a.dataset.ctr:sort==='name'?a.dataset.name.localeCompare(b.dataset.name,'zh-CN'):+b.dataset.cost-+a.dataset.cost);cards.forEach(c=>grid.appendChild(c))}
document.addEventListener('play',e=>{if(e.target.tagName==='VIDEO'){document.querySelectorAll('video').forEach(v=>{if(v!==e.target)v.pause()})}},true);
"""


def frame_stage(i: int, n: int) -> str:
    labels = ["钩子建立", "场景/问题展开", "卖点证据", "转化收口"]
    return labels[min(i, len(labels)-1)]


def render_rep(cat: str, item: dict, cat_items: list[dict], slug_dir: str) -> str:
    transcript = load_transcript(cat, item["stem"])
    analysis = material_analysis(item, cat_items, transcript)
    frames = get_frames(cat, item["stem"], slug_dir)
    poster = frames[0]["src"] if frames else ""
    poster_attr = f' poster="{esc(poster)}"' if poster else ""
    frame_html = "".join(
        f'<div class="frame"><img loading="lazy" src="{esc(fr["src"])}" alt="{esc(cat)}关键帧{idx+1}"><div>{frame_stage(idx,len(frames))} · {fr["time"]:.1f}s</div></div>'
        for idx, fr in enumerate(frames)
    ) or '<div class="empty">暂无关键帧</div>'
    tags = "".join(f'<span class="badge">{esc(x)}</span>' for x in analysis["tags"])
    risks = "".join(f'<span class="badge {"hot" if x != "未检出高风险关键词" else "green"}">{esc(x)}</span>' for x in analysis["risks"])
    strengths = "".join(f"<li>{esc(x)}</li>" for x in analysis["strengths"])
    improvements = "".join(f"<li>{esc(x)}</li>" for x in analysis["improvements"])
    return f"""
<article class="rep" id="top-{item['rank']}">
  <div class="rep-head"><div class="rep-title">TOP {item['rank']} · 代表素材深度拆解</div><div><span class="badge hot">{esc(analysis['cost_level'])}</span> <span class="badge blue">{esc(analysis['ctr_level'])}</span></div></div>
  <div class="rep-body">
    <div class="video-layout">
      <div class="video-box"><video controls preload="none" playsinline{poster_attr}><source src="{esc(item['video_url'])}" type="video/mp4">浏览器不支持视频播放</video><div class="video-note">视频为原始素材 HTTPS 链接；点击后加载，建议在网络环境良好时播放。</div></div>
      <div>
        <div class="perf-row">
          <div class="perf"><strong>{fmt_money(item['cost'])}</strong><span>素材消耗</span></div>
          <div class="perf"><strong>{item['ctr']:.2f}%</strong><span>CTR</span></div>
          <div class="perf"><strong>{analysis['share']:.1f}%</strong><span>类目消耗占比</span></div>
          <div class="perf"><strong>{analysis['ctr_delta']:+.2f}pp</strong><span>较类目均值</span></div>
        </div>
        <div class="analysis-box"><h4>表现判断</h4><p>该素材是类目内第 {item['rank']} 名，属于“{esc(analysis['cost_level'])}”；CTR {esc(analysis['ctr_position'])}。消耗体现承接规模，CTR 体现首屏与定向效率，两项应结合判断，不能仅以单指标下结论。</p></div>
        <div class="analysis-box"><h4>表达标签</h4><div class="tags">{tags}</div></div>
        <div class="analysis-box"><h4>口播三段式证据</h4><div class="quote-grid"><div class="quote"><b>开场钩子</b>{esc(analysis['opening'])}</div><div class="quote"><b>中段论证</b>{esc(analysis['middle'])}</div><div class="quote"><b>结尾转化</b>{esc(analysis['closing'])}</div></div></div>
        <div class="grid2 analysis-box"><div><h4>有效点</h4><ul class="bullet">{strengths}</ul></div><div><h4>迭代动作</h4><ul class="bullet">{improvements}</ul></div></div>
        <div class="analysis-box"><h4>合规关注</h4><div class="tags">{risks}</div></div>
      </div>
    </div>
    <div class="storyboard">{frame_html}</div>
    <details class="detail"><summary>查看完整口播摘要</summary><div class="transcript">{esc(analysis['full_text'])}</div></details>
  </div>
</article>"""


def render_category(index: int, cats_order: list[str], cat: str, items: list[dict], summary: dict, filename_map: dict[str, str]) -> str:
    form = CAT_TO_FORM.get(cat, "G 医药健身其他")
    strategy = FORM_STRATEGY[form]
    costs = [x["cost"] for x in items]
    ctrs = [x["ctr"] for x in items]
    total_cost = sum(costs)
    avg_ctr = statistics.mean(ctrs)
    top1_share = costs[0] / total_cost * 100 if total_cost else 0
    top3_share = sum(costs[:3]) / total_cost * 100 if total_cost else 0
    high_ctr = sum(1 for x in ctrs if x > avg_ctr)
    deep_n = 2 if len(items) >= 10 else 1
    slug_dir = Path(filename_map[cat]).stem
    reps = "".join(render_rep(cat, x, items, slug_dir) for x in items[:deep_n])
    rows = []
    for x in items:
        delta = x["ctr"] - avg_ctr
        diagnosis = "高点击" if delta >= avg_ctr * .25 else "均值以上" if delta >= 0 else "待优化"
        rows.append(f'<tr><td class="rank">#{x["rank"]}</td><td>{fmt_money(x["cost"])}</td><td>{x["ctr"]:.2f}%</td><td>{x["cost"]/total_cost*100:.1f}%</td><td><span class="badge {"green" if delta>=0 else "hot"}">{diagnosis}</span></td><td><a class="watch" href="{esc(x["video_url"])}" target="_blank" rel="noopener">播放素材</a></td></tr>')
    rank_rows = "".join(rows)
    prev_cat = cats_order[index - 1] if index > 0 else None
    next_cat = cats_order[index + 1] if index + 1 < len(cats_order) else None
    prev_link = f'<a href="{esc(filename_map[prev_cat])}">← {esc(prev_cat)}</a>' if prev_cat else '<span></span>'
    next_link = f'<a href="{esc(filename_map[next_cat])}">{esc(next_cat)} →</a>' if next_cat else '<span></span>'
    concentration = "头部高度集中" if top1_share >= 35 else "头部较集中" if top1_share >= 22 else "素材分布相对均衡"
    ctr_disp = statistics.pstdev(ctrs) if len(ctrs) > 1 else 0
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(cat)}类目Top素材视频创意深度分析"><title>{esc(cat)} · Top素材深度分析</title><link rel="stylesheet" href="../assets/style.css"></head><body>
<div class="topbar"><div class="container"><a class="brand" href="../index.html">商品素材 · 类目分析库</a><div class="navlinks"><a href="#diagnosis">类目诊断</a><a href="#deep">代表素材</a><a href="#ranking">完整排行</a></div></div></div>
<header class="hero category-hero"><div class="container"><div class="bread"><a href="../index.html">全部类目</a> / {esc(form)}</div><div class="eyebrow">CATEGORY {index+1:02d} / 65 · CREATIVE DEEP DIVE</div><h1>{esc(cat)}</h1><p>本页独立分析该类目全部 {len(items)} 条 Top 素材，并对消耗头部 {deep_n} 条代表视频进行“播放 + 关键帧 + ASR 口播 + 指标”四层拆解。</p><div class="kpis"><div class="kpi"><strong>{fmt_money(total_cost)}</strong><span>Top素材消耗</span></div><div class="kpi"><strong>{avg_ctr:.2f}%</strong><span>平均 CTR</span></div><div class="kpi"><strong>{len(items)}</strong><span>Top素材数</span></div><div class="kpi"><strong>{top3_share:.1f}%</strong><span>Top3 消耗集中度</span></div></div></div></header>
<main>
<section class="section" id="diagnosis"><div class="container"><h2>类目经营与创意诊断</h2><div class="desc">结论来自类目内素材横向对比；CTR 为简单平均，消耗体现规模，不等同于转化率。</div><div class="grid3"><div class="metric-card"><div class="num">{top1_share:.1f}%</div><div class="label">Top1 消耗占比 · {concentration}</div></div><div class="metric-card"><div class="num">{high_ctr}/{len(items)}</div><div class="label">CTR 高于类目均值的素材数</div></div><div class="metric-card"><div class="num">{ctr_disp:.2f}pp</div><div class="label">CTR 离散度 · 反映素材差异</div></div></div><div class="panel" style="margin-top:16px"><span class="badge">{esc(form)}</span><h3>类目创意公式</h3><div class="formula">{esc(strategy['formula'])}</div><div class="grid2" style="margin-top:14px"><div><h4>建议画面资产</h4><p>{esc(strategy['visual'])}</p></div><div><h4>下一轮迭代</h4><p>{esc(strategy['upgrade'])}</p></div></div></div></div></section>
<section class="section" id="deep"><div class="container"><h2>Top 代表素材 · 深度拆解</h2><div class="desc">大类目分析 Top2，小类目分析 Top1；关键帧均来自本地视频等距抽帧，口播来自 faster-whisper ASR，需允许少量同音字误差。</div>{reps}</div></section>
<section class="section" id="ranking"><div class="container"><h2>全部 Top 素材排行与视频入口</h2><div class="desc">每条素材均保留原视频播放入口；建议按“高消耗高CTR / 高消耗低CTR / 低消耗高CTR”三象限安排复投与改版。</div><div class="panel table-scroll"><table class="rank-table"><thead><tr><th>排名</th><th>消耗</th><th>CTR</th><th>消耗占比</th><th>诊断</th><th>视频</th></tr></thead><tbody>{rank_rows}</tbody></table></div><div class="prevnext">{prev_link}{next_link}</div></div></section>
</main><div class="footer">数据范围：65 类目 / 512 条类目 Top 素材 · 页面生成自真实消耗、CTR、视频、ASR 与关键帧数据</div><script src="../assets/app.js"></script></body></html>"""


def render_index(cats_order: list[str], grouped, summary, filename_map) -> str:
    total_items = sum(len(v) for v in grouped.values())
    total_cost = sum(x["cost"] for v in grouped.values() for x in v)
    avg_ctr = statistics.mean(x["ctr"] for v in grouped.values() for x in v)
    cards = []
    for idx, cat in enumerate(cats_order, 1):
        items = grouped[cat]
        form = CAT_TO_FORM.get(cat, "G 医药健身其他")
        cost = sum(x["cost"] for x in items)
        ctr = statistics.mean(x["ctr"] for x in items)
        cards.append(f'<a class="cat-card" href="categories/{esc(filename_map[cat])}" data-name="{esc(cat)}" data-form="{esc(form)}" data-cost="{cost}" data-ctr="{ctr}"><span class="badge">{esc(form[:1])}</span><h3>{idx:02d}. {esc(cat)}</h3><div class="mini"><span><b>{fmt_money(cost)}</b> 消耗</span><span><b>{ctr:.2f}%</b> CTR</span><span><b>{len(items)}</b> 素材</span></div></a>')
    options = "".join(f'<option value="{esc(x)}">{esc(x)}</option>' for x in FORM_MAP)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="65个商品类目独立Top素材视频创意分析库"><title>商品素材 · 65类目深度分析库</title><link rel="stylesheet" href="assets/style.css"></head><body>
<div class="topbar"><div class="container"><a class="brand" href="index.html">商品素材 · 类目分析库</a><div class="navlinks"><a href="#categories">进入类目</a><a href="overview.html">查看总览旧版</a><a href="商品素材创意框架分析.xlsx">下载 Excel</a></div></div></div>
<header class="hero"><div class="container"><div class="eyebrow">MULTI-CATEGORY CREATIVE INTELLIGENCE</div><h1>65 个类目 · Top 素材视频深度分析库</h1><p>从总览报告下钻到每一个类目：每类独立页面、全部 Top 素材排行与视频入口、Top1–2 代表作的关键帧/口播/指标/迭代动作四层拆解。</p><div class="kpis"><div class="kpi"><strong>{len(cats_order)}</strong><span>独立类目页面</span></div><div class="kpi"><strong>{total_items}</strong><span>Top 素材</span></div><div class="kpi"><strong>{total_cost/1e8:.2f}亿</strong><span>总消耗</span></div><div class="kpi"><strong>{avg_ctr:.2f}%</strong><span>素材平均 CTR</span></div><div class="kpi"><strong>83</strong><span>深度代表作</span></div></div></div></header>
<main><section class="section" id="categories"><div class="container"><h2>类目索引</h2><div class="desc">可按类目名搜索、按 7 大内容形态筛选，并按消耗、CTR 或名称排序。</div><div class="toolbar"><input class="input" id="q" placeholder="搜索类目，如：面部洗护、饮料冲调" oninput="filterCats()"><select class="select" id="form" onchange="filterCats()"><option value="">全部内容形态</option>{options}</select><select class="select" id="sort" onchange="filterCats()"><option value="cost">按消耗排序</option><option value="ctr">按 CTR 排序</option><option value="name">按类目名排序</option></select></div><div class="cat-grid" id="catGrid">{''.join(cards)}</div></div></section></main>
<div class="footer">类目页视频使用原素材 HTTPS 地址按需加载；关键帧为站点静态资产。报告仅用于创意研究与素材复盘。</div><script src="assets/app.js"></script></body></html>"""


def main():
    grouped, summary = read_data()
    cats_order = sorted(grouped, key=lambda c: -sum(x["cost"] for x in grouped[c]))
    unknown = [c for c in cats_order if c not in CAT_TO_FORM]
    if unknown:
        raise RuntimeError(f"未映射类目: {unknown}")

    if SITE.exists():
        shutil.rmtree(SITE)
    ASSETS.mkdir(parents=True)
    CATEGORIES_DIR.mkdir(parents=True)
    FRAMES_OUT.mkdir(parents=True)
    (ASSETS / "style.css").write_text(CSS, encoding="utf-8")
    (ASSETS / "app.js").write_text(JS, encoding="utf-8")

    filename_map = {cat: category_slug(i + 1, cat) for i, cat in enumerate(cats_order)}
    for i, cat in enumerate(cats_order):
        page = render_category(i, cats_order, cat, grouped[cat], summary.get(cat, {}), filename_map)
        (CATEGORIES_DIR / filename_map[cat]).write_text(page, encoding="utf-8")
        print(f"[{i+1:02d}/{len(cats_order)}] {cat} -> {filename_map[cat]}")

    (SITE / "index.html").write_text(render_index(cats_order, grouped, summary, filename_map), encoding="utf-8")
    # 保留原 onepage 总览与 Excel，便于索引页跳转和下载。
    desktop = Path.home() / "Desktop"
    shutil.copy2(desktop / "商品素材创意框架分析.html", SITE / "overview.html")
    shutil.copy2(desktop / "商品素材创意框架分析.xlsx", SITE / "商品素材创意框架分析.xlsx")

    html_count = len(list(SITE.rglob("*.html")))
    frame_count = len(list(FRAMES_OUT.rglob("*.jpg")))
    size_mb = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file()) / 1024 / 1024
    manifest = {
        "categories": len(cats_order), "top_materials": sum(len(v) for v in grouped.values()),
        "deep_representatives": sum(2 if len(v) >= 10 else 1 for v in grouped.values()),
        "html_files": html_count, "frame_images": frame_count, "site_size_mb": round(size_mb, 1),
    }
    (SITE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== SITE COMPLETE ===")
    print(json.dumps(manifest, ensure_ascii=False))
    print(SITE)


if __name__ == "__main__":
    main()
