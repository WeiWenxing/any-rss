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
from typing import Dict, List
from urllib.parse import urlparse
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from .manager import RSSHubManager, create_rsshub_manager
from .rss_parser import RSSParser, create_rss_parser
from services.common.unified_sender import UnifiedTelegramSender


def validate_rss_url(url: str) -> bool:
    """
    验证RSS URL格式

    Args:
        url: RSS源URL

    Returns:
        bool: 是否为有效的RSS URL
    """
    if not url:
        return False

    try:
        # 基础URL格式验证
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False

        # 检查协议
        if parsed.scheme not in ['http', 'https']:
            return False

        return True

    except Exception:
        return False


def validate_chat_id(chat_id: str) -> bool:
    """
    验证频道ID格式

    Args:
        chat_id: 频道ID

    Returns:
        bool: 是否为有效的频道ID
    """
    if not chat_id:
        return False

    # 支持的格式：@channel_name, -1001234567890, 1234567890
    return (chat_id.startswith('@') or 
            chat_id.startswith('-') or 
            chat_id.isdigit())


def _check_subscription_status(rss_url: str, chat_id: str, manager: RSSHubManager) -> str:
    """
    检查订阅状态（完全复用douyin逻辑）

    Args:
        rss_url: RSS源URL
        chat_id: 频道ID
        manager: RSSHub管理器实例

    Returns:
        str: 订阅状态 ("duplicate", "additional_channel", "first_channel")
    """
    try:
        all_rss_urls = manager.get_all_rss_urls()

        if rss_url in all_rss_urls:
            channels = manager.get_subscription_channels(rss_url)
            if chat_id in channels:
                return "duplicate"  # 重复订阅
            else:
                return "additional_channel"  # 后续频道
        else:
            return "first_channel"  # 首个频道

    except Exception as e:
        logging.error(f"检查订阅状态失败: {str(e)}", exc_info=True)
        return "first_channel"  # 默认为首个频道


# 全局实例
rsshub_manager = create_rsshub_manager()
rss_parser = create_rss_parser()


