"""
Sitemap调试命令模块

提供Sitemap模块的调试命令，用于开发和测试阶段。
支持通过文本方式调试Sitemap内容。

主要功能：
1. /sitemap-debug-show - 通过文本调试Sitemap内容

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import Optional
from telegram import Update, Message
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, Application
from telegram.error import TelegramError

from .manager import get_sitemap_manager
from .sitemap_parser import create_sitemap_parser
from .sender import create_sitemap_sender


async def sitemap_debug_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sitemap-debug-show 命令

    通过文本方式调试Sitemap内容，支持直接输入XML文本进行解析测试。
    使用正常的发送和解析流程，确保与实际使用场景一致。

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        # 获取命令参数
        if not context.args:
            await update.message.reply_text(
                "❌ 请提供Sitemap XML内容\n"
                "用法: /sitemap-debug-show <XML内容>"
            )
            return

        # 获取XML内容
        xml_content = " ".join(context.args)
        
        # 创建解析器
        parser = create_sitemap_parser()
        
        # 解析XML内容
        try:
            entries = await parser.parse_sitemap_content(xml_content)
            
            if not entries:
                await update.message.reply_text("❌ 未找到任何URL")
                return

            # 构建响应消息
            response = "✅ Sitemap解析成功\n\n"
            response += f"共发现 {len(entries)} 个URL:\n\n"
            
            # 添加每个URL的信息
            for i, entry in enumerate(entries, 1):
                response += f"{i}. {entry.url}\n"
                if entry.last_modified:
                    response += f"   最后修改: {entry.last_modified}\n"
                response += "\n"
            
            # 发送解析结果
            await update.message.reply_text(response)

            # 使用正常的发送流程发送每个URL
            sender = create_sitemap_sender()
            for entry in entries:
                try:
                    # 使用正常的发送流程
                    message_ids = await sender.send_entry(
                        bot=context.bot,
                        chat_id=update.effective_chat.id,
                        url=entry.url,
                        last_modified=entry.last_modified
                    )
                    logging.info(f"发送URL成功: {entry.url}, 消息ID: {message_ids}")
                except Exception as e:
                    logging.error(f"发送URL失败: {entry.url}, 错误: {str(e)}", exc_info=True)
                    await update.message.reply_text(
                        f"❌ 发送URL失败: {entry.url}\n"
                        f"错误信息: {str(e)}"
                    )
            
        except Exception as e:
            logging.error(f"Sitemap解析失败: {str(e)}", exc_info=True)
            await update.message.reply_text(
                f"❌ Sitemap解析失败\n"
                f"错误信息: {str(e)}"
            )
            
    except Exception as e:
        logging.error(f"处理调试命令失败: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ 处理命令失败\n"
            f"错误信息: {str(e)}"
        )


def register_sitemap_debug_commands(application: Application) -> None:
    """
    注册Sitemap调试命令

    Args:
        application: Telegram应用实例
    """
    # 注册调试命令
    application.add_handler(CommandHandler("sitemap_debug_show", sitemap_debug_show_command))
    
 