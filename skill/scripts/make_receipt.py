#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开饭确认单生成器：读 plan_meal.py 的输出文本，渲染麦当劳风格的 HTML 小票。

用法:
  python plan_meal.py --demo | python make_receipt.py --store "大雁塔北广场店"
  python make_receipt.py --plan-file out.txt --store "XX店" --out receipt.html
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ITEM_RE = re.compile(r"\[(.+?)\]\s+(.+?)\s+×(\d+)\s+@([\d.]+)\s+=\s+([\d.]+)\s*元")
KCAL_RE = re.compile(r"([\d.]+)\s*千卡/份")
TOTAL_RE = re.compile(r"合计：([\d.]+)\s*元")
SAVE_RE = re.compile(r"原价单：([\d.]+)\s*元\s*→\s*省钱单：([\d.]+)\s*元\s*\|\s*共省\s*([\d.]+)\s*元")
COUPON_RE = re.compile(r"用券后实付：([\d.]+)\s*元.*?累计省\s*([\d.]+)\s*元")
MEAL_RE = re.compile(r"=== 聚餐方案 \| (\d+) 人 \| 预算 ([\d.]+) 元")
CAL_RE = re.compile(r"=== 热量控制方案 \| (\d+) 人 \| 每人上限 ([\d.]+) 千卡 \| 预算 ([\d.]+) 元")
SAVE_TITLE_RE = re.compile(r"=== 麦门省钱单 ===")


def parse(text):
    items, head, total, saved, coupon_pay = [], "", 0.0, 0.0, None
    for line in text.splitlines():
        m = ITEM_RE.search(line)
        if m:
            cat, name, qty, price, sub = m.group(1), m.group(2), int(m.group(3)), float(m.group(4)), float(m.group(5))
            kcal = ""
            km = KCAL_RE.search(line)
            if km:
                kcal = f"{float(km.group(1)):g} kcal"
            items.append({"cat": cat, "name": name, "qty": qty, "price": price, "sub": sub, "kcal": kcal})
            continue
        m = TOTAL_RE.search(line)
        if m:
            total = float(m.group(1))
        m = SAVE_RE.search(line)
        if m:
            total = float(m.group(2))
            saved = float(m.group(3))
        m = COUPON_RE.search(line)
        if m:
            coupon_pay = (float(m.group(1)), float(m.group(2)))
            total = float(m.group(1))
            saved = float(m.group(2))
        m = MEAL_RE.search(line)
        if m:
            head = f"{m.group(1)} 人聚餐 · 预算 ¥{float(m.group(2)):g}"
        m = CAL_RE.search(line)
        if m:
            head = f"{m.group(1)} 人控卡配餐 · 每人 ≤{float(m.group(2)):g} 千卡 · 预算 ¥{float(m.group(3)):g}"
        if SAVE_TITLE_RE.search(line):
            head = "麦门省钱凑单"
    return head, items, total, saved, coupon_pay


