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
