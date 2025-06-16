from core.config import telegram_config, debug_config
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Application
import logging
import asyncio
from telegram.request import HTTPXRequest

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
    from services.common.help_manager import get_help_manager

    # 使用帮助管理器生成完整帮助信息
    help_manager = get_help_manager()
    help_text = help_manager.generate_full_help(debug_config["enabled"])

    await update.message.reply_text(help_text, disable_web_page_preview=True)


def create_application(token: str) -> Application:
    """
    创建Telegram应用实例，根据配置决定使用官方API还是本地API

    Args:
        token: 机器人Token

    Returns:
        Application: 配置好的应用实例
    """
    # 创建自定义请求对象，增加超时时间
    # 对于大文件上传，需要更长的超时时间
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=300,  # 读取超时：5分钟
        write_timeout=300,  # 写入超时：5分钟
        connect_timeout=30,  # 连接超时：30秒
        pool_timeout=30,   # 连接池超时：30秒
    )

    # 获取本地API配置
    api_base_url = telegram_config.get("api_base_url")

    if api_base_url:
        # 使用本地Bot API服务器
        base_url = f"{api_base_url}/bot"
        base_file_url = f"{api_base_url}/file/bot"

        application = (
            ApplicationBuilder()
            .token(token)
            .base_url(base_url)
            .base_file_url(base_file_url)
            .request(request)  # 使用自定义请求配置
            .concurrent_updates(True)
            .post_init(post_init)
            .build()
        )

        logging.info(f"✅ 机器人已配置使用本地Bot API服务器")
        logging.info(f"📍 API地址: {base_url}")
        logging.info(f"📁 文件地址: {base_file_url}")
        logging.info(f"⏱️ 超时配置: 读取/写入=300s, 连接=30s")
    else:
        # 使用官方Bot API服务器
        application = (
            ApplicationBuilder()
            .token(token)
            .request(request)  # 使用自定义请求配置
            .concurrent_updates(True)
            .post_init(post_init)
            .build()
        )

        logging.info(f"✅ 机器人已配置使用官方Bot API服务器")
        logging.info(f"📍 API地址: https://api.telegram.org/bot")
        logging.info(f"⏱️ 超时配置: 读取/写入=300s, 连接=30s")

    return application


async def run(token):
    global tel_bots

    # 使用新的创建函数
    application = create_application(token)

    # 用token作为key存储bot实例
    tel_bots[token] = application.bot

    # 基础命令
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))

    # 从services加载其他命令
    from services.rss.commands import register_commands
    from services.douyin.commands import register_douyin_commands
    from services.rsshub.commands import register_rsshub_commands
    from services.sitemap.commands import register_sitemap_commands

    register_commands(application)
    register_douyin_commands(application)
    register_rsshub_commands(application)
    register_sitemap_commands(application)

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
    await asyncio.sleep(600)  # 等待10分钟后开始定时任务

    bot = tel_bots.get(token)
    if not bot:
        logging.error(f"未找到token对应的bot实例: {token}", exc_info=True)
        return

    # 导入服务模块
    from services.rss.scheduler import run_scheduled_check as rss_run_scheduled_check
    from services.douyin.scheduler import run_scheduled_check as douyin_run_scheduled_check
    from services.rsshub.scheduler import run_scheduled_check as rsshub_run_scheduled_check

    while True:
        try:
            # RSS订阅检查 - 使用RSS调度器
            await rss_run_scheduled_check(bot)

            # 抖音订阅检查 - 使用抖音调度器
            await douyin_run_scheduled_check(bot)

            # RSSHub订阅检查 - 使用RSSHub调度器
            await rsshub_run_scheduled_check(bot)

            logging.info("所有订阅源检查完成，等待下一次检查")
            await asyncio.sleep(3600)  # 保持1小时检查间隔
        except Exception as e:
            logging.error(f"检查订阅源更新失败: {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # 出错后等待1分钟再试
