import asyncio
import os
import httpx

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

from telethon import TelegramClient, events

# --- Pydantic 模型 ---
class TelegramBotConfig(BaseModel):
    botToken: str
    chatId: str

class MonitorConfig(BaseModel):
    id: str
    channel: str
    keywords: List[str]
    apiId: str
    apiHash: str
    telegramBotConfig: TelegramBotConfig
    # isEnabled, backendUrl 等前端字段在此处非必需

class StopRequestBody(BaseModel):
    id: str

# --- 配置 ---
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# --- 全局变量 ---
app = FastAPI(
    title="Telemon Backend",
    description="一个基于 FastAPI 的后端服务，用于执行 Telegram 监控任务。",
    docs_url=None,
    redoc_url=None
)
active_monitors: Dict[str, Dict] = {}  # { 'monitor_id': {'client': client, 'task': task} }

# --- CORS 中间件 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议设置为您的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 辅助函数 ---
def parse_channel_identifier(channel: str) -> str:
    """
    解析频道标识符，支持多种格式：
    - https://t.me/channel_name -> @channel_name
    - t.me/channel_name -> @channel_name
    - @channel_name -> @channel_name
    - channel_name -> @channel_name
    """
    if not channel:
        raise ValueError("频道标识符不能为空")
    
    # 移除协议前缀
    if channel.startswith('https://t.me/'):
        channel = channel.replace('https://t.me/', '')
    elif channel.startswith('http://t.me/'):
        channel = channel.replace('http://t.me/', '')
    elif channel.startswith('t.me/'):
        channel = channel.replace('t.me/', '')
    
    # 确保以 @ 开头
    if not channel.startswith('@'):
        channel = '@' + channel
    
    return channel

# --- Telegram Bot 通知逻辑 ---
async def send_telegram_message(config: dict, message_text: str, message_link: str):
    bot_conf = config.get('telegramBotConfig', {})
    token = bot_conf.get('botToken')
    chat_id = bot_conf.get('chatId')

    if not token or not chat_id:
        print(f"[{config['id']}] Bot Token 或 Chat ID 未配置，跳过通知。")
        return

    # 构造消息内容
    notification_header = f"📢 **Telemon 关键词提醒**\n\n- **频道:** {config['channel']}\n- **原文:** [点击查看]({message_link})\n\n**-- 消息内容 --**\n"
    
    # 限制消息长度以避免 API 错误 (4096 字符限制)
    max_len = 4096 - len(notification_header.replace('\n', '\n'))
    truncated_message = message_text
    if len(truncated_message) > max_len:
        truncated_message = truncated_message[:max_len-3] + '...'
    
    payload = {
        'chat_id': chat_id,
        'text': f"{notification_header}{truncated_message}",
        'parse_mode': 'MarkdownV2'
    }
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"[{config['id']}] Telegram 通知已发送至 {chat_id}")
            else:
                print(f"[{config['id']}] 发送 Telegram 通知失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[{config['id']}] 发送 Telegram 通知时发生网络错误: {e}")

