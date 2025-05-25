"""
RSS调试命令模块
专门用于各种测试和调试功能
"""

import logging
import os
import tempfile
import asyncio
import requests
from pathlib import Path
from urllib.parse import urlparse
from telegram import Bot, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes

from .entry_processor import extract_entry_info
from .message_sender import extract_and_clean_media


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

        # 下载媒体文件到本地
        downloaded_files = []
        for i, media_info in enumerate(media_list, 1):
            try:
                await status_msg.edit_text(f"🔄 正在下载媒体 {i}/{len(media_list)}...")

                file_path = await download_media_file(media_info['url'], media_info['type'])
                if file_path:
                    downloaded_files.append({
                        'path': file_path,
                        'type': media_info['type'],
                        'original_url': media_info['url']
                    })
                    logging.info(f"✅ 媒体 {i} 下载成功: {file_path}")
                else:
                    logging.error(f"❌ 媒体 {i} 下载失败: {media_info['url']}")

            except Exception as e:
                logging.error(f"下载媒体 {i} 时出错: {str(e)}", exc_info=True)

        if not downloaded_files:
            await status_msg.edit_text("❌ 所有媒体文件下载失败")
            return

        # 尝试发送下载的媒体文件
        await status_msg.edit_text(f"📤 开始上传 {len(downloaded_files)} 个媒体文件...")

        try:
            await send_downloaded_media_group(
                context.bot,
                update.effective_chat.id,
                title,
                downloaded_files
            )
            await status_msg.edit_text(f"✅ 成功发送 {len(downloaded_files)} 个媒体文件")

        except Exception as e:
            logging.error(f"发送媒体组失败: {str(e)}", exc_info=True)
            await status_msg.edit_text(f"❌ 媒体组发送失败，尝试逐个发送...")

            # 降级：逐个发送
            success_count = 0
            for i, file_info in enumerate(downloaded_files, 1):
                try:
                    await send_single_media_file(
                        context.bot,
                        update.effective_chat.id,
                        file_info,
                        f"{title} ({i}/{len(downloaded_files)})"
                    )
                    success_count += 1
                except Exception as single_error:
                    logging.error(f"发送单个媒体失败: {str(single_error)}", exc_info=True)

            await status_msg.edit_text(f"✅ 成功发送 {success_count}/{len(downloaded_files)} 个媒体文件")

    except Exception as e:
        logging.error(f"DEBUG_SHOW命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")

    finally:
        # 清理临时文件
        cleanup_temp_files(downloaded_files if 'downloaded_files' in locals() else [])


async def download_media_file(url: str, media_type: str) -> str | None:
    """
    下载媒体文件到临时目录

    Args:
        url: 媒体URL
        media_type: 媒体类型 ('image' 或 'video')

    Returns:
        str | None: 下载的文件路径，失败返回None
    """
    try:
        # 解析URL获取文件扩展名
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('.')

        if len(path_parts) > 1:
            extension = path_parts[-1].split('?')[0]  # 去掉查询参数
        else:
            # 根据媒体类型设置默认扩展名
            extension = 'mp4' if media_type == 'video' else 'jpg'

        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        temp_filename = f"telegram_media_{os.getpid()}_{id(url)}.{extension}"
        temp_path = os.path.join(temp_dir, temp_filename)

        # 设置请求头（与message_sender.py保持一致）
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        # 下载文件
        logging.info(f"开始下载媒体文件: {url}")
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()

        # 检查文件大小
        content_length = response.headers.get('content-length')
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            logging.info(f"媒体文件大小: {size_mb:.2f}MB")

            # Telegram文件大小限制检查
            if size_mb > 50:  # 50MB限制
                logging.warning(f"文件过大 ({size_mb:.2f}MB)，可能上传失败")

        # 写入文件
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        file_size = os.path.getsize(temp_path)
        logging.info(f"文件下载完成: {temp_path}, 大小: {file_size / (1024*1024):.2f}MB")

        return temp_path

    except Exception as e:
        logging.error(f"下载媒体文件失败: {url}, 错误: {str(e)}", exc_info=True)
        return None


