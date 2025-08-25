#!/bin/bash

# Telemon Backend 统一启动脚本
# 使用方法: ./start.sh [dev|--dev] [--config-check] [--setup]

# 处理 --setup 参数
if [ "$1" = "--setup" ] || [ "$2" = "--setup" ] || [ "$3" = "--setup" ]; then
    echo "=== Telemon Backend 配置重置 ==="
    echo
    
    # 检查模板文件是否存在
    if [ ! -f "app_config.yaml.template" ]; then
        echo "❌ 错误: 找不到配置模板文件 app_config.yaml.template"
        exit 1
    fi
    
    # 检查是否已有配置文件
    if [ -f "app_config.yaml" ]; then
        echo "⚠️  检测到已存在配置文件 app_config.yaml"
        read -p "是否要重置配置文件？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ 取消重置配置文件"
        else
            # 备份现有配置
            BACKUP_FILE="app_config.yaml.backup.$(date +%Y%m%d_%H%M%S)"
            cp "app_config.yaml" "$BACKUP_FILE"
            echo "📝 已备份现有配置到: $BACKUP_FILE"
            
            # 重置配置文件
            cp "app_config.yaml.template" "app_config.yaml"
            echo "✅ 已重置配置文件为模板内容"
        fi
    else
        # 创建新配置文件
        cp "app_config.yaml.template" "app_config.yaml"
        echo "✅ 已创建配置文件: app_config.yaml"
    fi
    
    # 清理会话文件
    if [ -d "sessions" ]; then
        echo
        read -p "是否要清理 Telegram 会话文件？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf sessions/*
            echo "🗑️  已清理 sessions 目录"
        else
            echo "⏭️  跳过清理会话文件"
        fi
    fi
    
    echo
    echo "📋 接下来请编辑配置文件填入您的实际信息:"
    echo "   - Telegram API ID 和 API Hash"
    echo "   - 手机号码"
    echo "   - Bot Token"
    echo "   - Chat ID"
    echo "   - 代理设置 (如需要)"
    echo
    echo "🚀 配置完成后，使用以下命令启动服务:"
    echo "   ./start.sh dev    # 开发模式"
    echo "   ./start.sh        # 生产模式"
    echo
    exit 0
fi

# 检查虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 检查依赖
echo "检查依赖..."
python -c "import fastapi, uvicorn, telethon, pydantic, email_validator, yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "正在安装依赖..."
    pip install -r requirements.txt >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请检查网络连接"
        exit 1
    fi
fi

# 检查配置文件
if [ ! -f "app_config.yaml" ]; then
    echo "❌ 配置文件 app_config.yaml 不存在"
    echo "请根据以下模板创建配置文件："
    echo "---"
    echo "telegram:"
    echo "  api_id: \"your_api_id_here\""
    echo "  api_hash: \"your_api_hash_here\""
    echo "  phone: \"+8613812345678\""
    echo ""
    echo "proxy:"
    echo "  enabled: false  # 中国大陆用户建议设置为 true"
    echo "  type: \"socks5\""
    echo "  host: \"127.0.0.1\""
    echo "  port: 7890"
    echo ""
    echo "bot:"
    echo "  token: \"your_bot_token_here\""
    echo "  chat_ids:"
    echo "    - \"your_chat_id_here\""
    echo "---"
    echo "提示: 您也可以复制 app_config.yaml 模板文件并修改其中的配置"
    exit 1
fi

# 配置验证
if [ "$1" = "--config-check" ] || [ "$2" = "--config-check" ] || [ "$3" = "--config-check" ]; then
    echo "验证配置文件..."
    python -c "
from config import config
valid, errors = config.validate()
if not valid:
    print('❌ 配置验证失败:')
    for error in errors:
        print(f'  - {error}')
    exit(1)
else:
    print('✅ 配置验证通过')
"
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

# 启动服务
if [ "$1" = "dev" ] || [ "$1" = "--dev" ] || [ "$2" = "dev" ] || [ "$2" = "--dev" ]; then
    echo "🚀 启动开发服务器..."
    echo "配置文件: app_config.yaml"
    echo "代理状态: $(python -c 'from config import config; print("启用" if config.telegram.proxy.enabled else "禁用")')"
    uvicorn server:app --host 0.0.0.0 --port 8080 --reload
else
    echo "🚀 启动生产服务器..."
    echo "配置文件: app_config.yaml"
    echo "代理状态: $(python -c 'from config import config; print("启用" if config.telegram.proxy.enabled else "禁用")')"
    uvicorn server:app --host 0.0.0.0 --port 8080
fi