# 📋 媒体发送策略系统

## 🎯 策略概述

新的媒体发送策略系统实现了明确的三层降级机制，确保媒体文件能够可靠发送：

### 策略优先级

1. **URL直接发送** (`url_direct`)
   - 适用于：小于阈值的文件
   - 优点：速度快，不占用本地存储
   - 阈值：本地API=500MB，官方API=50MB

2. **下载后上传** (`download_upload`)
   - 适用于：大文件或URL发送失败的文件
   - 优点：可靠性高，支持大文件
   - 缺点：需要下载时间和临时存储

3. **文本降级** (`text_fallback`)
   - 适用于：无法访问的媒体文件
   - 行为：抛出`MediaAccessError`异常，由调用方处理

## 🏗️ 架构设计

### 核心类

#### `MediaSendStrategy` (枚举)
```python
URL_DIRECT = "url_direct"           # 直接URL发送
DOWNLOAD_UPLOAD = "download_upload" # 下载后上传
TEXT_FALLBACK = "text_fallback"     # 降级到文本
```

#### `MediaInfo` (数据类)
```python
class MediaInfo:
    url: str                    # 媒体URL
    media_type: str            # 'image' 或 'video'
    size_mb: float             # 文件大小(MB)
    accessible: bool           # 是否可访问
    local_path: Optional[str]  # 本地文件路径
    send_strategy: Optional[MediaSendStrategy]  # 发送策略
```

#### `MediaSendStrategyManager` (策略管理器)
- 分析媒体文件，确定发送策略
- 检查文件可访问性和大小
- 根据API类型调整大文件阈值

#### `MediaSender` (媒体发送器)
- 执行具体的发送逻辑
- 处理策略降级
- 管理临时文件清理

## 🔄 工作流程

### 1. 媒体分析阶段
```python
# 创建策略管理器
strategy_manager, media_sender = create_media_strategy_manager(bot)

# 分析媒体文件
analyzed_media = strategy_manager.analyze_media_files(media_list)
```

**分析过程：**
1. 检查每个媒体文件的可访问性（HEAD请求）
2. 获取文件大小信息
3. 根据大小和API类型确定发送策略
4. 记录详细的分析日志

### 2. 策略决策逻辑
```python
def _determine_send_strategy(self, media_info: MediaInfo) -> MediaSendStrategy:
    # 文件无法访问 → 文本降级
    if not media_info.accessible:
        return MediaSendStrategy.TEXT_FALLBACK
    
    # 文件过大 → 下载上传
    if media_info.size_mb > self.large_file_threshold_mb:
        return MediaSendStrategy.DOWNLOAD_UPLOAD
    
    # 默认 → URL直接发送
    return MediaSendStrategy.URL_DIRECT
```

### 3. 发送执行阶段
```python
success = await media_sender.send_media_group_with_strategy(
    chat_id=chat_id,
    media_list=analyzed_media,
    caption=caption
)
```

**执行流程：**
1. 按策略分组媒体文件
2. 先尝试URL直接发送
3. 失败时自动降级到下载上传
4. 清理临时文件

## 📊 策略决策表

| 文件状态 | 文件大小 | API类型 | 策略选择 | 说明 |
|---------|---------|---------|----------|------|
| 无法访问 | - | - | `text_fallback` | 抛出异常 |
| 可访问 | ≤50MB | 官方API | `url_direct` | 直接发送 |
| 可访问 | >50MB | 官方API | `download_upload` | 下载上传 |
| 可访问 | ≤500MB | 本地API | `url_direct` | 直接发送 |
| 可访问 | >500MB | 本地API | `download_upload` | 下载上传 |

## 🔧 配置说明

### API类型检测
```python
def create_media_strategy_manager(bot: Bot):
    # 自动检测是否使用本地API
    use_local_api = False
    if hasattr(bot, '_base_url') and bot._base_url:
        use_local_api = "localhost" in bot._base_url or "127.0.0.1" in bot._base_url
    
    return MediaSendStrategyManager(use_local_api=use_local_api)
```

### 大文件阈值
- **本地API**: 500MB（支持2GB，保留安全边际）
- **官方API**: 50MB（官方限制）

## 🚀 使用示例

### 基本使用
```python
from services.rss.media_strategy import create_media_strategy_manager

# 创建策略系统
strategy_manager, media_sender = create_media_strategy_manager(bot)

# 媒体列表
media_list = [
    {'url': 'https://example.com/image.jpg', 'type': 'image'},
    {'url': 'https://example.com/video.mp4', 'type': 'video'}
]

# 分析和发送
analyzed_media = strategy_manager.analyze_media_files(media_list)
success = await media_sender.send_media_group_with_strategy(
    chat_id=chat_id,
    media_list=analyzed_media,
    caption="测试发送"
)
```

### 集成到现有代码
```python
# 在 message_sender.py 中
async def send_media_groups_with_caption(bot, chat_id, title, author, media_list, full_caption=None):
    # 使用新的策略系统
    strategy_manager, media_sender = create_media_strategy_manager(bot)
    analyzed_media = strategy_manager.analyze_media_files(media_list)
    
    # 发送媒体
    success = await media_sender.send_media_group_with_strategy(
        chat_id=chat_id,
        media_list=analyzed_media,
        caption=caption
    )
```

## 🧪 测试命令

使用 `/debug_media_strategy` 命令测试策略系统：

```bash
/debug_media_strategy
```

**测试内容：**
- 分析不同大小的测试媒体文件
- 显示策略决策结果
- 执行实际发送测试
- 验证降级机制

## 📈 优势特点

### 1. 明确的策略机制
- 清晰的三层降级策略
- 详细的决策日志
- 可预测的行为

### 2. 智能文件分析
- 预先检查文件可访问性
- 获取准确的文件大小
- 避免无效发送尝试

### 3. 自动API适配
- 自动检测本地/官方API
- 动态调整大文件阈值
- 充分利用本地API优势

### 4. 可靠的错误处理
- 自动策略降级
- 详细的错误日志
- 临时文件自动清理

### 5. 向后兼容
- 保持现有接口不变
- 无缝集成到现有代码
- 渐进式升级

## 🔍 日志示例

```
📋 媒体发送策略管理器初始化: 本地API=True, 大文件阈值=500MB
🔍 开始分析 3 个媒体文件...
   📁 image1: 2.1MB → 策略: url_direct
   📁 video1: 101.5MB → 策略: download_upload
   ❌ image2: 无法访问 (HTTP 404) → 策略: text_fallback
🚀 开始发送媒体组: 2 个文件
📡 尝试URL直接发送 1 个媒体文件
✅ URL直接发送成功: 1 个文件
📥 开始下载 1 个媒体文件...
📥 下载文件 1/1: https://example.com/large_video.mp4
✅ 文件 1 下载成功
📤 开始上传 1 个文件...
✅ 下载上传发送成功: 1 个文件
🗑️ 清理临时文件: /tmp/telegram_media_12345.mp4
🎉 所有 2 批媒体组发送成功！
```

## 🛠️ 扩展性

### 未来优化方向

1. **并发下载**
   - 支持多文件并行下载
   - 提高大文件处理效率

2. **智能缓存**
   - 缓存已下载的文件
   - 避免重复下载

3. **更多策略**
   - 压缩策略（自动压缩大文件）
   - 分片策略（超大文件分片发送）

4. **性能监控**
   - 策略成功率统计
   - 发送时间监控
   - 自动策略优化

这个媒体策略系统为RSS机器人提供了强大而灵活的媒体发送能力，确保各种大小的媒体文件都能可靠发送。 