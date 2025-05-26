"""
抖音命令处理器

负责处理所有抖音相关的Telegram命令
"""

import logging
import asyncio
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from .manager import DouyinManager
from .formatter import DouyinFormatter
from .sender import send_douyin_content


# 全局实例
douyin_manager = DouyinManager()
douyin_formatter = DouyinFormatter()


async def douyin_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /douyin_add 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DOUYIN_ADD命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if not context.args:
        logging.info("显示DOUYIN_ADD命令帮助信息")
        await update.message.reply_text(
            "🎵 抖音订阅功能\n\n"
            "使用方法：\n"
            "/douyin_add <抖音链接> <频道ID> - 添加抖音订阅\n"
            "/douyin_del <抖音链接> - 删除抖音订阅\n"
            "/douyin_list - 查看所有抖音订阅\n"
            "/douyin_check - 手动检查更新\n\n"
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

    # 添加订阅
    success, error_msg, content_info = douyin_manager.add_subscription(douyin_url, target_chat_id)

    if success:
        if "更新成功" in error_msg:
            await update.message.reply_text(f"✅ 抖音订阅已更新，频道改为：{target_chat_id}")
        else:
            await update.message.reply_text(
                f"✅ 成功添加抖音订阅：{douyin_url}\n"
                f"📺 目标频道：{target_chat_id}\n"
                f"💡 系统将自动检查并推送新内容"
            )

        # 如果有内容信息，发送到指定频道
        if content_info:
            await send_douyin_content(context.bot, content_info, douyin_url, target_chat_id)
            logging.info(f"已尝试发送抖音内容 for {douyin_url} to {target_chat_id} after add command")

    else:
        logging.error(f"添加抖音订阅失败: {douyin_url} 原因: {error_msg}", exc_info=True)
        await update.message.reply_text(
            f"❌ 添加抖音订阅失败：{douyin_url}\n原因：{error_msg}"
        )


async def douyin_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /douyin_del 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DOUYIN_DEL命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    if not context.args:
        logging.warning("douyin_del命令缺少URL参数")
        await update.message.reply_text(
            "请提供要删除的抖音链接\n例如：/douyin_del https://v.douyin.com/iM5g7LsM/"
        )
        return

    douyin_url = context.args[0]
    logging.info(f"执行douyin_del命令，URL: {douyin_url}")

    success, error_msg = douyin_manager.remove_subscription(douyin_url)
    if success:
        logging.info(f"成功删除抖音订阅: {douyin_url}")
        await update.message.reply_text(f"✅ 成功删除抖音订阅：{douyin_url}")
    else:
        logging.error(f"删除抖音订阅失败: {douyin_url} 原因: {error_msg}", exc_info=True)
        await update.message.reply_text(
            f"❌ 删除抖音订阅失败：{douyin_url}\n原因：{error_msg}"
        )


async def douyin_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /douyin_list 命令"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DOUYIN_LIST命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    subscriptions = douyin_manager.get_subscriptions()
    if not subscriptions:
        logging.info("抖音订阅列表为空")
        await update.message.reply_text("当前没有抖音订阅")
        return

    # 构建订阅列表
    subscription_list = []
    for douyin_url, subscription_info in subscriptions.items():
        chat_id_info = subscription_info.get("chat_id", "")
        nickname = subscription_info.get("nickname", "")
        author = subscription_info.get("author", "")

        # 构建用户显示名
        if nickname and author and nickname != author:
            user_display = f"{nickname} (@{author})"
        elif nickname:
            user_display = nickname
        elif author:
            user_display = f"@{author}"
        else:
            user_display = "未知用户"

        # 缩短URL显示
        short_url = douyin_url
        if len(douyin_url) > 50:
            short_url = douyin_url[:25] + "..." + douyin_url[-20:]

        subscription_list.append(f"👤 {user_display}\n🔗 {short_url}\n📺 → {chat_id_info}")

    subscription_text = "\n\n".join(subscription_list)
    logging.info(f"显示抖音订阅列表，共 {len(subscriptions)} 个")
    await update.message.reply_text(f"当前抖音订阅列表：\n\n{subscription_text}")


async def douyin_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /douyin_check 命令 - 手动检查所有抖音订阅的更新"""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logging.info(f"收到DOUYIN_CHECK命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

    subscriptions = douyin_manager.get_subscriptions()
    if not subscriptions:
        await update.message.reply_text("❌ 当前没有监控任何抖音订阅")
        return

    await update.message.reply_text(
        f"🔄 开始强制检查 {len(subscriptions)} 个抖音订阅的更新...\n"
        f"这可能需要一些时间，请稍候。"
    )

    # 用于存储检查结果
    new_content_count = 0
    success_count = 0
    error_count = 0

    for douyin_url, subscription_info in subscriptions.items():
        try:
            target_chat_id = subscription_info.get("chat_id", "")
            logging.info(f"强制检查抖音订阅: {douyin_url} -> 频道: {target_chat_id}")

            # 检查更新
            success, error_msg, content_info = douyin_manager.check_updates(douyin_url)

            if success:
                success_count += 1
                if content_info:  # 有新内容
                    logging.info(f"抖音订阅 {douyin_url} 发现新内容")
                    # 发送新内容到绑定的频道
                    await send_douyin_content(context.bot, content_info, douyin_url, target_chat_id)
                    new_content_count += 1
                else:
                    logging.info(f"抖音订阅 {douyin_url} 无新内容")
            else:
                error_count += 1
                logging.warning(f"抖音订阅 {douyin_url} 检查失败: {error_msg}")

        except Exception as e:
            error_count += 1
            logging.error(f"检查抖音订阅失败: {douyin_url}, 错误: {str(e)}", exc_info=True)

    # 发送检查结果摘要
    result_message = (
        f"✅ 强制检查完成\n"
        f"📊 成功: {success_count} 个\n"
        f"❌ 失败: {error_count} 个\n"
        f"📈 发现新内容: {new_content_count} 个"
    )

    if new_content_count > 0:
        result_message += f"\n\n✅ 所有新内容已推送到对应频道"
    else:
        result_message += f"\n\n💡 所有订阅都没有新内容"

    await update.message.reply_text(result_message)
    logging.info(f"DOUYIN_CHECK命令执行完成，共处理 {len(subscriptions)} 个订阅，发现 {new_content_count} 个新内容")


def register_douyin_commands(application: Application) -> None:
    """注册抖音相关的命令处理器"""
    application.add_handler(CommandHandler("douyin_add", douyin_add_command))
    application.add_handler(CommandHandler("douyin_del", douyin_del_command))
    application.add_handler(CommandHandler("douyin_list", douyin_list_command))
    application.add_handler(CommandHandler("douyin_check", douyin_check_command))

    # 注册调试命令
    from .debug_commands import register_douyin_debug_commands
    register_douyin_debug_commands(application)

    logging.info("抖音命令处理器注册完成")