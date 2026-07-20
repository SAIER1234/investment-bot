# 投资顾问机器人 🤖📊

每天收盘后自动推送持仓分析 + AI操作建议到你的微信。

## 它做什么

1. **17:30** 自动抓取你的基金净值、ETF行情、板块走势、重仓股动态
2. 把数据喂给 **DeepSeek**，生成激进风格的投资建议
3. 通过 **PushPlus** 推送到你的微信
4. 每个交易日稳定运行，零维护

## 报告内容

```
📊 每日投资报告 | 2026年7月20日 周一

━━━━ 大盘 ━━━━
上证 3XXX.XX (+0.XX%)  创业板 2XXX.XX (-0.XX%)

━━━━ 你的持仓 ━━━━
159516 半导体设备ETF国泰
  最新价 0.643  今日 -2.43%  折价 -8.2%
  近一周 -22.5% | 近一月 -6.2% | 今年以来 +82.0%
  判断: 🔥 加仓
  建议价位: 0.62-0.66
  建议仓位: 占总资金20-25%
  理由: ...
  风险: ...

003579 沪深300 ...

━━━━ 重仓股动态 ━━━━
北方华创 677.00 (-3.67%)  中微公司 350.69 (-2.97%)

━━━━ 🤖 整体评价 ━━━━
...
```

## 快速开始（3步，5分钟）

### Step 1: 获取 API Key

| 服务 | 操作 | 费用 |
|------|------|------|
| **DeepSeek** | 去 [platform.deepseek.com](https://platform.deepseek.com/) 注册，充值10元够用几个月 | ¥10起充 |
| **PushPlus** | 微信扫码 [pushplus.plus](https://www.pushplus.plus/) → 一键登录 → 复制 token | 免费 |

### Step 2: 配置密钥

把 `.env.example` 复制为 `.env`，填入刚才拿到的 key：

```bash
cp .env.example .env
```

编辑 `.env`:
```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
PUSHPLUS_TOKEN=xxxxxxxxxxxxxxxx
```

### Step 3: 推送到 GitHub + 配置 Secrets

1. 把这个目录推到你的 GitHub 仓库（公开或私有都行，公开=无限Actions额度）
2. 在仓库 **Settings → Secrets and variables → Actions** 中添加：
   - `DEEPSEEK_API_KEY` = 你的 DeepSeek key
   - `PUSHPLUS_TOKEN` = 你的 PushPlus token
3. 去 **Actions** 标签页，手动触发一次 `每日投资报告` 测试

完成！每天17:30微信准时收到报告。

## 修改持仓

编辑 `config/portfolio.json`，按格式添加/删除基金。不改代码。

```json
{
  "holdings": [
    {
      "code": "159516",
      "name": "半导体设备ETF国泰",
      "type": "ETF",
      "amount": 20000,
      "planned": false
    }
  ]
}
```

- `type`: `ETF` 或 `场外基金`
- `planned: true` = 还没买，计划买入（AI会在建议里特别标注）

## 调整 AI 风格

编辑 `config/system_prompt.md`，改 AI 的角色和行为规则。不需要改 Python 代码。

## 目录结构

```
investment-bot/
├── .github/workflows/daily_report.yml   # GitHub Actions 定时
├── config/
│   ├── portfolio.json                   # 持仓配置
│   └── system_prompt.md                 # AI 系统提示词
├── src/
│   ├── main.py                          # 主入口
│   ├── fetch_data.py                    # akshare 数据抓取
│   ├── analyze.py                       # DeepSeek AI 分析
│   └── push_wechat.py                   # PushPlus 微信推送
├── data/                                # 历史数据缓存
├── .env.example
└── requirements.txt
```

## 常见问题

**Q: 为什么17:45才收到？**
A: 场外基金净值通常在17:00-18:00间公布，GitHub Actions有轻度延迟。如果某天净值还没出，报告会标注"N/A"。

**Q: 周末/节假日会推送吗？**
A: 不会，只周一到周五运行。节假日手动关闭 Actions 即可。

**Q: 费用？**
A: DeepSeek约¥0.5-1/天（按2-3万token算，约¥0.0014/千token），PushPlus免费。一个月不到¥30。

**Q: 能加晨间晨报/推特推送吗？**
A: 在 Phase 2 计划中，投资机器人跑稳定了就做。
