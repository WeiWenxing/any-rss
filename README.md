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

可选配置:
- `TELEGRAM_TARGET_CHAT`: 默认消息发送目标 (可以是频道如@channelname或用户ID如123456789)
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
│   ├── rss/            # RSS服务实现
│   │   ├── commands.py  # RSS命令处理
│   │   └── manager.py   # RSS管理器
│   └── douyin/         # 抖音服务实现
│       ├── commands.py  # 抖音命令处理
│       ├── manager.py   # 抖音管理器
│       ├── fetcher.py   # 抖音内容获取器
│       └── formatter.py # 抖音消息格式化器
├── storage/             # 数据存储层
│   ├── rss/
│   │   ├── config/      # RSS配置文件
│   │   └── feeds_data/  # RSS Feed数据存储
│   └── douyin/
│       ├── config/      # 抖音配置文件
│       ├── data/        # 抖音内容数据存储
│       └── media/       # 抖音媒体文件存储
└── any-rss-bot.py      # 主程序入口
```

## 命令使用说明

### Telegram 命令

#### 基础命令
- `/start` - 启动机器人
- `/help` - 显示帮助信息

#### RSS订阅管理
- `/add <RSS_URL> <CHAT_ID>` - 添加新的RSS/Feed监控并绑定到指定频道
- `/del <RSS_URL>` - 删除指定的RSS/Feed监控
- `/list` - 显示所有监控的RSS/Feed列表及其绑定的频道
- `/news` - 手动检查所有订阅源并发送更新内容到对应频道

#### 抖音订阅管理
- `/douyin_add <抖音链接> <CHAT_ID>` - 添加抖音用户订阅并绑定到指定频道
- `/douyin_del <抖音链接>` - 删除指定的抖音用户订阅
- `/douyin_list` - 显示所有抖音订阅列表及其绑定的频道
- `/douyin_check` - 手动检查所有抖音订阅并发送更新内容到对应频道

#### 开发者调试命令
- `/show [type] <item_xml>` - 测试单个RSS条目的消息格式

### 命令详细说明

#### 1. 添加RSS订阅
```bash
# 基本格式
/add <RSS_URL> <CHAT_ID>

# 示例
/add https://example.com/feed.xml @my_channel
/add https://rsshub.app/github/issue/DIYgod/RSSHub -1001234567890
/add https://feeds.feedburner.com/example 123456789
```

**支持的频道ID格式：**
- `@channel_name` - 频道用户名
- `-1001234567890` - 频道数字ID
- `123456789` - 用户数字ID

#### 2. 删除RSS订阅
```bash
# 删除指定订阅
/del https://example.com/feed.xml
```

#### 3. 查看订阅列表
```bash
# 显示所有订阅及其绑定的频道
/list
```

输出示例：
```
当前RSS订阅列表：
- https://example.com/feed.xml → @my_channel
- https://another.com/rss → -1001234567890
- https://third.com/atom.xml → (未设置频道)
```

#### 4. 手动检查更新
```bash
# 强制检查所有订阅源并发送更新
/news
```

#### 5. 抖音订阅管理

##### 添加抖音订阅
```bash
# 基本格式
/douyin_add <抖音链接> <CHAT_ID>

# 示例
/douyin_add https://v.douyin.com/iM5g7LsM/ @my_channel
/douyin_add https://www.douyin.com/user/MS4wLjABAAAAxxx -1001234567890
```

**支持的抖音链接格式：**
- `https://v.douyin.com/xxx` - 手机分享链接
- `https://www.douyin.com/user/xxx` - 电脑端用户主页链接

##### 删除抖音订阅
```bash
# 删除指定抖音订阅
/douyin_del https://v.douyin.com/iM5g7LsM/
```

##### 查看抖音订阅列表
```bash
# 显示所有抖音订阅及其绑定的频道
/douyin_list
```

##### 手动检查抖音更新
```bash
# 强制检查所有抖音订阅并发送更新
/douyin_check
```

#### 6. 开发者调试命令
```bash
# 自动判断消息模式（默认）
/show <item><title>标题</title><description>内容</description></item>

# 强制文字为主模式
/show text <item><title>标题</title><description>内容</description></item>

# 强制图片为主模式
/show media <item><title>标题</title><description>内容</description></item>

# Atom格式支持
/show <entry><title>标题</title><content>内容</content></entry>
```

**type参数说明：**
- `auto` - 自动判断（≥2张图片为图片为主，<2张图片为文字为主）
- `text` - 强制文字为主模式
- `media` - 强制图片为主模式

**支持的格式：**
- `RSS 2.0` - 使用`<item>`标签，内容字段为`<description>`
- `Atom 1.0` - 使用`<entry>`标签，内容字段为`<content>`

### 消息格式说明

#### 图片为主模式（≥2张图片）
- 发送图片组，每组最多10张图片
- 简洁caption格式：`#作者 标题 📊 1/2`（多批次时显示批次信息）
- 使用智能分批算法，确保图片分布均匀

#### 文字为主模式（<2张图片）
- 先发送完整文字消息（包含时间、标题、链接、内容）
- 再发送图片组（如果有图片，使用简洁caption）

### 支持的Feed格式
- **RSS 2.0**: 标准的RSS格式
- **Atom 1.0**: 标准的Atom格式
- **RSSHub生成的Feed**: 支持RSSHub等工具生成的标准Feed

### 监控功能说明

#### 订阅管理
1. **频道绑定**: 每个RSS源可以绑定到不同的频道，支持多频道分发
2. **首次添加**: 首次添加订阅源时，会展示所有现有内容
3. **智能去重**: 基于条目ID/链接的智能去重机制

#### 自动监控
1. **定时检查**: 每小时自动检查所有订阅源的更新
2. **差异检测**: 自动对比并发现新增的条目
3. **分频道推送**: 将更新内容发送到对应绑定的频道

#### 删除机制
- 删除订阅时只删除配置记录，保留所有历史数据
- 重新添加时可避免重复推送历史内容
- 保护用户的历史数据不丢失

### 数据存储
- 每个Feed使用URL哈希值作为唯一目录名
- 原始Feed内容以XML格式存储
- 支持历史版本对比和新增内容检测
- 配置文件记录URL与频道ID的映射关系

## 技术特性

- **异步处理**: 使用asyncio实现高效的并发处理
- **多平台支持**: 同时支持Telegram和Discord
- **多内容源支持**: 支持RSS/Feed和抖音用户内容订阅
- **智能消息格式**: 根据内容自动选择最佳显示方式
- **频道绑定**: 支持每个RSS源和抖音用户绑定到不同频道
- **媒体文件处理**: 自动下载并发送视频/图片文件
- **智能分批**: 图片发送使用均衡分批算法
- **Flood Control**: 完善的发送速度控制和重试机制
- **数据持久化**: 本地文件系统存储，支持数据恢复
- **错误处理**: 完善的异常处理和日志记录
- **标准兼容**: 支持标准的RSS 2.0和Atom 1.0格式
- **第三方API集成**: 集成抖音内容解析API

## 注意事项

1. 确保.env文件中配置了正确的bot token
2. 添加订阅时必须指定目标频道ID
3. 如果目标是Telegram频道，需要将机器人添加为频道的管理员
4. 机器人需要有在目标频道发布消息的权限
5. 首次运行时需要创建虚拟环境并安装依赖
