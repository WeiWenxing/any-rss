# RSSHub模块设计文档 (RSSHub Module Design Document)

## 📋 文档信息
- **文档版本**: v1.0
- **创建日期**: 2024年
- **最后更新**: 2024年
- **文档状态**: 设计阶段

## ⚠️ 重要技术说明

### 消息转发方式
本设计文档中的所有转发操作均使用 **`copy_messages`** 方法，与douyin模块保持一致。

**关键特点**：
- **`copy_messages`**：复制消息内容，**不显示"Forward From"转发源标识**
- 保持频道内容的一致性和美观性
- 提供更好的用户体验

**应用范围**：
- 多频道转发：从发送频道复制到其他频道
- 历史内容对齐：从已有频道复制到新订阅频道
- 错误恢复：从成功频道复制到失败频道

---

## 📖 目录
1. [文档概述](#文档概述)
2. [问题定义](#问题定义)
3. [设计目标](#设计目标)
4. [系统概述](#系统概述)
5. [架构设计](#架构设计)
6. [数据设计](#数据设计)
7. [接口设计](#接口设计)
8. [核心算法](#核心算法)

---

## 1. 文档概述

### 1.1 文档目的
本文档描述RSSHub内容订阅推送模块的设计方案，重点阐述多频道高效转发机制在RSS/Atom XML数据格式下的实现。文档旨在为开发团队提供清晰的技术设计指导，确保系统的可维护性和扩展性。

### 1.2 适用范围
本文档适用于：
- RSSHub平台生成的RSS/Atom feed的自动订阅与推送功能
- 多频道转发机制和历史内容对齐
- 与Telegram Bot的集成实现

本文档不包含：
- RSSHub平台的具体使用方法
- RSS/Atom协议的详细规范
- 具体的部署运维操作手册

### 1.3 目标读者
- **开发工程师**：了解模块架构和实现方案
- **系统架构师**：评估技术选型和设计合理性
- **产品负责人**：理解功能特性和业务价值

前置知识：熟悉Python异步编程、Telegram Bot API、RSS/Atom协议、订阅推送概念。

---

## 2. 问题定义

### 2.1 业务背景
用户需要及时获取RSSHub平台生成的各种RSS源的最新内容更新，通过Telegram频道进行推送。系统需要支持多个Telegram频道订阅同一个RSSHub源，确保所有频道都能收到完整的内容推送。

### 2.2 现有问题
**与现有RSS模块的差异**：
- 现有RSS模块仅支持单频道订阅，无法实现高效的多频道推送
- 缺乏历史内容对齐机制，新订阅频道会错过历史内容
- 没有转发优化，重复发送相同内容浪费资源

**数据格式特殊性**：
- RSSHub生成的RSS/Atom feed为XML格式，需要专门的解析处理
- 不同于douyin模块的JSON数据结构
- 需要保持XML结构的完整性和原始信息

### 2.3 解决需求
**核心需求**：
- 支持一个RSSHub URL订阅到多个Telegram频道
- 保证每个频道收到完整且一致的RSS内容
- 最大化资源利用效率，减少重复操作
- 处理RSS/Atom XML格式的数据结构

**具体要求**：
- 新频道订阅时自动同步历史RSS条目
- 新RSS条目发布时高效推送到所有订阅频道
- 提供简洁易用的RSSHub订阅管理命令
- 支持RSS媒体附件（enclosure）的处理

---

## 3. 设计目标

### 3.1 功能性目标
**多频道RSS订阅支持**：
- 支持一个RSSHub URL同时订阅到多个Telegram频道
- 新频道订阅时自动获取完整历史RSS条目
- 提供灵活的订阅管理（添加、删除、查看）

**RSS/Atom内容推送保障**：
- 确保所有订阅频道都能收到新RSS条目
- 保持RSS条目的时序性和完整性
- 支持RSS媒体附件（图片、视频、音频）
- 保持XML格式的原始信息

### 3.2 非功能性目标
**性能效率**：
- API调用次数优化：每个新RSS条目仅需1次发送 + N-1次转发
- 带宽使用优化：避免重复的媒体文件传输
- 响应时间：新RSS条目推送延迟控制在5分钟内

**可靠性**：
- 转发失败时自动降级为直接发送
- 异常情况下的错误恢复机制
- 完整的操作日志记录

**可维护性**：
- 复用douyin模块的成熟组件
- 模块化设计，职责分离
- 清晰的数据结构和接口定义

### 3.3 约束条件
**技术约束**：
- 基于现有的Telegram Bot框架
- 遵循Telegram API的频率限制（20条消息/分钟）
- Python异步编程模式
- 复用douyin模块的转发机制

**业务约束**：
- RSS/Atom协议的标准规范
- RSSHub平台的访问限制
- 存储空间的合理使用

---

## 4. 系统概述

### 4.1 系统定位
RSSHub模块是RSS订阅系统的专业化组件，专门负责RSSHub平台生成的RSS/Atom feed的订阅、解析和推送。该模块采用与douyin模块相同的"角色分工转发"机制，通过智能的发送和转发策略，实现高效的多频道内容分发。

### 4.2 核心功能
**订阅管理**：
- RSSHub URL的订阅和取消订阅
- 支持多个Telegram频道订阅同一RSSHub源
- 订阅列表的查看和管理

**RSS/Atom解析**：
- 定时检查RSSHub源的最新内容更新
- 支持RSS 2.0和Atom 1.0格式
- 智能解析RSS条目的各种字段
- 智能去重，避免重复推送

**多频道推送**：
- 发送频道直接发送RSS条目，转发频道使用copy_messages复制完整消息（不显示转发源标识）
- 新频道订阅时的智能历史内容对齐
- 转发失败时的多源重试和自动降级机制

### 4.3 关键特性
**高效转发机制**：
- 每个新RSS条目仅需1次发送 + N-1次copy_messages复制操作
- copy_messages复制保持原有消息的完整性和界面效果，且不显示"Forward From"转发源标识
- 显著减少带宽使用和API调用次数
- 支持大规模多频道部署

**智能历史对齐**：
- 该RSS URL的首个频道订阅：直接获取历史RSS条目并发送到该频道，建立内容基准
- 该RSS URL的后续频道订阅：从任意可用频道智能选择转发源，转发历史RSS条目到新频道
- 转发源优先级：订阅列表中的首个频道 > 任意有消息ID的频道
- 确保所有频道RSS内容的完整性和一致性

**容错降级设计**：
- 记录每个RSS条目在每个频道的消息ID
- 转发失败时从所有成功频道中智能选择转发源重试
- 多源转发重试失败后降级为直接发送
- 完整的操作日志和状态追踪

---

## 5. 架构设计

### 5.1 统一消息架构（跨模块设计）

#### 5.1.1 设计理念
不同数据源（douyin、rsshub、rss）的内容最终都要发送到Telegram，因此可以定义统一的Telegram消息实体作为所有模块的输出标准。这样设计的优势：

1. **发送逻辑统一**：所有模块共享相同的Telegram发送器
2. **格式标准化**：确保不同来源的消息具有一致的用户体验
3. **维护简化**：Telegram API变更时只需修改一处代码
4. **功能复用**：转发、对齐等功能可以跨模块使用

#### 5.1.2 消息转换流程
```
数据源实体 → 统一消息实体 → Telegram API
    ↓              ↓              ↓
RSSEntry  →  TelegramMessage → send_media_group()
Content   →  TelegramMessage → send_media_group()
```

#### 5.1.3 转换器接口设计
```python
# 统一的消息转换器接口
class MessageConverter:
    def to_telegram_message(self, source_entity) -> TelegramMessage:
        """将数据源实体转换为统一的Telegram消息实体"""
        pass

# RSS专用转换器
class RSSMessageConverter(MessageConverter):
    def to_telegram_message(self, rss_entry: RSSEntry) -> TelegramMessage:
        """将RSS条目转换为Telegram消息"""
        pass

# Douyin专用转换器
class DouyinMessageConverter(MessageConverter):
    def to_telegram_message(self, content: Content) -> TelegramMessage:
        """将抖音内容转换为Telegram消息"""
        pass
```

#### 5.1.4 统一发送器设计
```python
# 统一的Telegram发送器
class UnifiedTelegramSender:
    async def send_message(self, bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]:
        """发送统一格式的消息到Telegram"""
        if message.media_group:
            return await self._send_media_group(bot, chat_id, message)
        else:
            return await self._send_text_message(bot, chat_id, message)

    async def copy_messages(self, bot: Bot, from_chat: str, to_chat: str, message_ids: List[int]) -> List[Message]:
        """复制消息（跨模块通用）"""
        pass
```

### 5.2 整体架构
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Commands   │    │  Scheduler  │    │  Alignment  │
│  (用户触发)  │    │  (定时触发)  │    │  (历史对齐)  │
└─────┬───────┘    └─────┬───────┘    └─────┬───────┘
      │                  │                  │
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
                         ▼
                ┌─────────────┐
                │   Manager   │
                │  (核心管理)  │
                └─────┬───────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Parser  │ │ Sender  │ │ Storage │
    │(RSS解析)│ │(消息发送)│ │(数据存储)│
    └─────────┘ └─────────┘ └─────────┘
```

### 5.2 模块划分
**Commands（命令处理模块）**：
- 处理用户的RSSHub订阅管理命令
- 参数验证和错误处理
- 用户交互和反馈

**Scheduler（调度器模块）**：
- 定时检查RSS源更新
- 多频道转发机制的实现
- 批量处理和发送间隔控制

**Manager（管理器模块）**：
- 订阅数据的存储和管理
- 消息ID的记录和查询
- 已知RSS条目的去重管理

**Parser（RSS解析模块）**：
- RSS/Atom XML的解析和处理
- RSS条目信息的提取和格式化
- 媒体附件的处理
- 更新检测和新条目识别

**Sender（发送器模块）**：
- 完全复用douyin模块的发送逻辑
- Telegram消息的发送和转发
- 媒体文件的处理和上传

**Alignment（对齐模块）**：
- 完全复用douyin模块的对齐逻辑
- 新频道的历史内容对齐
- 批量转发和进度控制

### 5.3 模块间协作关系

#### 5.3.1 跨模块组件复用
```
┌─────────────────────────────────────────────────────────────┐
│                    统一Telegram层                           │
├─────────────────────────────────────────────────────────────┤
│  UnifiedTelegramSender  │  MessageConverter  │  Alignment   │
└─────────────────────────────────────────────────────────────┘
                              ↑
                    ┌─────────┼─────────┐
                    │         │         │
            ┌───────▼───┐ ┌───▼───┐ ┌───▼─────┐
            │  Douyin   │ │  RSS  │ │ RSSHub  │
            │  Module   │ │ Module│ │ Module  │
            └───────────┘ └───────┘ └─────────┘
```

#### 5.3.2 消息格式标准化收益
1. **douyin模块**：可以复用RSS模块的媒体处理策略
2. **rss模块**：可以复用douyin模块的多频道转发机制
3. **rsshub模块**：同时复用两者的优势功能
4. **未来扩展**：新增数据源只需实现转换器即可

### 5.4 组件关系
**数据流向**：
1. Commands接收用户指令，调用Manager进行订阅管理
2. Scheduler定时触发，通过Manager获取订阅列表
3. Scheduler调用Parser检查RSS源更新
4. Scheduler使用Sender进行多频道推送
5. 新订阅时的分支处理：
   - 该RSS URL的首个频道订阅：Commands调用Parser获取历史RSS条目，通过Sender发送，建立内容基准
   - 该RSS URL的后续频道订阅：Commands调用Alignment从可用频道智能选择转发源，转发历史RSS条目

**依赖关系**：
- Commands依赖Manager、Parser、Sender、Alignment
- Scheduler依赖Manager、Parser、Sender
- Alignment完全复用douyin模块（依赖Manager、Sender）
- Manager作为核心数据层，被其他模块依赖
- Sender完全复用douyin模块的实现

**复用策略**：
- **完全复用**: Sender、Alignment模块直接使用douyin的实现
- **数据结构复用**: Subscription、MessageMapping、KnownContent使用douyin的数据结构
- **独立实现**: Parser模块和RSSEntry实体为RSS专用

---

## 6. 数据设计

### 6.1 数据模型

#### 6.1.1 核心实体模型

**可复用实体（与douyin模块完全一致）**：
```
订阅实体 (Subscription) - 复用douyin
├── rss_url: str                    # RSSHub URL（作为主键，对应douyin_url）
└── target_channels: List[str]      # 订阅的频道列表

消息映射实体 (MessageMapping) - 复用douyin
├── rss_url: str                    # RSS URL（对应douyin_url）
├── item_id: str                    # 条目ID
├── chat_id: str                    # 频道ID
└── message_ids: List[int]          # Telegram消息ID列表（支持MediaGroup）

已知条目实体 (KnownContent) - 复用douyin
├── rss_url: str                    # RSS URL（对应douyin_url，作为分组）
└── item_ids: List[str]             # 已知条目ID列表
```

**数据源特定实体（RSS专用）**：
```
RSS条目实体 (RSSEntry) - RSS专用，对应douyin的Content，参考RSS模块的extract_entry_info
├── title: str                      # 条目标题
├── link: str                       # 条目链接
├── summary: str                    # 条目摘要
├── description: str                # 条目描述/内容
├── author: str                     # 作者
├── id: str                         # RSS条目原始ID（guid或link）
├── published: str                  # 发布时间
├── content: str                    # 完整内容（优先级：content > description > summary）
├── item_id: str                    # 生成的唯一标识（对应douyin的aweme_id）
└── target_channels: List[str]      # 目标频道列表（运行时添加）
```

**统一Telegram消息实体（跨模块标准）**：
```
Telegram消息实体 (TelegramMessage) - 统一的消息格式，所有模块最终输出
├── text: str                       # 消息文本内容
├── media_group: List[MediaItem]    # 媒体组列表
├── parse_mode: str                 # 解析模式（Markdown/HTML）
├── disable_web_page_preview: bool  # 是否禁用链接预览
└── reply_markup: Optional[Dict]    # 可选的键盘标记

MediaItem子实体：
├── type: str                       # 媒体类型（photo/video/audio/document）
├── url: str                        # 媒体URL
├── caption: Optional[str]          # 媒体标题（仅第一个媒体项有）
├── width: Optional[int]            # 媒体宽度
├── height: Optional[int]           # 媒体高度
└── duration: Optional[int]         # 媒体时长（视频/音频）
```

#### 6.1.2 数据关系图
```
┌─────────────────┐    1:N    ┌─────────────────┐
│   Subscription  │ ────────→ │    RSSEntry     │
│   (复用douyin)   │           │   (RSS专用)     │
│ - rss_url       │           │ - title         │
│ - channels[]    │           │ - link          │
└─────────────────┘           │ - published     │
         │                    │ - item_id       │
         │                    └─────────────────┘
         │ 1:1                         │
         ▼                             │ 1:N
┌─────────────────┐                    ▼
│  KnownContent   │           ┌─────────────────┐
│  (复用douyin)    │           │ MessageMapping  │
│ - rss_url       │           │  (复用douyin)    │
│ - item_ids[]    │           │ - rss_url       │
└─────────────────┘           │ - item_id       │
                               │ - chat_id       │
                               │ - message_ids[] │
                               └─────────────────┘

数据存储关系：
- Subscription: subscriptions.json (复用douyin格式)
- KnownContent: known_item_ids.json (复用douyin格式，唯一的内容存储文件)
- MessageMapping: message_mappings.json (复用douyin格式)
- RSSEntry: 运行时从RSS源实时获取和解析，不持久化存储
- TelegramMessage: 运行时生成，作为所有模块的统一输出格式
```

### 6.2 存储结构

#### 6.2.1 目录结构设计
```
storage/rsshub/
├── config/                          # 配置文件目录
│   ├── subscriptions.json          # 订阅配置文件
│   └── message_mappings.json       # 消息ID映射文件
├── data/                           # 数据文件目录（精简版，只保留必要文件）
│   └── {url_hash}/                 # 按URL哈希分组
│       ├── url.txt                 # 原始URL记录
│       └── known_item_ids.json     # 已知条目ID列表（唯一必要的存储文件）
└── media/                          # 媒体文件目录
    └── {url_hash}/                 # 按URL哈希分组
        ├── {entry_id}_1.jpg        # 图片文件
        ├── {entry_id}_2.mp4        # 视频文件
        └── ...
```

#### 6.2.2 配置文件格式

**订阅配置文件 (subscriptions.json)**：
```json
{
  "https://rsshub.app/github/issue/DIYgod/RSSHub": [
    "@tech_channel",
    "@dev_channel",
    "-1001234567890"
  ],
  "https://rsshub.app/bilibili/user/video/2267573": [
    "@video_channel"
  ]
}
```

**消息映射文件 (message_mappings.json)**：
```json
{
  "https://rsshub.app/github/issue/DIYgod/RSSHub": {
    "entry_abc123def456": {
      "@tech_channel": [789, 790],     // MediaGroup的多个消息ID
      "@dev_channel": [892, 893]       // 转发后的多个消息ID
    },
    "entry_def456ghi789": {
      "@tech_channel": [800],          // 单个消息ID
      "@dev_channel": [901]            // 转发后的单个消息ID
    }
  }
}
```

**已知条目ID列表 (known_item_ids.json)**：
```json
[
  "entry_abc123def456",
  "entry_def456ghi789",
  "entry_ghi789jkl012"
]
```

**URL记录文件 (url.txt)**：
```
https://rsshub.app/github/issue/DIYgod/RSSHub
```

---

## 7. 接口设计

### 7.1 命令接口设计

#### 7.1.1 /rsshub_add - 添加RSSHub订阅

**命令格式**：
```bash
/rsshub_add <RSS_URL> <频道ID>

# 示例
/rsshub_add https://rsshub.app/github/issue/DIYgod/RSSHub @tech_channel
/rsshub_add https://rsshub.app/bilibili/user/video/2267573 -1001234567890
```

**交互流程**：
```
用户输入命令 → 参数验证 → 立即反馈"正在处理" → 检查订阅状态
    ↓
┌─────────────┬─────────────┬─────────────┐
│  首个频道   │  后续频道   │  重复订阅   │
│             │             │             │
│        统一反馈流程        │ 立即反馈    │
│    "正在获取历史内容"      │ "已存在"    │
│             │             │     ↓       │
│        执行具体操作        │ 完成反馈    │
│    (获取/发送 或 对齐)     │             │
│             │             │             │
│        进度反馈           │             │
│    "正在发送 X 个内容"     │             │
│             │             │             │
│        记录消息ID         │             │
│             │             │             │
│        最终反馈           │             │
│    "完成同步 X 个内容"     │             │
└─────────────┴─────────────┴─────────────┘
```

**用户体验原则**：
- **统一性**：无论内部实现如何，用户看到的流程保持一致
- **及时性**：立即反馈 + 进度更新 + 最终结果
- **透明性**：隐藏技术细节（如"历史对齐"、"转发"等术语）
- **简洁性**：使用用户友好的语言，避免技术术语

**立即反馈**（用户发送命令后立即显示）：
```
✅ 正在添加RSSHub订阅...
🔗 RSS链接：{完整的rss_url}
📺 目标频道：{channel}
⏳ 正在获取历史内容，请稍候...
```

**进度反馈**（开始发送内容时更新）：
```
✅ 订阅添加成功！
🔗 RSS链接：{完整的rss_url}
📺 目标频道：{channel}
📤 正在发送 {count} 个历史内容...
```

**最终反馈**（所有内容发送完成后更新）：
```
✅ RSSHub订阅添加完成
🔗 RSS链接：{完整的rss_url}
📺 目标频道：{channel}
📊 已同步 {count} 个历史内容
🔄 系统将继续自动监控新内容
```

**重复订阅反馈**：
```
⚠️ 该RSS源已订阅到此频道
🔗 RSS链接：{完整的rss_url}
📺 目标频道：{channel}
📋 当前订阅状态：正常
🔄 系统正在自动监控新内容，无需重复添加
```

**错误反馈**：
```
❌ 添加RSSHub订阅失败
🔗 RSS链接：{完整的rss_url}
原因：{error_message}

💡 请检查：
- RSS链接格式是否正确
- 频道ID是否有效
- Bot是否有频道发送权限
```

**伪代码实现**：
```python
async def rsshub_add_command(rss_url: str, chat_id: str):
    """添加RSSHub订阅的伪代码实现 - 统一反馈流程"""

    # 1. 参数验证
    if not validate_rss_url(rss_url):
        return error_response("RSS链接格式不正确")

    if not validate_chat_id(chat_id):
        return error_response("频道ID格式不正确")

    # 2. 检查订阅状态
    subscription_status = check_subscription_status(rss_url, chat_id)

    if subscription_status == "duplicate":
        # 重复订阅分支 - 直接返回
        await send_message(duplicate_response(rss_url, chat_id))
        return

    # 3. 立即反馈（非重复订阅才需要处理反馈）
    processing_message = await send_processing_feedback(rss_url, chat_id)

    # 4. 统一处理流程（首个频道和后续频道使用相同的用户反馈）
    try:
        if subscription_status == "first_channel":
            # 首个频道：获取历史内容
            content_list = await fetch_rss_content(rss_url)
            content_count = len(content_list)
        else:
            # 后续频道：获取已知内容ID列表
            content_list = get_known_item_ids(rss_url)
            content_count = len(content_list)

        # 5. 进度反馈（统一格式）
        await edit_message(processing_message,
                          progress_feedback(rss_url, chat_id, content_count))

        # 6. 执行具体操作（用户无感知差异）
        if subscription_status == "first_channel":
            # 发送到频道
            sent_count = await manager.send_content_batch(
                bot, content_list, rss_url, [chat_id]
            )
        else:
            # 历史对齐（用户看不到技术细节）
            from .alignment import perform_historical_alignment
            alignment_success = await perform_historical_alignment(
                bot, rss_url, content_list, chat_id
            )
            sent_count = len(content_list) if alignment_success else 0

        # 7. 最终反馈（统一格式）
        await edit_message(processing_message,
                          final_success_response(rss_url, chat_id, sent_count))

    except Exception as e:
        # 错误反馈
        await edit_message(processing_message,
                          error_response(rss_url, str(e)))
```

#### 7.1.2 /rsshub_del - 删除RSSHub订阅

**命令格式**：
```bash
/rsshub_del <RSS_URL> <频道ID>

# 示例
/rsshub_del https://rsshub.app/github/issue/DIYgod/RSSHub @tech_channel
```

**交互流程**：
```
用户输入命令 → 参数验证 → 查找订阅
    ↓
┌─────────────┬─────────────┐
│  删除成功   │  订阅不存在  │
│             │             │
│ 移除频道    │ 返回提示    │
│     ↓       │     ↓       │
│ 更新配置    │ 完成反馈    │
│     ↓       │             │
│ 完成反馈    │             │
└─────────────┴─────────────┘
```

**成功反馈**：
```
✅ 成功删除RSSHub订阅
🔗 RSS链接：{完整的rss_url}
📺 目标频道：{channel}
```

**订阅不存在反馈**：
```
⚠️ 该RSS源未订阅到此频道
🔗 RSS链接：{完整的rss_url}
📺 目标频道：{channel}
💡 请检查链接和频道ID是否正确
```

**错误反馈**：
```
❌ 删除RSSHub订阅失败
🔗 RSS链接：{完整的rss_url}
原因：{error_message}

💡 请检查：
- RSS链接格式是否正确
- 频道ID是否有效
```

**伪代码实现**：
```python
async def rsshub_del_command(rss_url: str, chat_id: str):
    """删除RSSHub订阅的伪代码实现"""

    # 1. 参数验证
    if not validate_rss_url(rss_url):
        return error_response("RSS链接格式不正确")

    if not validate_chat_id(chat_id):
        return error_response("频道ID格式不正确")

    # 2. 查找订阅
    subscriptions = get_subscriptions()

    if rss_url not in subscriptions:
        return not_found_response(rss_url, chat_id, "该RSS源未被任何频道订阅")

    if chat_id not in subscriptions[rss_url]:
        return not_found_response(rss_url, chat_id, "该频道未订阅此RSS源")

    # 3. 删除频道
    try:
        subscriptions[rss_url].remove(chat_id)

        # 检查是否为最后一个频道
        if len(subscriptions[rss_url]) == 0:
            # 最后频道：只删除订阅配置，保留历史数据
            del subscriptions[rss_url]
            remaining_count = 0
        else:
            # 普通删除：只移除频道
            remaining_count = len(subscriptions[rss_url])

        # 4. 更新配置
        save_subscriptions(subscriptions)

        return success_response(rss_url, chat_id, remaining_count)

    except Exception as e:
        return error_response(f"删除订阅失败: {str(e)}")
```

#### 7.1.3 /rsshub_list - 查看订阅列表

**命令格式**：
```bash
/rsshub_list
```

**交互流程**：
```
用户输入命令 → 获取订阅列表
    ↓
┌─────────────┬─────────────┐
│  有订阅内容  │  无订阅内容  │
│             │             │
│ 格式化显示  │ 返回提示    │
│     ↓       │     ↓       │
│ 返回列表    │ 完成反馈    │
└─────────────┴─────────────┘
```

**有订阅时的反馈**：
```
📋 当前RSSHub订阅列表：

📰 GitHub Issues
   🔗 https://rsshub.app/github/issue/DIYgod/RSSHub
   📺 @tech_channel, @dev_channel

📰 Bilibili视频
   🔗 https://rsshub.app/bilibili/user/video/2267573
   📺 @video_channel

📊 总计：2个RSS源，3个频道订阅
```

**无订阅时的反馈**：
```
📋 当前没有RSSHub订阅

💡 使用 /rsshub_add <RSS链接> <频道ID> 添加订阅
```

**错误反馈**：
```
❌ 获取订阅列表失败
原因：{error_message}
```

**伪代码实现**：
```python
async def rsshub_list_command():
    """查看订阅列表的伪代码实现"""

    try:
        # 1. 获取订阅配置
        subscriptions = get_subscriptions()

        # 2. 检查是否有订阅
        if not subscriptions:
            return empty_list_response()

        # 3. 格式化订阅列表
        formatted_list = []
        total_sources = len(subscriptions)
        total_channels = 0

        for rss_url, channels in subscriptions.items():
            # 获取RSS源信息（可选，用于显示标题）
            feed_info = get_feed_info_from_url(rss_url)
            feed_display = feed_info.get('title', 'RSS源') if feed_info else 'RSS源'

            # 格式化频道列表
            channel_list = ', '.join(channels)
            total_channels += len(channels)

            formatted_list.append(f"📰 {feed_display}\n   🔗 {rss_url}\n   📺 {channel_list}")

        # 4. 生成完整响应（确保URL完整显示）
        response_text = "📋 当前RSSHub订阅列表：\n\n"
        response_text += "\n\n".join(formatted_list)
        response_text += f"\n\n📊 总计：{total_sources}个RSS源，{total_channels}个频道订阅"

        return success_list_response(response_text)

    except Exception as e:
        return error_response(f"获取订阅列表失败: {str(e)}")
```

### 7.2 内部接口设计

#### 7.2.1 Manager接口（复用douyin模块设计）
```python
class RSSHubManager:
    # 订阅管理（完全复用douyin接口）
    def add_subscription(self, rss_url: str, chat_id: str) -> tuple[bool, str, str, List[RSSEntry]]
    def remove_subscription(self, rss_url: str) -> tuple[bool, str]
    def get_subscriptions(self) -> Dict[str, List[str]]
    def get_subscription_channels(self, rss_url: str) -> List[str]

    # 内容获取（RSS专用）
    def download_and_parse_feed(self, rss_url: str) -> tuple[bool, str, List[RSSEntry]]
    def check_updates(self, rss_url: str) -> tuple[bool, str, List[RSSEntry]]

    # 去重管理（完全复用douyin接口）
    def get_known_item_ids(self, rss_url: str) -> List[str]
    def add_known_item_ids(self, rss_url: str, item_ids: List[str]) -> bool

    # 消息映射（完全复用douyin接口）
    def save_message_mapping(self, rss_url: str, item_id: str, chat_id: str, message_ids: List[int]) -> bool
    def get_message_mapping(self, rss_url: str, item_id: str) -> Dict[str, List[int]]
    def get_available_source_channels(self, rss_url: str, item_id: str) -> List[str]

    # 批量发送（完全复用douyin接口）
    async def send_content_batch(self, bot, content_items: List[RSSEntry], rss_url: str, target_channels: List[str]) -> int
```

#### 7.2.2 Parser接口（RSS专用）
```python
class RSSHubParser:
    # RSS解析核心功能
    def parse_rss_feed(self, rss_url: str) -> tuple[bool, str, List[RSSEntry]]
    def parse_rss_xml(self, xml_content: str) -> List[RSSEntry]
    def extract_entry_info(self, entry_element) -> RSSEntry
    def generate_entry_id(self, entry: RSSEntry) -> str
```

#### 7.2.3 统一消息转换器接口
```python
class RSSHubMessageConverter:
    def to_telegram_message(self, rss_entry: RSSEntry) -> TelegramMessage
    def extract_media_items(self, rss_entry: RSSEntry) -> List[MediaItem]
    def format_message_text(self, rss_entry: RSSEntry) -> str
    def determine_send_strategy(self, rss_entry: RSSEntry) -> str  # "media_group" | "text_with_preview"
```

#### 7.2.4 统一发送器接口（跨模块复用）
```python
class UnifiedTelegramSender:
    async def send_message(self, bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]
    async def send_media_group(self, bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]
    async def send_text_message(self, bot: Bot, chat_id: str, message: TelegramMessage) -> Message
    async def copy_messages(self, bot: Bot, from_chat: str, to_chat: str, message_ids: List[int]) -> List[Message]
```

#### 7.2.5 Scheduler接口（复用douyin模块设计）
```python
class RSSHubScheduler:
    # 定时检查（复用douyin逻辑）
    def check_all_subscriptions(self) -> None
    def check_single_subscription(self, rss_url: str) -> tuple[bool, str, List[RSSEntry]]

    # 批量发送（复用douyin的send_content_batch）
    def send_new_entries(self, rss_url: str, entries: List[RSSEntry]) -> None
```

---

## 8. 核心算法

### 8.1 RSS解析算法

#### 8.1.1 RSS/Atom格式检测
```python
def detect_feed_format(xml_content: str) -> str:
    """
    检测RSS/Atom格式

    算法：
    1. 解析XML根元素
    2. 检查namespace和版本信息
    3. 返回格式类型

    Returns:
        'rss2.0' | 'atom1.0' | 'rss1.0' | 'unknown'
    """
    try:
        root = ET.fromstring(xml_content)

        # 检查RSS格式
        if root.tag.lower() == 'rss':
            version = root.get('version', '')
            if version.startswith('2.'):
                return 'rss2.0'
            elif version.startswith('1.'):
                return 'rss1.0'

        # 检查Atom格式
        elif 'atom' in root.tag.lower():
            return 'atom1.0'

        return 'unknown'
    except:
        return 'unknown'
```

#### 8.1.2 条目ID生成算法
```python
def generate_entry_id(entry: RSSEntry) -> str:
    """
    生成条目唯一ID

    算法优先级：
    1. guid (如果是permalink)
    2. link + pub_date
    3. title + pub_date
    4. 内容hash

    Returns:
        16位哈希字符串
    """
    # 优先使用guid
    if entry.guid and entry.guid_is_permalink:
        content = entry.guid
    # 使用link + pub_date
    elif entry.link and entry.pub_date:
        content = f"{entry.link}|{entry.pub_date}"
    # 使用title + pub_date
    elif entry.title and entry.pub_date:
        content = f"{entry.title}|{entry.pub_date}"
    # 最后使用内容hash
    else:
        content = f"{entry.title}|{entry.description}|{entry.link}"

    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

#### 8.1.3 新条目检测算法（参考douyin模块）
```python
def detect_new_entries(current_entries: List[RSSEntry], known_item_ids: List[str]) -> List[RSSEntry]:
    """
    检测新条目（参考douyin模块的逻辑）

    算法（参考douyin模块的check_updates逻辑）：
    1. 为每个当前条目生成item_id
    2. 与已知ID列表比较
    3. 筛选出新条目
    4. 按发布时间排序
    """
    new_entries = []

    for entry in current_entries:
        item_id = generate_entry_id(entry)

        # 如果这个item_id不在已知列表中，说明是新的
        if item_id not in known_item_ids:
            entry.item_id = item_id
            new_entries.append(entry)
            logging.info(f"发现新RSS条目: {entry.title} (ID: {item_id})")

    # 按发布时间排序（旧的在前，确保发送顺序）
    new_entries.sort(key=lambda x: parse_date(x.published or ""))

    logging.info(f"RSS条目检测完成，发现 {len(new_entries)} 个新条目")
    return new_entries
```

### 8.2 多频道转发算法

#### 8.2.1 转发策略选择
```python
def select_forward_strategy(entry: RSSEntry, target_channels: List[str]) -> tuple[str, List[str]]:
    """
    选择转发策略

    算法：
    1. 第一个频道作为主发送频道
    2. 其余频道作为转发目标

    Returns:
        (primary_channel, forward_channels)
    """
    if not target_channels:
        return None, []

    primary_channel = target_channels[0]
    forward_channels = target_channels[1:]

    return primary_channel, forward_channels
```

#### 8.2.2 转发源选择算法
```python
def select_forward_source(rss_url: str, item_id: str, target_channels: List[str]) -> str:
    """
    为新频道选择转发源

    算法优先级：
    1. 订阅列表中的第一个频道
    2. 任意有该条目消息ID的频道
    3. None（需要直接发送）

    Returns:
        source_channel_id or None
    """
    # 获取该RSS URL的所有订阅频道
    all_channels = manager.get_subscription_channels(rss_url)

    # 优先选择第一个频道
    if all_channels and all_channels[0] not in target_channels:
        message_mapping = manager.get_message_mapping(rss_url, item_id)
        if all_channels[0] in message_mapping:
            return all_channels[0]

    # 选择任意可用频道
    available_channels = manager.get_available_source_channels(rss_url, item_id)
    for channel in available_channels:
        if channel not in target_channels:
            return channel

    return None
```

### 8.3 历史对齐算法

#### 8.3.1 历史条目获取（实时获取策略）
```python
def get_historical_entries(rss_url: str, known_item_ids: List[str]) -> List[RSSEntry]:
    """
    获取历史条目用于新频道对齐（实时获取策略）

    算法（与douyin模块一致）：
    1. 实时从RSS源获取当前所有条目
    2. 筛选出已知的条目（在known_item_ids中的）
    3. 按发布时间排序
    4. 返回历史条目列表

    Returns:
        历史条目列表（按时间倒序）
    """
    # 实时获取RSS数据
    success, error_msg, all_entries = parser.download_and_parse_feed(rss_url)
    if not success:
        logging.error(f"获取RSS历史条目失败: {error_msg}")
        return []

    # 筛选出已知的条目（用于历史对齐）
    historical_entries = []
    for entry in all_entries:
        item_id = generate_entry_id(entry)
        if item_id in known_item_ids:
            entry.item_id = item_id
            historical_entries.append(entry)

    # 按发布时间排序（新的在前）
    historical_entries.sort(key=lambda x: parse_date(x.published or ""), reverse=True)

    logging.info(f"获取到 {len(historical_entries)} 个历史RSS条目用于对齐")
    return historical_entries
```

#### 8.3.2 批量转发控制
```python
async def forward_entries_batch(entries: List[RSSEntry], source_chat_id: str, target_chat_id: str) -> None:
    """
    批量转发条目到新频道

    算法：
    1. 按时间顺序转发（旧的在前）
    2. 控制转发间隔（避免频率限制）
    3. 记录转发结果
    4. 失败时降级为直接发送
    """
    # 按发布时间排序（旧的在前）
    entries.sort(key=lambda x: parse_date(x.pub_date or ""))

    for entry in entries:
        try:
            # 尝试使用copy_messages转发
            message_ids = manager.get_message_mapping(entry.source_url, entry.item_id).get(source_chat_id, [])

            if message_ids:
                success = await sender.copy_messages(source_chat_id, target_chat_id, message_ids)

                if success:
                    # 记录转发成功的消息ID
                    manager.save_message_mapping(entry.source_url, entry.item_id, target_chat_id, success.message_ids)
                else:
                    # 转发失败，降级为直接发送
                    await sender.send_entry_direct(entry, target_chat_id)
            else:
                # 没有消息ID，直接发送
                await sender.send_entry_direct(entry, target_chat_id)

            # 控制发送间隔
            await asyncio.sleep(2)

        except Exception as e:
            logging.error(f"转发RSS条目失败: {entry.item_id}, 错误: {str(e)}", exc_info=True)
            continue
```

### 8.4 统一消息转换算法

#### 8.4.1 RSS到Telegram消息转换
```python
def to_telegram_message(rss_entry: RSSEntry) -> TelegramMessage:
    """
    将RSS条目转换为统一的Telegram消息格式

    算法：
    1. 提取媒体项列表
    2. 根据媒体数量决定发送策略
    3. 格式化消息文本
    4. 构建TelegramMessage对象

    Returns:
        TelegramMessage: 统一的消息格式
    """
    # 1. 提取媒体项
    media_items = extract_media_items(rss_entry)

    # 2. 决定发送策略
    if len(media_items) >= 2:
        send_strategy = "media_group"  # 媒体组模式
    elif len(media_items) == 1:
        send_strategy = "text_with_preview"  # 文本+预览模式
    else:
        send_strategy = "text_only"  # 纯文本模式

    # 3. 格式化消息文本
    message_text = format_message_text(rss_entry, send_strategy)

    # 4. 构建统一消息对象
    telegram_message = TelegramMessage(
        text=message_text,
        media_group=media_items if send_strategy == "media_group" else [],
        parse_mode="Markdown",
        disable_web_page_preview=(send_strategy != "text_with_preview")
    )

    return telegram_message

def extract_media_items(rss_entry: RSSEntry) -> List[MediaItem]:
    """提取RSS条目中的媒体项"""
    media_items = []

    # 从enclosures提取媒体
    for enclosure in rss_entry.enclosures:
        if enclosure.type.startswith('image/'):
            media_items.append(MediaItem(
                type="photo",
                url=enclosure.url,
                caption=rss_entry.title if len(media_items) == 0 else None
            ))
        elif enclosure.type.startswith('video/'):
            media_items.append(MediaItem(
                type="video",
                url=enclosure.url,
                caption=rss_entry.title if len(media_items) == 0 else None
            ))

    # 从内容中提取图片链接
    content_media = extract_media_from_content(rss_entry.content)
    media_items.extend(content_media)

    return media_items

def format_message_text(rss_entry: RSSEntry, send_strategy: str) -> str:
    """根据发送策略格式化消息文本"""
    message_parts = []

    if send_strategy == "media_group":
        # 媒体组模式：简洁文本
        if rss_entry.title:
            message_parts.append(f"📰 {rss_entry.title}")
        if rss_entry.author:
            message_parts.append(f"👤 {rss_entry.author}")
        if rss_entry.published:
            message_parts.append(f"⏰ {rss_entry.published}")
        if rss_entry.link:
            message_parts.append(f"🔗 [查看原文]({rss_entry.link})")
    else:
        # 文本模式：完整内容
        if rss_entry.title:
            message_parts.append(f"📰 **{rss_entry.title}**")

        if rss_entry.description:
            description = rss_entry.description[:500] + "..." if len(rss_entry.description) > 500 else rss_entry.description
            message_parts.append(f"\n{description}")

        if rss_entry.published:
            message_parts.append(f"\n⏰ {rss_entry.published}")
        if rss_entry.author:
            message_parts.append(f" | 👤 {rss_entry.author}")
        if rss_entry.link:
            message_parts.append(f"\n🔗 [查看原文]({rss_entry.link})")

    return "\n".join(message_parts)
```

#### 8.4.2 统一发送器算法
```python
async def send_message(bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]:
    """
    发送统一格式的Telegram消息

    算法：
    1. 根据消息类型选择发送方式
    2. 处理媒体组或文本消息
    3. 应用发送策略和容错机制
    4. 返回标准化的消息结果

    Returns:
        List[Message]: 发送的消息列表
    """
    try:
        if message.media_group:
            # 媒体组发送
            return await send_media_group(bot, chat_id, message)
        else:
            # 文本消息发送
            sent_message = await send_text_message(bot, chat_id, message)
            return [sent_message]
    except Exception as e:
        logging.error(f"统一发送器发送失败: {str(e)}", exc_info=True)
        raise

async def send_media_group(bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]:
    """
    发送媒体组消息（复用RSS模块的媒体策略）

    算法：
    1. 构建InputMedia列表
    2. 应用分批发送策略（每批最多10个）
    3. 使用URL直接发送，失败时降级到下载发送
    4. 返回所有批次的消息列表
    """
    # 构建Telegram媒体组
    telegram_media = []
    for i, media_item in enumerate(message.media_group):
        if media_item.type == "photo":
            telegram_media.append(InputMediaPhoto(
                media=media_item.url,
                caption=media_item.caption if i == 0 else None,
                parse_mode=message.parse_mode
            ))
        elif media_item.type == "video":
            telegram_media.append(InputMediaVideo(
                media=media_item.url,
                caption=media_item.caption if i == 0 else None,
                parse_mode=message.parse_mode
            ))

    # 分批发送（复用RSS模块的分批策略）
    batch_sizes = calculate_balanced_batches(len(telegram_media), max_per_batch=10)
    all_messages = []

    media_index = 0
    for batch_num, batch_size in enumerate(batch_sizes, 1):
        batch_media = telegram_media[media_index:media_index + batch_size]

        try:
            # 发送当前批次
            messages = await bot.send_media_group(chat_id=chat_id, media=batch_media)
            all_messages.extend(messages)
            logging.info(f"媒体组批次 {batch_num}/{len(batch_sizes)} 发送成功")

            # 批次间隔
            if batch_num < len(batch_sizes):
                await asyncio.sleep(3)

        except Exception as e:
            logging.error(f"媒体组批次 {batch_num} 发送失败: {str(e)}", exc_info=True)
            # 可以在这里实现降级策略
            continue

        media_index += batch_size

    return all_messages

async def send_text_message(bot: Bot, chat_id: str, message: TelegramMessage) -> Message:
    """发送文本消息"""
    return await bot.send_message(
        chat_id=chat_id,
        text=message.text,
        parse_mode=message.parse_mode,
        disable_web_page_preview=message.disable_web_page_preview,
        reply_markup=message.reply_markup
    )
```

---

## 总结

RSSHub模块设计充分借鉴了douyin模块的成功经验，特别是其高效的多频道转发机制和智能的历史对齐功能。通过适配RSS/Atom XML数据格式，RSSHub模块将为用户提供与douyin模块相同水平的订阅体验。

**核心优势**:
1. **统一消息架构**: 创新性地定义了跨模块的统一Telegram消息实体，实现真正的组件复用
2. **最大化复用**: 完全复用douyin模块的Sender、Alignment组件和数据结构
3. **高效转发**: 复用douyin的角色分工转发机制，显著减少API调用和带宽使用
4. **智能对齐**: 复用douyin的历史对齐逻辑，确保内容完整性
5. **架构一致**: 与douyin模块保持完全一致的架构设计，便于维护和扩展

**复用策略**:
1. **统一消息层**: TelegramMessage实体作为所有模块的标准输出格式
2. **数据结构复用**: Subscription、MessageMapping、KnownContent完全复用douyin的设计
3. **组件复用**: Sender、Alignment模块通过统一消息层实现跨模块复用
4. **转换器模式**: 每个数据源只需实现MessageConverter接口即可接入统一发送体系
5. **RSS专用**: 仅Parser模块和RSSEntry实体为RSS数据源特定实现

**技术特点**:
1. **统一消息标准**: 定义跨模块的TelegramMessage实体，实现真正的组件标准化
2. **实时获取策略**: 每次检查都从RSS源实时获取数据，确保数据最新性
3. **存储最小化**: 只存储必要的去重信息（known_item_ids.json），大幅减少存储开销
4. **架构一致性**: 与douyin模块保持完全一致的数据流向和处理逻辑
5. **格式兼容**: 支持RSS 2.0和Atom 1.0格式，提供良好的兼容性
6. **媒体支持**: 完整支持RSS媒体附件（enclosure）的处理和推送
7. **扩展性强**: 新增数据源只需实现转换器接口，无需重复开发发送逻辑

该设计文档为RSSHub模块的开发提供了完整的技术指导，确保模块能够成功集成到现有系统中，为用户提供优质的RSSHub订阅服务。