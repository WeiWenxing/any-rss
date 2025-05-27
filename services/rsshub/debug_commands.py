"""
RSSHub调试命令模块
专门用于RSSHub相关的测试和调试功能
"""

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application

from .rss_converter import create_rss_converter
from .rss_parser import create_rss_parser


async def rsshub_debug_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    RSSHub调试版本的show命令，用于测试单个RSSHub条目的格式化和发送
    用法: /rsshub_debug_show <XML数据>
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"🚀 收到RSSHUB_DEBUG_SHOW命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        if not context.args:
            await update.message.reply_text(
                "❌ 请提供RSS item XML数据\n\n"
                "用法: /rsshub_debug_show <XML数据>\n\n"
                "示例:\n"
                '/rsshub_debug_show <item><title>测试标题</title><link>https://example.com</link><description>测试描述</description></item>'
            )
            return

        # 合并所有参数作为XML字符串
        xml_str = " ".join(context.args)
        logging.info(f"📝 RSSHUB_DEBUG_SHOW命令接收到的XML长度: {len(xml_str)} 字符")

        # 发送状态消息
        status_msg = await update.message.reply_text("🔄 开始使用系统RSS解析器解析...")

        # 使用系统的RSSParser解析XML
        try:
            # 构造完整的RSS XML文档
            if not xml_str.strip().startswith('<item'):
                xml_str = f"<item>{xml_str}</item>"

            # 构造完整的RSS文档
            full_rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Debug RSS Feed</title>
        <link>https://debug.example.com</link>
        <description>Debug RSS feed for testing</description>
        {xml_str}
    </channel>
</rss>"""

            logging.info(f"🔧 构造完整RSS文档，长度: {len(full_rss_xml)} 字符")

            # 使用系统RSSParser解析
            parser = create_rss_parser()
            entries = parser._parse_rss_content(full_rss_xml, "debug://test")

            if not entries:
                await status_msg.edit_text("❌ 系统RSS解析器未能解析出任何条目")
                return

            # 取第一个条目
            rss_entry = entries[0]
            logging.info(f"✅ 系统解析成功: {rss_entry.item_id}")

            await status_msg.edit_text(
                f"✅ 系统RSS解析成功！\n"
                f"📋 GUID: {rss_entry.item_id}\n"
                f"📝 标题: {rss_entry.title}\n"
                f"👤 作者: {rss_entry.author or '无'}\n"
                f"📎 媒体附件: {len(rss_entry.enclosures)} 个"
            )

        except Exception as parse_error:
            logging.error(f"❌ 系统RSS解析失败: {str(parse_error)}", exc_info=True)
            await status_msg.edit_text(f"❌ 系统RSS解析失败: {str(parse_error)}")
            return

        # 使用系统转换器转换为TelegramMessage并发送
        try:
            # 创建RSS转换器
            converter = create_rss_converter()

            # 转换为TelegramMessage
            telegram_message = converter.convert(rss_entry)

                        # 使用统一发送器发送消息
            from services.common.unified_sender import UnifiedTelegramSender
            
            sender = UnifiedTelegramSender()

            # 发送消息
            sent_messages = await sender.send_message(
                bot=context.bot,
                chat_id=chat_id,
                message=telegram_message
            )
            success = len(sent_messages) > 0

            if success:
                await status_msg.edit_text(f"✅ RSSHub系统调试发送成功！")
                logging.info(f"🎉 RSSHUB_DEBUG_SHOW命令执行成功: {rss_entry.item_id}")
            else:
                await status_msg.edit_text(f"❌ 发送失败，请检查日志")
                logging.error(f"💥 发送RSSHub内容失败: {rss_entry.item_id}")

        except Exception as send_error:
            logging.error(f"💥 发送RSSHub内容失败: {str(send_error)}", exc_info=True)
            await status_msg.edit_text(f"❌ 发送失败: {str(send_error)}")

    except Exception as e:
        logging.error(f"💥 RSSHUB_DEBUG_SHOW命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


def register_rsshub_debug_commands(application: Application) -> None:
    """注册RSSHub调试命令"""
    application.add_handler(CommandHandler("rsshub_debug_show", rsshub_debug_show_command))
    logging.info("✅ RSSHub调试命令注册完成")