# My Telemon Backend

一个基于 FastAPI 构建的 Telegram 监控后端服务，用于实时监控指定频道的消息并通过 Telegram Bot 发送关键词匹配提醒。

## 🚀 功能特性

- **实时监控**: 基于 Telethon 监听指定 Telegram 频道的消息
- **关键词匹配**: 支持自定义关键词列表，支持普通字符串匹配和正则表达式匹配两种模式
- **服务端配置**: 所有敏感信息（API 凭证、Bot 配置）由服务器统一管理，安全可靠
- **Telegram Bot 通知**: 集成 Telegram Bot API，统一向指定聊天室发送通知消息
- **异步架构**: 基于 FastAPI 异步框架，支持多个监控任务同时运行
- **会话管理**: 自动维护 Telegram 客户端会话，无需重复登录
- **RESTful API**: 提供简洁的 HTTP 接口，便于前端集成

## 📁 项目结构

```
my-telemon-backend/
├── server.py          # 主程序入口，包含 API 路由和监控逻辑
├── config.py          # 服务器配置文件（通过 setup.py 自动生成）
├── setup.py           # 首次配置脚本
├── requirements.txt    # Python 依赖列表
├── start.sh           # 便捷启动脚本
├── sessions/          # Telegram 会话文件存储目录（自动创建）
└── README.md          # 项目说明文档
```

## 🛠 技术栈

- **后端框架**: FastAPI
- **异步服务器**: Uvicorn
- **Telegram 客户端**: Telethon
- **数据验证**: Pydantic
- **HTTP 客户端**: httpx (用于 Telegram Bot API 调用)
- **邮件验证**: email-validator (支持 EmailStr 类型)

## 📋 前置要求

- Python 3.8+
- Telegram API 凭证 (API ID 和 API Hash)
- Telegram Bot Token 和 Chat ID

### 获取 Telegram API 凭证

