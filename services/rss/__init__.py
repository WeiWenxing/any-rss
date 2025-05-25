"""
RSS服务模块

提供RSS/Feed订阅管理、消息发送和命令处理功能
"""

from .manager import RSSManager
from .commands import register_commands, send_update_notification
from .entry_processor import extract_entry_info, send_entry_unified, process_and_send_entry
from .message_sender import (
    extract_and_clean_images,
    send_image_groups_with_caption,
    send_text_message,
    calculate_balanced_batches
)

__all__ = [
    # 管理器
    'RSSManager',

    # 命令处理
    'register_commands',
    'send_update_notification',

    # 条目处理
    'extract_entry_info',
    'send_entry_unified',
    'process_and_send_entry',

    # 消息发送
    'extract_and_clean_images',
    'send_image_groups_with_caption',
    'send_text_message',
    'calculate_balanced_batches'
]