"""看板全局配置：路径、双十一周期、分类规则开关等。"""
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DESKTOP = Path.home() / "Desktop"

# 源表：默认取桌面最新的「服饰Q4客户&商品盘点*.xlsx」，也可通过 --src 指定
SRC_GLOB = "服饰Q4客户&商品盘点*.xlsx"

DATA_DIR = ROOT / "data"          # 清洗中间产物（clean.json / 品类地图图片）
INPUT_DIR = ROOT / "input"        # 后续补充的消耗类数据放这里
OUTPUT_DIR = ROOT / "output"      # 看板 HTML + 清洗结果 Excel
TEMPLATE = ROOT / "template.html"

# QTD 起始日（Q4），QTD 天数 = 数据日期 − Q_START + 1
Q_START = dt.date(2026, 10, 1)

# 双十一周期
D11_START = dt.date(2026, 10, 12)
D11_END = dt.date(2026, 11, 15)
D11_TOTAL_DAYS = (D11_END - D11_START).days + 1  # 35

# 数据日期（“昨日”），默认 = 今天 - 1；补数时如数据日期不同可在命令行 --date 覆盖
def default_data_date():
    return dt.date.today() - dt.timedelta(days=1)

# 消耗数据单位换算：BI 导出的消耗若为「元」，除以 10000 换算为「万元」与目标口径一致
COST_UNIT_DIVISOR = 10000

# 客户类型：直接取源表「客户类型」列（顺序即展示顺序，与源表表头 1~4 一致）
CTYPE_EMPTY = "未标注"
CTYPES = ["全平台生意下跌", "视频号微信豆和adq均下跌", "adq被豆子挤压", "视频号生意增长", CTYPE_EMPTY]

# ---- 看板客户范围 ----
# KEEP_CUSTOMERS：只保留这些客户（按简称/别名匹配，不区分大小写）；设为 None 则保留盘点表全部客户
# 11.8 起盘点表本身即为重点客户名单（28 家），不再额外筛选
KEEP_CUSTOMERS = None
# EXTRA_CUSTOMERS：盘点表中没有、需手动补充的客户（未提供的盘点类信息显示为未填写，消耗数据照常从客户数据读取）
# biz：客户生意情况（10.1-10.21），口径同源表：GMV/ams 单位万元，年同比/占比/TR 用小数（-0.1 = -10%）
# 写法示例：{"name": "xx", "industry": "男装", "ctype": "全平台生意下跌", "biz": {"gmv_all": 55, "gmv_all_yoy": -0.10}}
# 盘点表里已有同名客户时自动跳过（以盘点表为准）
EXTRA_CUSTOMERS = []

# CTYPE_OVERRIDE：手动指定客户类型（优先级高于源表「客户类型」列），键为客户简称（不区分大小写）
CTYPE_OVERRIDE = {
    "广州树语商贸有限公司": "视频号微信豆和adq均下跌",
}

# 作战思路地图（数据总览开篇）：每类客户的打法标签、当前问题、推进方向；改文案只需改这里
CT_PLAYBOOK = {
    "全平台生意下跌": {
        "tag": "稳基建 · 待回暖",
        "problem": "去年同期爆品今年爆发力下降，叠加天气偏暖影响",
        "actions": ["保持基建，等待天气降温", "提升商品起量率"],
    },
    "视频号微信豆和adq均下跌": {
        "tag": "提 ROI · 补利润",
        "problem": "退货率提升，叠加电商税影响，客户在视频号利润下降",
        "actions": ["创意专项提升 CTR，提高 ROI", "报名服饰造节 / 小店官方活动，补贴利润"],
    },
    "adq被豆子挤压": {
        "tag": "抢人力 · 拉预算",
        "problem": "微信豆起量率及 ROI 高于 adq，预算被微信豆挤压",
        "actions": ["前端销售运营拉回客户在 adq 的投放人力", "配置独立团队、专属投手"],
    },
    "视频号生意增长": {
        "tag": "放增量 · 抢份额",
        "problem": "视频号生意处于上升期，需承接双十一增量",
        "actions": ["加大双十一预算与素材供给，冲刺大场", "沉淀爆品与投放打法，向同类客户复制"],
    },
}

