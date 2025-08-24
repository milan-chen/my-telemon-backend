import asyncio
import os
import httpx
import re
import sys
import socket

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

from telethon import TelegramClient, events
from config import config as server_config

# --- 网络连接检查函数 ---
async def check_telegram_connectivity():
    """检查网络连接到 Telegram 服务器"""
    
    # 获取代理配置
    proxy_config = server_config.telegram.proxy.get_proxy_dict()
    
    # Telegram 服务器列表
    telegram_servers = [
        ("149.154.167.51", 443),
        ("149.154.175.53", 443),
        ("91.108.56.165", 443),
    ]
    
    connection_success = False
    
    if proxy_config:
        print(f"使用代理: {proxy_config['proxy_type']}://{proxy_config['addr']}:{proxy_config['port']}")
        
        try:
            session_path = os.path.join(SESSION_DIR, "connectivity_test.session")
            test_client = TelegramClient(
                session_path,
                int(server_config.telegram.api_id),
                server_config.telegram.api_hash,
                proxy=proxy_config
            )
            
            await test_client.connect()
            print("✅ 代理连接成功")
            connection_success = True
            await test_client.disconnect()
            
            if os.path.exists(session_path):
                os.remove(session_path)
            
        except Exception as e:
            print(f"❌ 代理连接失败: {e}")
    else:
        print("检查直连...")
        
        for server, port in telegram_servers:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((server, port))
                sock.close()
                
                if result == 0:
                    print(f"✅ 直连成功: {server}")
                    connection_success = True
                    break
            except Exception:
                continue
    
    if not connection_success:
        print("\n❌ 无法连接 Telegram 服务器")
        print("解决方案:")
        print("1. 检查网络连接")
        print("2. 配置代理: python setup.py")
        
        try:
            user_input = input("\n配置代理? (y/n): ").strip().lower()
            if user_input in ['y', 'yes']:
                print("运行: python setup.py")
                sys.exit(1)
            else:
                print("⚠️  跳过代理配置")
        except KeyboardInterrupt:
            sys.exit(1)
    else:
        print("✅ 连接检查通过")

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
active_monitors: Dict[str, Dict] = {}  # { 'monitor_id': {'client': client, 'task': task, 'config': config} }
monitor_configs: Dict[str, Dict] = {}  # 存储所有监控配置信息（包括已停止的），格式: {'config': {...}, 'status': 'running'|'stopped'}

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
def escape_html(text: str) -> str:
    """
    转义HTML格式的特殊字符
    HTML需要转义的字符: <, >, &
    """
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def send_telegram_message(config: dict, message_text: str, message_link: str):
    # 使用服务器配置的Bot
    if not server_config.validate_bot():
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
    
    # 转义HTML特殊字符
    escaped_message = escape_html(final_message)
    
    # 串行发送到多个 Chat ID
    successful_sends = []
    failed_sends = []
    
    for chat_id in chat_ids:
        payload = {
            'chat_id': chat_id,
            'text': escaped_message,
            'parse_mode': 'HTML'
        }
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    successful_sends.append(chat_id)
                else:
                    failed_sends.append({"chat_id": chat_id, "error": f"{response.status_code} - {response.text}"})
        except Exception as e:
            failed_sends.append({"chat_id": chat_id, "error": str(e)})
    
    # 记录发送结果
    success_count = len(successful_sends)
    failed_count = len(failed_sends)
    
    if failed_count > 0:
        print(f"[{config['id']}] 通知: {success_count}成功 {failed_count}失败")

