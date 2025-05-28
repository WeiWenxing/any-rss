# 📋 媒体发送策略系统

## 🎯 策略概述

全新简化的媒体发送策略系统，对整个媒体组采用统一策略，避免复杂的单项分析：

### 三层统一策略

1. **全部URL直接发送** (`url_direct`)
   - 所有媒体（图片+视频）都用URL直接发送
   - 优点：速度最快，零额外开销

2. **视频下载混合发送** (`video_download_mix`)
   - 仅当策略1失败且有视频时执行
   - 视频：下载到本地后上传
   - 图片：仍用URL直接发送
   - 优点：针对性解决视频URL问题

3. **文本降级** (`text_fallback`)
   - 当前面策略都失败时触发
   - 抛出`MediaAccessError`异常，由调用方处理

### 策略决策逻辑

```
媒体组 → 策略1: 全部URL直接
       ↓ (失败)
       → 有视频? → 是 → 策略2: 视频下载+图片URL
                 → 否 → 策略3: 文本降级
       ↓ (失败)
       → 策略3: 文本降级
```

## 🏗️ 架构设计

### 核心类

#### `MediaSendStrategy` (枚举)
```python
URL_DIRECT = "url_direct"                    # 全部URL直接发送
VIDEO_DOWNLOAD_MIX = "video_download_mix"    # 视频下载+图片URL混合
TEXT_FALLBACK = "text_fallback"              # 降级到文本
```

#### `MediaInfo` (数据类)
```python
class MediaInfo:
    url: str                    # 媒体URL
    media_type: str            # 'image' 或 'video'
    poster_url: Optional[str]  # 视频封面图URL（仅对视频有效）
    local_path: Optional[str]  # 本地文件路径
    local_poster_path: Optional[str]  # 本地封面图路径
```

#### `MediaSendStrategyManager` (策略管理器)
- 分析媒体组，转换为MediaInfo对象
- 检查媒体组是否包含视频
- 无复杂策略分析，直接统一处理

#### `MediaSender` (媒体发送器)
- 执行三层统一策略
- 自动策略降级
- 管理临时文件清理

## 🔄 工作流程

### 1. 媒体分析阶段
```python
# 创建策略管理器
strategy_manager, media_sender = create_media_strategy_manager(bot)

# 分析媒体组（无策略决策，仅转换格式）
analyzed_media = strategy_manager.analyze_media_files(media_list)
```

**分析过程：**
1. 转换为MediaInfo对象
2. 统计媒体类型（图片/视频数量）
3. 无策略分析，零开销

### 2. 统一策略执行
```python
try:
    success = await media_sender.send_media_group_with_strategy(
        chat_id=chat_id,
        media_list=analyzed_media,
        caption=caption,
        parse_mode=parse_mode
    )
except MediaAccessError:
    # 处理文本降级
    await send_text_message(chat_id, text_content)
```

**执行流程：**
1. **策略1**：全部URL直接发送
2. **策略2**：失败且有视频 → 视频下载+图片URL混合
3. **策略3**：再失败 → 抛出异常，文本降级

### 3. 策略降级机制
- **无视频媒体组**：策略1失败直接跳到策略3
- **有视频媒体组**：策略1 → 策略2 → 策略3
- **异常处理**：抛出`MediaAccessError`，由调用方处理

## 📊 策略决策表

| 媒体组类型 | 策略1 | 策略2 | 策略3 | 说明 |
|-----------|-------|-------|-------|------|
| 纯图片组 | 全部URL | - | 文本降级 | 图片失败直接文本 |
| 纯视频组 | 全部URL | 视频下载 | 文本降级 | 视频三层完整降级 |
| 混合组 | 全部URL | 视频下载+图片URL | 文本降级 | 混合策略处理 |

## 🔧 配置说明

### 策略简化优势
- **统一处理**：整个媒体组采用相同策略
- **逻辑清晰**：三层线性降级，易于理解
- **性能优化**：无单项分析开销
- **针对性强**：视频下载混合策略专门解决视频URL问题

### 降级触发条件
- **策略1失败**：任何Telegram API错误
- **策略2触发**：策略1失败 + 媒体组包含视频
- **策略3触发**：前面策略都失败

