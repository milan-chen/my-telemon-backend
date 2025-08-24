#!/bin/bash

# Telemon Backend 统一启动脚本
# 自动检测首次配置并启动服务
# 使用方法: ./start.sh [dev|--dev] [--setup]

echo "🚀 Telemon Backend 统一启动脚本"

# 检查虚拟环境是否存在
if [ -d ".venv" ]; then
    echo "📦 激活虚拟环境..."
    source .venv/bin/activate
else
    echo "⚠️  未找到虚拟环境，使用系统Python环境"
fi

# 检查依赖是否已安装
echo "🔍 检查依赖..."
python -c "import fastapi, uvicorn, telethon, pydantic, email_validator" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 缺少依赖，正在安装..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请检查网络连接和权限"
        exit 1
    fi
fi

# 检查是否需要首次配置
if [ ! -f "config.py" ] || [ "$1" = "--setup" ] || [ "$2" = "--setup" ]; then
    echo "⚙️  检测到需要配置，启动首次配置流程..."
    echo ""
    python setup.py
    
    if [ $? -ne 0 ]; then
        echo "❌ 配置失败，请重试"
        exit 1
    fi
    
    echo ""
    echo "✅ 配置完成！现在验证 Telegram 认证..."
    echo ""
else
    echo "✅ 配置文件已存在，验证 Telegram 认证..."
fi

# 验证 Telegram 认证状态
echo "🔐 验证 Telegram 认证..."
python -c "
import asyncio
import sys
import os
from telethon import TelegramClient
from config import config as server_config

async def verify_auth():
    session_path = 'sessions/default.session'
    if not os.path.exists(session_path):
        print('❌ 未找到会话文件，请重新配置')
        return False
    
    client = TelegramClient(
        session_path,
        int(server_config.telegram.api_id),
        server_config.telegram.api_hash
    )
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print('❌ Telegram 认证已失效，请重新配置')
            await client.disconnect()
            return False
        
        me = await client.get_me()
        print(f'✅ Telegram 认证有效！用户: {me.first_name} (@{me.username})')
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f'❌ Telegram 认证验证失败: {e}')
        await client.disconnect()
        return False

if not asyncio.run(verify_auth()):
    print('\n💡 解决方案:')
    print('1. 重新运行配置: ./start.sh --setup')
    print('2. 检查网络连接')
    print('3. 确认 Telegram API 凭证正确')
    sys.exit(1)
" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "❌ Telegram 认证验证失败，服务无法启动"
    echo ""
    echo "💡 解决方案:"
    echo "1. 重新运行配置: ./start.sh --setup"
    echo "2. 检查网络连接"
    echo "3. 确认 Telegram API 凭证正确"
    exit 1
fi

echo "🎉 所有验证通过，启动服务..."

# 启动服务
if [ "$1" = "dev" ] || [ "$1" = "--dev" ] || [ "$2" = "dev" ] || [ "$2" = "--dev" ]; then
    echo "🛠️  以开发模式启动 (带热重载)..."
    uvicorn server:app --host 0.0.0.0 --port 8080 --reload
else
    echo "🏭 以生产模式启动..."
    uvicorn server:app --host 0.0.0.0 --port 8080
fi