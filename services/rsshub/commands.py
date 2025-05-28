"""
RSSHub命令处理器模块

该模块负责处理所有RSSHub相关的Telegram命令，完全复用douyin模块的命令处理逻辑。
支持RSS订阅的添加、删除和查看功能，提供统一的用户反馈体验。

主要功能：
1. /rsshub_add - 添加RSS订阅（包含完整的反馈流程）
2. /rsshub_del - 删除RSS订阅
3. /rsshub_list - 查看订阅列表
4. RSS URL验证和格式化
5. 统一的错误处理和用户反馈

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from .manager import RSSHubManager, create_rsshub_manager
from .rss_parser import RSSParser, create_rss_parser
from services.common.unified_commands import UnifiedCommandHandler


class RSSHubCommandHandler(UnifiedCommandHandler):
    """
    RSSHub命令处理器

    继承统一命令处理器基类，完全复用douyin模块的命令处理逻辑
    """

    def __init__(self, data_dir: str = "storage/rsshub"):
        """
        初始化RSSHub命令处理器

        Args:
            data_dir: 数据存储目录
        """
        # 创建RSSHub管理器
        rsshub_manager = create_rsshub_manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name="rsshub", manager=rsshub_manager)

        # 初始化RSS特定组件
        self.rss_parser = create_rss_parser()

        self.logger.info("RSSHub命令处理器初始化完成")

    # ==================== 实现UnifiedCommandHandler抽象接口 ====================

    def validate_source_url(self, source_url: str) -> Tuple[bool, str]:
        """
        验证RSS URL格式

        Args:
            source_url: RSS源URL

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not source_url:
            return False, "RSS URL不能为空"

        try:
            # 基础URL格式验证
            parsed = urlparse(source_url)
            if not parsed.scheme or not parsed.netloc:
                return False, "RSS URL格式错误，缺少协议或域名"

            # 检查协议
            if parsed.scheme not in ['http', 'https']:
                return False, "RSS URL必须使用HTTP或HTTPS协议"

            return True, ""

        except Exception as e:
            return False, f"RSS URL验证失败: {str(e)}"

    def normalize_source_url(self, source_url: str) -> str:
        """
        标准化RSS URL

        Args:
            source_url: 原始URL

        Returns:
            str: 标准化后的URL
        """
        # RSS URL一般不需要特殊标准化，直接返回
        return source_url.strip()

    def get_source_display_name(self, source_url: str) -> str:
        """
        获取RSS源的显示名称

        Args:
            source_url: RSS源URL

        Returns:
            str: 显示名称
        """
        try:
            # 尝试获取RSS源的标题
            feed_info = self.rss_parser.get_feed_info(source_url)
            title = feed_info.get('title', '')
            if title:
                return f"{title} ({source_url})"
            else:
                return source_url
        except Exception:
            return source_url

    # ==================== 重写UnifiedCommandHandler的可选方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于用户反馈）

        Returns:
            str: 模块显示名称
        """
        return "RSS"

    async def perform_additional_validation(self, source_url: str, chat_id: str) -> Tuple[bool, str]:
        """
        执行额外的RSS验证

        Args:
            source_url: RSS源URL
            chat_id: 频道ID

        Returns:
            Tuple[bool, str]: (是否通过, 错误信息)
        """
        try:
            self.logger.info(f"🔍 开始RSS源有效性验证: {source_url}")

            # 验证RSS源有效性
            is_valid = self.rss_parser.validate_rss_url(source_url)
            if not is_valid:
                self.logger.error(f"❌ RSS源验证失败: 源无效或无法访问 - {source_url}")
                return False, "RSS源无效或无法访问"

            self.logger.info(f"✅ RSS源验证通过: {source_url}")
            return True, ""
        except Exception as e:
            self.logger.error(f"💥 RSS源验证异常: {source_url}, 错误: {str(e)}", exc_info=True)
            return False, f"RSS源验证失败: {str(e)}"

    async def _add_first_channel_subscription(self, source_url: str, chat_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        添加首个频道订阅（RSS特定实现）

        Args:
            source_url: RSS源URL
            chat_id: 频道ID

        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 错误信息, 内容数据)
        """
        try:
            self.logger.info(f"🆕 开始添加首个频道订阅: {source_url} -> {chat_id}")

            # 获取RSS源信息
            try:
                self.logger.info(f"📡 获取RSS源信息: {source_url}")
                feed_info = self.rss_parser.get_feed_info(source_url)
                rss_title = feed_info.get('title', '')
                self.logger.info(f"📰 RSS源标题: {rss_title if rss_title else '无标题'}")
            except Exception as e:
                self.logger.warning(f"⚠️ 获取RSS源信息失败: {str(e)}")
                rss_title = ''

            # 添加订阅
            self.logger.info(f"💾 保存订阅配置到管理器")
            success = self.manager.add_subscription(source_url, chat_id, rss_title)
            if not success:
                self.logger.error(f"❌ 添加订阅失败: {source_url} -> {chat_id}")
                return False, "添加订阅失败", None

            self.logger.info(f"✅ 首个频道订阅添加成功: {source_url} -> {chat_id}")
            return True, "", {}

        except Exception as e:
            self.logger.error(f"💥 添加首个频道订阅异常: {source_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False, str(e), None

    async def _add_additional_channel_subscription(self, source_url: str, chat_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        添加额外频道订阅（需要历史对齐）

        Args:
            source_url: RSS源URL
            chat_id: 频道ID

        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 错误信息, 对齐信息)
        """
        try:
            self.logger.info(f"➕ 开始添加额外频道订阅: {source_url} -> {chat_id}")

            # 添加订阅
            self.logger.info(f"💾 保存订阅配置到管理器")
            success = self.manager.add_subscription(source_url, chat_id)
            if not success:
                self.logger.error(f"❌ 添加订阅失败: {source_url} -> {chat_id}")
                return False, "添加订阅失败", None

            # 获取已知内容列表（用于历史对齐）
            self.logger.info(f"📋 获取已知内容列表用于历史对齐")
            known_item_ids = self.manager.get_known_item_ids(source_url)
            self.logger.info(f"📊 已知内容统计: {len(known_item_ids)} 个条目")

            # 返回对齐信息
            alignment_info = {
                "need_alignment": True,
                "known_item_ids": known_item_ids,
                "new_channel": chat_id
            }

            self.logger.info(f"✅ 额外频道订阅添加成功，需要历史对齐: {source_url} -> {chat_id}")
            return True, "", alignment_info

        except Exception as e:
            self.logger.error(f"💥 添加额外频道订阅异常: {source_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False, str(e), None


    async def _remove_subscription(self, source_url: str, chat_id: str) -> bool:
        """
        删除RSS订阅

        Args:
            source_url: RSS源URL
            chat_id: 频道ID

        Returns:
            bool: 是否删除成功
        """
        try:
            self.logger.info(f"🗑️ 开始删除RSS订阅: {source_url} -> {chat_id}")

            result = self.manager.remove_subscription(source_url, chat_id)

            if result:
                self.logger.info(f"✅ RSS订阅删除成功: {source_url} -> {chat_id}")
            else:
                self.logger.warning(f"⚠️ RSS订阅删除失败（可能不存在）: {source_url} -> {chat_id}")

            return result
        except Exception as e:
            self.logger.error(f"💥 删除RSS订阅异常: {source_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False


# 全局实例
_rsshub_command_handler = None


def get_rsshub_command_handler(data_dir: str = "storage/rsshub") -> RSSHubCommandHandler:
    """
    获取RSSHub命令处理器实例（单例模式）

    Args:
        data_dir: 数据存储目录

    Returns:
        RSSHubCommandHandler: 命令处理器实例
    """
    global _rsshub_command_handler
    if _rsshub_command_handler is None:
        _rsshub_command_handler = RSSHubCommandHandler(data_dir)
    return _rsshub_command_handler


# ==================== Telegram命令处理函数 ====================

async def rsshub_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_add 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_rsshub_command_handler()
    await handler.handle_add_command(update, context)


async def rsshub_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_del 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_rsshub_command_handler()
    await handler.handle_remove_command(update, context)


async def rsshub_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_list 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_rsshub_command_handler()
    await handler.handle_list_command(update, context)


def register_rsshub_commands(application: Application) -> None:
    """
    注册RSSHub相关的命令处理器

    Args:
        application: Telegram应用实例
    """
    # 导入debug配置
    from core.config import debug_config

    # 注册基础命令
    application.add_handler(CommandHandler("rsshub_add", rsshub_add_command))
    application.add_handler(CommandHandler("rsshub_del", rsshub_del_command))
    application.add_handler(CommandHandler("rsshub_list", rsshub_list_command))

    # 根据debug模式决定是否注册调试命令
    if debug_config["enabled"]:
        # 注册调试命令
        from .debug_commands import register_rsshub_debug_commands
        register_rsshub_debug_commands(application)
        logging.info("✅ RSSHub调试命令已注册（DEBUG模式开启）")
    else:
        logging.info("ℹ️ RSSHub调试命令已跳过（DEBUG模式关闭）")

    logging.info("RSSHub命令处理器注册完成")