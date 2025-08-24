# My Telemon Backend

一个基于 FastAPI 构建的 Telegram 监控后端服务，用于实时监控指定频道的消息并通过 Telegram Bot 发送关键词匹配提醒。

## 🚀 功能特性

- **实时监控**: 基于 Telethon 监听指定 Telegram 频道的消息
- **关键词匹配**: 支持自定义关键词列表，匹配时自动发送 Telegram Bot 提醒
- **Telegram Bot 通知**: 集成 Telegram Bot API，支持向指定聊天室发送通知消息
- **异步架构**: 基于 FastAPI 异步框架，支持多个监控任务同时运行
- **会话管理**: 自动维护 Telegram 客户端会话，无需重复登录
- **RESTful API**: 提供简洁的 HTTP 接口，便于前端集成

## 📁 项目结构

```
my-telemon-backend/
├── server.py          # 主程序入口，包含 API 路由和监控逻辑
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

### 3. 启动服务

**方式一：使用启动脚本（推荐）**

```bash
# 开发模式（带热重载）
./start.sh dev

# 生产模式
./start.sh
```

**方式二：手动启动**

开发环境（带热重载）：
```bash
source .venv/bin/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8080
```

生产环境：
```bash
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8080
```

服务启动后，可通过 API 端点进行调用。

## 📚 API 文档

### 1. 启动监控

**POST** `/monitor/start`

启动一个新的 Telegram 频道监控任务。

**请求体:**
```json
{
  "id": "monitor_001",
  "channel": "@channel_username",
  "keywords": ["关键词1", "关键词2"],
  "apiId": "你的API_ID",
  "apiHash": "你的API_HASH",
  "telegramBotConfig": {
    "botToken": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chatId": "-1001234567890"
  }
}
```

**频道格式说明:**
支持多种频道标识符格式：
- `@channel_username` (推荐)
- `https://t.me/channel_username`
- `t.me/channel_username`
- `channel_username`

**响应:**
```json
{
  "message": "监控 monitor_001 已启动"
}
```

### 2. 停止监控

**POST** `/monitor/stop`

停止指定的监控任务。

**请求体:**
```json
{
  "id": "monitor_001"
}
```

**响应:**
```json
{
  "message": "监控 monitor_001 已停止"
}
```

### 3. 查看状态

**GET** `/status`

获取当前正在运行的监控任务列表。

**响应:**
```json
{
  "active_monitors": ["monitor_001", "monitor_002"]
}
```

## ⚙️ 配置说明

### Telegram Bot 配置

配置 Telegram Bot 通知需要以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| botToken | 从 @BotFather 获取的机器人 Token | 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz |
| chatId | 目标聊天室的 ID（支持群组、频道、私聊） | -1001234567890 |

**获取 Chat ID 的方法：**

1. **私聊**: 使用 @userinfobot 查看你的用户 ID
2. **群组**: 将机器人添加到群组后，可以通过 API 或第三方工具获取
3. **频道**: 使用 格式：`-100` + 频道ID（去掉前缀）

### 关键词匹配

- 支持多个关键词，任一匹配即触发通知
- 关键词匹配不区分大小写
- 如果关键词列表为空，则匹配所有消息

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

1. **Telegram 登录失败**
   - 检查 API ID 和 API Hash 是否正确
   - 确保网络连接正常
   - 首次使用可能需要输入验证码（检查终端输出）

2. **Telegram Bot 通知失败**
   - 检查 Bot Token 是否正确
   - 确认 Chat ID 格式是否正确
   - 确保机器人已被添加到目标聊天室
   - 检查网络连接是否正常

3. **监控无法启动**
   - 检查频道名称是否正确（应以 @ 开头）
   - 确保 Telegram 账户已加入该频道
   - 检查终端日志输出

### 日志查看

服务运行时会在终端输出详细日志，包括：
- 监控启动/停止状态
- 消息接收情况
- 关键词匹配结果
- Telegram Bot 通知发送状态

## 🔐 安全注意事项

1. **API 凭证保护**: 不要将 Telegram API 凭证和 Bot Token 提交到版本控制系统
2. **Bot Token 安全**: 定期更换 Bot Token，避免泄露
3. **网络安全**: 生产环境建议使用 HTTPS 和防火墙保护
4. **会话文件**: `sessions/` 目录包含敏感登录信息，注意保护

## 📝 开发说明

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