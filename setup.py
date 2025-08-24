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
    print("=== Telemon Backend 首次配置 ===\n")
    
    # 获取 API 凭证
    print("1. 请访问 https://my.telegram.org 获取 API 凭证")
    api_id = input("请输入您的 API ID: ").strip()
    api_hash = input("请输入您的 API Hash: ").strip()
    phone = input("请输入您的手机号(格式: +8613812345678): ").strip()
    
    # 获取 Bot 配置
    print("\n2. 通知 Bot 配置（必需）")
    print("请访问 @BotFather 创建Bot并获取Token")
    bot_token = input("请输入 Bot Token: ").strip()
    print("请将Bot添加到您的聊天室，并发送 /start 命令")
    
    # 支持多个 Chat ID
    print("\n支持多个通知目标，可以同时发送到：")
    print("- 个人私聊（正整数，如 123456789）")
    print("- 群组（负整数，如 -987654321）")
    print("- 频道（以-100开头，如 -1001234567890）")
    print("多个 Chat ID 请用英文逗号分隔")
    
    chat_ids = input("请输入 Chat ID（多个用逗号分隔）: ").strip()
    
    # 创建配置文件内容
    config_content = f'''"""
服务器端配置文件
包含敏感的 Telegram API 凭证和全局配置
"""
import os
from typing import Optional

class TelegramConfig:
    """Telegram API 配置"""
    
    def __init__(self):
        # 从环境变量或直接配置获取
        self.api_id = os.getenv('TELEGRAM_API_ID', '{api_id}')
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '{api_hash}')
        self.phone = os.getenv('TELEGRAM_PHONE', '{phone}')
    
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

async def test_login(api_id: str, api_hash: str, phone: str):
    """测试登录并创建会话文件"""
    print("\n3. 测试 Telegram 登录...")
    
    session_path = "sessions/default.session"
    os.makedirs("sessions", exist_ok=True)
    
    client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        print(f"正在连接 Telegram...")
        await client.start(phone=phone)
        
        # 获取用户信息
        me = await client.get_me()
        print(f"✅ 登录成功！用户: {me.first_name} (@{me.username})")
        print(f"✅ 会话文件已保存到: {session_path}")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ 登录失败: {e}")
        await client.disconnect()
        return False

def main():
    try:
        api_id, api_hash, phone = setup_config()
        
        # 测试登录
        if input("\n是否立即测试登录? (y/n): ").lower() == 'y':
            success = asyncio.run(test_login(api_id, api_hash, phone))
            if success:
                print("\n🎉 配置完成！您现在可以启动服务:")
                print("   ./start.sh")
                print("\nℹ️ 前端只需配置: 频道、关键词、监控ID")
                print(f"ℹ️ 所有通知都将发送到以下 Chat ID: {chat_ids}")
            else:
                print("\n⚠️  配置已保存，但登录测试失败。")
                print("💡 请检查以下内容后重试:")
                print("1. API ID 和 API Hash 是否正确")
                print("2. 手机号格式是否正确(+8613812345678)")
                print("3. 网络连接是否正常")
                print("4. 是否正确输入了验证码")
                print("\n❌ 由于认证失败，服务将无法正常启动")
                exit(1)  # 返回错误状态
        else:
            print("\n✅ 配置已保存。首次启动监控时将需要验证码。")
            print("ℹ️ 前端只需配置: 频道、关键词、监控ID")
            print(f"ℹ️ 通知将发送到: {chat_ids}")
            print("\n⚠️  注意: 跳过登录测试可能导致后续服务启动失败")
            
    except KeyboardInterrupt:
        print("\n配置已取消。")
        exit(1)  # 用户取消也返回错误状态
    except Exception as e:
        print(f"\n配置过程中发生错误: {e}")
        exit(1)  # 异常也返回错误状态

if __name__ == "__main__":
    main()