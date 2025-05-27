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
    # 基础帮助内容
    help_text = (
        "🤖 Any RSS Bot - 通用RSS/Feed订阅机器人\n\n"
        "这是一个通用的RSS/Feed监控机器人，支持标准的RSS 2.0和Atom 1.0格式，以及抖音用户内容订阅。\n\n"
        "🎯 主要功能：\n"
        "• 监控RSS/Feed订阅源\n"
        "• 监控抖音用户发布内容\n"
        "• 自动检测新增内容\n"
        "• 推送更新到指定频道\n"
        "• 生成关键词汇总\n"
        "• 智能内容展示（标题、描述、发布时间、图片、视频）\n"
        "• 防刷屏保护机制\n\n"
        "📋 RSS/Feed 命令：\n\n"
        "🔹 /add <RSS_URL> <CHAT_ID>\n"
        "   添加RSS/Feed订阅源到指定频道\n"
        "   • 支持标准RSS 2.0和Atom 1.0格式\n"
        "   • 首次添加时会展示所有现有内容\n"
        "   • 频道ID格式：@channel_name 或 -1001234567890\n"
        "   • 示例：/add https://example.com/feed.xml @my_channel\n\n"
        "🔹 /del <RSS_URL>\n"
        "   删除RSS/Feed订阅源\n"
        "   • 示例：/del https://example.com/feed.xml\n\n"
        "🔹 /list\n"
        "   查看当前所有RSS/Feed订阅源及其绑定频道\n\n"
        "🔹 /news\n"
        "   强制检查RSS/Feed更新并发送差异内容\n\n"
    )

    # 根据debug模式决定是否显示RSS调试命令
    if debug_config["enabled"]:
        help_text += (
            "🔹 /show [type] <item_xml>\n"
            "   开发者调试命令，测试单个RSS条目的消息格式\n"
            "   • type: auto(默认)/text/media\n\n"
        )

    help_text += (
        "📱 抖音订阅命令：\n\n"
        "🎵 **抖音订阅**\n"
        "   • /douyin_add <链接> <频道ID> - 添加抖音用户订阅\n"
        "   • /douyin_del <链接> <频道ID> - 删除抖音订阅\n"
        "   • /douyin_list - 查看抖音订阅列表\n"
        "   • 支持抖音用户主页和短链接\n"
        "   • 自动推送新发布的视频和图片内容\n\n"
        "📡 **RSSHub订阅**\n"
        "   • /rsshub_add <RSS链接> <频道ID> - 添加RSS订阅\n"
        "   • /rsshub_del <RSS链接> <频道ID> - 删除RSS订阅\n"
        "   • /rsshub_list - 查看RSS订阅列表\n"
        "   • 支持RSS 2.0和Atom 1.0格式\n"
        "   • 自动推送新发布的RSS内容\n\n"
    )

    # 根据debug模式决定是否显示抖音调试命令
    if debug_config["enabled"]:
        help_text += (
            "🔧 抖音调试命令：\n\n"
            "🔹 `/douyin_debug_show` [JSON数据]\n"
            "   **推荐用法**: `/douyin_debug_show` (无参数) → 上传JSON文件\n"
            "   • 二步交互：先发命令，再上传文件\n"
            "   • 避免长JSON参数限制问题\n"
            "   • 包含格式化预览和实际媒体发送\n"
            "   • 也支持传统方式：`/douyin_debug_show <短JSON>`\n\n"
            "🔹 `/douyin_debug_format` <JSON数据>\n"
            "   调试抖音内容格式化，只显示格式化结果不发送媒体\n"
            "   • 用于测试消息格式化效果\n"
            "   • 显示详细的格式化统计信息\n"
            "   ⚠️ 注意：JSON数据不能太长，建议使用文件上传方式\n\n"
            "🔹 `/douyin_debug_url` <抖音链接>\n"
            "   通过抖音链接自动获取内容并调试\n"
            "   • 自动解析抖音链接获取JSON数据\n"
            "   • 无需手动复制JSON，最简单的调试方式\n"
            "   • 支持手机和电脑端链接\n\n"
            "🔹 📁 **直接上传JSON文件**\n"
            "   无需命令，直接上传.json文件进行通用调试\n"
            "   • 支持任意大小的JSON文件\n"
            "   • 自动解析并调试\n"
            "   • 适合快速测试\n\n"
            "🔹 `/douyin_debug_sample` [type]\n"
            "   获取抖音调试数据样例（消息形式）\n"
            "   • type: simple(默认) | full\n"
            "   • simple: 基础字段样例\n"
            "   • full: 包含视频、音乐等完整信息的样例\n\n"
            "🔹 `/douyin_debug_file` [type]\n"
            "   下载抖音调试数据样例文件\n"
            "   • type: simple(默认) | full\n"
            "   • 避免长消息限制，提供JSON文件下载\n"
            "   • 适合获取完整的调试数据\n\n"
        )

    help_text += (
        "🔹 /help\n"
        "   显示此帮助信息\n\n"
        "🔄 自动功能：\n"
        "• 每小时自动检查所有RSS和抖音订阅\n"
        "• 发现新内容时自动推送到绑定频道\n"
        "• 智能去重，避免重复推送\n"
        "• 自动下载并发送视频/图片文件\n"
        "• 自动生成关键词汇总\n\n"
        "✨ 内容展示特性：\n"
        "• 标题、描述、发布时间\n"
        "• 自动提取和展示图片链接\n"
        "• 视频文件下载和发送\n"
        "• HTML标签清理和格式化\n"
        "• 智能控制发送速度，避免刷屏\n\n"
        "💡 使用示例：\n"
        "• /add https://feeds.bbci.co.uk/news/rss.xml @news_channel\n"
        "• /douyin_add https://v.douyin.com/iM5g7LsM/ @douyin_channel\n"
        "• /rsshub_add https://example.com/rss.xml @rss_channel\n"
        "• /list\n"
        "• /douyin_list\n"
        "• /rsshub_list\n"
        "• /news\n\n"
        "🔧 技术支持：\n"
        "项目地址：https://github.com/WeiWenxing/any-rss\n"
        "如有问题请提交Issue或联系管理员"
    )

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

    register_commands(application)
    register_douyin_commands(application)
    register_rsshub_commands(application)

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
        logging.error(f"未找到token对应的bot实例: {token}", exc_info=True)
        return

    # 导入服务模块
    from services.rss.scheduler import run_scheduled_check as rss_run_scheduled_check
    from services.douyin.scheduler import run_scheduled_check as douyin_run_scheduled_check
    from services.rsshub.scheduler import create_rsshub_scheduler

    # 创建RSSHub调度器实例
    rsshub_scheduler = create_rsshub_scheduler()

    while True:
        try:
            # RSS订阅检查 - 使用RSS调度器
            await rss_run_scheduled_check(bot)

            # 抖音订阅检查 - 使用抖音调度器
            await douyin_run_scheduled_check(bot)

            # RSSHub订阅检查 - 使用RSSHub调度器
            await rsshub_scheduler.check_all_rss_updates(bot)

            logging.info("所有订阅源检查完成，等待下一次检查")
            await asyncio.sleep(3600)  # 保持1小时检查间隔
        except Exception as e:
            logging.error(f"检查订阅源更新失败: {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # 出错后等待1分钟再试
