#!/bin/bash

# 检查当前目录是否存在site-bot.py
if [ ! -f "site-bot.py" ]; then
    echo "错误：当前目录下未找到site-bot.py文件"
    echo "请确保脚本在与site-bot.py相同的目录中运行"
    exit 1
fi

# 查找并杀死现有进程
echo "查找正在运行的site-bot.py进程..."
PID=$(ps aux | grep site-bot.py | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "没有找到正在运行的site-bot.py进程"
else
    echo "找到进程PID: $PID, 正在杀死..."
    kill -9 $PID
    echo "进程已终止"
fi

# 激活虚拟环境并重启
echo "正在重启site-bot.py..."
source venv/bin/activate
nohup python site-bot.py > /tmp/site-bot.log 2>&1 &

# 检查是否启动成功
sleep 2
NEW_PID=$(ps aux | grep site-bot.py | grep -v grep | awk '{print $2}')

if [ -z "$NEW_PID" ]; then
    echo "启动失败，请检查日志: /tmp/site-bot.log"
    exit 1
else
    echo "启动成功，新进程PID: $NEW_PID"
    echo "日志输出到: /tmp/site-bot.log"
fi

