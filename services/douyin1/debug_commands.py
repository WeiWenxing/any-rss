"""
调试命令模块

该模块提供模块的调试和管理命令，用于开发和维护。

主要功能：
1. 动态调试命令生成（基于模块名自动生成命令前缀）
2. 显示单个内容项

作者: Assistant
创建时间: 2024年
"""

import logging
import json
from telegram import Update
from telegram.ext import ContextTypes, Application, CommandHandler, MessageHandler, filters

from .commands import get_command_handler
from .converter import create_douyin_converter
from services.common.unified_sender import UnifiedTelegramSender
from . import MODULE_NAME, MODULE_DISPLAY_NAME, get_command_names


async def handle_debug_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理调试显示命令（动态生成）- 显示单个内容项

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        user = update.message.from_user
        command_names = get_command_names()
        debug_show_cmd = command_names["debug_show"]

        logging.info(f"👁️ 收到{debug_show_cmd}命令 - 用户: {user.username}(ID:{user.id})")

        # 参数验证
        if not context.args:
            await update.message.reply_text(f"用法: /{debug_show_cmd} <链接>")
            return

        source_url = context.args[0].strip()
        logging.info(f"👁️ 显示内容项: {source_url}")

        # 获取命令处理器
        handler = get_command_handler()

        # 基本URL检查（简化版）
        if not source_url or not source_url.startswith(('http://', 'https://')):
            await update.message.reply_text("❌ 请提供有效的链接")
            return

        # 发送处理中消息
        processing_message = await update.message.reply_text("⏳ 获取内容中...")

        try:
            # 获取最新内容
            success, message, content_list = handler.manager.fetch_latest_content(source_url)

            if not success:
                logging.error(f"❌ 获取内容失败: {message}")
                await processing_message.edit_text(f"❌ 获取失败: {message}")
                return

            if not content_list:
                logging.info(f"📭 没有找到内容: {source_url}")
                await processing_message.edit_text("📭 没有找到内容")
                return

            # 显示第一个内容项
            first_item = content_list[0]

            # 记录详细信息到日志
            logging.info(f"👁️ 内容项详情:")
            logging.info(f"  标题: {first_item.get('title', 'Unknown')}")
            logging.info(f"  作者: {first_item.get('author', 'Unknown')}")
            logging.info(f"  链接: {first_item.get('url', source_url)}")
            logging.info(f"  内容ID: {handler.manager.generate_content_id(first_item)}")
            logging.info(f"  发布时间: {first_item.get('publish_time', 'Unknown')}")
            logging.info(f"  总内容数: {len(content_list)}")

            # 简化的消息显示
            await processing_message.edit_text(
                f"✅ 找到 {len(content_list)} 个内容\n"
                f"标题: {first_item.get('title', 'Unknown')[:50]}{'...' if len(first_item.get('title', '')) > 50 else ''}"
            )

        except Exception as e:
            logging.error(f"❌ 显示内容项失败: {e}", exc_info=True)
            await processing_message.edit_text(f"❌ 显示失败: {str(e)}")

    except Exception as e:
        logging.error(f"❌ 处理调试显示命令时发生错误: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")


async def handle_debug_file_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理带有debug_file标题的文档消息 - 测试converter和统一发送器

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        # 检查是否是文档消息且caption包含debug_file命令
        if not update.message.document:
            return

        caption = update.message.caption or ""
        debug_file_cmd = f"{MODULE_NAME}_debug_file"

        if debug_file_cmd not in caption:
            return

        user = update.message.from_user
        logging.info(f"📄 收到{debug_file_cmd}文件消息 - 用户: {user.username}(ID:{user.id})")

        # 文档已经在上面检查过了，直接处理

        # 发送简单的处理中消息
        processing_message = await update.message.reply_text("⏳ 处理中...")

        try:
            # 下载文件
            file = await context.bot.get_file(update.message.document.file_id)
            file_content = await file.download_as_bytearray()

            # 解析JSON
            try:
                video_data = json.loads(file_content.decode('utf-8'))
                logging.info(f"📄 成功解析JSON文件，aweme_id: {video_data.get('aweme_id', 'unknown')}")
            except json.JSONDecodeError as e:
                logging.error(f"❌ JSON文件格式错误: {e}")
                await processing_message.edit_text(f"❌ JSON格式错误: {str(e)}")
                return

            # 创建converter并转换
            converter = create_douyin_converter()
            try:
                telegram_message = converter.convert(video_data)
                logging.info(f"✅ converter转换成功，文本长度: {len(telegram_message.text)}, 媒体数量: {telegram_message.media_count}")

            except Exception as e:
                logging.error(f"❌ converter转换失败: {e}", exc_info=True)
                await processing_message.edit_text(f"❌ 转换失败: {str(e)}")
                return

            # 获取目标频道
            # 直接使用当前聊天作为目标频道
            target_channels = [str(update.effective_chat.id)]
            if not target_channels:
                await processing_message.edit_text(
                    f"❌ JSON文件中缺少target_channels字段\n"
                    f"请在JSON中添加target_channels数组"
                )
                return

            # 使用统一发送器发送消息
            sender = UnifiedTelegramSender()
            try:
                # 发送到指定频道
                success_count = 0
                total_channels = len(target_channels)

                for channel in target_channels:
                    try:
                        sent_messages = await sender.send_message(
                            bot=context.bot,
                            chat_id=channel,
                            message=telegram_message
                        )
                        if sent_messages:
                            success_count += 1
                            logging.info(f"✅ 成功发送到频道: {channel}, 发送了{len(sent_messages)}条消息")
                        else:
                            logging.error(f"❌ 发送到频道失败: {channel}")
                    except Exception as e:
                        logging.error(f"❌ 发送到频道{channel}时发生错误: {str(e)}")

                # 更新结果
                await processing_message.edit_text(
                    f"✅ 测试完成: {success_count}/{total_channels} 成功"
                )

            except Exception as e:
                logging.error(f"❌ 统一发送器发送失败: {e}", exc_info=True)
                await processing_message.edit_text(f"❌ 发送失败: {str(e)}")

        except Exception as e:
            logging.error(f"❌ 处理文件失败: {e}", exc_info=True)
            await processing_message.edit_text(f"❌ 处理失败: {str(e)}")

    except Exception as e:
        logging.error(f"❌ 处理调试文件消息时发生错误: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理文件时发生错误: {str(e)}")


def register_debug_commands(application: Application) -> None:
    """
    注册调试命令处理器（动态生成命令名称）

    Args:
        application: Telegram应用实例
    """
    # 获取动态生成的命令名称
    command_names = get_command_names()

    # 注册debug show命令（使用动态生成的命令名称）
    application.add_handler(CommandHandler(command_names["debug_show"], handle_debug_show_command))

    # 注册文档消息处理器，检测caption中的debug_file命令
    document_handler = MessageHandler(filters.Document.ALL, handle_debug_file_message)
    application.add_handler(document_handler)

    debug_file_cmd = f"{MODULE_NAME}_debug_file"

    logging.info(f"{MODULE_DISPLAY_NAME}调试命令处理器注册完成")
    logging.info(f"📋 已注册调试命令: /{command_names['debug_show']}")
    logging.info(f"🔧 已注册调试文件处理器: 检测caption中的{debug_file_cmd}")