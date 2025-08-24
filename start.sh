#!/bin/bash

# Telemon Backend 统一启动脚本
# 使用方法: ./start.sh [dev|--dev] [--setup] [--fast]

# 检查虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 检查依赖
python -c "import fastapi, uvicorn, telethon, pydantic, email_validator" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "正在安装依赖..."
    pip install -r requirements.txt >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请检查网络连接"
        exit 1
    fi
fi

# 检查配置
if [ ! -f "config.py" ] || [ "$1" = "--setup" ] || [ "$2" = "--setup" ] || [ "$3" = "--setup" ]; then
    echo "开始配置..."
    python setup.py
    if [ $? -ne 0 ]; then
        echo "❌ 配置失败"
        exit 1
    fi
fi

# 启动服务
if [ "$1" = "dev" ] || [ "$1" = "--dev" ] || [ "$2" = "dev" ] || [ "$2" = "--dev" ]; then
    echo "🚀 启动开发服务器..."
    uvicorn server:app --host 0.0.0.0 --port 8080 --reload
else
    echo "🚀 启动生产服务器..."
    uvicorn server:app --host 0.0.0.0 --port 8080
fi