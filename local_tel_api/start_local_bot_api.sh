#!/bin/bash

# 本地Bot API服务器启动脚本
# 用途：启动Telegram Bot API本地服务器

# 配置参数（请修改为你的实际值）
API_ID="YOUR_API_ID"           # 从 https://my.telegram.org/apps 获取
API_HASH="YOUR_API_HASH"       # 从 https://my.telegram.org/apps 获取
LOCAL_PORT="8081"              # 本地服务器端口
LOG_LEVEL="2"                  # 日志级别 (0-5, 2为INFO)
DATA_DIR="$HOME/telegram-bot-api-data"  # 数据目录

# 创建数据目录
mkdir -p "$DATA_DIR"

echo "🚀 启动Telegram Bot API本地服务器..."
echo "📍 端口: $LOCAL_PORT"
echo "📁 数据目录: $DATA_DIR"
echo "📊 日志级别: $LOG_LEVEL"

# 检查配置
if [ "$API_ID" = "YOUR_API_ID" ] || [ "$API_HASH" = "YOUR_API_HASH" ]; then
    echo "❌ 错误：请先配置API_ID和API_HASH"
    echo "📋 获取地址: https://my.telegram.org/apps"
    echo "✏️ 编辑此文件: nano $0"
    echo ""
    echo "📝 编辑步骤："
    echo "1. nano $0"
    echo "2. 修改 API_ID=\"你的API_ID\""
    echo "3. 修改 API_HASH=\"你的API_HASH\""
    echo "4. 保存并退出 (Ctrl+X, Y, Enter)"
    exit 1
fi

# 检查可执行文件
if ! command -v telegram-bot-api &> /dev/null; then
    echo "❌ 错误：找不到telegram-bot-api可执行文件"
    echo "📋 请先运行安装脚本: ./install_local_bot_api.sh"
    echo "🔗 或更新PATH: source ~/.bashrc"
    exit 1
fi

echo "✅ 配置检查通过，启动服务器..."
echo ""

# 启动服务器
telegram-bot-api \
    --api-id="$API_ID" \
    --api-hash="$API_HASH" \
    --local \
    --http-port="$LOCAL_PORT" \
    --dir="$DATA_DIR" \
    --verbosity="$LOG_LEVEL" \
    --max-webhook-connections=100000 \
    --max-connections=100000

echo "🛑 服务器已停止" 