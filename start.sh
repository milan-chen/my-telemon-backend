#!/bin/bash

# Telemon Backend 启动脚本
# 使用方法: ./start.sh [开发模式]

echo "🚀 启动 Telemon Backend 服务..."

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

# 启动服务
if [ "$1" = "dev" ] || [ "$1" = "--dev" ]; then
    echo "🛠️  以开发模式启动 (带热重载)..."
    uvicorn server:app --host 0.0.0.0 --port 8080 --reload
else
    echo "🏭 以生产模式启动..."
    uvicorn server:app --host 0.0.0.0 --port 8080
fi