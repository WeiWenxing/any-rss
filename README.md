# Any RSS Bot

一个支持 Telegram 和 Discord 的通用 RSS/Feed 监控机器人。

## 环境要求

- Python 3.8+
- pip
- virtualenv

## 安装步骤

1. 克隆项目
```bash
git clone https://github.com/WeiWenxing/any-rss.git
cd any-rss
```

2. 创建并激活虚拟环境
```bash
# 创建虚拟环境
python -m venv venv

# Windows激活虚拟环境
venv\Scripts\activate

# Linux/Mac激活虚拟环境
source venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
```bash
# 复制环境变量示例文件
cp env.example .env

# 编辑.env文件，填入必要的配置
```

### 环境变量说明

必填配置:
- `TELEGRAM_BOT_TOKEN`: Telegram机器人token (从@BotFather获取)
- `TELEGRAM_TARGET_CHAT`: 消息发送目标 (可以是频道如@channelname或用户ID如123456789)

可选配置:
- `DISCORD_TOKEN`: Discord机器人token (如需Discord功能则必填)

## 运行方式

1. 直接运行
```bash
python any-rss-bot.py
```

2. 使用启动脚本（推荐）
```bash
# 添加执行权限
chmod +x restart.sh

# 运行脚本
./restart.sh
```

## 日志查看

程序运行日志位于：
```bash
tail -f /tmp/any-rss-bot.log
```

## 目录结构

```
project/
├── apps/                 # 应用入口层
│   ├── telegram_bot.py
│   └── discord_bot.py
├── core/                 # 核心配置层
│   └── config.py        # 配置文件处理
├── services/            # 具体服务层
│   └── rss/            # RSS服务实现
│       ├── commands.py  # RSS命令处理
│       └── manager.py   # RSS管理器
├── storage/             # 数据存储层
│   └── rss/
│       ├── config/      # 配置文件
│       └── feeds_data/  # Feed数据存储
└── any-rss-bot.py      # 主程序入口
```

## 注意事项

1. 确保.env文件中配置了正确的bot token和发送目标
2. 运行restart.sh前确保在项目根目录
3. 首次运行时需要创建虚拟环境并安装依赖
4. 发送目标(TELEGRAM_TARGET_CHAT)必须配置，否则程序无法正常工作
5. 如果发送目标是Telegram频道，需要将机器人添加为频道的管理员，确保其有发布消息的权限

## 命令使用说明

### Telegram 命令
- `/start` - 启动机器人
- `/help` - 显示帮助信息
- `/rss` - RSS订阅管理，包含以下子命令：
  - `/rss list` - 显示所有监控的RSS/Feed列表
  - `/rss add URL` - 添加新的RSS/Feed监控（支持标准RSS 2.0和Atom 1.0格式）
  - `/rss del URL` - 删除指定的RSS/Feed监控
- `/news` - 手动触发关键词汇总的生成和发送。该命令会比较每个监控源已存储的 `current` 和 `latest` Feed 文件，收集所有新增的条目，并发送汇总的关键词速览到配置的目标频道。

示例:
```bash
# 查看所有监控的RSS/Feed
/rss list

# 添加新的RSS/Feed监控
/rss add https://example.com/feed.xml
/rss add https://rsshub.app/github/issue/DIYgod/RSSHub

# 删除RSS/Feed监控
/rss del https://example.com/feed.xml
```

### 支持的Feed格式
- **RSS 2.0**: 标准的RSS格式
- **Atom 1.0**: 标准的Atom格式
- **RSSHub生成的Feed**: 支持RSSHub等工具生成的标准Feed

### 监控功能说明
1. 添加Feed后，机器人会：
   - 立即下载并验证Feed格式
   - 保存Feed内容到本地存储
   - 发送Feed更新到指定频道/用户
   - 如有新的条目，会单独列出发送
2. 定时任务会：
   - 每小时检查一次所有订阅的Feed
   - 自动对比并发现新增的条目
   - 将更新内容发送到指定频道/用户
3. 删除机制：
   - 删除订阅时不会真正删除历史数据
   - 使用标记方式，重新订阅时可避免重复推送
   - 保护用户的历史数据不丢失

### 数据存储
- 每个Feed使用URL哈希值作为唯一目录名
- 原始Feed内容以XML格式存储
- 支持历史版本对比和新增内容检测
- 删除订阅时使用标记方式，保留历史数据

## 技术特性

- **异步处理**: 使用asyncio实现高效的并发处理
- **多平台支持**: 同时支持Telegram和Discord
- **智能去重**: 基于条目ID/链接的智能去重机制
- **数据持久化**: 本地文件系统存储，支持数据恢复
- **错误处理**: 完善的异常处理和日志记录
- **标准兼容**: 支持标准的RSS 2.0和Atom 1.0格式