async def rsshub_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_add 命令 - 完全复用douyin的统一反馈流程

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到RSSHUB_ADD命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    # 1. 参数验证
    if not context.args:
        logging.info("显示RSSHUB_ADD命令帮助信息")
        await update.message.reply_text(
            "📡 RSS订阅功能\n\n"
            "使用方法：\n"
            "/rsshub_add <RSS链接> <频道ID> - 添加RSS订阅\n"
            "/rsshub_del <RSS链接> <频道ID> - 删除RSS订阅\n"
            "/rsshub_list - 查看所有RSS订阅\n\n"
            "支持的RSS链接格式：\n"
            "• https://example.com/rss.xml\n"
            "• https://example.com/feed\n"
            "• https://example.com/atom.xml\n\n"
            "系统会自动监控并推送新内容到指定频道"
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ 参数不足\n"
            "请提供RSS链接和目标频道ID\n"
            "格式：/rsshub_add <RSS链接> <频道ID>\n\n"
            "例如：/rsshub_add https://example.com/rss.xml @my_channel"
        )
        return

    rss_url = context.args[0]
    target_chat_id = context.args[1]

    logging.info(f"执行rsshub_add命令，URL: {rss_url}, 目标频道: {target_chat_id}")

    # 验证RSS URL格式
    if not validate_rss_url(rss_url):
        await update.message.reply_text(_format_url_validation_error_message())
        return

    # 验证频道ID格式
    if not validate_chat_id(target_chat_id):
        await update.message.reply_text(_format_chat_id_validation_error_message())
        return

    # 2. 检查订阅状态
    subscription_status = _check_subscription_status(rss_url, target_chat_id, rsshub_manager)

    if subscription_status == "duplicate":
        # 重复订阅分支 - 直接返回
        await update.message.reply_text(_format_duplicate_subscription_message(rss_url, target_chat_id))
        return

    # 3. 立即反馈（非重复订阅才需要处理反馈）
    processing_message = await update.message.reply_text(_format_processing_message(rss_url, target_chat_id))

    # 4. 统一处理流程（首个频道和后续频道使用相同的用户反馈）
    try:
        # 验证RSS源有效性
        try:
            is_valid = rss_parser.validate_rss_url(rss_url)
            if not is_valid:
                await processing_message.edit_text(_format_error_message(rss_url, "RSS源无效或无法访问"))
                return
        except Exception as e:
            await processing_message.edit_text(_format_error_message(rss_url, f"RSS源验证失败: {str(e)}"))
            return

        # 获取RSS源信息
        try:
            feed_info = rss_parser.get_feed_info(rss_url)
            rss_title = feed_info.get('title', '')
        except Exception as e:
            logging.warning(f"获取RSS源信息失败: {str(e)}")
            rss_title = ''

        # 添加订阅
        success = rsshub_manager.add_subscription(rss_url, target_chat_id, rss_title)
        if not success:
            await processing_message.edit_text(_format_error_message(rss_url, "添加订阅失败"))
            return

        if subscription_status == "first_channel":
            # 首个频道：获取历史内容
            try:
                entries = rss_parser.parse_feed(rss_url)
                content_count = len(entries)

                # 保存已知条目ID（避免重复发送）
                if entries:
                    known_item_ids = [entry.item_id for entry in entries]
                    rsshub_manager.save_known_item_ids(rss_url, known_item_ids)

            except Exception as e:
                logging.warning(f"获取RSS历史内容失败: {str(e)}")
                content_count = 0

        else:
            # 后续频道：获取已知内容ID列表
            known_item_ids = rsshub_manager.get_known_item_ids(rss_url)
            content_count = len(known_item_ids)

        # 5. 进度反馈（统一格式）
        if content_count > 0:
            await processing_message.edit_text(_format_progress_message(rss_url, target_chat_id, content_count))

            # 6. 执行具体操作（用户无感知差异）
            if subscription_status == "first_channel":
                # 发送到频道
                sent_count = await _send_rss_content_batch(
                    context.bot, entries, rss_url, [target_chat_id]
                )
            else:
                # 历史对齐（用户看不到技术细节）
                from services.common.unified_alignment import perform_historical_alignment
                alignment_success = await perform_historical_alignment(
                    context.bot, rss_url, known_item_ids, target_chat_id, rsshub_manager
                )
                sent_count = len(known_item_ids) if alignment_success else 0

            # 7. 最终反馈（统一格式）
            await processing_message.edit_text(_format_final_success_message(rss_url, target_chat_id, sent_count))
        else:
            # 无内容的情况
            await processing_message.edit_text(_format_final_success_message(rss_url, target_chat_id, 0))

    except Exception as e:
        # 错误反馈
        logging.error(f"RSS订阅处理失败: {rss_url} -> {target_chat_id}", exc_info=True)
        await processing_message.edit_text(_format_error_message(rss_url, str(e)))


async def rsshub_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_del 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到RSSHUB_DEL命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ 参数不足\n"
            "请提供RSS链接和目标频道ID\n"
            "格式：/rsshub_del <RSS链接> <频道ID>\n\n"
            "例如：/rsshub_del https://example.com/rss.xml @my_channel"
        )
        return

    rss_url = context.args[0]
    target_chat_id = context.args[1]
    logging.info(f"执行rsshub_del命令，URL: {rss_url}, 频道: {target_chat_id}")

    # 验证频道ID格式
    if not validate_chat_id(target_chat_id):
        await update.message.reply_text(
            "❌ 无效的频道ID格式\n"
            "支持的格式：\n"
            "- @channel_name (频道用户名)\n"
            "- -1001234567890 (频道数字ID)\n"
            "- 1234567890 (用户数字ID)"
        )
        return

    success = rsshub_manager.remove_subscription(rss_url, target_chat_id)
    if success:
        logging.info(f"成功删除RSS订阅: {rss_url} -> {target_chat_id}")
        await update.message.reply_text(
            f"✅ 成功删除RSS订阅\n"
            f"🔗 RSS链接：{rss_url}\n"
            f"📺 目标频道：{target_chat_id}"
        )
    else:
        logging.error(f"删除RSS订阅失败: {rss_url} -> {target_chat_id}")
        await update.message.reply_text(
            f"⚠️ 该RSS源未订阅到此频道\n"
            f"🔗 RSS链接：{rss_url}\n"
            f"📺 目标频道：{target_chat_id}\n"
            f"💡 请检查链接和频道ID是否正确"
        )


