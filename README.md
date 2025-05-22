# Site Bot

一个支持 Telegram 和 Discord 的站点监控机器人。

## 环境要求

- Python 3.8+
- pip
- virtualenv

## 安装步骤

1. 克隆项目
```bash
git clone [项目地址]
cd site-bot
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
python site-bot.py
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
tail -f /tmp/site-bot.log
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
├── storage/             # 数据存储层
└── site-bot.py         # 主程序入口
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
  - `/rss list` - 显示所有监控的sitemap列表
  - `/rss add URL` - 添加新的sitemap监控（URL必须以sitemap.xml结尾）
  - `/rss del URL` - 删除指定的sitemap监控
- `/news` - 手动触发关键词汇总的生成和发送。该命令会比较每个监控源已存储的 `current` 和 `latest` sitemap 文件，收集所有新增的 URL，并发送汇总的关键词速览到配置的目标频道。

示例:
```bash
# 查看所有监控的sitemap
/rss list

# 添加新的sitemap监控
/rss add https://example.com/sitemap.xml

# 删除sitemap监控
/rss del https://example.com/sitemap.xml
```

### 监控功能说明
1. 添加sitemap后，机器人会：
   - 立即下载并保存sitemap文件
   - 发送sitemap文件到指定频道/用户
   - 如有新的URL，会单独列出发送
2. 定时任务会：
   - 每小时检查一次所有订阅的sitemap
   - 自动对比并发现新增的URL
   - 将更新内容发送到指定频道/用户
