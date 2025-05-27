"""
抖音命令处理器

负责处理所有抖音相关的Telegram命令
"""

import logging
import asyncio
from typing import Dict
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from .manager import DouyinManager
from .formatter import DouyinFormatter
from .sender import send_douyin_content
from .alignment import perform_historical_alignment


def validate_douyin_url(url: str) -> bool:
    """验证抖音URL格式 - 简单域名匹配"""
    if not url:
        return False

    # 支持的抖音域名开头
    valid_domains = [
        'https://www.douyin.com/',
        'http://www.douyin.com/',
        'https://v.douyin.com/',
        'http://v.douyin.com/',
    ]

    for domain in valid_domains:
        if url.startswith(domain):
            return True
    return False


# 全局实例
douyin_manager = DouyinManager()
douyin_formatter = DouyinFormatter()


async def douyin_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /douyin_add 命令 - 按照设计文档的三分支结构实现"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DOUYIN_ADD命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    # 1. 参数验证
    if not context.args:
        logging.info("显示DOUYIN_ADD命令帮助信息")
        await update.message.reply_text(
            "🎵 抖音订阅功能\n\n"
            "使用方法：\n"
            "/douyin_add <抖音链接> <频道ID> - 添加抖音订阅\n"
            "/douyin_del <抖音链接> <频道ID> - 删除抖音订阅\n"
            "/douyin_list - 查看所有抖音订阅\n\n"
            "支持的抖音链接格式：\n"
            "• https://www.douyin.com/user/xxx\n"
            "• https://v.douyin.com/xxx (短链接)\n\n"
            "系统会自动监控并推送新内容到指定频道"
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ 参数不足\n"
            "请提供抖音链接和目标频道ID\n"
            "格式：/douyin_add <抖音链接> <CHAT_ID>\n\n"
            "例如：/douyin_add https://v.douyin.com/iM5g7LsM/ @my_channel"
        )
        return

    douyin_url = context.args[0]
    target_chat_id = context.args[1]

    logging.info(f"执行douyin_add命令，URL: {douyin_url}, 目标频道: {target_chat_id}")

    # 验证抖音URL格式
    if not validate_douyin_url(douyin_url):
        await update.message.reply_text(_format_url_validation_error_message())
        return

    # 验证频道ID格式
    if not (target_chat_id.startswith('@') or target_chat_id.startswith('-') or target_chat_id.isdigit()):
        await update.message.reply_text(_format_chat_id_validation_error_message())
        return

    # 2. 检查订阅状态
    subscriptions = douyin_manager.get_subscriptions()
    subscription_status = _check_subscription_status(douyin_url, target_chat_id, subscriptions)

    # 3. 三分支处理
    if subscription_status == "duplicate":
        # 重复订阅分支
        await update.message.reply_text(_format_duplicate_subscription_message(douyin_url, target_chat_id))
        return

    elif subscription_status == "first_channel":
        # 首个频道分支
        try:
            # 添加订阅
            success, error_msg, content_info = douyin_manager.add_subscription(douyin_url, target_chat_id)

            if not success:
                await update.message.reply_text(_format_error_message(douyin_url, error_msg))
                return

            # 获取历史内容并发送
            check_success, check_error_msg, new_items = douyin_manager.check_updates(douyin_url)

            if check_success and new_items:
                # 发送到频道
                sent_count = await douyin_manager.send_content_batch(
                    context.bot, new_items, douyin_url, [target_chat_id]
                )

                # 成功反馈
                await update.message.reply_text(_format_success_message(douyin_url, target_chat_id, sent_count))
            else:
                # 无内容或获取失败
                await update.message.reply_text(_format_success_no_content_message(douyin_url, target_chat_id))

        except Exception as e:
            logging.error(f"首个频道订阅失败: {douyin_url}", exc_info=True)
            await update.message.reply_text(_format_error_message(douyin_url, str(e)))

    elif subscription_status == "additional_channel":
        # 后续频道分支
        try:
            # 添加订阅
            success, error_msg, content_info = douyin_manager.add_subscription(douyin_url, target_chat_id)

            if not success:
                await update.message.reply_text(_format_error_message(douyin_url, error_msg))
                return

            # 检查是否需要历史对齐
            if isinstance(content_info, dict) and content_info.get("need_alignment"):
                known_item_ids = content_info.get("known_item_ids", [])
                new_channel = content_info.get("new_channel")

                # 历史对齐
                alignment_success = await perform_historical_alignment(
                    context.bot, douyin_url, known_item_ids, new_channel
                )

                # 无论历史对齐成功还是部分失败，对用户都显示成功消息
                await update.message.reply_text(_format_success_message(douyin_url, target_chat_id, len(known_item_ids)))
            else:
                # 无需历史对齐的情况
                await update.message.reply_text(_format_success_message(douyin_url, target_chat_id, 0))

        except Exception as e:
            logging.error(f"后续频道订阅失败: {douyin_url}", exc_info=True)
            await update.message.reply_text(_format_error_message(douyin_url, str(e)))


