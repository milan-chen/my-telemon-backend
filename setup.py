#!/usr/bin/env python3
"""
首次配置脚本
用于设置服务器端的 Telegram API 凭证和默认通知配置
"""
import os
import asyncio
from telethon import TelegramClient

def setup_config():
    """设置服务器配置"""
    print("=== Telemon Backend 配置 ===")
    
    # 获取 API 凭证
    print("\n1. Telegram API 凭证 (访问 https://my.telegram.org)")
    api_id = input("API ID: ").strip()
    api_hash = input("API Hash: ").strip()
    phone = input("手机号(+8613812345678): ").strip()
    
    # 代理配置（可选）
    print("\n2. 代理配置 (可选，中国大陆建议配置)")
    use_proxy = input("使用代理? (y/n): ").strip().lower() == 'y'
    
    proxy_type = "None"
    proxy_addr = "None"
    proxy_port = "None"
    proxy_username = "None"
    proxy_password = "None"
    
    if use_proxy:
        proxy_choice = input("代理类型 (1:SOCKS5, 2:HTTP): ").strip()
        proxy_type = "socks5" if proxy_choice == "1" else "http"
        
        proxy_addr = input("代理地址 (默认 127.0.0.1): ").strip() or "127.0.0.1"
        proxy_port_input = input("代理端口 (默认 7890): ").strip()
        proxy_port = proxy_port_input if proxy_port_input else "7890"
        
        need_auth = input("需要认证? (y/n): ").strip().lower() == 'y'
        if need_auth:
            proxy_username = input("用户名: ").strip()
            proxy_password = input("密码: ").strip()
    
    # 获取 Bot 配置
    print("\n3. Telegram Bot 配置")
    bot_token = input("Bot Token (@BotFather获取): ").strip()
    
    print("支持多个通知目标: 私聊(123456789), 群组(-987654321), 频道(-1001234567890)")
    chat_ids = input("Chat ID(多个用逗号分隔): ").strip()
    
    # 创建配置文件内容
    config_content = f'''"""
服务器端配置文件
包含敏感的 Telegram API 凭证和全局配置
"""
import os
from typing import Optional
from telethon.sessions import StringSession

class ProxyConfig:
    """代理配置"""
    
    def __init__(self):
        # 代理配置
        self.proxy_type = os.getenv('PROXY_TYPE', '{proxy_type}')
        self.proxy_addr = os.getenv('PROXY_ADDR', '{proxy_addr}')
        self.proxy_port = os.getenv('PROXY_PORT', '{proxy_port}')
        self.proxy_username = os.getenv('PROXY_USERNAME', '{proxy_username}')
        self.proxy_password = os.getenv('PROXY_PASSWORD', '{proxy_password}')
    
    def has_proxy(self) -> bool:
        """检查是否配置了代理"""
        return (
            self.proxy_type not in ['None', None, ''] and 
            self.proxy_addr not in ['None', None, ''] and 
            self.proxy_port not in ['None', None, '']
        )
    
    def get_proxy_dict(self) -> Optional[dict]:
        """获取 Telethon 兼容的代理配置"""
        if not self.has_proxy():
            return None
        
        proxy_config = {{
            'proxy_type': self.proxy_type,
            'addr': self.proxy_addr,
            'port': int(self.proxy_port),
        }}
        
        # 如果有用户名密码，添加认证信息
        if (self.proxy_username not in ['None', None, ''] and 
            self.proxy_password not in ['None', None, '']):
            proxy_config.update({{
                'username': self.proxy_username,
                'password': self.proxy_password
            }})
        
        return proxy_config

class TelegramConfig:
    """Telegram API 配置"""
    
    def __init__(self):
        # 从环境变量或直接配置获取
        self.api_id = os.getenv('TELEGRAM_API_ID', '{api_id}')
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '{api_hash}')
        self.phone = os.getenv('TELEGRAM_PHONE', '{phone}')
        
        # 代理配置
        self.proxy = ProxyConfig()
    
    def validate(self) -> bool:
        """验证配置是否完整"""
        return all([
            self.api_id and self.api_id != 'your_api_id_here',
            self.api_hash and self.api_hash != 'your_api_hash_here',
            self.phone and self.phone.startswith('+')
        ])

class ServerConfig:
    """服务器配置"""
    
    def __init__(self):
        self.telegram = TelegramConfig()
        self.session_dir = "sessions"
        self.host = "0.0.0.0"
        self.port = 8080
        
        # Telegram Bot 通知配置（必需）
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '{bot_token}')
        
        # 支持多个 Chat ID，用逗号分隔
        chat_ids_str = os.getenv('TELEGRAM_CHAT_IDS', '{chat_ids}')
        if chat_ids_str == 'your_chat_id_here':
            self.chat_ids = ['your_chat_id_here']
        else:
            # 从环境变量解析多个Chat ID，支持逗号分隔
            self.chat_ids = [id.strip() for id in chat_ids_str.split(',') if id.strip()]
    
    def validate_bot(self) -> bool:
        """验证Bot配置是否完整"""
        # 验证 Bot Token
        if not self.bot_token or self.bot_token == 'your_bot_token_here':
            return False
            
        # 验证 Chat IDs
        if not self.chat_ids or len(self.chat_ids) == 0:
            return False
            
        # 验证每个 Chat ID 格式
        for chat_id in self.chat_ids:
            if not chat_id or chat_id == 'your_chat_id_here':
                return False
            # 检查 Chat ID 是否为数字（可以以负号开头）
            if not str(chat_id).lstrip('-').isdigit():
                return False
                
        return True

# 全局配置实例
config = ServerConfig()
'''
    
    # 写入配置文件
    with open('config.py', 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"\n✅ 配置文件已保存到 config.py")
    
    return api_id, api_hash, phone

async def test_login(api_id: str, api_hash: str, phone: str, proxy_config: dict = None):
    """测试登录并创建会话文件"""
    print("\n测试 Telegram 连接...")
    
    session_path = "sessions/default.session"
    os.makedirs("sessions", exist_ok=True)
    
    # 创建客户端
    if proxy_config:
        print(f"使用代理: {proxy_config['proxy_type']}://{proxy_config['addr']}:{proxy_config['port']}")
        client = TelegramClient(session_path, api_id, api_hash, proxy=proxy_config)
    else:
        client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        await client.start(phone=phone)
        
        # 获取用户信息
        me = await client.get_me()
        print(f"✅ 登录成功: {me.first_name} (@{me.username})")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        if "连接" in str(e) or "connect" in str(e).lower() or "timeout" in str(e).lower():
            print("提示: 如在中国大陆，请配置代理")
        await client.disconnect()
        return False

def main():
    try:
        api_id, api_hash, phone = setup_config()
        
        # 导入刚创建的配置文件
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", "config.py")
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        
        # 获取代理配置
        proxy_config = config_module.config.telegram.proxy.get_proxy_dict()
        
        # 测试登录
        if input("\n测试登录? (y/n): ").lower() == 'y':
            success = asyncio.run(test_login(api_id, api_hash, phone, proxy_config))
            if success:
                print("\n✅ 配置完成！可以启动服务: ./start.sh")
            else:
                print("\n❌ 登录失败，请检查配置")
                exit(1)
        else:
            print("\n✅ 配置已保存")
            
    except KeyboardInterrupt:
        print("\n配置已取消")
        exit(1)
    except Exception as e:
        print(f"\n配置失败: {e}")
        exit(1)

if __name__ == "__main__":
    main()