# --- Telethon 监控逻辑 ---
async def monitor_channel(config: dict, task_ref: dict):
    # 使用服务器配置而非前端传递的参数
    session_path = os.path.join(SESSION_DIR, f"{config['id']}.session")
    
    # 如果特定的会话文件不存在，尝试使用默认会话文件
    default_session_path = os.path.join(SESSION_DIR, "default.session")
    if not os.path.exists(session_path) and os.path.exists(default_session_path):
        print(f"[{config['id']}] 特定会话文件不存在，使用默认会话: {default_session_path}")
        session_path = default_session_path
    
    # 创建客户端，如果配置了代理则使用代理
    proxy_config = server_config.telegram.proxy.get_proxy_dict()
    if proxy_config:
        print(f"[{config['id']}] 使用代理连接: {proxy_config['proxy_type']}://{proxy_config['addr']}:{proxy_config['port']}")
        client = TelegramClient(
            session_path,
            int(server_config.telegram.api_id),
            server_config.telegram.api_hash,
            proxy=proxy_config
        )
    else:
        print(f"[{config['id']}] 直连 Telegram 服务器")
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
        keywords = config.get('keywords', [])
        use_regex = config.get('useRegex', False)
        
        print(f"[{monitor_id}] 监控频道: {parsed_channel}")
        if keywords:
            keyword_text = ', '.join(keywords[:3])  # 只显示前3个关键词避免输出过长
            if len(keywords) > 3:
                keyword_text += f" (共{len(keywords)}个)"
            regex_flag = " [正则]" if use_regex else ""
            print(f"[{monitor_id}] 关键词: {keyword_text}{regex_flag}")
        else:
            print(f"[{monitor_id}] 关键词: 全部消息")
        
        try:
            # 先连接客户端
            await client.connect()
            
            # 检查是否需要验证
            if not await client.is_user_authorized():
                print(f"[{monitor_id}] 首次登录，等待验证码...")
                await client.start(phone=server_config.telegram.phone)
                print(f"[{monitor_id}] ✅ 认证完成")
            
            print(f"[{monitor_id}] ✅ 连接成功")
        except Exception as e:
            error_str = str(e)
            print(f"[{monitor_id}] ❌ 连接失败: {error_str}")
            
            if "AUTH_KEY_UNREGISTERED" in error_str:
                print(f"[{monitor_id}] 错误: API 凭证无效")
            elif "PHONE_NUMBER_INVALID" in error_str:
                print(f"[{monitor_id}] 错误: 手机号无效")
            elif "ConnectionError" in error_str or "TimeoutError" in error_str:
                print(f"[{monitor_id}] 错误: 网络连接问题")
            raise
        
        current_task = asyncio.current_task()
        task_ref['task'] = current_task
        active_monitors[monitor_id] = {'client': client, 'task': current_task, 'config': config}
        
        # 获取频道实体
        try:
            channel_entity = await client.get_entity(parsed_channel)
            print(f"[{monitor_id}] ✅ 获取频道: {channel_entity.title if hasattr(channel_entity, 'title') else parsed_channel}")
        except Exception as e:
            print(f"[{monitor_id}] ❌ 无法获取频道: {e}")
            raise
        
        @client.on(events.NewMessage(chats=parsed_channel))
        async def handler(event):
            message_obj = event.message
            message_text = message_obj.text
            if not message_text:
                return

            keywords = config.get('keywords', [])
            use_regex = config.get('useRegex', False)
            
            # 使用新的关键词匹配函数
            should_notify = check_keyword_match(message_text, keywords, use_regex)
            
            if should_notify:
                print(f"[{monitor_id}] 🎯 关键词匹配")
                
                # 构造消息链接
                if hasattr(channel_entity, 'username') and channel_entity.username:
                    message_link = f"https://t.me/{channel_entity.username}/{message_obj.id}"
                else: # 私有频道
                    message_link = f"https://t.me/c/{channel_entity.id}/{message_obj.id}"
                
                await send_telegram_message(config, message_text, message_link)
        
        print(f"[{monitor_id}] 🚀 监控启动")
        await client.run_until_disconnected()
        
    except asyncio.CancelledError:
        print(f"[{monitor_id}] 监控取消")
        raise
    except Exception as e:
        print(f"[{monitor_id}] 监控错误: {e}")
        if monitor_id in active_monitors: del active_monitors[monitor_id]
        # 更新状态为错误，保留配置以便重试
        if monitor_id in monitor_configs:
            monitor_configs[monitor_id]['status'] = 'error'
        raise
    finally:
        if client.is_connected(): await client.disconnect()
        if monitor_id in active_monitors: del active_monitors[monitor_id]
        # 不删除 monitor_configs，保留配置以便恢复
        print(f"[{monitor_id}] 监控结束")