def _check_subscription_status(douyin_url: str, chat_id: str, subscriptions: Dict) -> str:
    """检查订阅状态"""
    if douyin_url in subscriptions:
        if chat_id in subscriptions[douyin_url]:
            return "duplicate"  # 重复订阅
        else:
            return "additional_channel"  # 后续频道
    else:
        return "first_channel"  # 首个频道


def _format_duplicate_subscription_message(douyin_url: str, chat_id: str) -> str:
    """格式化重复订阅消息"""
    return (
        f"⚠️ 该抖音用户已订阅到此频道\n"
        f"🔗 抖音链接：{douyin_url}\n"
        f"📺 目标频道：{chat_id}\n"
        f"📋 当前订阅状态：正常\n"
        f"🔄 系统正在自动监控新内容，无需重复添加"
    )


def _format_success_message(douyin_url: str, chat_id: str, content_count: int) -> str:
    """格式化成功添加订阅消息"""
    return (
        f"✅ 成功添加抖音订阅\n"
        f"🔗 抖音链接：{douyin_url}\n"
        f"📺 目标频道：{chat_id}\n"
        f"📊 已同步 {content_count} 个历史内容\n"
        f"🔄 系统将继续自动监控新内容"
    )


def _format_success_no_content_message(douyin_url: str, chat_id: str) -> str:
    """格式化成功添加订阅但无内容消息"""
    return (
        f"✅ 成功添加抖音订阅\n"
        f"🔗 抖音链接：{douyin_url}\n"
        f"📺 目标频道：{chat_id}\n"
        f"📊 当前没有可用内容\n"
        f"🔄 系统将继续自动监控新内容"
    )





def _format_error_message(douyin_url: str, error_reason: str) -> str:
    """格式化添加订阅失败消息"""
    return (
        f"❌ 添加抖音订阅失败\n"
        f"🔗 抖音链接：{douyin_url}\n"
        f"原因：{error_reason}\n\n"
        f"💡 请检查：\n"
        f"- 抖音链接格式是否正确\n"
        f"- 频道ID是否有效\n"
        f"- Bot是否有频道发送权限"
    )