# --- Telethon 监控逻辑 ---
async def monitor_channel(config: dict, task_ref: dict):
    session_path = os.path.join(SESSION_DIR, f"{config['id']}.session")
    client = TelegramClient(
        session_path,
        int(config['apiId']),
        config['apiHash']
    )
    
    monitor_id = config['id']
    
    try:
        # 解析频道标识符
        original_channel = config['channel']
        parsed_channel = parse_channel_identifier(original_channel)
        print(f"[{monitor_id}] 原始频道: {original_channel} -> 解析后: {parsed_channel}")
        
        print(f"[{monitor_id}] 连接 Telegram 并开始监听频道: {parsed_channel}...")
        try:
            # 检查是否需要验证
            if not await client.is_user_authorized():
                print(f"[{monitor_id}] 检测到首次登录，尝试自动登录...")
                print(f"[{monitor_id}] 注意: 如果需要手机验证码，请在服务器终端查看并输入")
            
            await client.start()
            print(f"[{monitor_id}] Telegram 客户端连接成功")
        except Exception as e:
            error_str = str(e)
            print(f"[{monitor_id}] Telegram 连接失败: {error_str}")
            
            if "AUTH_KEY_UNREGISTERED" in error_str or "UNAUTHORIZED" in error_str:
                print(f"[{monitor_id}] 错误: API 凭证无效或未授权")
                print(f"[{monitor_id}] 请检查: 1) API ID 和 API Hash 是否正确 2) 是否需要在终端输入验证码")
            elif "PHONE_NUMBER_INVALID" in error_str:
                print(f"[{monitor_id}] 错误: 手机号码无效")
            elif "ConnectionError" in error_str or "TimeoutError" in error_str:
                print(f"[{monitor_id}] 错误: 网络连接问题")
            else:
                print(f"[{monitor_id}] 可能的原因: 需要验证码或 API 凭证错误")
            raise
        
        current_task = asyncio.current_task()
        task_ref['task'] = current_task
        active_monitors[monitor_id] = {'client': client, 'task': current_task}
        
        # 获取频道实体
        try:
            channel_entity = await client.get_entity(parsed_channel)
            print(f"[{monitor_id}] 成功获取频道实体: {channel_entity.title if hasattr(channel_entity, 'title') else parsed_channel}")
        except Exception as e:
            print(f"[{monitor_id}] 无法获取频道实体: {e}")
            print(f"[{monitor_id}] 请检查: 1) 频道名称是否正确 2) 是否已加入该频道 3) 频道是否公开")
            raise
        
        @client.on(events.NewMessage(chats=parsed_channel))
        async def handler(event):
            message_obj = event.message
            message_text = message_obj.text
            if not message_text:
                return

            print(f"[{monitor_id}] 收到消息: {message_text[:50]}...")
            
            keywords = config.get('keywords', [])
            should_notify = not keywords # 如果没有关键词，则匹配所有消息
            
            if not should_notify:
                for keyword in keywords:
                    if keyword.lower() in message_text.lower():
                        should_notify = True
                        break
            
            if should_notify:
                print(f"[{monitor_id}] 关键词匹配成功！准备发送 Telegram 通知。")
                
                # 构造消息链接
                if hasattr(channel_entity, 'username') and channel_entity.username:
                    message_link = f"https://t.me/{channel_entity.username}/{message_obj.id}"
                else: # 私有频道
                    message_link = f"https://t.me/c/{channel_entity.id}/{message_obj.id}"
                
                await send_telegram_message(config, message_text, message_link)
        
        print(f"[{monitor_id}] 监控已成功启动。")
        await client.run_until_disconnected()
        
    except asyncio.CancelledError:
        print(f"[{monitor_id}] 监控任务被取消。")
        raise
    except Exception as e:
        print(f"[{monitor_id}] 监控时发生错误: {e}")
        if monitor_id in active_monitors: del active_monitors[monitor_id]
        raise
    finally:
        if client.is_connected(): await client.disconnect()
        if monitor_id in active_monitors: del active_monitors[monitor_id]
        print(f"[{monitor_id}] 客户端已断开连接，监控任务结束。")

async def stop_monitor_internal(monitor_id: str):
    if monitor_id in active_monitors:
        monitor_info = active_monitors.pop(monitor_id)
        task = monitor_info['task']
        
        print(f"[{monitor_id}] 正在停止监控...")
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass # 任务取消是预期的

        print(f"[{monitor_id}] 监控已成功停止。")
        return True, f"监控 {monitor_id} 已停止"
    else:
        print(f"[{monitor_id}] 尝试停止，但未找到正在运行的监控。")
        return False, f"未找到正在运行的监控 {monitor_id}"

# --- API 端点 ---
@app.post("/monitor/start")
async def start_monitor_endpoint(config: MonitorConfig):
    monitor_id = config.id
    
    # 验证输入参数
    try:
        parsed_channel = parse_channel_identifier(config.channel)
        print(f"[{monitor_id}] 验证参数成功: {config.channel} -> {parsed_channel}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"频道标识符错误: {str(e)}")
    
    if monitor_id in active_monitors:
        print(f"[{monitor_id}] 监控已在运行，将重启...")
        await stop_monitor_internal(monitor_id)
        await asyncio.sleep(1)

    print(f"[{monitor_id}] 正在启动新监控...")
    task_ref = {}
    
    try:
        task = asyncio.create_task(monitor_channel(config.dict(), task_ref))
        await asyncio.sleep(0.5)
        
        if task.done():
            try: 
                await task
            except Exception as e: 
                error_msg = str(e)
                if "Could not find the input entity" in error_msg:
                    error_msg = f"无法找到频道 '{config.channel}'。请检查: 1) 频道名称是否正确 2) 是否已加入该频道 3) 频道是否公开"
                elif "AUTH_KEY_UNREGISTERED" in error_msg:
                    error_msg = "账户未注册，请检查 API ID 和 API Hash 是否正确"
                elif "PHONE_NUMBER_INVALID" in error_msg:
                    error_msg = "手机号码无效，请检查 Telegram 账户设置"
                raise HTTPException(status_code=500, detail=f"监控启动失败: {error_msg}")
        
        if monitor_id not in active_monitors:
            task.cancel()
            raise HTTPException(status_code=500, detail="监控注册失败")
            
        return {"message": f"监控 {monitor_id} 已成功启动"}
        
    except HTTPException: 
        raise
    except Exception as e:
        print(f"[{monitor_id}] 启动监控时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")

@app.post("/monitor/stop")
async def stop_monitor_endpoint(body: StopRequestBody):
    monitor_id = body.id
    success, message = await stop_monitor_internal(monitor_id)
    if success: return {"message": message}
    else: raise HTTPException(status_code=404, detail=message)

@app.get("/status")
async def get_status():
    return {"active_monitors": list(active_monitors.keys())}

# --- 启动说明 ---
# 要运行此服务，请在终端中使用 uvicorn:
# uvicorn server:app --host 0.0.0.0 --port 8080