async def stop_monitor_internal(monitor_id: str):
    if monitor_id in active_monitors:
        monitor_info = active_monitors.pop(monitor_id)
        task = monitor_info['task']
        
        # 更新状态为停止，但保留配置
        if monitor_id in monitor_configs:
            monitor_configs[monitor_id]['status'] = 'stopped'
        
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass # 任务取消是预期的

        print(f"[{monitor_id}] 监控已停止")
        return True, f"监控 {monitor_id} 已停止"
    elif monitor_id in monitor_configs:
        # 监控已经停止但配置还在
        monitor_configs[monitor_id]['status'] = 'stopped'
        print(f"[{monitor_id}] 监控已停止")
        return True, f"监控 {monitor_id} 已停止"
    else:
        return False, f"未找到监控 {monitor_id}"

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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"频道标识符错误: {str(e)}")
    
    if monitor_id in active_monitors:
        await stop_monitor_internal(monitor_id)
        await asyncio.sleep(1)

    task_ref = {}
    
    # 保存配置信息用于状态查询，使用新的状态管理机制
    config_dict = config.model_dump()
    monitor_configs[monitor_id] = {
        'config': config_dict,
        'status': 'starting'  # 初始状态
    }
    
    try:
        task = asyncio.create_task(monitor_channel(config.model_dump(), task_ref))
        # 给任务更多时间初始化
        await asyncio.sleep(2.0)
        
        if task.done():
            try: 
                await task
            except Exception as e: 
                error_msg = str(e)
                if "Could not find the input entity" in error_msg:
                    error_msg = f"无法找到频道 '{config.channel}'"
                elif "AUTH_KEY_UNREGISTERED" in error_msg:
                    error_msg = "账户未注册，请检查服务器配置"
                elif "PHONE_NUMBER_INVALID" in error_msg:
                    error_msg = "手机号无效"
                raise HTTPException(status_code=500, detail=f"监控启动失败: {error_msg}")
        
        if monitor_id not in active_monitors:
            task.cancel()
            # 更新状态为错误
            if monitor_id in monitor_configs:
                monitor_configs[monitor_id]['status'] = 'error'
            raise HTTPException(status_code=500, detail="监控注册失败")
            
        # 更新状态为运行中
        if monitor_id in monitor_configs:
            monitor_configs[monitor_id]['status'] = 'running'
            
        return {"message": f"监控 {monitor_id} 已成功启动"}
        
    except HTTPException: 
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")

@app.post("/monitor/stop")
async def stop_monitor_endpoint(body: StopRequestBody):
    monitor_id = body.id
    success, message = await stop_monitor_internal(monitor_id)
    if success: return {"message": message}
    else: raise HTTPException(status_code=404, detail=message)

