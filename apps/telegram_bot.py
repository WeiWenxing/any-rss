from core.config import telegram_config
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Application
import logging
import asyncio

tel_bots = {}
commands = [
    BotCommand(command="help", description="Show help message"),
]


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(commands)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 命令"""
    await help(update, context)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /help 命令"""
    help_text = (
        "🤖 欢迎使用 Any RSS Bot！\n\n"
        "这是一个通用的 RSS/Feed 监控机器人，支持标准的 RSS 2.0 和 Atom 1.0 格式。\n\n"
        "🎯 主要功能：\n"
        "• 监控 RSS/Feed 订阅源\n"
        "• 自动检测新增内容\n"
        "• 推送更新到指定频道\n"
        "• 生成关键词汇总\n\n"
        "📋 命令列表：\n\n"
        "🔹 /add <URL>\n"
        "   添加新的RSS/Feed订阅\n"
        "   支持：RSS 2.0、Atom 1.0、RSSHub等\n"
        "   示例：/add https://rsshub.app/github/issue/DIYgod/RSSHub\n\n"
        "🔹 /del <URL>\n"
        "   删除指定的RSS/Feed订阅\n"
        "   注意：删除时会保留历史数据，重新订阅不会重复推送\n\n"
        "🔹 /list\n"
        "   显示当前所有订阅的RSS/Feed列表\n\n"
        "🔹 /news\n"
        "   手动触发关键词汇总生成和发送\n"
        "   会比较已存储的数据，提取新增内容的关键词\n\n"
        "🔹 /help\n"
        "   显示此帮助信息\n\n"
        "🔄 自动功能：\n"
        "• 每小时自动检查所有订阅源\n"
        "• 发现新内容时自动推送\n"
        "• 智能去重，避免重复推送\n\n"
        "💡 使用示例：\n"
        "• /add https://example.com/feed.xml\n"
        "• /del https://example.com/feed.xml\n"
        "• /list\n"
        "• /news\n\n"
        "❓ 如有问题，请检查URL格式是否正确，确保是有效的RSS/Feed地址。"
    )
    await update.message.reply_text(help_text, disable_web_page_preview=True)


async def run(token):
    global tel_bots
    application = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )

    # 用token作为key存储bot实例
    tel_bots[token] = application.bot

    # 基础命令
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))

    # 从services加载其他命令
    from services.rss.commands import register_commands

    register_commands(application)

    await application.initialize()
    await application.start()
    logging.info("Telegram bot startup successful")
    await application.updater.start_polling(drop_pending_updates=True)


async def init_task():
    logging.info("Initializing Telegram bot")


async def start_task(token):
    return await run(token)


def close_all():
    logging.info("Closing Telegram bot")


async def scheduled_task(token):
    """定时任务"""
    await asyncio.sleep(5)

    bot = tel_bots.get(token)
    if not bot:
        logging.error(f"未找到token对应的bot实例: {token}")
        return

    # 修改导入
    from services.rss.commands import (
        rss_manager,
        send_update_notification,
        send_keywords_summary,
    )

    while True:
        try:
            feeds = rss_manager.get_feeds()
            logging.info(f"定时任务开始检查订阅源更新，共 {len(feeds)} 个订阅")

            # 用于存储所有新增的URL
            all_new_urls = []
            for url in feeds:
                logging.info(f"正在检查订阅源: {url}")
                # add_feed 内部会调用 download_sitemap
                success, error_msg, dated_file, new_urls = rss_manager.add_feed(url)

                if success and dated_file.exists():
                    # 直接调用合并后的函数
                    await send_update_notification(bot, url, new_urls, dated_file)
                    if new_urls:
                        logging.info(
                            f"订阅源 {url} 更新成功，发现 {len(new_urls)} 个新URL，已发送通知。"
                        )
                    else:
                        logging.info(f"订阅源 {url} 更新成功，无新增URL，已发送通知。")
                elif "今天已经更新过此sitemap" in error_msg:
                    logging.info(f"订阅源 {url} {error_msg}")
                else:
                    logging.warning(f"订阅源 {url} 更新失败: {error_msg}")
                # 将新URL添加到汇总列表中
                all_new_urls.extend(new_urls)

            # 调用新封装的函数发送关键词汇总
            await asyncio.sleep(10)  # 等待10秒，确保所有消息都发送完成
            await send_keywords_summary(bot, all_new_urls)

            logging.info("所有订阅源检查完成，等待下一次检查")
            await asyncio.sleep(3600)  # 保持1小时检查间隔
        except Exception as e:
            logging.error(f"检查订阅源更新失败: {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # 出错后等待1分钟再试
