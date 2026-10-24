# 麦门全能点餐助手（mcd-meal-planner）

一个 WorkBuddy Skill：**聚餐点餐、麦门省钱凑单、热量控制配餐、套餐推荐、活动新品推荐**，五个场景一个入口。搭配方案由确定性求解脚本计算（总价/总热量不靠心算），实时菜单、价格、活动、官方营养数据全部来自**麦当劳 MCP**。

> 2026 麦当劳程序员创意开发大赛 × WaytoAGI 1024 切磋大会「用餐」赛道参赛作品。
>
> **在线演示**：https://ni-guvara.github.io/mcd-meal-planner/ ｜ **零 Token 体验**：`cd skill/scripts && python plan_meal.py --demo`

## 它解决什么问题

点麦当劳的三大痛点：

1. **聚餐点餐算不清**——人数、预算、忌口凑一起，谁都不想心算总价；
2. **凑单不知道怎么省**——单点、套餐、1+1随心配、优惠券，价格规则太多；
3. **想吃又怕热量爆表**——官方营养数据散落在 App 各处，不好按上限配餐。

本 Skill 把这些交给一套确定性算法 + 麦当劳 MCP 实时数据：

| 场景 | 输入 | 输出 |
|---|---|---|
| 聚餐一键点餐 | 人数、预算、忌口（忌辣/忌牛肉/素食/不吃禽畜肉） | 完整搭配清单 + 总价 + 全单千卡 + 选择依据 |
| 麦门省钱凑单 | 想吃清单 | 套餐拆散点对比 + 1+1随心配平替 + 优惠后实付价 |
| 热量控制配餐 | 每人千卡上限、预算、口味 | 主食≤上限65%、零卡饮品优先的搭配 + 人均千卡 |
| 套餐推荐 | 口味偏好 | 基于 MCP 实时菜单的推荐 + 理由 |
| 活动新品推荐 | — | MCP 活动日历：进行中/即将开始的营销活动 |

## 快速开始

### 1. 安装 Skill

把 `skill/` 目录复制到 WorkBuddy 用户级技能目录：

```
~/.workbuddy/skills/mcd-meal-planner/
├── SKILL.md              # 场景路由 + 工作流
├── scripts/plan_meal.py  # 确定性求解器（三模式）
└── references/menu.csv   # 菜单快照兜底（价格+官方热量+标签）
```

### 2. 配置麦当劳 MCP

在 open.mcd.cn/mcp 申请 MCP Token 后，在 WorkBuddy【连接器】→【自定义连接器】→【配置MCP】中填入（**替换为你的 Token**）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

保存并启用 `mcd-mcp`。Token 也可以用环境变量管理，不要提交到仓库。

### 3. 使用

在 WorkBuddy 对话框里直接说：

- 「4 个人 150 块，两人不吃辣，点个麦当劳」→ 聚餐方案
- 「我要一个巨无霸套餐加麦乐鸡和可乐，怎么买最划算」→ 省钱单
- 「帮我配个 700 卡以内的麦当劳，预算 80」→ 热量方案
- 「麦当劳最近有什么活动新品」→ 活动日历

也可以直接跑求解脚本（离线快照模式）：

```bash
python skill/scripts/plan_meal.py --people 4 --budget 150 --no-spicy --veg 1
python skill/scripts/plan_meal.py --mode save --items "巨无霸套餐,麦乐鸡5块,可口可乐(中)"
python skill/scripts/plan_meal.py --mode calorie --people 2 --budget 80 --calorie-max 700
```

## 目标用户

- 拉群点麦当劳的打工人/学生（聚餐场景）
- 精打细算的「麦门」信徒（省钱凑单）
- 健身减脂期但馋麦当劳的人（热量控制）
- 想追新品和活动的尝鲜党

## 目录结构

```
├── README.md                 # 本文件
├── CONTEST_DECLARATION.md    # 参赛声明（官方原文，未改动）
├── MCP_INTEGRATION.md        # 麦当劳 MCP 集成说明与实测记录
├── workbuddy.md              # WorkBuddy 开发对话记录（提交前导出替换）
└── skill/                    # Skill 源码（可直接放入 ~/.workbuddy/skills/）
    ├── SKILL.md
    ├── scripts/plan_meal.py
    └── references/menu.csv
```

## 说明

- 快照价格仅为离线兜底，实际价格以 `calculate-price` 返回的实时结果为准
- 热量数据来自麦当劳 MCP `list-nutrition-foods` 官方口径
- 本项目为参赛者独立开发，非麦当劳官方产品
