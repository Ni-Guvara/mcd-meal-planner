---
name: mcd-meal-planner
description: 麦当劳用餐规划 Skill（麦门全能点餐助手）。覆盖五个场景：聚餐一键点餐（人数/预算/忌口→完整方案）、麦门省钱凑单（同一份想吃清单算出最省买法）、按热量和口味配套餐、套餐推荐、活动与新品推荐。触发词：点麦当劳、聚餐点餐、麦当劳搭配、用餐方案、开饭、麦门、省钱凑单、热量/卡路里点餐、麦当劳新品。总价与选择依据由确定性脚本计算，菜单数据自带快照兜底，配置 mcd-mcp 连接器后自动切换实时数据。
agent_created: true
---

# 麦门全能点餐助手（McD Meal Planner v2）

## Overview

一个 Skill、五个场景、一套底座。共享菜单数据（`references/menu.csv`，含价格+热量+标签）和确定性求解脚本（`scripts/plan_meal.py`），总价/总热量不靠心算。

## 场景路由（先判断场景，再走对应路径）

| 用户意图示例 | 场景 | 路径 |
|---|---|---|
| "4 个人 150 块点麦当劳，俩人不吃辣" | 聚餐点餐 | 脚本 `--mode meal`（默认） |
| "我要一个巨无霸套餐+麦乐鸡+可乐，怎么买最划算" | 麦门省钱凑单 | 脚本 `--mode save --items "..."` |
| "帮我配个 700 卡以内的麦当劳" / 减脂期 | 热量口味配套餐 | 脚本 `--mode calorie --calorie-max N` |
| "麦当劳有什么推荐""巨无霸和板烧哪个好" | 套餐推荐 | mcd-mcp 查实时菜单/评价 → 无 MCP 则用 menu.csv 直接推荐（给 2-3 个理由） |
| "最近有什么新品/活动" | 活动新品推荐 | **仅 mcd-mcp**（快照无此数据）；无 MCP 时如实说明并建议查 App |

### 需求收集原则

- 必需：人数+预算（聚餐/热量模式）；省钱模式只要"想吃清单"；推荐模式只要口味偏好
- 缺信息先按合理假设跑一版并标注假设，别铺一串问题
- 忌口映射：忌辣→`--no-spicy`；忌牛肉→`--no-beef`；素食 N 人→`--veg N`；不吃禽畜肉可吃鱼→`--pescatarian`

## 脚本调用（必做，不要手算）

```bash
# 聚餐（默认模式）
python "<skill目录>/scripts/plan_meal.py" --people 4 --budget 150 --no-spicy --veg 1

# 省钱凑单：items 用菜单里的名称，逗号分隔（支持模糊包含匹配）
python "<skill目录>/scripts/plan_meal.py" --mode save --items "巨无霸套餐,麦乐鸡5块,可口可乐(中)"

# 热量控制：每人上限，预算必填
python "<skill目录>/scripts/plan_meal.py" --mode calorie --people 2 --budget 80 --calorie-max 700
```

内置算法要点（输出里的"依据"与之一一对应，不要另编理由）：

1. 忌口硬过滤 → 2. 人均分档选主食（套餐 > 主食+饮品 > 1+1随心配，动态人均防吃垮预算）→ 3. 素食者固定篮子（薯条+派+饮品，麦当劳无素汉堡，如实说明）→ 4. 每人补饮品 → 5. 剩余预算按满足度/元（或/千卡）补共享小食，每种有数量上限
2. 省钱模式四板斧：套餐 vs 散点对比 → 1+1随心配平替 → **券最优匹配**（双路对比：优化后用券 vs 原单直接用券，取实付更低；满减券差一点时先算"凑单净省"，倒贴就提示不值）→ 快照价即价格上限

### 券最优匹配（省钱模式进阶）

连着 mcd-mcp 时，省钱模式先调 `available-coupons` 拿券标题，把每张券**翻译**成 JSON 传给脚本 `--coupons`。券模型（脚本头部注释同款，一张订单只能用一张券）：