# ---- 后续消耗数据的列名映射（拿到真实导出文件后按实际列名补充别名即可） ----
# 昨日分客户：消耗、广告数、全新创意唯一性id数 + 对比期
YDAY_FILE_GLOB = "昨日分客户*"
YDAY_COLS = {
    "name": ["客户简称", "主计客户简称", "客户"],
    "y_cost": ["昨日消耗", "消耗"],
    "y_cost_prev": ["对比期消耗", "前日消耗", "环比期消耗"],
    "y_ads": ["昨日广告数", "广告数"],
    "y_ads_prev": ["对比期广告数", "前日广告数"],
    "y_cre": ["昨日全新创意唯一性id数", "全新创意唯一性id数"],
    "y_cre_prev": ["对比期全新创意唯一性id数", "前日全新创意唯一性id数"],
}
# QTD 分客户（10.1-昨日）：可直接给日耗，也可给累计消耗（÷QTD天数换算日耗）；去年同期同理
# 既可单独成文件「QTD分客户*」，也可作为列放进「昨日分客户*」文件（两处不要重复提供同一客户）
QTD_FILE_GLOB = "QTD分客户*"
QTD_COLS = {
    "name": ["客户简称", "主计客户简称", "客户"],
    "q_day": ["QTD日耗", "QTD日均消耗"],
    "q_day_ly": ["去年同期QTD日耗", "QTD日耗去年同期", "去年同期日耗"],
    "q_cost": ["QTD消耗", "QTD累计消耗", "Q4累计消耗"],
    "q_cost_ly": ["去年同期QTD消耗", "QTD消耗去年同期", "去年同期累计消耗"],
}
YDAY_COLS.update({k: v for k, v in QTD_COLS.items() if k != "name"})

# 双十一期间分客户（10.12-昨日）：累计消耗、有消耗广告数、全新创意唯一性id数 + 对比期
D11_FILE_GLOB = "双十一分客户*"
D11_COLS = {
    "name": ["客户简称", "主计客户简称", "客户"],
    "d_cost": ["期间消耗", "累计消耗", "消耗"],
    "d_cost_prev": ["对比期消耗"],
    "d_ads": ["期间有消耗广告数", "有消耗广告数"],
    "d_ads_prev": ["对比期有消耗广告数"],
    "d_cre": ["期间全新创意唯一性id数", "全新创意唯一性id数"],
    "d_cre_prev": ["对比期全新创意唯一性id数"],
}

# ---- 多 sheet 合并版客户数据（BI 导出格式，如「客户数据11.1.xlsx」）----
# 优先级：--perf 指定 > input/ 下最新 > 桌面最新；找到后不再读上面的分文件。
# 每个指标列后紧跟「环比/年同比对比值、变化量、变化率」，对比值按位置取「指标列的下一列」。
# 文件名中的「M.D」会被识别为数据日期（命令行 --date 优先）。
PERF_BOOK_GLOB = "客户数据*.xlsx"
PERF_BOOK_TOTAL_ROW = "整体对比汇总"   # BI 汇总行：不计入客户，只用于核对加总
# sheet 名关键字（不区分大小写） -> (标签, {指标表头前缀: (本期key, 对比期key)})
PERF_BOOK_SHEETS = {
    "昨日": ("昨日", {"消耗": ("y_cost", "y_cost_prev"), "有消耗广告数": ("y_ads", "y_ads_prev"),
                      "全新创意唯一性id数": ("y_cre", "y_cre_prev")}),
    "双十一": ("双十一期间", {"消耗": ("d_cost", "d_cost_prev"), "日均消耗": ("d_day", "d_day_prev"),
                            "有消耗广告数": ("d_ads", "d_ads_prev"),
                            "全新创意唯一性id数": ("d_cre", "d_cre_prev"), "日均全新创意唯一性id数": ("d_cre_day", "d_cre_day_prev")}),
    "qtd": ("QTD", {"日均消耗": ("q_day", "q_day_ly"), "消耗": ("q_cost", "q_cost_ly")}),
}
# 每个 sheet 内的指标为「可选」：至少命中一个即可（如 11.3 版 qtd 只给日均消耗）；缺失的指标看板显示待补充