1. 访问 [https://my.telegram.org/](https://my.telegram.org/)
2. 使用你的手机号登录
3. 在 "API development tools" 页面创建新应用
4. 获取 `api_id` 和 `api_hash`

### 获取 Telegram Bot Token

1. 在 Telegram 中搜索 @BotFather
2. 发送 `/newbot` 命令创建新机器人
3. 按照指示设置机器人名称和用户名
4. 获取 Bot Token
5. 将机器人添加到目标聊天室中
6. 获取 Chat ID（可使用 @userinfobot 或直接查看聊天室信息）

**支持多个通知目标**：
- 个人私聊：正整数 Chat ID（如 `123456789`）
- 群组：负整数 Chat ID（如 `-987654321`）
- 频道：以 `-100` 开头的 Chat ID（如 `-1001234567890`）

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd my-telemon-backend
```

### 2. 安装依赖

```bash
# 激活虚拟环境（如果存在）
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 一键启动服务

**推荐方式**（自动处理所有配置）：

```bash
# 开发模式（带热重载）- 推荐
./start.sh dev

# 生产模式
./start.sh
```

**脚本自动处理**：
- ✅ 自动检测虚拟环境并激活
- ✅ 自动安装缺失的依赖
- ✅ 自动检测并引导首次配置
- ✅ 自动验证 Telegram 认证状态
- ✅ 启动服务

**重新配置**（如需要）：

```bash
# 强制重新配置
./start.sh --setup
```

> **💡 提示**: 首次运行时，脚本会自动引导您完成 Telegram API 和 Bot 的配置，无需手动操作。

## 📚 API 文档

### 1. 启动监控

**POST** `/monitor/start`

启动一个新的 Telegram 频道监控任务。

#### 请求参数

**Content-Type**: `application/json`

**请求体 (JSON)**:
``json
{
  "id": "monitor_001",
  "channel": "@channel_username", 
  "keywords": ["关键词1", "关键词2"],
  "useRegex": false
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| id | string | ✅ | 监控任务的唯一标识符，由前端生成 |
| channel | string | ✅ | 目标频道标识符，支持多种格式 |
| keywords | string[] | ✅ | 关键词列表（空数组匹配所有消息） |
| useRegex | boolean | ❌ | 是否使用正则表达式匹配（默认false） |

> **⚠️ 重要说明**: 
> - 所有敏感信息（API凭证、Bot配置）由服务器端统一管理
> - 前端只需提供业务逻辑参数
> - 通知将自动发送到服务器配置的所有Chat ID

#### 频道格式支持

支持多种频道标识符格式，系统会自动转换：

| 输入格式 | 转换结果 | 说明 |
|----------|----------|------|
| `@channel_username` | `@channel_username` | 推荐格式 |
| `https://t.me/channel_username` | `@channel_username` | 完整URL |
| `t.me/channel_username` | `@channel_username` | 简化URL |
| `channel_username` | `@channel_username` | 纯用户名 |

#### 关键词匹配模式

**普通字符串匹配** (`useRegex: false`):
- 不区分大小写的包含匹配
- 示例：关键词 `"比特币"` 匹配 `"今天比特币价格上涨"`

**正则表达式匹配** (`useRegex: true`):
- 支持完整正则语法，不区分大小写
- JSON中需要双反斜杠转义
- 语法错误时自动降级为字符串匹配

``json
// 正则表达式示例
{
  "keywords": [
    "\\\\d+",                    // 匹配数字
    "\\\\$\\\\d+\\\\.\\\\d{2}",        // 匹配价格格式 $45.99
    "[\\\\u4e00-\\\\u9fa5]+"       // 匹配中文字符
  ],
  "useRegex": true
}
```

#### 响应格式

**成功响应** (200):
``json
{
  "message": "监控 monitor_001 已成功启动"
}
```

**错误响应** (400/500):
```json
{
  "detail": "频道标识符错误: 频道标识符不能为空"
}
```

#### 常见错误码

| 状态码 | 错误类型 | 说明 |
|--------|----------|------|
| 400 | 参数错误 | 频道格式错误、ID重复等 |
| 500 | 服务器配置错误 | API凭证或Bot配置不完整 |
| 500 | 连接错误 | 无法连接Telegram或找不到频道 |

### 2. 停止监控

**POST** `/monitor/stop`

停止指定的监控任务。监控配置将保留，可以后续恢复。

#### 请求参数

```json
{
  "id": "monitor_001"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| id | string | ✅ | 要停止的监控任务ID |

#### 响应格式

**成功响应** (200):
``json
{
  "message": "监控 monitor_001 已停止"
}
```

**错误响应** (404):
```json
{
  "detail": "未找到监控 monitor_001"
}
```

### 3. 恢复监控

**POST** `/monitor/resume`

恢复已停止的监控任务。使用之前保存的配置重新启动监控。

#### 请求参数

```json
{
  "id": "monitor_001"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| id | string | ✅ | 要恢复的监控任务ID |

#### 响应格式

**成功响应** (200):
``json
{
  "message": "监控 monitor_001 已成功恢复"
}
```

**错误响应** (400/404/500):
```json
{
  "detail": "未找到监控 monitor_001 的配置"
}
```

#### 常见错误码

| 状态码 | 错误类型 | 说明 |
|--------|----------|---------|
| 400 | 状态错误 | 监控已在运行或配置错误 |
| 404 | 配置不存在 | 未找到监控配置 |
| 500 | 服务器错误 | 恢复失败或配置错误 |

### 4. 删除监控

**POST** `/monitor/delete`

彻底删除监控任务和配置。这是不可逆的操作，删除后无法恢复。

#### 请求参数

```json
{
  "id": "monitor_001"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| id | string | ✅ | 要删除的监控任务ID |

#### 响应格式

**成功响应** (200):
``json
{
  "message": "监控 monitor_001 已彻底删除"
}
```

**错误响应** (404):
```json
{
  "detail": "未找到监控 monitor_001"
}
```

### 5. 查看状态

**GET** `/status`

获取当前所有监控任务的详细信息（包括已停止的）。

#### 响应格式

**成功响应** (200):
```json
{
  "active_monitors": ["monitor_001"],
  "monitors": [
    {
      "id": "monitor_001",
      "channel": "tech_news",
      "keywords": ["AI", "人工智能"],
      "useRegex": false,
      "status": "running"
    },
    {
      "id": "monitor_002",
      "channel": "crypto_news",
      "keywords": ["Bitcoin", "以太坊", "区块链"],
      "useRegex": true,
      "status": "stopped"
    },
    {
      "id": "monitor_003",
      "channel": "news_channel",
      "keywords": ["破发", "紧急"],
      "useRegex": false,
      "status": "error"
    }
  ]
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| active_monitors | string[] | 活跃监控ID列表（向后兼容） |
| monitors | object[] | 所有监控信息列表（包括已停止的） |

**monitors 数组对象字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 监控任务ID |
| channel | string | 频道名称（自动去除@前缀） |
| keywords | string[] | 关键词列表 |
| useRegex | boolean | 是否使用正则表达式匹配 |
| status | string | 监控状态 |

**监控状态说明**:

| 状态 | 说明 |
|------|------|
| running | 正在运行 |
| stopped | 已停止（可恢复） |
| starting | 启动中 |
| error | 错误状态（可重试） |

**空状态响应**（无监控任务时）:
```json
{
  "active_monitors": [],
  "monitors": []
}
```

### 6. 检查服务器配置

**GET** `/config/check`

检查服务器的 Telegram API 和 Bot 配置状态。主要用于前端验证服务器配置完整性。

#### 响应格式

```json
{
  "telegram_config_valid": true,
  "bot_config_valid": true,
  "all_ready": true,
  "telegram_message": "已配置 Telegram API",
  "bot_message": "已配置 3 个通知目标"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| telegram_config_valid | boolean | Telegram API配置是否有效 |
| bot_config_valid | boolean | Bot配置是否有效 |
| all_ready | boolean | 所有配置是否就绪 |
| telegram_message | string | Telegram配置状态描述 |
| bot_message | string | Bot配置状态描述 |

## ⚙️ 配置说明

### Telegram Bot 配置

配置 Telegram Bot 通知需要以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| botToken | 从 @BotFather 获取的机器人 Token | 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz |
| chatIds | 目标聊天室的 ID 列表（支持多个目标） | ["123456789", "-987654321", "-1001234567890"] |

**支持多个通知目标**：
- **个人私聊**：正整数 Chat ID（如 `123456789`）
- **群组**：负整数 Chat ID（如 `-987654321`）
- **频道**：以 `-100` 开头的 Chat ID（如 `-1001234567890`）

**配置方式**：
- 环境变量：`TELEGRAM_CHAT_IDS="123456789,-987654321,-1001234567890"`
- 配置文件：直接修改 `config.py` 中的 `chat_ids` 列表
- 设置脚本：运行 `python setup.py` 按提示配置

**获取 Chat ID 的方法：**

1. **私聊**: 使用 @userinfobot 查看你的用户 ID
2. **群组**: 将机器人添加到群组后，可以通过 API 或第三方工具获取
3. **频道**: 使用 格式：`-100` + 频道ID（去掉前缀）

### 关键词匹配

支持两种匹配模式：

**1. 普通字符串匹配** (默认模式)
- 不区分大小写的字符串包含匹配
- 简单易用，适合大多数场景
- 示例：关键词 "测试" 可以匹配 "这是一个测试消息"

**2. 正则表达式匹配** (useRegex: true)
- 支持复杂的模式匹配
- 适合需要精确匹配的场景（如数字、邮箱、URL等）
- 具有强大的灵活性和表达能力

**共同特性:**
- 支持多个关键词，任一匹配即触发通知
- 关键词列表为空时，匹配所有消息
- 匹配过程不区分大小写

## 🔧 高级配置

### 自定义会话目录

默认会话文件存储在 `sessions/` 目录。可以通过修改 `server.py` 中的 `SESSION_DIR` 变量来自定义：

```python
SESSION_DIR = "custom_sessions"
```

### CORS 配置

默认允许所有来源的跨域请求。生产环境建议修改为具体的前端域名：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🐛 故障排除

### 常见问题

1. **配置文件缺失**
   - 运行 `./start.sh --setup` 重新配置
   - 或手动运行 `python setup.py` 进行配置

2. **Telegram 认证失败**
   - 检查 API ID 和 API Hash 是否正确
   - 确保网络连接正常
   - 首次使用需要在控制台输入验证码
   - 会话文件损坏时需要重新认证

3. **Telegram Bot 通知失败**
   - 检查服务器 Bot Token 是否正确
   - 确认所有 Chat ID 格式是否正确
   - 确保机器人已被添加到所有目标聊天室
   - 查看控制台日志确认发送状态

4. **监控无法启动**
   - 检查频道名称是否正确
   - 确保 Telegram 账户已加入该频道
   - 检查服务器配置是否完整（运行 `/config/check`）
   - 查看终端日志获取详细错误信息

5. **服务启动失败**
   - 运行 `./start.sh` 查看具体错误信息
   - 检查虚拟环境是否正确激活
   - 确认所有依赖已安装

### 日志查看

服务运行时会在终端输出详细日志，包括：
- 监控启动/停止状态
- 消息接收情况
- 关键词匹配结果
- Telegram Bot 通知发送状态（包括每个 Chat ID 的成功/失败情况）
- 发送结果汇总（成功数量/失败数量）

**日志示例**：
```
[monitor-001] ✅ Telegram 通知已发送至 123456789
[monitor-001] ❌ 发送至 -987654321 失败: 403 - Bot was blocked by the user
[monitor-001] ✅ Telegram 通知已发送至 -1001234567890
[monitor-001] 📄 发送完成: 成功 2/3, 失败 1
[monitor-001] ⚠️  失败的Chat ID: ['-987654321']
```

## 🔐 安全注意事项

1. **配置文件安全**: `config.py` 包含敏感信息，不要提交到版本控制系统（已在 .gitignore 中排除）
2. **会话文件保护**: `sessions/` 目录包含 Telegram 登录凭证，需要妥善保管
3. **Bot Token 安全**: 定期更换 Bot Token，避免泄露
4. **网络安全**: 生产环境建议使用 HTTPS 和防火墙保护
5. **CORS 配置**: 生产环境应限制跨域访问来源，不要使用 `allow_origins=["*"]`

## 📝 开发说明

### 正则表达式使用示例

以下是一些常用的正则表达式匹配示例：

```json
{
  "id": "regex_monitor",
  "channel": "@news_channel",
  "keywords": [
    "\\d{4}-\\d{2}-\\d{2}",     // 匹配日期格式 (2024-01-01)
    "\\$\\d+",                   // 匹配美元价格 ($100)
    "[\\u4e00-\\u9fa5]{2,4}股",   // 匹配中文股票名称 (如：腾讯股)
    "\\b(Bitcoin|BTC)\\b",       // 匹配比特币相关词汇
    "\\w+@\\w+\\.\\w+"          // 匹配邮箱地址
  ],
  "useRegex": true
}
```

**注意事项：**
- JSON 中的反斜杠需要双重转义（`\\` 表示一个反斜杠）
- 正则表达式匹配不区分大小写
- 如果正则表达式语法错误，会自动降级为普通字符串匹配
- 建议在测试环境中验证正则表达式的正确性

### 项目架构

```
FastAPI 应用
├── CORS 中间件
├── Pydantic 数据模型
│   ├── TelegramBotConfig
│   ├── MonitorConfig
│   └── StopRequestBody
├── API 路由
│   ├── /monitor/start
│   ├── /monitor/stop
│   └── /status
└── 核心功能
    ├── Telethon 客户端管理
    ├── 异步消息监听
    └── Telegram Bot 通知发送
```

### 扩展开发

要添加新功能，可以：

1. 在 Pydantic 模型中添加新的配置字段
2. 扩展监控逻辑处理更多事件类型
3. 添加其他通知方式（如邮件、微信、钉钉等）
4. 集成数据库存储监控历史

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

如有问题或建议，请创建 Issue 或联系项目维护者。