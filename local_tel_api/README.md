# Telegram 本地Bot API服务器部署指南

## 📋 项目简介

本项目提供了在Ubuntu 22.04上部署Telegram本地Bot API服务器的完整解决方案。通过使用本地Bot API服务器，你的机器人可以：

- ✅ 发送最大2GB的文件（vs 官方50MB限制）
- ✅ 获得更快的文件上传速度
- ✅ 享受更高的API调用频率限制
- ✅ 实现本地文件缓存
- ✅ 获得更好的隐私保护

## 🎯 适用场景

- RSS机器人需要发送大视频文件
- 需要频繁API调用的机器人
- 对隐私有特殊要求的项目
- 需要本地文件缓存的应用

## 📦 文件说明

| 文件名 | 用途 |
|--------|------|
| `install_local_bot_api.sh` | 自动安装脚本，编译和安装本地Bot API |
| `start_local_bot_api.sh` | 手动启动脚本，用于测试和调试 |
| `telegram-bot-api.service` | systemd服务文件，用于自动启动 |
| `config_local_api.py` | Python配置模块，用于机器人代码集成 |

## 🚀 快速部署

### 第一步：获取API凭据

1. 访问 https://my.telegram.org/apps
2. 登录你的Telegram账号
3. 创建新应用：
   - **App title**: `Your Bot Name`
   - **Short name**: `yourbotname`（5-32字符，字母数字）
   - **Platform**: 选择 `Desktop`
   - **Description**: 简短描述
4. 获取 `API ID` 和 `API Hash`

### 第二步：安装本地Bot API

```bash
# 1. 上传所有文件到Ubuntu服务器
# 2. 给脚本执行权限
chmod +x install_local_bot_api.sh
chmod +x start_local_bot_api.sh

# 3. 运行安装脚本（需要10-30分钟）
./install_local_bot_api.sh

# 4. 更新环境变量
source ~/.bashrc
```

### 第三步：配置API凭据

```bash
# 编辑启动脚本
nano start_local_bot_api.sh

# 修改这两行：
API_ID="你的API_ID"        # 替换为实际的API ID
API_HASH="你的API_HASH"    # 替换为实际的API Hash
```

### 第四步：测试启动

```bash
# 手动测试启动
./start_local_bot_api.sh

# 成功启动的标志：
# ✅ Bot API 9.0 server started
# ✅ Server is listening on http port 8081
```

### 第五步：配置系统服务

```bash
# 1. 编辑服务文件，填入API凭据
nano telegram-bot-api.service

# 替换以下内容：
# - YOUR_USERNAME → ubuntu（或你的用户名）
# - YOUR_API_ID → 你的API ID
# - YOUR_API_HASH → 你的API Hash

# 2. 安装系统服务
sudo cp telegram-bot-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot-api
sudo systemctl start telegram-bot-api

# 3. 检查服务状态
sudo systemctl status telegram-bot-api
```

### 第六步：修改机器人代码

在你的Python机器人代码中：

```python
# 原来的代码：
# from telegram.ext import Application
# application = Application.builder().token(BOT_TOKEN).build()

# 新的代码：
from config_local_api import create_local_bot_application
application = create_local_bot_application(BOT_TOKEN)
```

## 🔧 配置说明

### 服务器配置

- **端口**: 8081（可在脚本中修改）
- **数据目录**: `~/telegram-bot-api-data`
- **日志级别**: 2（INFO级别）
- **最大连接数**: 100,000

### 系统要求

- **操作系统**: Ubuntu 22.04 LTS
- **内存**: 至少1GB RAM
- **磁盘**: 至少2GB可用空间
- **网络**: 稳定的互联网连接

## 🚨 常见问题

### Q1: systemd服务启动失败，报"No such file or directory"

**原因**: systemd安全沙箱限制

**解决方案**:
```bash
# 编辑服务文件
sudo nano /etc/systemd/system/telegram-bot-api.service

# 将这两行：
# ProtectSystem=strict
# ProtectHome=true

# 改为：
# ProtectSystem=false
# ProtectHome=false

# 重新加载并启动
sudo systemctl daemon-reload
sudo systemctl restart telegram-bot-api
```

### Q2: 编译失败

**可能原因**:
- 网络连接问题
- 依赖包缺失
- 磁盘空间不足

**解决方案**:
```bash
# 检查磁盘空间
df -h

# 重新安装依赖
sudo apt update
sudo apt install -y git cmake build-essential libssl-dev zlib1g-dev gperf

# 重新运行安装脚本
./install_local_bot_api.sh
```

### Q3: 机器人无法连接到本地API

**检查步骤**:
```bash
# 1. 检查服务状态
sudo systemctl status telegram-bot-api

# 2. 检查端口监听
netstat -tlnp | grep 8081

# 3. 测试API连接
curl http://localhost:8081/

# 4. 查看日志
journalctl -u telegram-bot-api -f
```

## 📊 性能优化

### 内存优化

```bash
# 在服务文件中添加内存限制
MemoryMax=512M
MemoryHigh=400M
```

### 日志管理

```bash
# 限制日志大小
sudo journalctl --vacuum-size=100M
sudo journalctl --vacuum-time=7d
```

## 🔒 安全建议

1. **防火墙配置**:
   ```bash
   # 如果需要外部访问，开放8081端口
   sudo ufw allow 8081
   ```

2. **定期更新**:
   ```bash
   # 定期更新本地Bot API到最新版本
   cd ~/telegram-bot-api/telegram-bot-api
   git pull
   cd build
   cmake --build . --target install
   ```

3. **备份数据**:
   ```bash
   # 定期备份数据目录
   tar -czf telegram-bot-api-backup-$(date +%Y%m%d).tar.gz ~/telegram-bot-api-data/
   ```

## 📝 维护命令

```bash
# 查看服务状态
sudo systemctl status telegram-bot-api

# 重启服务
sudo systemctl restart telegram-bot-api

# 查看实时日志
journalctl -u telegram-bot-api -f

# 停止服务
sudo systemctl stop telegram-bot-api

# 手动启动（调试用）
./start_local_bot_api.sh
```

## 🆘 故障排除

### 服务无法启动

1. 检查API凭据是否正确
2. 检查文件权限
3. 查看详细错误日志
4. 尝试手动启动测试

### 性能问题

1. 监控CPU和内存使用
2. 检查网络连接质量
3. 调整日志级别
4. 优化系统参数

## 📞 技术支持

如果遇到问题：

1. 查看本文档的常见问题部分
2. 检查系统日志：`journalctl -u telegram-bot-api`
3. 尝试手动启动进行调试
4. 确认API凭据和网络连接

## 📄 许可证

本项目基于Telegram官方Bot API源码，遵循相应的开源许可证。

---

**注意**: 请妥善保管你的API ID和API Hash，不要泄露给他人或提交到公开代码仓库。 