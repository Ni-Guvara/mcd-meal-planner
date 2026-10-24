# MCP 集成说明（MCP_INTEGRATION.md）

## 使用的 MCP Server

| 项 | 值 |
|---|---|
| 名称 | 麦当劳中国官方 MCP（mcd-mcp） |
| 接入地址 | `https://mcp.mcd.cn` |
| 协议 | Streamable HTTP |
| 认证 | `Authorization: Bearer <MCP_TOKEN>`（Token 从 open.mcd.cn/mcp 申请，本仓库不包含真实 Token） |
| 官方指南 | github.com/M-China/mcd-mcp-server |

## 实际调用的 Tool 与用途

| Tool | 在本 Skill 中的用途 |
|---|---|
| `now-time-info` | 获取服务器时间，为活动日历判断「进行中/未来」提供锚点 |
| `list-nutrition-foods` | 官方营养数据（能量/蛋白质/脂肪/碳水/钠/钙），用于热量控制配餐场景；已同步至快照 `menu.csv` |
| `query-nearby-stores` | 到店场景查询用户附近可点餐门店，返回 storeCode 供后续调用 |
| `query-meals` | 查询指定门店实时菜单（分类、商品编码、现价/原价、优惠类型），是搭配推荐与省钱计算的数据源 |
| `calculate-price` | 按商品列表计算实付总价（含优惠、打包费），价格单位为分；本 Skill 的「最终多少钱」以此为准 |
| `query-store-coupons` / `available-coupons` / `auto-bind-coupons` / `query-my-coupons` | 省钱凑单场景查询与领取优惠券 |
| `campaign-calendar` | 活动新品推荐场景，返回当月营销活动时间线 |
| `create-order` / `cancel-order` / `query-order` | （可选进阶）确认价格后真实下单、取消与订单查询 |

## 调用流程

```
用户需求（人数/预算/忌口/想吃清单/热量上限）
        │
        ▼
[now-time-info] 取当前时间 ──────────► [campaign-calendar] 活动新品场景
        │
        ▼
[query-nearby-stores] 查附近门店 ──► 选定 storeCode（本文实测：西安大雁塔北广场店 1960674）
        │
        ▼
[query-meals] 拉实时菜单（商品 code + 现价） ──► [list-nutrition-foods] 官方热量（热量场景）
        │
        ▼
plan_meal.py 确定性求解（分档选主食 / 省钱平替 / 热量约束，见 skill/scripts/）
        │
        ▼
[available-coupons] 查券标题 ──► 翻译为券 JSON ──► 脚本券最优匹配（逐券枚举实减 + 凑单陷阱判断）
        │
        ▼
[calculate-price] 实付价核算（分→元，最终以此为准）
        │
        ▼
输出方案：搭配清单 + 总价 + 全单千卡 + 选择依据（可选：create-order 真实下单）
```

## 实测记录（2026-10-24）

以下为开发时真实调用结果（西安，大雁塔北广场餐厅 storeCode=1960674，到店自取 beType=1 / orderType=1）：

1. **now-time-info** → `2026-10-24 14:33:02 GMT+08:00`，code 200
2. **list-nutrition-foods** → 返回 160 项餐品营养数据（如：巨无霸 513 千卡、麦辣鸡腿汉堡 485 千卡、圆筒冰淇淋 93 千卡），code 200
3. **query-nearby-stores**（city=西安市，keyword=大雁塔）→ 返回 5 家门店，最近 308 米，含 storeCode、营业时间、预约时段，code 200
4. **campaign-calendar** → 返回 2026 年 10 月活动时间线（GD 联名系列、龙焰鸡腿堡三件套 26.9 元起、麦金卡四件套 29 元起等），code 200
5. **query-meals** → 返回该门店 12 个分类、约 100 个在售商品及实时价格（如麦辣鸡腿汉堡三件套 49 元、巨无霸三件套 54.5 元、龙焰鸡腿堡三件套 53 元），code 200
6. **calculate-price**（2×麦辣鸡腿堡三件套 + 1×麦乐鸡5块 + 2×圆筒冰淇淋）→ 原价 12350 分 = **123.50 元**，无适用优惠，返回堂食/外带取餐选项，code 200
7. **available-coupons** → 返回可领券列表（免费脆薯饼 / 11.9 元麦辣鸡腿堡 / 19.9 元王牌炸鸡任选 2），券标题翻译为结构化券 JSON 后喂给求解器做券最优匹配——实测「麦辣鸡腿堡+脆薯饼+可乐」原价 44 元 → 1+1 平替 + 免费脆薯饼券后 **13.9 元**，且满减券凑单判断正确给出「倒贴 8.5 元，不值」，code 200

> 实测发现实时菜单价格与任何静态快照均有差异（部分品类快照价偏低 10-20%），因此本 Skill 设计为：**搭配逻辑由本地脚本计算，最终价格一律以 `calculate-price` 为准**。

## 错误处理

- `401`：Token 无效/过期 → 提示用户到 open.mcd.cn/mcp 重新获取
- `429`：超过 600 次/分钟限流 → 脚本内置调用合并与间隔控制
- MCP 不可用时：三模式（聚餐/省钱/热量）自动降级为快照数据离线运行，活动新品场景如实提示需要联网

## 业务价值

1. **真实性**：门店、菜单、价格、活动全部来自麦当劳官方 MCP，方案可直接执行
2. **确定性**：搭配与算价核心在本地脚本完成，总价/总热量可复现、可审计，不依赖模型心算
3. **降级可用**：MCP 故障时快照兜底，Skill 永远能给出一个方案并明确标注数据时效
