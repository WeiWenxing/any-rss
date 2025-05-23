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
        "🤖 Any RSS Bot - 通用RSS/Feed订阅机器人\n\n"
        "这是一个通用的RSS/Feed监控机器人，支持标准的RSS 2.0和Atom 1.0格式。\n\n"
        "🎯 主要功能：\n"
        "• 监控RSS/Feed订阅源\n"
        "• 自动检测新增内容\n"
        "• 推送更新到指定频道\n"
        "• 生成关键词汇总\n"
        "• 智能内容展示（标题、描述、发布时间、图片）\n"
        "• 防刷屏保护机制\n\n"
        "📋 可用命令：\n\n"
        "🔹 /add <RSS_URL> <CHAT_ID>\n"
        "   添加RSS/Feed订阅源到指定频道\n"
        "   • 支持标准RSS 2.0和Atom 1.0格式\n"
        "   • 首次添加时会展示所有现有内容\n"
        "   • 频道ID格式：@channel_name 或 -1001234567890\n"
        "   • 示例：/add https://example.com/feed.xml @my_channel\n"
        "   • 示例：/add https://example.com/feed.xml -1001234567890\n\n"
        "🔹 /del <RSS_URL>\n"
        "   删除RSS/Feed订阅源\n"
        "   • 软删除机制，可重新添加\n"
        "   • 示例：/del https://example.com/feed.xml\n\n"
        "🔹 /list\n"
        "   查看当前所有订阅源及其绑定频道\n"
        "   • 显示所有已添加的RSS/Feed订阅源列表\n"
        "   • 显示每个订阅源对应的目标频道\n\n"
        "🔹 /news\n"
        "   强制检查更新并发送差异内容\n"
        "   • 立即检查所有订阅源的更新\n"
        "   • 发送新增内容到对应绑定频道\n"
        "   • 生成关键词汇总报告\n\n"
        "🔹 /help\n"
        "   显示此帮助信息\n\n"
        "🔄 自动功能：\n"
        "• 每小时自动检查所有订阅源\n"
        "• 发现新内容时自动推送到绑定频道\n"
        "• 智能去重，避免重复推送\n"
        "• 自动生成关键词汇总\n\n"
        "✨ 内容展示特性：\n"
        "• 标题、描述、发布时间\n"
        "• 自动提取和展示图片链接\n"
        "• HTML标签清理和格式化\n"
        "• 智能控制发送速度，避免刷屏\n\n"
        "💡 使用示例：\n"
        "• /add https://feeds.bbci.co.uk/news/rss.xml @news_channel\n"
        "• /add https://rss.cnn.com/rss/edition.rss -1001234567890\n"
        "• /list\n"
        "• /news\n\n"
        "🔧 技术支持：\n"
        "项目地址：https://github.com/WeiWenxing/any-rss\n"
        "如有问题请提交Issue或联系管理员"
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
    )

    while True:
        try:
            feeds = rss_manager.get_feeds()
            logging.info(f"定时任务开始检查订阅源更新，共 {len(feeds)} 个订阅")

            # 用于存储所有新增的条目
            all_new_entries = []
            for url, target_chat_id in feeds.items():
                logging.info(f"正在检查订阅源: {url} -> 频道: {target_chat_id}")

                # 对于定时任务，我们直接调用download_and_parse_feed而不是add_feed
                # 这样可以避免首次添加的特殊逻辑
                success, error_msg, xml_content, new_entries = rss_manager.download_and_parse_feed(url)

                if success:
                    if new_entries:
                        logging.info(f"订阅源 {url} 发现 {len(new_entries)} 个新条目，正在发送通知到 {target_chat_id}")
                        await send_update_notification(bot, url, new_entries, xml_content, target_chat_id)
                        all_new_entries.extend(new_entries)
                    else:
                        logging.info(f"订阅源 {url} 无新增内容")
                elif "今天已经更新过此Feed" in error_msg:
                    logging.info(f"订阅源 {url} {error_msg}")
                else:
                    logging.warning(f"订阅源 {url} 更新失败: {error_msg}")

            # 如果有新增条目，记录日志
            if all_new_entries:
                logging.info(f"定时任务完成，共发现 {len(all_new_entries)} 个新条目")

            logging.info("所有订阅源检查完成，等待下一次检查")
            await asyncio.sleep(3600)  # 保持1小时检查间隔
        except Exception as e:
            logging.error(f"检查订阅源更新失败: {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # 出错后等待1分钟再试