async def send_downloaded_media_group(
    bot: Bot,
    chat_id: str,
    title: str,
    downloaded_files: list[dict]
) -> None:
    """
    发送下载的媒体文件组

    Args:
        bot: Telegram Bot实例
        chat_id: 目标聊天ID
        title: 标题
        downloaded_files: 下载的文件信息列表
    """
    if not downloaded_files:
        return

    # 构建媒体组
    media_group = []

    for i, file_info in enumerate(downloaded_files):
        file_path = file_info['path']
        media_type = file_info['type']

        # 读取文件内容
        with open(file_path, 'rb') as f:
            file_content = f.read()

        if media_type == 'video':
            media_item = InputMediaVideo(
                media=file_content,
                caption=title if i == 0 else None  # 只在第一个媒体上添加标题
            )
        else:  # image
            media_item = InputMediaPhoto(
                media=file_content,
                caption=title if i == 0 else None  # 只在第一个媒体上添加标题
            )

        media_group.append(media_item)

    # 发送媒体组
    await bot.send_media_group(chat_id=chat_id, media=media_group)
    logging.info(f"✅ 成功发送媒体组，包含 {len(media_group)} 个文件")


async def send_single_media_file(
    bot: Bot,
    chat_id: str,
    file_info: dict,
    caption: str
) -> None:
    """
    发送单个媒体文件

    Args:
        bot: Telegram Bot实例
        chat_id: 目标聊天ID
        file_info: 文件信息
        caption: 标题
    """
    file_path = file_info['path']
    media_type = file_info['type']

    with open(file_path, 'rb') as f:
        if media_type == 'video':
            await bot.send_video(chat_id=chat_id, video=f, caption=caption)
        else:  # image
            await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)

    logging.info(f"✅ 成功发送单个{media_type}: {file_path}")


def cleanup_temp_files(downloaded_files: list[dict]) -> None:
    """
    清理临时文件

    Args:
        downloaded_files: 下载的文件信息列表
    """
    for file_info in downloaded_files:
        try:
            file_path = file_info['path']
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"🗑️ 清理临时文件: {file_path}")
        except Exception as e:
            logging.error(f"清理临时文件失败: {str(e)}", exc_info=True)


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
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }

            response = requests.head(media_url, headers=headers, timeout=10, allow_redirects=True)

            info_text = f"📊 媒体信息分析\n"
            info_text += f"🔗 URL: {media_url}\n"
            info_text += f"📡 状态码: {response.status_code}\n"

            if response.status_code == 200:
                content_type = response.headers.get('content-type', 'Unknown')
                content_length = response.headers.get('content-length')

                info_text += f"📄 类型: {content_type}\n"

                if content_length:
                    size_bytes = int(content_length)
                    size_mb = size_bytes / (1024 * 1024)
                    info_text += f"📏 大小: {size_mb:.2f}MB ({size_bytes:,} bytes)\n"

                    if size_mb > 50:
                        info_text += "⚠️ 警告: 超过Telegram 50MB限制\n"
                else:
                    info_text += "📏 大小: 未知\n"

                # 显示重要的响应头
                info_text += "\n📋 响应头:\n"
                important_headers = ['content-type', 'content-length', 'server', 'cache-control', 'expires']
                for header in important_headers:
                    value = response.headers.get(header)
                    if value:
                        info_text += f"  {header}: {value}\n"

            else:
                info_text += f"❌ 无法访问媒体文件\n"

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
    try:
        if not context.args:
            await update.message.reply_text("❌ 请提供媒体URL\n用法: /debug_download <媒体URL>")
            return

        media_url = context.args[0]
        logging.info(f"DEBUG_DOWNLOAD命令测试下载: {media_url}")

        # 发送状态消息
        status_msg = await update.message.reply_text("🔄 正在测试下载...")

        # 判断媒体类型
        media_type = 'video' if any(ext in media_url.lower() for ext in ['.mp4', '.mov', '.avi']) else 'image'

        # 下载文件
        file_path = await download_media_file(media_url, media_type)

        if file_path:
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)

            await status_msg.edit_text(f"✅ 下载成功\n📁 文件: {os.path.basename(file_path)}\n📏 大小: {size_mb:.2f}MB\n🔄 正在上传到Telegram...")

            # 尝试发送文件
            try:
                with open(file_path, 'rb') as f:
                    if media_type == 'video':
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=f,
                            caption=f"📹 测试视频上传\n📏 大小: {size_mb:.2f}MB"
                        )
                    else:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=f,
                            caption=f"🖼️ 测试图片上传\n📏 大小: {size_mb:.2f}MB"
                        )

                await status_msg.edit_text(f"✅ 下载并上传成功\n📏 大小: {size_mb:.2f}MB")

            except Exception as upload_error:
                await status_msg.edit_text(f"✅ 下载成功，❌ 上传失败\n📏 大小: {size_mb:.2f}MB\n💥 错误: {str(upload_error)}")

            # 清理文件
            try:
                os.remove(file_path)
                logging.info(f"🗑️ 清理临时文件: {file_path}")
            except:
                pass

        else:
            await status_msg.edit_text("❌ 下载失败")

    except Exception as e:
        logging.error(f"DEBUG_DOWNLOAD命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


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