async def rsshub_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_list 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到RSSHUB_LIST命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    try:
        all_rss_urls = rsshub_manager.get_all_rss_urls()
        if not all_rss_urls:
            logging.info("RSS订阅列表为空")
            await update.message.reply_text(
                "📋 当前没有RSS订阅\n\n"
                "💡 使用 /rsshub_add <RSS链接> <频道ID> 添加订阅"
            )
            return

        # 构建订阅列表
        subscription_list = []
        total_channels = 0

        for rss_url in all_rss_urls:
            channels = rsshub_manager.get_subscription_channels(rss_url)
            total_channels += len(channels)

            # 获取RSS源标题（如果有）
            try:
                feed_info = rss_parser.get_feed_info(rss_url)
                rss_title = feed_info.get('title', '')
                if rss_title:
                    display_title = f"{rss_title}"
                else:
                    display_title = "RSS源"
            except Exception:
                display_title = "RSS源"

            # 格式化频道列表
            if len(channels) == 1:
                subscription_list.append(f"📡 {display_title}\n🔗 {rss_url}\n📺 {channels[0]}")
            else:
                channels_text = ', '.join(channels)
                subscription_list.append(f"📡 {display_title}\n🔗 {rss_url}\n📺 {channels_text}")

        subscription_text = "\n\n".join(subscription_list)

        logging.info(f"显示RSS订阅列表，共 {len(all_rss_urls)} 个")
        await update.message.reply_text(
            f"📋 当前RSS订阅列表：\n\n{subscription_text}\n\n"
            f"📊 总计：{len(all_rss_urls)}个RSS源，{total_channels}个频道订阅"
        )

    except Exception as e:
        logging.error(f"获取RSS订阅列表失败: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ 获取订阅列表失败\n"
            f"原因：{str(e)}"
        )


async def _send_rss_content_batch(
    bot: Bot, 
    entries: List, 
    rss_url: str, 
    target_chat_ids: List[str]
) -> int:
    """
    批量发送RSS内容到指定频道

    Args:
        bot: Telegram Bot实例
        entries: RSS条目列表
        rss_url: RSS源URL
        target_chat_ids: 目标频道ID列表

    Returns:
        int: 发送成功的内容数量
    """
    try:
        from .rss_converter import create_rss_converter
        from services.common.unified_interval_manager import UnifiedIntervalManager

        # 创建转换器和发送器
        converter = create_rss_converter()
        sender = UnifiedTelegramSender()
        interval_manager = UnifiedIntervalManager("rsshub_send")

        sent_count = 0

        # 按发布时间排序（从旧到新）
        sorted_entries = sorted(entries, key=lambda x: x.effective_published_time or x.updated or x.published, reverse=False)

        for entry in sorted_entries:
            try:
                # 转换为统一消息格式
                telegram_message = converter.to_telegram_message(entry)

                # 发送到所有目标频道
                for chat_id in target_chat_ids:
                    try:
                        # 发送消息
                        message_ids = await sender.send_message(bot, chat_id, telegram_message)

                        if message_ids:
                            # 保存消息映射
                            rsshub_manager.save_message_mapping(rss_url, entry.item_id, chat_id, message_ids)
                            logging.debug(f"RSS内容发送成功: {entry.item_id} -> {chat_id}")

                        # 应用发送间隔
                        await interval_manager.apply_interval()

                    except Exception as e:
                        logging.error(f"发送RSS内容到频道失败: {chat_id}, 错误: {str(e)}", exc_info=True)
                        continue

                # 标记为已知条目
                rsshub_manager.add_known_item_id(rss_url, entry.item_id)
                sent_count += 1

            except Exception as e:
                logging.error(f"处理RSS条目失败: {entry.item_id}, 错误: {str(e)}", exc_info=True)
                continue

        logging.info(f"RSS批量发送完成: {sent_count}/{len(entries)} 个内容发送成功")
        return sent_count

    except Exception as e:
        logging.error(f"RSS批量发送失败: {str(e)}", exc_info=True)
        return 0