## 🚀 使用示例

### 基本使用
```python
from services.common.media_strategy import create_media_strategy_manager, MediaAccessError

# 创建策略系统
strategy_manager, media_sender = create_media_strategy_manager(bot)

# 媒体列表
media_list = [
    {'url': 'https://example.com/image.jpg', 'type': 'image'},
    {'url': 'https://example.com/video.mp4', 'type': 'video'}
]

# 分析媒体组
analyzed_media = strategy_manager.analyze_media_files(media_list)

# 发送媒体组（自动三层策略）
try:
    messages = await media_sender.send_media_group_with_strategy(
        chat_id=chat_id,
        media_list=analyzed_media,
        caption="测试发送",
        parse_mode="Markdown"
    )
    print(f"✅ 媒体发送成功: {len(messages)} 条消息")
except MediaAccessError:
    # 所有媒体策略都失败，发送文本
    await bot.send_message(
        chat_id=chat_id,
        text="📝 媒体发送失败，以下是文本内容：\n\n测试发送",
        parse_mode="Markdown"
    )
```

### 错误处理
```python
try:
    messages = await media_sender.send_media_group_with_strategy(
        chat_id=chat_id,
        media_list=analyzed_media,
        caption=caption
    )
except MediaAccessError as e:
    logging.warning(f"媒体发送失败，降级到文本: {str(e)}")
    # 调用方处理文本发送
    await handle_text_fallback(chat_id, text_content)
```

## 📈 优势特点

### 1. 极简的策略机制
- 三层线性策略，逻辑清晰
- 无复杂分析，直接执行
- 统一处理整个媒体组

### 2. 高效的性能表现
- 零策略分析开销
- 无不必要的HTTP检查
- 最优路径优先执行

### 3. 智能的降级设计
- 针对性视频处理
- 无视频组快速降级
- 异常驱动的文本降级

### 4. 可靠的错误处理
- 清晰的异常边界
- 自动临时文件清理
- 详细的日志记录

### 5. 简洁的接口设计
- 统一的调用方式
- 明确的异常契约
- 向后兼容保证

## 🔍 日志示例

### 成功场景（策略1）
```
📋 媒体发送策略管理器初始化: 媒体组统一策略模式
🔍 分析媒体组: 3 个文件
   📊 媒体组成: 2 张图片, 1 个视频
🚀 开始发送媒体组: 3 个文件
📡 策略1: 尝试全部URL直接发送
✅ 策略1成功: 全部URL直接发送完成
```

### 降级场景（策略1→策略2）
```
🚀 开始发送媒体组: 3 个文件
📡 策略1: 尝试全部URL直接发送
⚠️ 策略1失败: HTTP 403 Forbidden
📥 策略2: 尝试视频下载+图片URL混合发送
📥 开始下载 1 个视频文件...
📥 下载视频 1/1: https://example.com/video.mp4
✅ 视频 1 下载成功
📤 开始发送混合媒体组...
✅ 策略2成功: 视频下载混合发送完成
🗑️ 清理临时文件: /tmp/telegram_media_12345.mp4
```

### 完全失败场景（策略1→策略3）
```
🚀 开始发送媒体组: 2 个文件
📡 策略1: 尝试全部URL直接发送
⚠️ 策略1失败: HTTP 403 Forbidden
📝 跳过策略2: 媒体组无视频，直接降级到文本
❌ 所有媒体发送策略都失败，触发文本降级
```

## 🛠️ 扩展性

### 未来优化方向

1. **并发处理**
   - 视频并行下载
   - 异步文件处理

2. **智能缓存**
   - 视频文件缓存
   - 避免重复下载

3. **更多策略**
   - 压缩策略（自动压缩大文件）
   - 分片策略（超大文件分片发送）

4. **性能监控**
   - 策略成功率统计
   - 发送时间监控
   - 自动策略优化

这个简化的媒体策略系统为RSS机器人提供了清晰而高效的媒体发送能力，通过统一的媒体组策略避免了复杂的单项分析，确保各种媒体文件都能可靠发送。