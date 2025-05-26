# 抖音模块多频道转发实现计划

## 实现状态

### ✅ 已完成
- 数据结构重构：`{url: [channel1, channel2]}`
- check_updates支持多频道
- scheduler框架搭建
- 命令层适配

### 🚧 待实现
- 消息ID存储机制
- 实际转发逻辑
- 历史对齐转发

## 实现步骤

### 第五步：消息ID存储机制

#### 修改_send_notification_safe返回消息ID

**文件**：`services/douyin/scheduler.py`

```python
async def _send_notification_safe(
    self, bot: Bot, content_info: dict, douyin_url: str, target_chat_id: str
) -> Tuple[bool, Optional[int]]:
    """
    安全地发送通知，返回发送结果和消息ID
    
    Returns:
        Tuple[bool, Optional[int]]: (是否发送成功, 消息ID)
    """
    try:
        message = await send_douyin_content(bot, content_info, douyin_url, target_chat_id)
        
        if hasattr(message, 'message_id'):
            return True, message.message_id
        elif isinstance(message, list) and len(message) > 0:
            return True, message[0].message_id
        else:
            return True, None
    except Exception as e:
        logging.error(f"发送抖音通知失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
        return False, None
```

#### 修改sender.py返回消息对象

**文件**：`services/douyin/sender.py`

关键修改：
- `_send_video_content`：返回发送的消息对象
- `_send_images_content`：返回发送的消息列表
- `send_douyin_content`：返回实际的消息对象

#### 存储消息ID

```python
# 在_process_batch_with_forwarding中
send_success, message_id = await self._send_notification_safe(
    bot, content_info, douyin_url, primary_channel
)

if send_success and message_id:
    item_id = self.douyin_manager.fetcher.generate_content_id(content_info)
    self.douyin_manager.save_message_id(douyin_url, item_id, primary_channel, message_id)
```

### 第六步：实际转发逻辑

#### 实施bot.forward_message

**文件**：`services/douyin/scheduler.py`

```python
# 转发到其他频道
for secondary_channel in secondary_channels:
    try:
        primary_message_id = self.douyin_manager.get_message_id(douyin_url, item_id, primary_channel)
        
        if primary_message_id:
            forwarded_message = await bot.forward_message(
                chat_id=secondary_channel,
                from_chat_id=primary_channel,
                message_id=primary_message_id
            )
            
            if hasattr(forwarded_message, 'message_id'):
                self.douyin_manager.save_message_id(
                    douyin_url, item_id, secondary_channel, forwarded_message.message_id
                )
            
            logging.info(f"✅ 转发成功: {item_id} 从 {primary_channel} 到 {secondary_channel}")
        else:
            raise Exception("无法获取主频道消息ID")
            
    except Exception as e:
        logging.error(f"转发失败，降级为直接发送: {secondary_channel}, 错误: {str(e)}")
        # 降级为直接发送
        fallback_success, fallback_message_id = await self._send_notification_safe(
            bot, content_info, douyin_url, secondary_channel
        )
        
        if fallback_success and fallback_message_id:
            self.douyin_manager.save_message_id(
                douyin_url, item_id, secondary_channel, fallback_message_id
            )
```

#### 图片组处理

MediaGroup无法直接转发，检测到图片组时自动降级为直接发送。

### 第七步：历史对齐转发

#### 修改add_subscription

**文件**：`services/douyin/commands.py`

```python
# 处理历史对齐
if isinstance(content_info, dict) and content_info.get("need_alignment"):
    known_item_ids = content_info.get("known_item_ids", [])
    primary_channel = content_info.get("primary_channel")
    new_channel = content_info.get("new_channel")

    await update.message.reply_text(
        f"✅ 成功添加抖音订阅：{douyin_url}\n"
        f"📺 目标频道：{target_chat_id}\n"
        f"🔄 正在进行历史对齐，从主频道 {primary_channel} 转发 {len(known_item_ids)} 个历史内容..."
    )

    alignment_success = await perform_historical_alignment(
        context.bot, douyin_url, known_item_ids, primary_channel, new_channel
    )
    
    if alignment_success:
        await update.message.reply_text(f"🎉 历史对齐完成！成功转发 {len(known_item_ids)} 个历史内容")
    else:
        await update.message.reply_text(f"⚠️ 历史对齐部分失败，尝试转发 {len(known_item_ids)} 个历史内容")
```

#### 实现历史对齐函数

**新增文件**：`services/douyin/alignment.py`

```python
async def perform_historical_alignment(
    bot: Bot, douyin_url: str, known_item_ids: List[str], 
    primary_channel: str, new_channel: str
) -> bool:
    """执行历史对齐转发"""
    success_count = 0
    
    for item_id in known_item_ids:
        try:
            primary_message_id = douyin_manager.get_message_id(douyin_url, item_id, primary_channel)
            
            if primary_message_id:
                forwarded_message = await bot.forward_message(
                    chat_id=new_channel,
                    from_chat_id=primary_channel,
                    message_id=primary_message_id
                )
                
                if hasattr(forwarded_message, 'message_id'):
                    douyin_manager.save_message_id(
                        douyin_url, item_id, new_channel, forwarded_message.message_id
                    )
                
                success_count += 1
                logging.info(f"历史对齐转发成功: {item_id}")
                await asyncio.sleep(1)  # 避免flood control
            else:
                logging.warning(f"无法获取历史内容的消息ID: {item_id}")
                
        except Exception as e:
            logging.error(f"历史对齐转发失败: {item_id}, 错误: {str(e)}")
            continue
    
    logging.info(f"历史对齐完成: {success_count}/{len(known_item_ids)} 成功")
    return success_count == len(known_item_ids)
```

## 实现优先级

### 高优先级
1. **第五步**：消息ID存储机制
2. **第六步**：实际转发逻辑

### 中优先级
3. **第七步**：历史对齐转发

### 低优先级
4. 图片组转发优化
5. 主频道故障切换
6. 性能监控

## 技术要点

### Telegram API限制
- 转发间隔1秒避免flood control
- 图片组降级为直接发送
- 转发失败自动降级

### 容错处理
- 消息ID失效时跳过该内容
- 网络异常时重试机制
- 主频道不可用时切换逻辑

### 性能优化
- 批量处理减少API调用
- 消息ID缓存减少文件读写
- 智能分批避免限制

## 测试计划

### 功能测试
1. 首次订阅收到所有历史内容
2. 多频道订阅历史对齐
3. 新内容转发机制
4. 转发失败降级

### 异常测试
1. 网络异常重试
2. 主频道不可用切换
3. 消息ID失效处理
4. API限制处理

### 性能测试
1. 大量频道转发性能
2. 大量内容处理时间
3. 并发订阅处理能力 