def _format_url_validation_error_message() -> str:
    """格式化URL验证错误消息"""
    return (
        "❌ 抖音链接格式不正确\n"
        "支持的格式：\n"
        "• https://www.douyin.com/user/xxx\n"
        "• https://v.douyin.com/xxx\n"
        "• http://www.douyin.com/user/xxx\n"
        "• http://v.douyin.com/xxx"
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


async def douyin_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /douyin_del 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DOUYIN_DEL命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ 参数不足\n"
            "请提供抖音链接和目标频道ID\n"
            "格式：/douyin_del <抖音链接> <频道ID>\n\n"
            "例如：/douyin_del https://v.douyin.com/iM5g7LsM/ @my_channel"
        )
        return

    douyin_url = context.args[0]
    target_chat_id = context.args[1]
    logging.info(f"执行douyin_del命令，URL: {douyin_url}, 频道: {target_chat_id}")

    # 验证频道ID格式
    if not (target_chat_id.startswith('@') or target_chat_id.startswith('-') or target_chat_id.isdigit()):
        await update.message.reply_text(
            "❌ 无效的频道ID格式\n"
            "支持的格式：\n"
            "- @channel_name (频道用户名)\n"
            "- -1001234567890 (频道数字ID)\n"
            "- 1234567890 (用户数字ID)"
        )
        return

    success, error_msg = douyin_manager.remove_subscription(douyin_url, target_chat_id)
    if success:
        logging.info(f"成功删除抖音订阅: {douyin_url} -> {target_chat_id}")
        await update.message.reply_text(
            f"✅ 成功删除抖音订阅\n"
            f"🔗 抖音链接：{douyin_url}\n"
            f"📺 目标频道：{target_chat_id}"
        )
    else:
        logging.error(f"删除抖音订阅失败: {douyin_url} -> {target_chat_id} 原因: {error_msg}", exc_info=True)
        if "未订阅" in error_msg or "不存在" in error_msg:
            await update.message.reply_text(
                f"⚠️ 该抖音用户未订阅到此频道\n"
                f"🔗 抖音链接：{douyin_url}\n"
                f"📺 目标频道：{target_chat_id}\n"
                f"💡 请检查链接和频道ID是否正确"
            )
        else:
            await update.message.reply_text(
                f"❌ 删除抖音订阅失败\n"
                f"🔗 抖音链接：{douyin_url}\n"
                f"原因：{error_msg}\n\n"
                f"💡 请检查：\n"
                f"- 抖音链接格式是否正确\n"
                f"- 频道ID是否有效"
            )


async def douyin_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /douyin_list 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DOUYIN_LIST命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    subscriptions = douyin_manager.get_subscriptions()
    if not subscriptions:
        logging.info("抖音订阅列表为空")
        await update.message.reply_text(
            "📋 当前没有抖音订阅\n\n"
            "💡 使用 /douyin_add <抖音链接> <频道ID> 添加订阅"
        )
        return

    # 构建订阅列表
    subscription_list = []
    for douyin_url, target_channels in subscriptions.items():
        # 处理多频道显示
        if isinstance(target_channels, list):
            if len(target_channels) == 1:
                subscription_list.append(f"🎬 抖音用户\n🔗 {douyin_url}\n📺 {target_channels[0]}")
            else:
                channels_text = ', '.join(target_channels)
                subscription_list.append(f"🎬 抖音用户\n🔗 {douyin_url}\n📺 {channels_text}")
        else:
            # 兼容旧格式
            subscription_list.append(f"🎬 抖音用户\n🔗 {douyin_url}\n📺 {target_channels}")

    subscription_text = "\n\n".join(subscription_list)
    total_channels = sum(len(channels) if isinstance(channels, list) else 1 for channels in subscriptions.values())

    logging.info(f"显示抖音订阅列表，共 {len(subscriptions)} 个")
    await update.message.reply_text(
        f"📋 当前抖音订阅列表：\n\n{subscription_text}\n\n"
        f"📊 总计：{len(subscriptions)}个抖音用户，{total_channels}个频道订阅"
    )





def register_douyin_commands(application: Application) -> None:
    """注册抖音相关的命令处理器"""
    application.add_handler(CommandHandler("douyin_add", douyin_add_command))
    application.add_handler(CommandHandler("douyin_del", douyin_del_command))
    application.add_handler(CommandHandler("douyin_list", douyin_list_command))

    # 注册调试命令
    from .debug_commands import register_douyin_debug_commands
    register_douyin_debug_commands(application)

    logging.info("抖音命令处理器注册完成")