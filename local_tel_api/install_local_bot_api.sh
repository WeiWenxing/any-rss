#!/bin/bash

# Ubuntu 22.04 本地Bot API服务器安装脚本
# 作者：AI助手
# 用途：在Ubuntu 22.04上构建和安装Telegram Bot API本地服务器

set -e  # 遇到错误立即退出

echo "🚀 开始在Ubuntu 22.04上安装Telegram Bot API本地服务器..."

# 更新系统包
echo "📦 更新系统包..."
sudo apt update && sudo apt upgrade -y

# 安装必需的依赖
echo "🔧 安装构建依赖..."
sudo apt install -y \
    git \
    cmake \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    gperf \
    ccache \
    curl \
    wget \
    pkg-config

# 创建工作目录
WORK_DIR="$HOME/telegram-bot-api"
echo "📁 创建工作目录: $WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# 克隆源码
echo "📥 克隆Telegram Bot API源码..."
if [ ! -d "telegram-bot-api" ]; then
    git clone --recursive https://github.com/tdlib/telegram-bot-api.git
else
    echo "源码目录已存在，跳过克隆"
fi

cd telegram-bot-api

# 创建构建目录
echo "🏗️ 创建构建目录..."
rm -rf build
mkdir build
cd build

# 配置CMake
echo "⚙️ 配置CMake..."
cmake -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
      ..

# 编译（使用所有可用CPU核心）
echo "🔨 开始编译（这可能需要10-30分钟）..."
CORES=$(nproc)
echo "使用 $CORES 个CPU核心进行编译"
cmake --build . --target install -j"$CORES"

# 检查安装
if [ -f "$HOME/.local/bin/telegram-bot-api" ]; then
    echo "✅ 编译成功！"
    echo "📍 可执行文件位置: $HOME/.local/bin/telegram-bot-api"
    
    # 添加到PATH
    if ! grep -q "$HOME/.local/bin" ~/.bashrc; then
        echo "🔗 添加到PATH..."
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        echo "请运行: source ~/.bashrc 或重新登录以更新PATH"
    fi
    
    # 创建数据目录
    mkdir -p "$HOME/telegram-bot-api-data"
    
    echo ""
    echo "🎉 安装完成！"
    echo ""
    echo "📋 下一步："
    echo "1. 获取API ID和API Hash: https://my.telegram.org/apps"
    echo "2. 编辑启动脚本: nano start_local_bot_api.sh"
    echo "3. 运行服务器: ./start_local_bot_api.sh"
    echo "4. 默认端口: 8081"
    echo ""
else
    echo "❌ 编译失败！请检查错误信息"
    exit 1
fi 