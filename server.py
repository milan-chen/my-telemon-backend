import asyncio
import os
import httpx
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

from telethon import TelegramClient, events
from config import config as server_config

# --- Pydantic 模型 ---
class MonitorConfig(BaseModel):
    """监控任务配置（仅包含业务逻辑）"""
    id: str
    channel: str
    keywords: List[str]
    useRegex: bool = False  # 是否使用正则表达式匹配

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

def check_keyword_match(message_text: str, keywords: List[str], use_regex: bool = False) -> bool:
    """
    检查消息文本是否匹配关键词列表
    
    Args:
        message_text: 消息文本
        keywords: 关键词列表
        use_regex: 是否使用正则表达式匹配
    
    Returns:
        bool: 是否匹配
    """
    if not keywords:
        return True  # 没有关键词时匹配所有消息
    
    if not message_text:
        return False
    
    for keyword in keywords:
        if not keyword:  # 跳过空关键词
            continue
            
        try:
            if use_regex:
                # 使用正则表达式匹配（忽略大小写）
                if re.search(keyword, message_text, re.IGNORECASE):
                    return True
            else:
                # 使用普通字符串包含匹配（忽略大小写）
                if keyword.lower() in message_text.lower():
                    return True
        except re.error as e:
            # 正则表达式语法错误时，降级为普通字符串匹配
            print(f"正则表达式语法错误: {keyword}, 错误: {e}，降级为字符串匹配")
            if keyword.lower() in message_text.lower():
                return True
    
    return False

# --- Telegram Bot 通知逻辑 ---
async def send_telegram_message(config: dict, message_text: str, message_link: str):
    # 使用服务器配置的Bot
    if not server_config.validate_bot():
        print(f"[{config['id']}] 服务器未配置 Bot Token 或 Chat ID，跳过通知。")
        return

    token = server_config.bot_token
    chat_ids = server_config.chat_ids

    # 构造消息内容
    notification_header = f"📢 **Telemon 关键词提醒**\n\n- **频道:** {config['channel']}\n- **原文:** [点击查看]({message_link})\n\n**-- 消息内容 --**\n"
    
    # 限制消息长度以避免 API 错误 (4096 字符限制)
    max_len = 4096 - len(notification_header.replace('\n', '\n'))
    truncated_message = message_text
    if len(truncated_message) > max_len:
        truncated_message = truncated_message[:max_len-3] + '...'
    
    final_message = f"{notification_header}{truncated_message}"
    
    # 串行发送到多个 Chat ID
    successful_sends = []
    failed_sends = []
    
    for chat_id in chat_ids:
        payload = {
            'chat_id': chat_id,
            'text': final_message,
            'parse_mode': 'MarkdownV2'
        }
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    successful_sends.append(chat_id)
                    print(f"[{config['id']}] ✅ Telegram 通知已发送至 {chat_id}")
                else:
                    failed_sends.append({"chat_id": chat_id, "error": f"{response.status_code} - {response.text}"})
                    print(f"[{config['id']}] ❌ 发送至 {chat_id} 失败: {response.status_code} - {response.text}")
        except Exception as e:
            failed_sends.append({"chat_id": chat_id, "error": str(e)})
            print(f"[{config['id']}] ❌ 发送至 {chat_id} 时发生网络错误: {e}")
    
    # 记录发送结果汇总
    total_targets = len(chat_ids)
    success_count = len(successful_sends)
    failed_count = len(failed_sends)
    
    print(f"[{config['id']}] 📄 发送完成: 成功 {success_count}/{total_targets}, 失败 {failed_count}")
    
    if failed_count > 0:
        print(f"[{config['id']}] ⚠️  失败的Chat ID: {[f['chat_id'] for f in failed_sends]}")

# --- Telethon 监控逻辑 ---
async def monitor_channel(config: dict, task_ref: dict):
    # 使用服务器配置而非前端传递的参数
    session_path = os.path.join(SESSION_DIR, f"{config['id']}.session")
    client = TelegramClient(
        session_path,
        int(server_config.telegram.api_id),
        server_config.telegram.api_hash
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
                print(f"[{monitor_id}] 检测到首次登录，将使用服务器配置的手机号: {server_config.telegram.phone}")
                print(f"[{monitor_id}] ⚠️  重要提示: 验证码将发送到手机 {server_config.telegram.phone}")
                print(f"[{monitor_id}] ⚠️  请在【服务器控制台】输入验证码")
                print(f"[{monitor_id}] ⚠️  前端页面可能会显示'加载中'，这是正常现象")
                await client.start(phone=server_config.telegram.phone)
                print(f"[{monitor_id}] ✅ 首次登录认证完成！会话文件已保存")
            else:
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
            use_regex = config.get('useRegex', False)
            
            # 使用新的关键词匹配函数
            should_notify = check_keyword_match(message_text, keywords, use_regex)
            
            if should_notify:
                match_type = "正则表达式" if use_regex else "字符串"
                print(f"[{monitor_id}] {match_type}关键词匹配成功！准备发送 Telegram 通知。")
                
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
    
    # 检查服务器配置
    if not server_config.telegram.validate():
        raise HTTPException(
            status_code=500, 
            detail="服务器 Telegram API 配置不完整，请检查 config.py 或环境变量"
        )
    
    if not server_config.validate_bot():
        raise HTTPException(
            status_code=500,
            detail="服务器 Bot 配置不完整，请检查 config.py 中的 Bot Token 和 Chat ID"
        )
    
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
        task = asyncio.create_task(monitor_channel(config.model_dump(), task_ref))
        await asyncio.sleep(0.5)
        
        if task.done():
            try: 
                await task
            except Exception as e: 
                error_msg = str(e)
                if "Could not find the input entity" in error_msg:
                    error_msg = f"无法找到频道 '{config.channel}'。请检查: 1) 频道名称是否正确 2) 是否已加入该频道 3) 频道是否公开"
                elif "AUTH_KEY_UNREGISTERED" in error_msg:
                    error_msg = "账户未注册，请检查服务器 API 配置"
                elif "PHONE_NUMBER_INVALID" in error_msg:
                    error_msg = "手机号码无效，请检查服务器 Telegram 配置"
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

@app.get("/config/check")
async def check_server_config():
    """检查服务器配置状态"""
    telegram_valid = server_config.telegram.validate()
    bot_valid = server_config.validate_bot()
    
    return {
        "telegram_config_valid": telegram_valid,
        "bot_config_valid": bot_valid,
        "all_ready": telegram_valid and bot_valid,
        "telegram_message": "已配置 Telegram API" if telegram_valid else "请检查 config.py 中的 API ID/Hash/Phone",
        "bot_message": f"已配置 {len(server_config.chat_ids)} 个通知目标" if bot_valid else "请检查 config.py 中的 Bot Token/Chat IDs"
    }

# --- 启动说明 ---
# 要运行此服务，请在终端中使用 uvicorn:
# uvicorn server:app --host 0.0.0.0 --port 8080