"""
RSS调试命令模块
专门用于各种测试和调试功能
"""

import logging
import os
import tempfile
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from telegram import Bot, InputMediaPhoto, InputMediaVideo, Update
from telegram.ext import ContextTypes

from .entry_processor import extract_entry_info
from .message_sender import extract_and_clean_media
from .network_utils import get_network_manager


async def debug_show_command(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试版本的show命令，支持下载媒体到本地再上传
    用法: /debug_show <RSS条目XML>
    """
    try:
        logging.info("DEBUG_SHOW命令开始执行")

        if not context.args:
            await update.message.reply_text("❌ 请提供RSS条目XML内容\n用法: /debug_show <RSS条目XML>")
            return

        xml_content = " ".join(context.args)
        logging.info(f"DEBUG_SHOW命令接收到的XML内容长度: {len(xml_content)} 字符")

        # 解析条目信息
        entry_info = extract_entry_info(xml_content)
        if not entry_info:
            await update.message.reply_text("❌ 无法解析RSS条目信息")
            return

        title = entry_info.get('title', 'Unknown')
        content = entry_info.get('content', '')

        logging.info(f"解析到标题: {title}")

        # 提取媒体信息
        media_list = extract_and_clean_media(content)
        logging.info(f"提取到 {len(media_list)} 个媒体文件")

        if not media_list:
            await update.message.reply_text(f"📰 {title}\n\n❌ 未找到媒体文件")
            return

        # 发送状态消息
        status_msg = await update.message.reply_text(f"🔄 开始下载 {len(media_list)} 个媒体文件...")

        # 使用新的媒体策略系统
        from .media_strategy import create_media_strategy_manager

        try:
            # 创建媒体策略管理器和发送器
            strategy_manager, media_sender = create_media_strategy_manager(context.bot)

            # 分析媒体文件
            analyzed_media = strategy_manager.analyze_media_files(media_list)

            # 发送媒体组
            success = await media_sender.send_media_group_with_strategy(
                chat_id=update.effective_chat.id,
                media_list=analyzed_media,
                caption=title
            )

            if success:
                await status_msg.edit_text(f"✅ 成功发送 {len(analyzed_media)} 个媒体文件")
            else:
                await status_msg.edit_text(f"❌ 媒体发送失败")

        except Exception as e:
            logging.error(f"使用媒体策略系统发送失败: {str(e)}", exc_info=True)
            await status_msg.edit_text(f"❌ 媒体发送失败: {str(e)}")

    except Exception as e:
        logging.error(f"DEBUG_SHOW命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def debug_media_info_command(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试媒体信息命令，显示媒体文件的详细信息
    用法: /debug_media <媒体URL>
    """
    try:
        if not context.args:
            await update.message.reply_text("❌ 请提供媒体URL\n用法: /debug_media <媒体URL>")
            return

        media_url = context.args[0]
        logging.info(f"DEBUG_MEDIA命令检查URL: {media_url}")

        # 发送状态消息
        status_msg = await update.message.reply_text("🔄 正在检查媒体信息...")

        # 检查媒体信息
        try:
            network_manager = get_network_manager()
            accessible, error_msg, size_mb = network_manager.check_url_accessibility(media_url, use_cache=False)

            info_text = f"📊 媒体信息分析\n"
            info_text += f"🔗 URL: {media_url}\n"

            if accessible:
                info_text += f"📡 状态码: 200\n"
                info_text += f"📏 大小: {size_mb:.2f}MB\n"

                if size_mb > 50:
                    info_text += "⚠️ 警告: 超过Telegram 50MB限制\n"
                elif size_mb == 0:
                    info_text += "📏 大小: 未知\n"
            else:
                info_text += f"❌ 无法访问: {error_msg}\n"

            await status_msg.edit_text(info_text)

        except Exception as e:
            error_text = f"❌ 检查媒体信息失败\n"
            error_text += f"🔗 URL: {media_url}\n"
            error_text += f"💥 错误: {str(e)}"
            await status_msg.edit_text(error_text)

    except Exception as e:
        logging.error(f"DEBUG_MEDIA命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def debug_download_test_command(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试下载测试命令，测试下载媒体文件
    用法: /debug_download <媒体URL>
    """
    file_path = None  # 初始化文件路径变量
    try:
        if not context.args:
            await update.message.reply_text("❌ 请提供媒体URL\n用法: /debug_download <媒体URL>")
            return

        media_url = context.args[0]
        logging.info(f"DEBUG_DOWNLOAD命令测试下载: {media_url}")

        # 发送状态消息
        status_msg = await update.message.reply_text("🔄 正在测试下载...")
        logging.info("✅ 状态消息发送成功")

        # 判断媒体类型
        media_type = 'video' if any(ext in media_url.lower() for ext in ['.mp4', '.mov', '.avi']) else 'image'
        logging.info(f"📁 检测到媒体类型: {media_type}")

        # 下载文件
        logging.info("🔄 开始下载文件...")

        # 使用网络管理器下载文件
        from .network_utils import get_network_manager
        import tempfile
        import os
        from urllib.parse import urlparse

        # 解析URL获取文件扩展名
        parsed_url = urlparse(media_url)
        path_parts = parsed_url.path.split('.')

        if len(path_parts) > 1:
            extension = path_parts[-1].split('?')[0]  # 去掉查询参数
        else:
            # 根据媒体类型设置默认扩展名
            extension = 'mp4' if media_type == 'video' else 'jpg'

        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        temp_filename = f"telegram_media_{os.getpid()}_{id(media_url)}.{extension}"
        file_path = os.path.join(temp_dir, temp_filename)

        # 使用网络管理器下载文件
        network_manager = get_network_manager()
        success, error_msg = network_manager.download_media_file(media_url, file_path)

        if success:
            logging.info(f"📥 下载成功: {file_path}")
        else:
            logging.error(f"📥 下载失败: {error_msg}")
            file_path = None

        if file_path:
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            logging.info(f"📏 文件大小: {size_mb:.2f}MB")

            # 更新状态消息 - 分步进行，避免一次性更新失败
            try:
                await status_msg.edit_text(f"✅ 下载成功\n📁 文件: {os.path.basename(file_path)}\n📏 大小: {size_mb:.2f}MB")
                logging.info("✅ 状态消息更新成功 - 下载完成")
            except Exception as edit_error:
                logging.error(f"❌ 状态消息更新失败: {str(edit_error)}")
                # 继续执行，不因为消息更新失败而中断

            # 更新上传状态
            try:
                await status_msg.edit_text(f"✅ 下载成功\n📁 文件: {os.path.basename(file_path)}\n📏 大小: {size_mb:.2f}MB\n🔄 正在上传到Telegram...")
                logging.info("✅ 状态消息更新成功 - 开始上传")
            except Exception as edit_error:
                logging.error(f"❌ 上传状态消息更新失败: {str(edit_error)}")

            # 尝试发送文件
            logging.info("🚀 开始尝试上传文件到Telegram...")
            try:
                with open(file_path, 'rb') as f:
                    logging.info(f"📂 文件已打开，准备发送{media_type}")
                    if media_type == 'video':
                        logging.info("📹 发送视频文件...")
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=f,
                            caption=f"📹 测试视频上传\n📏 大小: {size_mb:.2f}MB"
                        )
                        logging.info("✅ 视频文件发送成功")
                    else:
                        logging.info("🖼️ 发送图片文件...")
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=f,
                            caption=f"🖼️ 测试图片上传\n📏 大小: {size_mb:.2f}MB"
                        )
                        logging.info("✅ 图片文件发送成功")

                # 更新最终状态
                try:
                    await status_msg.edit_text(f"✅ 下载并上传成功\n📏 大小: {size_mb:.2f}MB")
                    logging.info("✅ 最终状态消息更新成功")
                except Exception as edit_error:
                    logging.error(f"❌ 最终状态消息更新失败: {str(edit_error)}")

            except Exception as upload_error:
                error_msg = str(upload_error)
                logging.error(f"❌ 文件上传失败: {error_msg}", exc_info=True)
                try:
                    await status_msg.edit_text(f"✅ 下载成功，❌ 上传失败\n📏 大小: {size_mb:.2f}MB\n💥 错误: {error_msg}")
                except Exception as edit_error:
                    logging.error(f"❌ 错误状态消息更新失败: {str(edit_error)}")

        else:
            logging.error("❌ 文件下载失败")
            try:
                await status_msg.edit_text("❌ 下载失败")
            except Exception as edit_error:
                logging.error(f"❌ 失败状态消息更新失败: {str(edit_error)}")

    except Exception as e:
        logging.error(f"DEBUG_DOWNLOAD命令执行失败: {str(e)}", exc_info=True)
        try:
            await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")
        except:
            logging.error("❌ 连错误消息都发送失败")
    finally:
        # 清理文件
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"🗑️ 清理临时文件: {file_path}")
            except Exception as cleanup_error:
                logging.error(f"❌ 清理临时文件失败: {str(cleanup_error)}")


async def debug_send_url_command(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试URL发送命令，直接用URL发送媒体（不下载到本地）
    用法: /debug_send_url <媒体URL>
    """
    try:
        if not context.args:
            await update.message.reply_text("❌ 请提供媒体URL\n用法: /debug_send_url <媒体URL>")
            return

        media_url = context.args[0]
        logging.info(f"DEBUG_SEND_URL命令直接发送: {media_url}")

        # 发送状态消息
        status_msg = await update.message.reply_text("🔄 正在直接发送媒体URL...")

        # 判断媒体类型
        media_type = 'video' if any(ext in media_url.lower() for ext in ['.mp4', '.mov', '.avi']) else 'image'
        media_type_name = "视频" if media_type == 'video' else "图片"

        # 尝试直接发送URL
        try:
            if media_type == 'video':
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=media_url,
                    caption=f"📹 直接发送{media_type_name}\n🔗 URL: {media_url}"
                )
            else:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=media_url,
                    caption=f"🖼️ 直接发送{media_type_name}\n🔗 URL: {media_url}"
                )

            await status_msg.edit_text(f"✅ 成功直接发送{media_type_name}")
            logging.info(f"✅ 成功直接发送{media_type_name}: {media_url}")

        except Exception as send_error:
            error_msg = str(send_error)
            await status_msg.edit_text(f"❌ 直接发送失败\n💥 错误: {error_msg}")
            logging.error(f"❌ 直接发送{media_type_name}失败: {media_url}, 错误: {error_msg}", exc_info=True)

    except Exception as e:
        logging.error(f"DEBUG_SEND_URL命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def debug_api_status_command(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试API状态命令，检查当前使用的API服务器和配置
    用法: /debug_api
    """
    try:
        logging.info("DEBUG_API命令检查API状态")

        # 获取Bot实例信息
        bot = context.bot
        logging.info(f"🤖 获取到Bot实例: {type(bot)}")

        # 检查Bot API配置
        api_info = "🔍 Bot API 配置信息\n\n"

        # 获取base_url信息
        logging.info("🔍 检查Bot的base_url属性...")
        if hasattr(bot, '_base_url'):
            base_url = bot._base_url
            logging.info(f"📍 Bot._base_url = {base_url}")
            api_info += f"📍 API地址: {base_url}\n"

            if "localhost" in base_url or "127.0.0.1" in base_url:
                logging.info("🏠 检测到使用本地Bot API服务器")
                api_info += "🏠 使用本地Bot API服务器\n"
                api_info += "✅ 支持2GB大文件上传\n"
            else:
                logging.info("🌐 检测到使用官方Bot API服务器")
                api_info += "🌐 使用官方Bot API服务器\n"
                api_info += "⚠️ 文件大小限制20MB\n"
        else:
            logging.info("❌ Bot没有_base_url属性，使用默认官方API")
            api_info += "📍 API地址: 官方API (默认)\n"
            api_info += "🌐 使用官方Bot API服务器\n"
            api_info += "⚠️ 文件大小限制20MB\n"

        # 获取file_url信息
        logging.info("🔍 检查Bot的base_file_url属性...")
        if hasattr(bot, '_base_file_url'):
            base_file_url = bot._base_file_url
            logging.info(f"📁 Bot._base_file_url = {base_file_url}")
            api_info += f"📁 文件地址: {base_file_url}\n"
        else:
            logging.info("❌ Bot没有_base_file_url属性，使用默认官方文件API")
            api_info += "📁 文件地址: 官方文件API (默认)\n"

        # 检查环境配置
        logging.info("🔍 检查环境配置...")
        from core.config import telegram_config
        api_base_url = telegram_config.get("api_base_url")
        logging.info(f"🔧 telegram_config.api_base_url = {api_base_url}")

        api_info += f"\n🔧 环境配置:\n"
        if api_base_url:
            api_info += f"   TELEGRAM_API_BASE_URL: {api_base_url}\n"
            api_info += "   ✅ 已配置本地API\n"
            logging.info("✅ 环境变量已配置本地API")
        else:
            api_info += "   TELEGRAM_API_BASE_URL: 未设置\n"
            api_info += "   ❌ 未配置本地API\n"
            logging.info("❌ 环境变量未配置本地API")

        # 测试本地API连接（如果配置了）
        if api_base_url:
            api_info += f"\n🔗 本地API连接测试:\n"
            logging.info(f"🔗 开始测试本地API连接: {api_base_url}")
            try:
                test_url = f"{api_base_url}/"
                logging.info(f"📡 发送请求到: {test_url}")

                # 使用网络管理器进行连接测试
                network_manager = get_network_manager()
                accessible, error_msg, _ = network_manager.check_url_accessibility(test_url, use_cache=False)

                if accessible:
                    api_info += "   ✅ 本地API服务器连接正常\n"
                    logging.info("✅ 本地API服务器连接测试成功")
                else:
                    api_info += f"   ❌ 本地API服务器连接失败: {error_msg}\n"
                    logging.warning(f"⚠️ 本地API服务器连接失败: {error_msg}")
            except Exception as conn_error:
                api_info += f"   ❌ 本地API服务器连接失败: {str(conn_error)}\n"
                logging.error(f"❌ 本地API服务器连接失败: {str(conn_error)}")

        # 获取Bot信息
        logging.info("🤖 获取Bot基本信息...")
        try:
            bot_info = await bot.get_me()
            logging.info(f"🤖 Bot信息获取成功: @{bot_info.username} (ID: {bot_info.id})")
            api_info += f"\n🤖 Bot信息:\n"
            api_info += f"   用户名: @{bot_info.username}\n"
            api_info += f"   ID: {bot_info.id}\n"
            api_info += f"   名称: {bot_info.first_name}\n"
        except Exception as bot_error:
            api_info += f"\n❌ 获取Bot信息失败: {str(bot_error)}\n"
            logging.error(f"❌ 获取Bot信息失败: {str(bot_error)}")

        # 发送信息
        logging.info("📤 发送API状态信息...")
        await update.message.reply_text(api_info, disable_web_page_preview=True)
        logging.info("✅ API状态信息发送成功")

    except Exception as e:
        logging.error(f"DEBUG_API命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def debug_media_strategy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    测试新的媒体策略系统
    """
    try:
        chat_id = str(update.effective_chat.id)
        bot = context.bot

        # 发送开始消息
        await bot.send_message(chat_id=chat_id, text="🧪 开始测试媒体策略系统...")

        # 测试媒体列表（包含不同大小的文件）
        test_media_list = [
            {
                'url': 'https://picsum.photos/800/600.jpg',  # 小图片
                'type': 'image'
            },
            {
                'url': 'https://picsum.photos/1920/1080.jpg',  # 中等图片
                'type': 'image'
            },
            {
                'url': 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4',  # 小视频
                'type': 'video'
            }
        ]

        # 导入媒体策略系统
        from .media_strategy import create_media_strategy_manager

        # 创建策略管理器和发送器
        strategy_manager, media_sender = create_media_strategy_manager(bot)

        # 分析媒体文件
        analyzed_media = strategy_manager.analyze_media_files(test_media_list)

        # 发送分析结果
        analysis_text = "📊 媒体策略分析结果:\n\n"
        for i, media_info in enumerate(analyzed_media, 1):
            strategy_name = media_info.send_strategy.value
            size_info = f"{media_info.size_mb:.1f}MB" if media_info.size_mb > 0 else "大小未知"
            accessible_status = "✅" if media_info.accessible else "❌"

            analysis_text += f"{i}. {media_info.media_type} - {size_info} {accessible_status}\n"
            analysis_text += f"   策略: {strategy_name}\n"
            analysis_text += f"   URL: {media_info.url[:50]}...\n\n"

        await bot.send_message(chat_id=chat_id, text=analysis_text)

        # 测试发送
        sendable_media = [m for m in analyzed_media if m.send_strategy.value != 'text_fallback']
        if sendable_media:
            await bot.send_message(chat_id=chat_id, text="🚀 开始测试发送...")

            success = await media_sender.send_media_group_with_strategy(
                chat_id=chat_id,
                media_list=sendable_media,
                caption="🧪 媒体策略系统测试"
            )

            if success:
                await bot.send_message(chat_id=chat_id, text="✅ 媒体策略系统测试成功！")
            else:
                await bot.send_message(chat_id=chat_id, text="❌ 媒体策略系统测试失败")
        else:
            await bot.send_message(chat_id=chat_id, text="❌ 没有可发送的媒体文件")

    except Exception as e:
        logging.error(f"媒体策略测试失败: {str(e)}", exc_info=True)
        await bot.send_message(chat_id=chat_id, text=f"❌ 测试失败: {str(e)}")


def register_debug_commands(application):
    """注册调试命令"""
    from telegram.ext import CommandHandler

    application.add_handler(CommandHandler("debug_show", debug_show_command))
    application.add_handler(CommandHandler("debug_media", debug_media_info_command))
    application.add_handler(CommandHandler("debug_download", debug_download_test_command))
    application.add_handler(CommandHandler("debug_send_url", debug_send_url_command))
    application.add_handler(CommandHandler("debug_api", debug_api_status_command))
    application.add_handler(CommandHandler("debug_media_strategy", debug_media_strategy_command))

    logging.info("✅ 调试命令注册完成")