#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦当劳用餐搭配求解器 v2（确定性算法，避免手算总价/总热量出错）

三种模式:
  meal     聚餐点餐: python plan_meal.py --people 4 --budget 150 [--no-spicy] [--no-beef] [--veg 1] [--pescatarian]
  save     省钱凑单: python plan_meal.py --mode save --items "巨无霸套餐,麦乐鸡5块,可口可乐(中)"
  calorie  热量控制: python plan_meal.py --mode calorie --people 2 --budget 80 --calorie-max 700 [--no-spicy ...]

共用逻辑: 忌口硬过滤 -> 分档选主食 -> 补饮品 -> 剩余预算补共享小食
"""
import argparse
import csv
import sys
from pathlib import Path

MENU_PATH = Path(__file__).resolve().parent.parent / "references" / "menu.csv"


def load_menu():
    items = []
    with open(MENU_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row["price"] = float(row["price"])
            row["calories"] = float(row.get("calories") or 0)
            row["satiety"] = float(row["satiety"])
            row["tags"] = set(t for t in row["tags"].split("|") if t)
            items.append(row)
    return items


def affordable(pool, cap):
    return [x for x in pool if x["price"] <= cap + 1e-9]


def best_by_satiety(pool, cap):
    cands = affordable(pool, cap)
    if not cands:
        return None
    return max(cands, key=lambda x: (x["satiety"], -x["price"]))


def cheapest(pool):
    return min(pool, key=lambda x: x["price"]) if pool else None


def pick_drink(drinks, cap):
    cands = affordable(drinks, cap)
    return min(cands, key=lambda x: (x["price"], -x["satiety"])) if cands else None


def filter_restrictions(menu, no_spicy, no_beef, pescatarian, notes):
    if no_spicy:
        menu = [x for x in menu if "辣" not in x["tags"]]
        notes.append("忌辣：已排除所有「辣」标签单品")
    if no_beef:
        menu = [x for x in menu if "牛肉" not in x["tags"]]
        notes.append("忌牛肉：已排除所有「牛肉」标签单品")
    if pescatarian:
        menu = [x for x in menu if "鸡肉" not in x["tags"] and "猪肉" not in x["tags"]]
        notes.append("不吃禽畜肉：仅保留鱼/素类")
    return menu


def find_item(menu, name):
    """先精确后包含匹配"""
    for x in menu:
        if x["name"] == name:
            return x
    for x in menu:
        if name in x["name"] or x["name"] in name:
            return x
    return None


# ================= 聚餐模式 =================
def plan_meal(people, budget, no_spicy, no_beef, veg_count, pescatarian):
    notes = []
    menu = filter_restrictions(load_menu(), no_spicy, no_beef, pescatarian, notes)

    combos = [x for x in menu if x["category"] == "套餐"]
    mains = [x for x in menu if x["category"] == "主食"]
    drinks = [x for x in menu if x["category"] == "饮品"]
    shareable = [x for x in menu if x["category"] in ("小食", "甜品")]
    fries = [x for x in shareable if "薯" in x["name"] and "素" in x["tags"]]
    pies = [x for x in shareable if x["category"] == "甜品" and "派" in x["name"]]

    chosen = []

    def add(item, qty=1):
        for i, (it, q) in enumerate(chosen):
            if it["name"] == item["name"]:
                chosen[i] = (it, q + qty)
                return
        chosen.append((item, qty))

    total = 0.0
    tier = budget / people
    min_combo = min((x["price"] for x in combos), default=999)
    min_main = min((x["price"] for x in mains), default=999)
    min_drink = cheapest(drinks)["price"] if drinks else 999.0
    one_plus_one = next((x for x in combos if "组合" in x["tags"]), None)

    # 素食者：薯条 + 派 + 饮品
    for _ in range(veg_count):
        cap = min(tier, budget - total)
        f = best_by_satiety(fries, cap * 0.6) or cheapest(fries)
        if f:
            add(f)
            total += f["price"]
            cap -= f["price"]
        p = best_by_satiety(pies, cap - min_drink)
        if p:
            add(p)
            total += p["price"]
            cap -= p["price"]
        d = pick_drink(drinks, cap)
        if d:
            add(d)
            total += d["price"]
    if veg_count:
        notes.append(f"{veg_count} 位素食者按「薯条+派+饮品」配餐（麦当劳无素汉堡）")

    # 非素食者按人均预算分档（动态人均，前面吃多了后面自动收紧）
    meat_people = people - veg_count
    for i in range(meat_people):
        t = (budget - total) / (meat_people - i)
        if t >= min_combo and (c := best_by_satiety(combos, t)):
            add(c)
            total += c["price"]
        elif drinks and t >= min_main + min_drink and (m := best_by_satiety(mains, t - min_drink)):
            d = pick_drink(drinks, t - m["price"])
            add(m)
            add(d)
            total += m["price"] + d["price"]
        elif one_plus_one and t >= one_plus_one["price"]:
            add(one_plus_one)
            total += one_plus_one["price"]
        else:
            m = best_by_satiety(mains, t)
            if m is None:
                notes.append("⚠ 预算不足以覆盖全部主食，请提高预算")
                continue
            add(m)
            total += m["price"]

    # 每人一杯饮品（套餐已含的不补）
    combo_units = sum(q for it, q in chosen if it["category"] == "套餐")
    drink_units = sum(q for it, q in chosen if it["category"] == "饮品")
    need = people - combo_units - drink_units
    for _ in range(max(0, need)):
        t_left = (budget - total) / max(1, need)
        d = pick_drink(drinks, t_left)
        if d is None:
            break
        add(d)
        total += d["price"]

    # 剩余预算补共享小食（满足度/元 降序 + 多样性上限）
    def cap_for(x):
        return max(2, people // 2) if x["category"] == "甜品" else people

    qty_bought = {}
    guard = 0
    while guard < 200:
        guard += 1
        cands = [
            x for x in affordable(shareable, budget - total)
            if qty_bought.get(x["name"], 0) < cap_for(x)
        ]
        if not cands:
            break
        pick = max(cands, key=lambda x: x["satiety"] / x["price"])
        add(pick)
        total += pick["price"]
        qty_bought[pick["name"]] = qty_bought.get(pick["name"], 0) + 1

    kcal = sum(it["calories"] * q for it, q in chosen)
    lines = [f"=== 聚餐方案 | {people} 人 | 预算 {budget:g} 元（人均 {tier:.1f}）==="]
    lines += fmt_list(chosen)
    lines.append(f"合计：{total:.1f} 元 | 预算剩余：{budget - total:.1f} 元 | 全单约 {kcal:.0f} 千卡")
    lines += notes_block(notes, [
        f"人均 {tier:.1f} 元 → 按档位选主食（套餐优先 > 主食+饮品 > 1+1随心配）",
        "忌口条件已作硬过滤，不符合的单品不进入候选",
        "剩余预算按「满足度/元」降序补共享小食甜品（每种有数量上限）",
    ])
    return lines


# ================= 省钱凑单模式 =================
def plan_save(items_wanted, no_spicy, no_beef):
    notes = []
    menu = filter_restrictions(load_menu(), no_spicy, no_beef, False, notes)

    resolved, missing = [], []
    for name in items_wanted:
        it = find_item(menu, name)
        (resolved.append(it) if it else missing.append(name))
    if missing:
        notes.append("⚠ 未匹配到（已跳过，请核对名称）：" + "、".join(missing))
    if not resolved:
        return ["⚠ 没有任何想吃的单品匹配成功，请用菜单里的名称重试"]

    original = sum(x["price"] for x in resolved)
    lines = ["=== 麦门省钱单 ===", f"想吃：{'、'.join(x['name'] for x in resolved)}"]

    # 规则1: 套餐 vs 散点（主品+中薯+中可）
    optimized = list(resolved)
    swaps = []
    for it in [x for x in resolved if x["category"] == "套餐"]:
        base_name = it["name"].replace("套餐", "")
        main = next((m for m in menu if m["category"] == "主食" and base_name in m["name"]), None)
        fries_m = next((m for m in menu if m["name"] == "中薯条"), None)
        cola = next((m for m in menu if m["name"] == "可口可乐(中)"), None)
        if main and fries_m and cola:
            scatter = main["price"] + fries_m["price"] + cola["price"]
            if scatter < it["price"]:
                swaps.append((it, [main, fries_m, cola], it["price"] - scatter))
    for combo, parts, saving in swaps:
        optimized.remove(combo)
        optimized.extend(parts)
        notes.append(f"「{combo['name']}」拆散点更省：{'+'.join(p['name'] for p in parts)} = "
                     f"{sum(p['price'] for p in parts):g} 元 < 套餐 {combo['price']:g} 元，省 {saving:g} 元")
    if not swaps:
        notes.append("套餐项对比过散点价：套餐含薯含饮反而更便宜，保持套餐不动")

    # 规则2: 主食/小食 + 饮品 组合价 > 1+1随心配 → 用 1+1 替代（最多换一组）
    one_plus_one = next((x for x in menu if "组合" in x["tags"]), None)
    if one_plus_one:
        pool = [x for x in optimized if x["category"] in ("主食", "小食", "甜品", "饮品")]
        pair, best_saving = None, 0
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                a, b = pool[i], pool[j]
                if a["category"] == "主食" and b["category"] == "主食":
                    continue  # 两主食换 1+1 不现实
                saving = a["price"] + b["price"] - one_plus_one["price"]
                if saving > best_saving:
                    pair, best_saving = (a, b), saving
        if pair and best_saving >= 1:
            a, b = pair
            optimized.remove(a)
            optimized.remove(b)
            optimized.append(one_plus_one)
            notes.append(f"「{a['name']} + {b['name']}」（{a['price']+b['price']:g} 元）用「1+1随心配」"
                         f"（{one_plus_one['price']:g} 元）平替，省 {best_saving:g} 元"
                         "（以门店 1+1 实际可选为准）")

    optimized_total = sum(x["price"] for x in optimized)
    lines += fmt_list([(x, 1) for x in optimized])
    lines.append(f"原价单：{original:g} 元 → 省钱单：{optimized_total:g} 元 | 共省 {original - optimized_total:g} 元")
    lines += notes_block(notes, [
        "省钱三板斧：套餐拆散点对比 → 1+1随心配平替 → 快照价为上限，App 券只会更低",
    ])
    return lines


# ================= 热量控制模式 =================
def plan_calorie(people, budget, cal_max, no_spicy, no_beef, veg_count, pescatarian):
    notes = []
    menu = filter_restrictions(load_menu(), no_spicy, no_beef, pescatarian, notes)

    combos = [x for x in menu if x["category"] == "套餐"]
    mains = [x for x in menu if x["category"] == "主食"]
    drinks = [x for x in menu if x["category"] == "饮品"]
    shareable = [x for x in menu if x["category"] in ("小食", "甜品")]
    veg_pool = [x for x in menu if "素" in x["tags"] and x["category"] in ("小食", "甜品")]

    chosen = []

    def add(item, qty=1):
        for i, (it, q) in enumerate(chosen):
            if it["name"] == item["name"]:
                chosen[i] = (it, q + qty)
                return
        chosen.append((item, qty))

    total = 0.0
    kcal_used = 0.0
    tier = budget / people if people else budget
    cal_share = cal_max  # 每人热量上限

    def fit(it, price_left, kcal_left):
        return it["price"] <= price_left + 1e-9 and it["calories"] <= kcal_left + 1e-9

    # 素食者
    for _ in range(veg_count):
        p_left, k_left = min(tier, budget - total), cal_share
        for pool in ([x for x in veg_pool if "薯" in x["name"]],
                     [x for x in veg_pool if "派" in x["name"]]):
            cands = [x for x in pool if fit(x, p_left, k_left * 0.5)]
            if cands:
                pick = max(cands, key=lambda x: x["satiety"])
                add(pick)
                total += pick["price"]
                kcal_used += pick["calories"]
                p_left -= pick["price"]
                k_left -= pick["calories"]
        cands = [x for x in drinks if fit(x, p_left, k_left)]
        if cands:
            pick = min(cands, key=lambda x: x["calories"])
            add(pick)
            total += pick["price"]
            kcal_used += pick["calories"]

    # 非素食者：热量 <= 每人上限的 65% 留空间给小食，价格走动态人均
    meat_people = people - veg_count
    for i in range(meat_people):
        p_left = min((budget - total) / (meat_people - i), tier * 1.3)
        k_left = cal_share * 0.65
        pool = [x for x in combos + mains if fit(x, p_left, k_left)]
        pick = best_by_satiety(pool, p_left) if pool else None
        if pick is None:
            notes.append("⚠ 热量上限太紧，无主食可选，请放宽 --calorie-max")
            continue
        add(pick)
        total += pick["price"]
        kcal_used += pick["calories"]
        p_left -= pick["price"]
        k_left -= pick["calories"]
        if pick["category"] != "套餐":
            cands = [x for x in drinks if fit(x, p_left, k_left)]
            if cands:
                pick_d = min(cands, key=lambda x: (x["calories"], x["price"]))
                add(pick_d)
                total += pick_d["price"]
                kcal_used += pick_d["calories"]

    # 共享小食：剩余热量预算 = 总热量 - 已用，价格仍受总预算约束
    kcal_left_total = people * cal_share - kcal_used
    qty_bought = {}
    guard = 0
    while guard < 200:
        guard += 1
        cands = [
            x for x in shareable
            if fit(x, budget - total, min(kcal_left_total, cal_share * 0.3))
            and qty_bought.get(x["name"], 0) < max(2, people // 2)
        ]
        if not cands:
            break
        pick = max(cands, key=lambda x: x["satiety"] / max(x["calories"], 1))
        add(pick)
        total += pick["price"]
        kcal_used += pick["calories"]
        kcal_left_total -= pick["calories"]
        qty_bought[pick["name"]] = qty_bought.get(pick["name"], 0) + 1

    kcal_per = kcal_used / people if people else 0
    lines = [f"=== 热量控制方案 | {people} 人 | 每人上限 {cal_max:g} 千卡 | 预算 {budget:g} 元 ==="]
    lines += fmt_list(chosen, show_kcal=True)
    lines.append(f"合计：{total:.1f} 元 | 预算剩余：{budget - total:.1f} 元 | "
                 f"全单约 {kcal_used:.0f} 千卡（人均 {kcal_per:.0f} / 上限 {cal_max:g}）")
    lines += notes_block(notes, [
        "主食热量控制在每人上限的 65% 内，给小食留空间；饮品优先零卡（零度/茶/水）",
        "共享小食按「满足度/千卡」降序补齐，且不超过剩余热量预算",
    ])
    return lines


# ================= 输出工具 =================
def fmt_list(chosen, show_kcal=False):
    order = {"套餐": 0, "主食": 1, "饮品": 2, "小食": 3, "甜品": 4}
    lines = []
    for it, q in sorted(chosen, key=lambda x: (order.get(x[0]["category"], 9), -x[0]["satiety"])):
        kcal_txt = f" | {it['calories']:g} 千卡/份" if show_kcal else ""
        lines.append(f"  [{it['category']}] {it['name']} ×{q}  @{it['price']:g} = {it['price']*q:g} 元{kcal_txt}")
    return lines


def notes_block(notes, rationale):
    lines = []
    if notes:
        lines.append("说明：" + "；".join(notes))
    lines.append("依据：")
    lines += [f"  {i+1}. {r}" for i, r in enumerate(rationale)]
    lines.append("注：价格为菜单快照价（热量为公开口径估算），实际以门店/App 为准。")
    return lines


def main():
    ap = argparse.ArgumentParser(description="麦当劳用餐搭配求解器 v2")
    ap.add_argument("--mode", choices=["meal", "save", "calorie"], default="meal")
    ap.add_argument("--people", type=int, default=1)
    ap.add_argument("--budget", type=float, default=None)
    ap.add_argument("--calorie-max", type=float, default=800, help="每人热量上限(千卡)")
    ap.add_argument("--items", type=str, default="", help="省钱模式：想吃的单品，逗号分隔")
    ap.add_argument("--no-spicy", action="store_true")
    ap.add_argument("--no-beef", action="store_true")
    ap.add_argument("--veg", type=int, default=0)
    ap.add_argument("--pescatarian", action="store_true")
    args = ap.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if args.mode == "save":
        items = [s.strip() for s in args.items.split(",") if s.strip()]
        lines = plan_save(items, args.no_spicy, args.no_beef)
    elif args.mode == "calorie":
        if args.budget is None:
            ap.error("calorie 模式需要 --budget")
        lines = plan_calorie(args.people, args.budget, args.calorie_max,
                             args.no_spicy, args.no_beef, args.veg, args.pescatarian)
    else:
        if args.budget is None:
            ap.error("meal 模式需要 --budget")
        lines = plan_meal(args.people, args.budget, args.no_spicy,
                          args.no_beef, args.veg, args.pescatarian)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
