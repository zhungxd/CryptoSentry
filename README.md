# Trace - 虚拟货币价格监控系统

基于币安API的实时加密货币价格监控系统，支持多种技术指标分析和钉钉机器人通知。

## 功能特性

- **实时行情**：通过币安WebSocket实时获取K线数据
- **价格日志**：定时输出监控币种的实时价格与涨跌幅
- **行情异动报警**：价格相对当根K线开盘价涨跌超过阈值时，钉钉推送通知
- **技术指标**：8种主流指标，插件式架构，可自由扩展
  - RSI（相对强弱指数）
  - MACD（移动平均收敛散度）
  - 布林带（Bollinger Bands）
  - EMA（指数移动平均线）
  - KDJ（随机指标）
  - ATR（真实波幅）
  - SuperTrend（趋势跟踪）
  - OBV（能量潮/量价背离）
- **信号系统**：多指标共振判断，信号强度评级（弱/中/强），冷却防重复
- **钉钉通知**：加签安全验证，Markdown格式消息，发送频控
- **数据存储**：SQLite存储K线历史和信号记录

## 项目结构

```
trace/
├── config.yaml              # 配置文件
├── requirements.txt         # Python依赖
├── main.py                  # 入口文件
├── core/
│   ├── market.py            # 币安API连接（REST + WebSocket）
│   ├── storage.py           # SQLite数据存储
│   ├── signal.py            # 买卖信号判断与聚合
│   └── indicators/          # 技术指标（插件式）
│       ├── base.py          # 指标基类
│       ├── rsi.py
│       ├── macd.py
│       ├── bollinger.py
│       ├── ema.py
│       ├── kdj.py
│       ├── atr.py
│       ├── supertrend.py
│       └── volume.py
└── notify/
    └── dingtalk.py          # 钉钉机器人通知
```

## 快速开始

### 1. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 2. 修改配置

编辑 `config.yaml`：

```yaml
proxy:
  enabled: true
  http: "http://127.0.0.1:7897"    # 你的代理地址
  https: "http://127.0.0.1:7897"

dingtalk:
  webhook: "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
  secret: "YOUR_SECRET"
```

### 3. 测试连接

```bash
python3 main.py --test
```

### 4. 启动监控

```bash
# 前台运行
python3 main.py

# 后台运行
python3 main.py --daemon
```

## 配置说明

### 代理

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `proxy.enabled` | 是否启用代理 | `true` |
| `proxy.http` | HTTP代理地址 | - |
| `proxy.https` | HTTPS代理地址 | - |

### 交易对

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `symbols[].name` | 币种名称 | - |
| `symbols[].intervals` | K线周期 | `["1h", "4h", "1d"]` |
| `symbols[].price_alerts` | 价格突破提醒价位列表 | - |

### 价格日志

定时在控制台输出所有监控币种的实时价格和1h涨跌幅。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `price_log.enabled` | 是否启用 | `true` |
| `price_log.interval_seconds` | 输出间隔（秒） | `1800`（30分钟） |

### 行情异动报警

当价格相对当根1h K线开盘价涨跌超过阈值时，发送钉钉通知并记录日志。同一币种在冷却时间内不重复报警。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `price_change_alert.enabled` | 是否启用 | `true` |
| `price_change_alert.pct_threshold` | 涨跌幅阈值（%） | `1.0` |
| `price_change_alert.cooldown_seconds` | 同币种报警冷却时间（秒） | `1800`（30分钟） |

### 技术指标

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `indicators.*.enabled` | 是否启用该指标 | `true` |
| `indicators.rsi.period` | RSI周期 | `14` |
| `indicators.rsi.overbought` | RSI超买线 | `70` |
| `indicators.rsi.oversold` | RSI超卖线 | `30` |
| `indicators.macd.fast/slow/signal` | MACD参数 | `12/26/9` |
| `indicators.bollinger.period` | 布林带周期 | `20` |
| `indicators.bollinger.std` | 布林带标准差倍数 | `2.0` |
| `indicators.ema.periods` | EMA周期列表 | `[7, 25, 99]` |
| `indicators.kdj.k_period/d_period/j_period` | KDJ参数 | `9/3/3` |
| `indicators.supertrend.period` | SuperTrend周期 | `10` |
| `indicators.supertrend.multiplier` | SuperTrend乘数 | `3.0` |
| `indicators.atr.period` | ATR周期 | `14` |

### 信号系统

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `signal.cooldown_seconds` | 信号冷却时间（秒） | `900`（15分钟） |
| `signal.max_notifications_per_hour` | 每小时最大通知数 | `10` |
| `signal.min_strength` | 最低信号强度 | `"medium"` |

### 钉钉通知

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `dingtalk.webhook` | 机器人Webhook地址 | - |
| `dingtalk.secret` | 加签密钥 | - |
| `dingtalk.message_type` | 消息格式（`markdown`/`text`） | `markdown` |
| `dingtalk.min_interval_seconds` | 发送频控，两次消息最小间隔（秒） | `20` |

## 新增指标

1. 在 `core/indicators/` 下创建新文件
2. 继承 `BaseIndicator`，实现 `calculate()` 和 `get_signals()`
3. 在 `core/indicators/__init__.py` 注册
4. 在 `config.yaml` 中添加配置并 `enabled: true`

## 通知示例

### 买入信号

```markdown
### 🟢 买入信号 - BTCUSDT

**信号强度**：强（3个指标共振）

**触发指标**：
- RSI: RSI(14)=28.5，进入超卖区域
- MACD: MACD金叉: DIF=120.5, DEA=115.3
- Bollinger: 价格触及布林带下轨

**当前价格**：$95,234.56
**K线周期**：4h
**时间**：2026-04-18 14:30:00
```

### 行情异动

```markdown
### 🔥 行情异动 - BTCUSDT

**方向**：上涨 +2.35%

**开盘价**：$84,500.00

**当前价**：$86,485.75

**变动额**：+$1,985.75

**时间**：2026-04-18 14:30:00
```

## 技术栈

- Python 3.9+
- aiohttp（异步HTTP/WebSocket）
- pandas + ta（数据处理与技术指标）
- aiosqlite（异步SQLite）
- 钉钉自定义机器人Webhook

## License

MIT
