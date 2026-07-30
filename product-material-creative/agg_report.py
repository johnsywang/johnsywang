# -*- coding: utf-8 -*-
"""聚合报告数据:65类目→7大内容形态映射 + 消耗/ctr聚合。输出 out/report_data.json"""
import csv, json, sys, io
from pathlib import Path
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CAT_SUM = Path("out/category_summary.csv")
TOP20 = Path("out/material_top20.csv")

# 类目 -> 形态
FORM = {
 "A 食补滋补冲调": ["饮料冲调","传统滋补品","保健滋补","普通膳食营养食品","海外膳食营养补充食品","茗茶"],
 "B 护肤美妆个护": ["面部洗护","彩妆","防晒","身体洗护","女性护理","香水/香水用品","足部洗护","美妆工具","个护健康","成人护理"],
 "C 零食生鲜食品": ["休闲食品","方便速食","生肉/肉制品","海鲜/水产制品","新鲜水果","调味品/果酱/沙拉","粮油米面/南北干货","白酒","烘焙原辅料/半成品/食品添加剂"],
 "D 家清口腔清洁": ["洗护清洁/除臭剂/纸品","口腔洗护","头发洗护/造型","清洁工具","生活用品","收纳整理"],
 "E 服饰鞋包家纺": ["内衣裤袜/睡衣/家居服","婴童服/婴童用品","男装","女装","男鞋","女鞋","家纺","箱包皮具","时尚饰品","家居饰品","户外服装/运动服装","童装/亲子装"],
 "F 家电数码智能": ["生活电器","厨房用具","电脑及周边","影音娱乐","智能设备","手机","3C数码配件","手机配件","汽车内饰品"],
 "G 医药健身其他": ["医药非药械类","外用贴膏或凝胶","中小型健身器材","运动装备","运动/休闲玩具","益智玩具","眼镜及配件","电子教育产品","人文社科","日常学习用品","宠物营养品","露营/野炊/旅行装备"],
}
cat2form = {}
for f, cats in FORM.items():
    for c in cats: cat2form[c] = f

# 读类目汇总
cats = []
for r in csv.DictReader(open(CAT_SUM, encoding='utf-8-sig')):
    if not r.get('类目'): continue
    cats.append({
        'cat': r['类目'],
        'n': int(r['可下载素材总数']),
        'top20': int(r['Top20实际数']),
        'cost_w': float(r['Top20消耗合计(万元)']),
        'ctr': float(r['Top20平均ctr(%)']),
        'form': cat2form.get(r['类目'], 'G 医药健身其他'),
    })
cats.sort(key=lambda x: -x['cost_w'])

# 形态聚合
forms = defaultdict(lambda: {'cost_w':0.0,'n':0,'top20':0,'cats':[],'ctr_sum':0,'ctr_cnt':0})
for c in cats:
    f = forms[c['form']]
    f['cost_w'] += c['cost_w']; f['n'] += c['n']; f['top20'] += c['top20']
    f['cats'].append(c['cat']); f['ctr_sum'] += c['ctr']*c['top20']; f['ctr_cnt'] += c['top20']
form_list = []
for name in FORM:
    f = forms[name]
    form_list.append({'form':name,'cost_w':round(f['cost_w'],1),'n':f['n'],'top20':f['top20'],
        'ncat':len(f['cats']),'cats':f['cats'],'ctr':round(f['ctr_sum']/max(f['ctr_cnt'],1),2)})
form_list.sort(key=lambda x:-x['cost_w'])

total_cost = round(sum(c['cost_w'] for c in cats),1)
total_n = sum(c['n'] for c in cats)
total_top20 = sum(c['top20'] for c in cats)
avg_ctr = round(sum(c['ctr']*c['top20'] for c in cats)/total_top20,2)

data = {
 'total': {'ncat':len(cats),'n_material':total_n,'top20':total_top20,'cost_w':total_cost,'avg_ctr':avg_ctr},
 'forms': form_list,
 'cats': cats,
}
json.dump(data, open('out/report_data.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"类目{len(cats)} 素材{total_n} Top20素材{total_top20} 总消耗{total_cost}万 均ctr{avg_ctr}%")
print("--- 形态消耗排名 ---")
for f in form_list:
    print(f"  {f['form']:16s} {f['cost_w']:8.1f}万  {f['ncat']}类目 {f['top20']}素材 ctr{f['ctr']}%")
