# 抖音模块多频道高效转发设计

## 核心设计

### 设计目标
1. 支持一个URL订阅到多个频道
2. 保证每个频道收到完整内容
3. 高效转发机制节省资源
4. 向后兼容现有订阅

### 核心机制
**主频道发送 + 其他频道转发**：
- 全局维护一份known_items（按URL）
- 新频道订阅时从主频道转发历史内容
- 新内容发送到主频道，转发到其他频道

## 数据结构

### 订阅格式
```json
{
  "https://v.douyin.com/xxx": ["@channel1", "@channel2", "@channel3"]
}
```

### 消息ID存储
```json
{
  "https://v.douyin.com/xxx": {
    "item_123": {
      "@channel1": 456,  // 主频道消息ID
      "@channel2": 789,  // 转发消息ID
      "@channel3": 101   // 转发消息ID
    }
  }
}
```

### 已知内容
```json
{
  "https://v.douyin.com/xxx": ["item_1", "item_2", "item_3"]
}
```

## 核心流程

### 订阅添加
1. **首次订阅**：获取历史内容 → 发送到频道 → 更新known_items
2. **多频道订阅**：添加频道 → 从主频道转发历史内容 → 立即对齐

### 定时检查
1. 遍历所有URL（不是频道）
2. 检查新内容
3. 发送到主频道，获取消息ID
4. 转发到其他频道
5. 更新known_items

### 转发降级
转发失败 → 自动降级为直接发送

## 实现架构

### Manager层
- `add_subscription`：支持多频道和历史对齐检测
- `check_updates`：返回包含频道信息的新内容
- `save_message_id/get_message_id`：消息ID存储

### Scheduler层
- `process_multi_channel_subscription`：多频道处理
- `_process_batch_with_forwarding`：高效转发
- 发送间隔控制

### Commands层
- 适配多频道格式
- 历史对齐处理

## 关键方法

### check_updates
```python
def check_updates(self, douyin_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
    """
    1. 获取当前所有内容
    2. 与known_items比对找出新内容
    3. 为新内容添加target_channels信息
    4. 返回新内容列表
    """
```

### _process_batch_with_forwarding
```python
async def _process_batch_with_forwarding(self, bot, new_items, douyin_url, target_channels):
    """
    1. 选择主频道（第一个）
    2. 发送到主频道，获取消息ID
    3. 转发到其他频道
    4. 转发失败时降级为直接发送
    5. 统一标记为已发送
    """
```

## 实现状态

### ✅ 已完成
- 数据结构重构为简单数组格式
- 兼容旧格式自动转换
- check_updates支持多频道
- scheduler按URL遍历
- 高效转发框架搭建
- 命令层适配

### 🚧 待实现
- 修改sender返回消息ID
- 实施bot.forward_message调用
- 历史对齐转发逻辑

## 实现步骤

### 第五步：消息ID存储
1. 修改`_send_notification_safe`返回消息ID
2. 修改`sender.py`返回消息对象
3. 调用`save_message_id`存储

### 第六步：转发逻辑
1. 实施`bot.forward_message`
2. 转发失败降级处理
3. 存储转发消息ID

### 第七步：历史对齐
1. 新频道订阅时检测需要对齐
2. 从主频道批量转发历史内容
3. 对齐完成反馈

## 技术要点

### 图片组处理
MediaGroup无法直接转发，需要降级为直接发送

### 限流控制
转发间隔1秒，避免Telegram API限制

### 容错机制
消息ID失效时跳过该内容，继续处理其他内容

## 优势

- **内容完整性**：每个频道都能收到所有内容
- **高效率**：1次发送+N次转发
- **简单维护**：全局一份known_items
- **自动对齐**：新频道自动获得历史内容 