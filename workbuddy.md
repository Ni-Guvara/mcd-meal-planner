# workbuddy.md — WorkBuddy 开发对话记录

> 本文件为开发过程记录（按实际开发时间线整理）。如与 WorkBuddy 内导出的对话原文有出入，以官方导出为准。

## 项目

**麦门全能点餐助手（mcd-meal-planner）**——基于麦当劳 MCP 的 WorkBuddy Skill，覆盖聚餐点餐、麦门省钱凑单、热量控制配餐、套餐推荐、活动新品推荐五个场景。

开发时间：2026-10-24，开发工具：WorkBuddy（AI Agent 对话式开发）。

## 开发时间线

### 1. 需求确认与方案设计

- 开发者提供 1024 切磋大会「用餐」赛道海报，要求：做一个用餐 Skill，输入人数/预算/口味饮食偏好，输出搭配清晰、总价与选择有依据的麦当劳点餐方案。
- 讨论了「五个功能做成五个 Skill vs 一个 Skill」：结论是**单 Skill 多场景**（避免触发词打架、共享数据与算法底座），SKILL.md 内做场景路由。
- 确定数据源策略：**麦当劳 MCP 实时数据优先，内置菜单快照兜底**。

### 2. Skill 骨架与求解器 v1

- 使用 skill-creator 初始化 `~/.workbuddy/skills/mcd-meal-planner/`。
- 编写 `references/menu.csv`（30 SKU：价格+热量+标签）与 `scripts/plan_meal.py`（确定性求解脚本，总价不靠模型心算）。
- 聚餐模式算法：忌口硬过滤 → 人均预算分档选主食（套餐优先 > 主食+饮品 > 1+1随心配，动态人均防吃垮预算）→ 素食者固定篮子 → 每人补饮品 → 剩余预算按「满足度/元」补共享小食（带多样性上限）。
- 5 个演示 case 回归测试通过；修复 CSV BOM 编码问题（`utf-8-sig`）。

### 3. 升级 v2：三模式求解器

- 开发者确认五场景合并方案后升级：新增**省钱凑单模式**（套餐拆散点对比 + 1+1随心配平替）与**热量控制模式**（主食≤每人上限65%、零卡饮品优先、按满足度/千卡补小食）。
- menu.csv 增加热量列；SKILL.md 增加五场景路由表。
- 修复两个回归 bug（参数漏传、列表结构不一致）后全模式测试通过。

### 4. 接入麦当劳 MCP

- 开发者提供 MCP Token，按官方指南（github.com/M-China/mcd-mcp-server）以 Streamable HTTP + Bearer 认证写入 WorkBuddy 连接器配置，开发者在连接器页面启用。
- 依据官方工具清单，将 35+ 工具按场景映射进 SKILL.md（query-meals / query-meal-detail / list-nutrition-foods / calculate-price / campaign-calendar / 各优惠券工具等）。

### 5. MCP 全链路实测（2026-10-24）

六个工具真实调用全部返回 200（详见 MCP_INTEGRATION.md「实测记录」）：

1. `now-time-info` — 服务器时间
2. `list-nutrition-foods` — 160 项官方营养数据，并据此修正快照热量（如圆筒冰淇淋 200→93 千卡）
3. `query-nearby-stores` — 西安市大雁塔关键词搜索，返回 5 家门店
4. `campaign-calendar` — 2026 年 10 月活动时间线（GD 联名、龙焰鸡腿堡三件套 26.9 元起等）
5. `query-meals` — 大雁塔北广场店（storeCode 1960674）12 分类约 100 商品实时价
6. `calculate-price` — 2×麦辣鸡腿堡三件套 + 1×麦乐鸡5块 + 2×圆筒冰淇淋 = 123.50 元

实测发现实时菜单价格与静态快照差异 10-20%，最终确立设计原则：**搭配由本地脚本确定性计算，实付价格一律以 calculate-price 为准**。

### 6. 比赛材料

- 整理 GitHub 仓库：README.md、MCP_INTEGRATION.md、CONTEST_DECLARATION.md（官方原文未改动）、skill/ 源码。
- 安全处理：参赛声明要求不包含真实 Token，所有配置示例使用占位符 `YOUR_MCP_TOKEN`。

## 关键设计决策

| 决策 | 理由 |
|---|---|
| 单 Skill 五场景而非五个 Skill | 触发词不打架；菜单/算法底座共享；作品聚焦 |
| 求解用确定性脚本而非模型心算 | 总价/总热量可复现可审计，杜绝算错 |
| MCP 优先 + 快照兜底 | 实时价格/活动必须官方数据；MCP 故障时 Skill 仍可用并标注时效 |
| 实付价以 calculate-price 为准 | 实测快照与实时价差 10-20%，静态数据不可作报价依据 |