@app.post("/monitor/resume")
async def resume_monitor_endpoint(body: StopRequestBody):
    """恢复已停止的监控任务"""
    monitor_id = body.id
    
    # 检查是否存在已停止的监控配置
    if monitor_id not in monitor_configs:
        raise HTTPException(status_code=404, detail=f"未找到监控 {monitor_id} 的配置")
    
    monitor_data = monitor_configs[monitor_id]
    current_status = monitor_data.get('status', 'unknown')
    
    # 检查状态
    if current_status == 'running':
        raise HTTPException(status_code=400, detail=f"监控 {monitor_id} 已经在运行中")
    
    if monitor_id in active_monitors:
        raise HTTPException(status_code=400, detail=f"监控 {monitor_id} 已经在运行中")
    
    # 获取原始配置
    config_dict = monitor_data.get('config', {})
    if not config_dict:
        raise HTTPException(status_code=400, detail=f"监控 {monitor_id} 的配置为空")
    
    # 重用启动监控的逻辑
    try:
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
            parsed_channel = parse_channel_identifier(config_dict.get('channel', ''))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"频道标识符错误: {str(e)}")
        
        # 更新状态为启动中
        monitor_configs[monitor_id]['status'] = 'starting'
        
        task_ref = {}
        task = asyncio.create_task(monitor_channel(config_dict, task_ref))
        
        # 给任务更多时间初始化
        await asyncio.sleep(2.0)
        
        if task.done():
            try: 
                await task
            except Exception as e: 
                error_msg = str(e)
                if "Could not find the input entity" in error_msg:
                    error_msg = f"无法找到频道 '{config_dict.get('channel', '')}'"
                elif "AUTH_KEY_UNREGISTERED" in error_msg:
                    error_msg = "账户未注册，请检查服务器配置"
                elif "PHONE_NUMBER_INVALID" in error_msg:
                    error_msg = "手机号无效"
                # 更新状态为错误
                monitor_configs[monitor_id]['status'] = 'error'
                raise HTTPException(status_code=500, detail=f"监控恢复失败: {error_msg}")
        
        if monitor_id not in active_monitors:
            task.cancel()
            monitor_configs[monitor_id]['status'] = 'error'
            raise HTTPException(status_code=500, detail="监控注册失败")
            
        # 更新状态为运行中
        monitor_configs[monitor_id]['status'] = 'running'
            
        return {"message": f"监控 {monitor_id} 已成功恢复"}
        
    except HTTPException: 
        raise
    except Exception as e:
        # 更新状态为错误
        if monitor_id in monitor_configs:
            monitor_configs[monitor_id]['status'] = 'error'
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")

@app.post("/monitor/delete")
async def delete_monitor_endpoint(body: StopRequestBody):
    """彻底删除监控任务和配置"""
    monitor_id = body.id
    
    # 先停止监控（如果正在运行）
    if monitor_id in active_monitors:
        monitor_info = active_monitors.pop(monitor_id)
        task = monitor_info['task']
        
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass  # 任务取消是预期的
        
        print(f"[{monitor_id}] 监控已停止")
    
    # 删除配置
    if monitor_id in monitor_configs:
        del monitor_configs[monitor_id]
        print(f"[{monitor_id}] 配置已删除")
        return {"message": f"监控 {monitor_id} 已彻底删除"}
    else:
        raise HTTPException(status_code=404, detail=f"未找到监控 {monitor_id}")

@app.get("/status")
async def get_status():
    """获取所有监控任务的详细状态信息（包括已停止的）"""
    monitor_list = []
    active_list = []  # 保持向后兼容
    
    # 遍历所有配置（包括已停止的）
    for monitor_id, monitor_data in monitor_configs.items():
        config = monitor_data.get('config', {})
        status = monitor_data.get('status', 'unknown')
        
        # 解析频道名称，去除 @ 前缀用于展示
        channel_display = config.get('channel', '')
        if channel_display.startswith('@'):
            channel_display = channel_display[1:]
        
        monitor_info = {
            "id": monitor_id,
            "channel": channel_display,
            "keywords": config.get('keywords', []),
            "useRegex": config.get('useRegex', False),
            "status": status
        }
        monitor_list.append(monitor_info)
        
        # 保持向后兼容：只有运行中的监控才加入 active_monitors
        if status == 'running':
            active_list.append(monitor_id)
    
    return {
        "active_monitors": active_list,  # 保持向后兼容
        "monitors": monitor_list  # 新的详细信息（包括所有状态）
    }

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

# --- 启动事件处理 ---
@app.on_event("startup")
async def startup_event():
    """服务启动时执行的检查"""
    print("\n🚀 Telemon Backend 启动中...")
    
    # 检查服务器配置
    if not server_config.telegram.validate():
        print("❌ Telegram API 配置不完整，请运行: python setup.py")
        sys.exit(1)
    
    if not server_config.validate_bot():
        print("❌ Bot 配置不完整，请运行: python setup.py")
        sys.exit(1)
    
    # 执行网络连接检查
    await check_telegram_connectivity()
    
    print("✅ 服务启动成功！现在可以使用监控功能。\n")