```json
[
  {"name":"免费脆薯饼","type":"free_item","item":"脆薯饼"},
  {"name":"11.9元麦辣鸡腿堡","type":"fixed_price","item":"麦辣鸡腿堡","price":11.9},
  {"name":"19.9元王牌炸鸡任选2","type":"fixed_price_n","items":["麦辣鸡翅2块","麦乐鸡5块"],"count":2,"price":19.9},
  {"name":"满40减10","type":"threshold_discount","threshold":40,"discount":10},
  {"name":"全场8.8折","type":"percent","percent":0.88}
]
```

翻译规则：`item`/`items` 必须用 menu.csv（或 MCP 菜单）里的**确切单品名**；"XX元XX"标题 → `fixed_price`；"免费XX" → `free_item`；"N件任选" → `fixed_price_n`；满减/折扣按字面。翻译不准的（如通用代金券）宁可不传，别猜。

## mcd-mcp 数据源（实时数据优先，官方能力）

麦当劳中国官方 MCP（streamable HTTP，`https://mcp.mcd.cn`，Bearer token，已写入 `~/.workbuddy/mcp.json`；限流 600 次/分钟，401=token 失效、429=限流）。

**按场景映射工具：**

| 场景 | 用哪些 MCP 工具 |
|---|---|
| 套餐推荐 / 菜单 | `query-meals`（当前可售菜单）→ `query-meal-detail`（套餐组成/可替换项） |
| 热量配套餐 | `list-nutrition-foods`（**官方营养数据：能量/蛋白质/脂肪/钠**，优先于快照估算） |
| 麦门省钱凑单 | `available-coupons`/`query-my-coupons`（券标题翻译成 `--coupons` JSON）→ 脚本算散点/1+1/券最优匹配 → `calculate-price`（含券实付价，最终以它为准） |
| 活动新品 | `campaign-calendar`（活动日历）、`mall-points-products`（积分商城） |
| 真点餐（进阶） | `query-nearby-stores`/`delivery-query-stores` → `create-order` → `query-order`；取消用 `cancel-order` |
| 积分福利 | `query-my-account`（积分）、`auto-bind-coupons`（一键领券）、`draw-lottery`（抽奖） |
| 时间 | `now-time-info`（活动日历判断"进行中/未来"前先调它） |

**规则：**

- 配置了 mcd-mcp 的会话中，价格/菜单/活动一律 **MCP 实时数据优先**，`menu.csv` 快照只做兜底和离线演示
- 价格计算：脚本逻辑负责"怎么配"，`calculate-price` 负责"最终多少钱"——两者不一致时以 MCP 为准并说明
- 营养热量：连着 MCP 时用 `list-nutrition-foods` 的官方值替换快照估算值输出
- 未配置 MCP 时：三模式照常跑快照价，活动新品场景如实说"需要连麦当劳 MCP 或查 App"

## 输出格式

- 搭配清单：`[类别] 单品 ×数量 @单价 = 小计`（热量模式附每份千卡）
- 合计 + 预算剩余 + 全单千卡
- "依据"条目直接采用脚本输出，不要手写替代
- 固定尾注：快照价/估算热量，实际以门店/App 为准
- 用户要"单子/海报"→ 生成 HTML「开饭确认单」（M 黄底红字，点单小票风），present_files 展示

## 菜单数据维护

- `references/menu.csv`：`name,category,price,calories,satiety,tags`
- `category`：套餐/主食/小食/甜品/饮品；`tags` 用 `|` 分隔（辣/牛肉/鸡肉/鱼类/猪肉/素/套餐/含薯含饮/组合/共享/饮料|冰/零卡）
- `satiety`：满足度（套餐 5-6、主食 3-4、小食 1.5-3.5、甜品饮品 0.3-1.2）；`calories` 千卡
- 文件带 BOM，脚本已用 `utf-8-sig` 读取；照抄现有行格式新增即可