def html(head, items, total, saved, coupon_pay, store):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = "\n".join(
        f'<tr><td class="cat">{it["cat"]}</td><td>{it["name"]}'
        f'<span class="kcal">{it["kcal"]}</span></td>'
        f'<td class="r">×{it["qty"]}</td><td class="r">@{it["price"]:g}</td>'
        f'<td class="r b">{it["sub"]:g}</td></tr>'
        for it in items)
    coupon_line = ""
    if coupon_pay:
        coupon_line = f'<div class="coupon">已用最优券，累计为你省下 ¥{coupon_pay[1]:g}</div>'
    saved_line = f'<div class="saved">本单共省 ¥{saved:g}</div>' if saved > 0 else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>开饭确认单 · {store}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #ffbc0d; font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
         display: flex; justify-content: center; padding: 48px 16px; }}
  .wrap {{ max-width: 420px; width: 100%; }}
  .logo {{ text-align: center; color: #da291c; font-weight: 900; font-size: 40px;
           letter-spacing: 2px; margin-bottom: 6px; text-shadow: 2px 2px 0 #fff; }}
  .slogan {{ text-align: center; color: #7a4a00; font-size: 14px; margin-bottom: 24px; }}
  .ticket {{ background: #fff; border-radius: 14px; padding: 28px 24px;
             box-shadow: 0 12px 30px rgba(122, 74, 0, .35); position: relative; }}
  .ticket::before, .ticket::after {{
      content: ""; position: absolute; width: 28px; height: 28px; background: #ffbc0d;
      border-radius: 50%; top: 50%; }}
  .ticket::before {{ left: -14px; }} .ticket::after {{ right: -14px; }}
  .store {{ color: #da291c; font-size: 20px; font-weight: 800; }}
  .head {{ color: #555; font-size: 13px; margin: 4px 0 2px; }}
  .time {{ color: #999; font-size: 12px; margin-bottom: 16px; }}
  .dash {{ border-top: 2px dashed #e0d5c0; margin: 14px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  td {{ padding: 7px 0; vertical-align: top; }}
  .cat {{ color: #fff; background: #da291c; border-radius: 4px; font-size: 11px;
          padding: 1px 6px; margin-right: 6px; white-space: nowrap; }}
  .kcal {{ color: #b08a2e; font-size: 11px; margin-left: 8px; }}
  .r {{ text-align: right; color: #666; white-space: nowrap; }}
  .b {{ color: #222; font-weight: 700; }}
  .total-row {{ display: flex; justify-content: space-between; align-items: baseline; margin-top: 6px; }}
  .total-row .label {{ color: #555; font-size: 15px; }}
  .total-row .amount {{ color: #da291c; font-size: 34px; font-weight: 900; }}
  .saved {{ margin-top: 10px; text-align: center; background: #fff3cd; color: #8a6d00;
            border: 1px dashed #e0b400; border-radius: 8px; padding: 8px; font-size: 14px; font-weight: 700; }}
  .coupon {{ margin-top: 8px; text-align: center; color: #da291c; font-size: 13px; font-weight: 700; }}
  .barcode {{ margin-top: 20px; height: 44px; background: repeating-linear-gradient(90deg,
      #222 0 2px, #fff 2px 5px, #222 5px 6px, #fff 6px 10px, #222 10px 13px, #fff 13px 15px); }}
  .foot {{ text-align: center; color: #b08a2e; font-size: 12px; margin-top: 12px; letter-spacing: 4px; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="logo">M</div>
    <div class="slogan">i'm lovin' it · 开饭了麦门</div>
    <div class="ticket">
      <div class="store">麦当劳 {store}</div>
      <div class="head">{head or "点餐方案"}</div>
      <div class="time">确认单号 {now.replace('-', '').replace(':', '').replace(' ', '-')} · {now}</div>
      <div class="dash"></div>
      <table>{rows}</table>
      <div class="dash"></div>
      <div class="total-row"><span class="label">实付</span><span class="amount">¥{total:g}</span></div>
      {saved_line}
      {coupon_line}
      <div class="barcode"></div>
      <div class="foot">总 价 由 脚 本 计 算 · 实 付 以 门 店 为 准</div>
    </div>
  </div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="开饭确认单生成器")
    ap.add_argument("--plan-file", type=str, default="", help="plan 输出文本；缺省读 stdin")
    ap.add_argument("--store", type=str, default="麦门食堂")
    ap.add_argument("--out", type=str, default="", help="输出 HTML 路径；缺省打印到 stdout")
    args = ap.parse_args()

    if sys.stdin.isatty() and not args.plan_file:
        ap.error("需要 --plan-file 或从管道传入 plan_meal.py 的输出")
    text = Path(args.plan_file).read_text(encoding="utf-8") if args.plan_file else sys.stdin.read()

    head, items, total, saved, coupon_pay = parse(text)
    if not items:
        print("⚠ 未解析到任何单品行，请确认输入是 plan_meal.py 的原始输出", file=sys.stderr)
        sys.exit(1)

    out = html(head, items, total, saved, coupon_pay, args.store)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"✅ 开饭确认单已生成：{args.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
