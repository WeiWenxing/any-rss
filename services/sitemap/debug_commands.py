"""
Sitemap调试命令模块

提供Sitemap模块的调试命令，用于开发和测试阶段。
支持通过文本方式调试Sitemap内容。

主要功能：
1. /sitemap_debug_show - 通过文本调试Sitemap内容

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import Optional
from telegram import Update, Message
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, Application
from telegram.error import TelegramError

from .sitemap_parser import create_sitemap_parser
from .converter import create_sitemap_converter
from .sender import create_sitemap_sender

# 配置日志记录器
logger = logging.getLogger("sitemap.debug")


async def sitemap_debug_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sitemap_debug_show 命令

    通过文本方式调试Sitemap内容，支持直接输入XML文本进行解析测试。
    使用正常的发送和解析流程，确保与实际使用场景一致。

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        logger.info(f"收到调试命令: /sitemap_debug_show, 用户: {update.effective_user.id}")

        # 获取命令参数
        if not context.args:
            logger.warning("未提供XML内容")
            await update.message.reply_text(
                "❌ 请提供Sitemap XML内容\n"
                "用法: /sitemap_debug_show <XML内容>"
            )
            return

        # 获取XML内容
        xml_content = " ".join(context.args)
        logger.info(f"收到XML内容，长度: {len(xml_content)} 字符")

        # 补全XML头部信息
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
{xml_content}
</urlset>"""
        logger.info("补全XML头部信息")

        # 创建解析器
        parser = create_sitemap_parser()
        logger.info("创建Sitemap解析器")

        # 解析XML内容
        try:
            logger.info("开始解析XML内容")
            entries = parser._parse_content(xml_content, "")

            if not entries:
                logger.warning("未找到任何URL")
                await update.message.reply_text("❌ 未找到任何URL")
                return

            logger.info(f"解析成功，找到 {len(entries)} 个URL")

            # 构建响应消息
            response = "✅ Sitemap解析成功\n\n"
            response += f"共发现 {len(entries)} 个URL:\n\n"

            # 添加每个URL的信息
            for i, entry in enumerate(entries, 1):
                response += f"{i}. {entry.url}\n"
                if entry.last_modified:
                    response += f"   最后修改: {entry.last_modified}\n"
                response += "\n"
                logger.debug(f"URL {i}: {entry.url}, 最后修改: {entry.last_modified}")

            # 发送解析结果
            logger.info("发送解析结果")
            await update.message.reply_text(response)

            # 创建转换器
            converter = create_sitemap_converter()
            logger.info("创建Sitemap转换器")

            # 创建发送器
            sender = create_sitemap_sender()
            logger.info("创建Sitemap发送器")

            # 使用正常的发送流程发送每个URL
            for i, entry in enumerate(entries, 1):
                try:
                    logger.info(f"开始发送第 {i}/{len(entries)} 个URL: {entry.url}")

                    # 转换内容
                    content = converter.convert({
                        'url': entry.url,
                        'last_modified': entry.last_modified
                    })

                    # 使用正常的发送流程
                    message_ids = await sender.send_message(
                        bot=context.bot,
                        chat_id=update.effective_chat.id,
                        message=content
                    )
                    logger.info(f"✅ 发送URL成功: {entry.url}, 消息ID: {message_ids}")
                except Exception as e:
                    logger.error(f"❌ 发送URL失败: {entry.url}, 错误: {str(e)}", exc_info=True)
                    await update.message.reply_text(
                        f"❌ 发送URL失败: {entry.url}\n"
                        f"错误信息: {str(e)}"
                    )

            logger.info("所有URL处理完成")

        except Exception as e:
            logger.error(f"❌ Sitemap解析失败: {str(e)}", exc_info=True)
            await update.message.reply_text(
                f"❌ Sitemap解析失败\n"
                f"错误信息: {str(e)}"
            )

    except Exception as e:
        logger.error(f"❌ 处理调试命令失败: {str(e)}", exc_info=True)
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
    logger.info("注册Sitemap调试命令")
    # 注册调试命令
    application.add_handler(CommandHandler("sitemap_debug_show", sitemap_debug_show_command))
    logger.info("✅ Sitemap调试命令注册完成")