# ==================== 消息格式化函数（复用douyin逻辑）====================

def _format_url_validation_error_message() -> str:
    """格式化RSS URL验证错误消息"""
    return (
        "❌ 无效的RSS链接格式\n\n"
        "支持的RSS链接格式：\n"
        "• https://example.com/rss.xml\n"
        "• https://example.com/feed\n"
        "• https://example.com/atom.xml\n"
        "• http://example.com/rss\n\n"
        "💡 请确保链接以 http:// 或 https:// 开头"
    )


def _format_chat_id_validation_error_message() -> str:
    """格式化频道ID验证错误消息"""
    return (
        "❌ 无效的频道ID格式\n"
        "支持的格式：\n"
        "- @channel_name (频道用户名)\n"
        "- -1001234567890 (频道数字ID)\n"
        "- 1234567890 (用户数字ID)"
    )


def _format_duplicate_subscription_message(rss_url: str, chat_id: str) -> str:
    """格式化重复订阅消息"""
    return (
        f"⚠️ 该RSS源已订阅到此频道\n"
        f"🔗 RSS链接：{rss_url}\n"
        f"📺 目标频道：{chat_id}\n"
        f"📋 当前订阅状态：正常\n"
        f"🔄 系统正在自动监控新内容，无需重复添加"
    )


def _format_processing_message(rss_url: str, chat_id: str) -> str:
    """格式化正在处理消息（统一格式）"""
    return (
        f"✅ 正在添加RSS订阅...\n"
        f"🔗 RSS链接：{rss_url}\n"
        f"📺 目标频道：{chat_id}\n"
        f"⏳ 正在获取历史内容，请稍候..."
    )


def _format_progress_message(rss_url: str, chat_id: str, content_count: int) -> str:
    """格式化进度消息"""
    return (
        f"✅ 订阅添加成功！\n"
        f"🔗 RSS链接：{rss_url}\n"
        f"📺 目标频道：{chat_id}\n"
        f"📤 正在发送 {content_count} 个历史内容..."
    )


def _format_final_success_message(rss_url: str, chat_id: str, sent_count: int) -> str:
    """格式化最终成功消息"""
    return (
        f"✅ RSS订阅添加完成\n"
        f"🔗 RSS链接：{rss_url}\n"
        f"📺 目标频道：{chat_id}\n"
        f"📊 已同步 {sent_count} 个历史内容\n"
        f"🔄 系统将继续自动监控新内容"
    )


def _format_error_message(rss_url: str, error_reason: str) -> str:
    """格式化添加订阅失败消息"""
    return (
        f"❌ 添加RSS订阅失败\n"
        f"🔗 RSS链接：{rss_url}\n"
        f"原因：{error_reason}\n\n"
        f"💡 请检查：\n"
        f"- RSS链接格式是否正确\n"
        f"- RSS源是否可访问\n"
        f"- 频道ID是否有效\n"
        f"- Bot是否有频道发送权限"
    )


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
        # 注册调试命令（如果需要的话）
        # from .debug_commands import register_rsshub_debug_commands
        # register_rsshub_debug_commands(application)
        logging.info("ℹ️ RSSHub调试命令暂未实现")
    else:
        logging.info("ℹ️ RSSHub调试命令已跳过（DEBUG模式关闭）")

    logging.info("RSSHub命令处理器注册完成") 