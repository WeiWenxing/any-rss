"""
RSS服务模块

提供RSS/Feed订阅管理、消息发送、状态管理和定时任务调度功能
"""

from .manager import RSSManager
from .commands import register_commands, send_update_notification
from .entry_processor import extract_entry_info, send_entry_unified, process_and_send_entry
from .message_sender import (
    extract_and_clean_media,
    send_media_groups_with_caption,
    send_text_message,
    calculate_balanced_batches,
    MediaAccessError
)
from .media_strategy import (
    MediaSendStrategy,
    MediaSendResult,
    MediaInfo,
    MediaSendStrategyManager,
    MediaSender,
    create_media_strategy_manager
)
from .state_manager import FeedStateManager
from .scheduler import RSSScheduler, run_scheduled_check
from .config import get_config, update_config, rss_config
from .network_utils import get_network_manager, network_manager

__all__ = [
    # 管理器
    'RSSManager',
    'FeedStateManager',
    'RSSScheduler',

    # 命令处理
    'register_commands',
    'send_update_notification',

    # 条目处理
    'extract_entry_info',
    'send_entry_unified',
    'process_and_send_entry',

    # 消息发送
    'extract_and_clean_media',
    'send_media_groups_with_caption',
    'send_text_message',
    'calculate_balanced_batches',
    'MediaAccessError',

    # 媒体策略
    'MediaSendStrategy',
    'MediaSendResult',
    'MediaInfo',
    'MediaSendStrategyManager',
    'MediaSender',
    'create_media_strategy_manager',

    # 配置管理
    'get_config',
    'update_config',
    'rss_config',

    # 网络工具
    'get_network_manager',
    'network_manager',

    # 定时任务
    'run_scheduled_check'
]