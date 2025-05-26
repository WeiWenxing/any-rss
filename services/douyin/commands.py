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
from .alignment import perform_historical_alignment


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
        # 检查是否需要历史对齐
        if isinstance(content_info, dict) and content_info.get("need_alignment"):
            # 需要历史对齐的情况
            known_item_ids = content_info.get("known_item_ids", [])
            primary_channel = content_info.get("primary_channel")
            new_channel = content_info.get("new_channel")

            await update.message.reply_text(
                f"✅ 成功添加抖音订阅：{douyin_url}\n"
                f"📺 目标频道：{target_chat_id}\n"
                f"🔄 正在进行历史对齐，从主频道 {primary_channel} 转发 {len(known_item_ids)} 个历史内容..."
            )

            # 实施历史对齐转发
            alignment_success = await perform_historical_alignment(
                context.bot, douyin_url, known_item_ids, primary_channel, new_channel
            )
            
            if alignment_success:
                await update.message.reply_text(
                    f"🎉 历史对齐完成！\n"
                    f"📊 成功转发 {len(known_item_ids)} 个历史内容\n"
                    f"🔄 系统将继续自动监控新内容"
                )
            else:
                await update.message.reply_text(
                    f"⚠️ 历史对齐部分失败\n"
                    f"📊 尝试转发 {len(known_item_ids)} 个历史内容\n"
                    f"🔄 系统将继续自动监控新内容"
                )
            return

        # 判断是否为更新现有订阅
        is_update = "更新成功" in error_msg

        # 根据操作类型显示不同的初始消息
        if is_update:
            await update.message.reply_text(
                f"✅ 抖音订阅已更新，频道改为：{target_chat_id}\n"
                f"💡 正在检查并推送内容..."
            )
        else:
            await update.message.reply_text(
                f"✅ 成功添加抖音订阅：{douyin_url}\n"
                f"📺 目标频道：{target_chat_id}\n"
                f"💡 正在检查并推送内容..."
            )

        # 统一逻辑：立即检查更新并发送所有新内容
        # 首次订阅时：new_items = 所有历史内容
        # 非首次订阅时：new_items = 真正的新内容
        try:
            check_success, check_error_msg, new_items = douyin_manager.check_updates(douyin_url)

            if check_success and new_items:
                logging.info(f"订阅检查到 {len(new_items)} 个新内容，开始发送")

                # 使用调度器的多频道批量处理逻辑
                from .scheduler import DouyinScheduler
                scheduler = DouyinScheduler()
                sent_count = await scheduler._process_batch_with_forwarding(context.bot, new_items, douyin_url, [target_chat_id])

                logging.info(f"抖音订阅 {douyin_url} 成功发送 {sent_count}/{len(new_items)} 个内容到 1 个频道")

                # 根据操作类型显示不同的完成消息
                if is_update:
                    await update.message.reply_text(
                        f"🎉 订阅更新完成！\n"
                        f"📊 成功推送 {sent_count}/{len(new_items)} 个内容\n"
                        f"🔄 系统将继续自动监控新内容"
                    )
                else:
                    await update.message.reply_text(
                        f"🎉 首次订阅完成！\n"
                        f"📊 成功推送 {sent_count}/{len(new_items)} 个历史内容\n"
                        f"🔄 系统将继续自动监控新内容"
                    )

            elif check_success:
                # 根据操作类型显示不同的无内容消息
                if is_update:
                    await update.message.reply_text(
                        f"✅ 订阅更新成功，当前没有新内容\n"
                        f"🔄 系统将自动监控新内容"
                    )
                else:
                    await update.message.reply_text(
                        f"✅ 订阅添加成功，但当前没有内容\n"
                        f"🔄 系统将自动监控新内容"
                    )
            else:
                logging.warning(f"订阅后检查更新失败: {check_error_msg}")
                await update.message.reply_text(
                    f"✅ 订阅操作成功\n"
                    f"⚠️ 但检查内容时出现问题: {check_error_msg}\n"
                    f"🔄 系统将在下次定时检查时重试"
                )

        except Exception as e:
            logging.error(f"订阅后立即检查失败: {str(e)}", exc_info=True)
            await update.message.reply_text(
                f"✅ 订阅操作成功\n"
                f"⚠️ 但立即检查时出现错误\n"
                f"🔄 系统将在下次定时检查时处理"
            )

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

    success, error_msg = douyin_manager.remove_subscription(douyin_url, target_chat_id)
    if success:
        logging.info(f"成功删除抖音订阅: {douyin_url} -> {target_chat_id}")
        await update.message.reply_text(f"✅ 成功删除抖音订阅：{douyin_url} -> {target_chat_id}")
    else:
        logging.error(f"删除抖音订阅失败: {douyin_url} -> {target_chat_id} 原因: {error_msg}", exc_info=True)
        await update.message.reply_text(
            f"❌ 删除抖音订阅失败：{douyin_url} -> {target_chat_id}\n原因：{error_msg}"
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
    for douyin_url, target_channels in subscriptions.items():
        # 缩短URL显示
        short_url = douyin_url
        if len(douyin_url) > 50:
            short_url = douyin_url[:25] + "..." + douyin_url[-20:]

        # 处理多频道显示
        if isinstance(target_channels, list):
            if len(target_channels) == 1:
                subscription_list.append(f"🔗 {short_url}\n📺 → {target_channels[0]}")
            else:
                channels_text = "\n".join([f"📺 → {ch}" for ch in target_channels])
                subscription_list.append(f"🔗 {short_url}\n{channels_text}")
        else:
            # 兼容旧格式
            subscription_list.append(f"🔗 {short_url}\n📺 → {target_channels}")

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

    for douyin_url, target_channels in subscriptions.items():
        try:
            # 确保target_channels是列表格式
            if isinstance(target_channels, str):
                target_channels = [target_channels]

            logging.info(f"强制检查抖音订阅: {douyin_url} -> 频道: {target_channels}")

            # 检查更新（返回的内容已包含target_channels信息）
            success, error_msg, new_items = douyin_manager.check_updates(douyin_url)

            if success:
                success_count += 1
                if new_items:  # 有新内容
                    logging.info(f"抖音订阅 {douyin_url} 发现 {len(new_items)} 个新内容")

                    # 使用调度器的多频道批量处理逻辑
                    from .scheduler import DouyinScheduler
                    scheduler = DouyinScheduler()
                    sent_count = await scheduler._process_batch_with_forwarding(context.bot, new_items, douyin_url, target_channels)

                    new_content_count += sent_count
                    logging.info(f"抖音订阅 {douyin_url} 成功发送 {sent_count}/{len(new_items)} 个内容到 {len(target_channels)} 个频道")
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