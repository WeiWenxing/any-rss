"""
Sample调试命令模块

该模块提供Sample模块的调试和管理命令，用于开发和维护。

主要功能：
1. 显示单个样本内容项

作者: Assistant
创建时间: 2024年
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, Application, CommandHandler

from .commands import get_sample_command_handler


async def sample_debug_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sample_debug_show 命令 - 显示单个样本内容项

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    try:
        user = update.message.from_user
        logging.info(f"👁️ 收到sample_debug_show命令 - 用户: {user.username}(ID:{user.id})")

        # 参数验证
        if not context.args:
            await update.message.reply_text(
                "👁️ 显示样本内容项\n\n"
                "用法: /sample_debug_show <样本链接>\n\n"
                "示例:\n"
                "/sample_debug_show https://www.sample.com/user/MS4wLjABAAAA...\n"
                "/sample_debug_show https://v.sample.com/iM5g7LsM/"
            )
            return

        sample_url = context.args[0].strip()
        logging.info(f"👁️ 显示内容项: {sample_url}")

        # 获取命令处理器
        handler = get_sample_command_handler()
        
        # 基本URL检查（简化版）
        if not sample_url or not sample_url.startswith(('http://', 'https://')):
            await update.message.reply_text("❌ 请提供有效的样本链接")
            return

        # 发送处理中消息
        processing_message = await update.message.reply_text(
            f"👁️ 正在获取内容信息...\n"
            f"🔗 链接: {sample_url}\n"
            f"⏳ 请稍候..."
        )

        try:
            # 获取最新内容
            success, message, content_list = handler.manager.fetch_latest_content(sample_url)
            
            if not success:
                await processing_message.edit_text(
                    f"❌ 获取内容失败\n"
                    f"🔗 链接: {sample_url}\n"
                    f"❌ 错误: {message}"
                )
                return
            
            if not content_list:
                await processing_message.edit_text(
                    f"📭 没有找到内容\n"
                    f"🔗 链接: {sample_url}\n"
                    f"💡 该账号可能没有发布内容或链接无效"
                )
                return
            
            # 显示第一个内容项
            first_item = content_list[0]
            
            # 构建显示信息
            display_text = (
                f"👁️ 样本内容项详情\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎵 标题: {first_item.get('title', 'Unknown')}\n"
                f"👤 作者: {first_item.get('author', 'Unknown')}\n"
                f"🔗 链接: {first_item.get('url', sample_url)}\n"
                f"🆔 内容ID: {handler.manager.generate_content_id(first_item)}\n"
                f"📅 发布时间: {first_item.get('publish_time', 'Unknown')}\n\n"
                f"📝 描述:\n{first_item.get('description', '无描述')}\n\n"
                f"🎬 媒体信息:\n"
                f"  • 视频链接: {first_item.get('video_url', '无')}\n"
                f"  • 封面链接: {first_item.get('cover_url', '无')}\n\n"
                f"📊 统计信息:\n"
                f"  • 总内容数: {len(content_list)}\n"
                f"  • 显示: 第1个内容项\n\n"
                f"💡 提示: 这是模拟数据，实际功能待开发"
            )
            
            await processing_message.edit_text(display_text)
            
        except Exception as e:
            logging.error(f"❌ 显示内容项失败: {e}", exc_info=True)
            await processing_message.edit_text(
                f"❌ 显示内容项失败\n"
                f"🔗 链接: {sample_url}\n"
                f"❌ 错误: {str(e)}"
            )

    except Exception as e:
        logging.error(f"❌ 处理sample_debug_show命令时发生错误: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")


def register_sample_debug_commands(application: Application) -> None:
    """
    注册Sample调试命令处理器

    Args:
        application: Telegram应用实例
    """
    # 注册debug show命令
    application.add_handler(CommandHandler("sample_debug_show", sample_debug_show_command))

    logging.info("Sample调试命令处理器注册完成") 