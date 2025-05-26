"""
抖音调试命令模块
专门用于各种抖音相关的测试和调试功能
"""

import logging
import json
import asyncio
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from .formatter import DouyinFormatter
from .commands import send_douyin_content


# 全局实例
douyin_formatter = DouyinFormatter()


async def douyin_debug_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试版本的抖音内容展示命令，用于测试单个抖音数据的格式化和发送
    用法: /douyin_debug_show <JSON数据>
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_SHOW命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        if not context.args:
            help_text = (
                "❌ 请提供抖音内容JSON数据\n\n"
                "用法: /douyin_debug_show <JSON数据>\n\n"
                "示例JSON格式:\n"
                "{\n"
                '  "aweme_id": "7478284850366090536",\n'
                '  "nickname": "小神仙",\n'
                '  "title": "人在知足时最幸福",\n'
                '  "type": "视频",\n'
                '  "video_info": {...},\n'
                '  "time": "2025-03-05"\n'
                "}\n\n"
                "💡 此命令用于测试抖音内容的格式化和发送功能"
            )
            await update.message.reply_text(help_text)
            return

        # 合并所有参数作为JSON字符串
        json_str = " ".join(context.args)
        logging.info(f"DOUYIN_DEBUG_SHOW命令接收到的JSON长度: {len(json_str)} 字符")

        # 解析JSON数据
        try:
            content_info = json.loads(json_str)
            logging.info(f"成功解析JSON数据，包含字段: {list(content_info.keys())}")
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析失败: {str(e)}")
            await update.message.reply_text(
                f"❌ JSON格式错误: {str(e)}\n\n"
                "请确保提供有效的JSON格式数据"
            )
            return

        # 验证必要字段
        required_fields = ["aweme_id", "title", "type"]
        missing_fields = [field for field in required_fields if field not in content_info]

        if missing_fields:
            await update.message.reply_text(
                f"❌ 缺少必要字段: {', '.join(missing_fields)}\n\n"
                f"必要字段: {', '.join(required_fields)}"
            )
            return

        title = content_info.get('title', 'Unknown')
        aweme_id = content_info.get('aweme_id', 'Unknown')
        content_type = content_info.get('type', 'Unknown')

        logging.info(f"解析到内容: ID={aweme_id}, 标题={title}, 类型={content_type}")

        # 发送状态消息
        status_msg = await update.message.reply_text(
            f"🔄 开始调试抖音内容...\n"
            f"📋 ID: {aweme_id}\n"
            f"📝 标题: {title}\n"
            f"📱 类型: {content_type}"
        )

        # 格式化消息预览
        try:
            message_text = douyin_formatter.format_content_message(content_info)
            caption = douyin_formatter.format_caption(content_info)

            preview_text = (
                f"📊 格式化结果预览:\n\n"
                f"🔹 消息文本 (前200字符):\n"
                f"{message_text[:200]}{'...' if len(message_text) > 200 else ''}\n\n"
                f"🔹 媒体标题 (前100字符):\n"
                f"{caption[:100]}{'...' if len(caption) > 100 else ''}\n\n"
                f"📏 消息长度: {len(message_text)} 字符\n"
                f"📏 标题长度: {len(caption)} 字符"
            )

            await status_msg.edit_text(preview_text)

            # 等待一下再发送实际内容
            await asyncio.sleep(2)

        except Exception as format_error:
            logging.error(f"格式化预览失败: {str(format_error)}", exc_info=True)
            await status_msg.edit_text(f"❌ 格式化预览失败: {str(format_error)}")
            return

        # 发送实际内容
        try:
            await update.message.reply_text("🚀 开始发送实际内容...")

            # 使用抖音内容发送函数
            await send_douyin_content(
                bot=context.bot,
                content_info=content_info,
                douyin_url="debug://test",  # 调试用的虚拟URL
                target_chat_id=str(chat_id)
            )

            await update.message.reply_text("✅ 抖音内容调试发送成功！")
            logging.info(f"DOUYIN_DEBUG_SHOW命令执行成功: {aweme_id}")

        except Exception as send_error:
            logging.error(f"发送抖音内容失败: {str(send_error)}", exc_info=True)
            await update.message.reply_text(f"❌ 发送失败: {str(send_error)}")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_SHOW命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def douyin_debug_format_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    调试抖音内容格式化命令，只显示格式化结果不发送媒体
    用法: /douyin_debug_format <JSON数据>
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_FORMAT命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        if not context.args:
            await update.message.reply_text(
                "❌ 请提供抖音内容JSON数据\n\n"
                "用法: /douyin_debug_format <JSON数据>\n\n"
                "💡 此命令只显示格式化结果，不发送媒体文件"
            )
            return

        # 合并所有参数作为JSON字符串
        json_str = " ".join(context.args)
        logging.info(f"DOUYIN_DEBUG_FORMAT命令接收到的JSON长度: {len(json_str)} 字符")

        # 解析JSON数据
        try:
            content_info = json.loads(json_str)
            logging.info(f"成功解析JSON数据，包含字段: {list(content_info.keys())}")
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析失败: {str(e)}")
            await update.message.reply_text(f"❌ JSON格式错误: {str(e)}")
            return

        # 格式化内容
        try:
            message_text = douyin_formatter.format_content_message(content_info)
            caption = douyin_formatter.format_caption(content_info)

            # 构建详细的格式化结果
            result_text = (
                f"📊 抖音内容格式化结果\n\n"
                f"🔹 完整消息文本:\n"
                f"{'='*30}\n"
                f"{message_text}\n"
                f"{'='*30}\n\n"
                f"🔹 媒体标题:\n"
                f"{'='*20}\n"
                f"{caption}\n"
                f"{'='*20}\n\n"
                f"📊 统计信息:\n"
                f"• 消息长度: {len(message_text)} 字符\n"
                f"• 标题长度: {len(caption)} 字符\n"
                f"• 媒体类型: {content_info.get('type', 'Unknown')}\n"
                f"• 作者: {content_info.get('nickname', 'Unknown')}\n"
                f"• 发布时间: {content_info.get('time', 'Unknown')}"
            )

            # 如果消息太长，分段发送
            if len(result_text) > 4000:
                # 分段发送
                await update.message.reply_text(
                    f"📊 抖音内容格式化结果\n\n"
                    f"🔹 完整消息文本:\n"
                    f"{'='*30}"
                )
                await update.message.reply_text(message_text)
                await update.message.reply_text(
                    f"{'='*30}\n\n"
                    f"🔹 媒体标题:\n"
                    f"{'='*20}"
                )
                await update.message.reply_text(caption)
                await update.message.reply_text(
                    f"{'='*20}\n\n"
                    f"📊 统计信息:\n"
                    f"• 消息长度: {len(message_text)} 字符\n"
                    f"• 标题长度: {len(caption)} 字符\n"
                    f"• 媒体类型: {content_info.get('type', 'Unknown')}\n"
                    f"• 作者: {content_info.get('nickname', 'Unknown')}\n"
                    f"• 发布时间: {content_info.get('time', 'Unknown')}"
                )
            else:
                await update.message.reply_text(result_text)

            logging.info(f"DOUYIN_DEBUG_FORMAT命令执行成功")

        except Exception as format_error:
            logging.error(f"格式化失败: {str(format_error)}", exc_info=True)
            await update.message.reply_text(f"❌ 格式化失败: {str(format_error)}")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_FORMAT命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


async def douyin_debug_sample_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    提供抖音调试数据样例
    用法: /douyin_debug_sample [type]
    type: simple(默认) | full
    """
    try:
        user = update.message.from_user
        chat_id = update.message.chat_id
        logging.info(f"收到DOUYIN_DEBUG_SAMPLE命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

        # 检查参数，决定返回简单样例还是完整样例
        sample_type = "simple"
        if context.args and len(context.args) > 0:
            sample_type = context.args[0].lower()

        if sample_type == "full":
            # 提供完整的示例数据（包含视频信息）
            sample_data = {
                "aweme_id": "7478284850366090536",
                "nickname": "小神仙",
                "avatar": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_0c674ba9c10210a155778a3b29f2987e.jpeg?from=327834062",
                "share_url": "https://www.iesdouyin.com/share/video/7478284850366090536/?region=CN&mid=7456268046764739366&u_code=154976742&did=MS4wLjABAAAAaQQlJ5k7rEi3LJKVPpMRgdlMiKvnRcdfjHHxdel0lXeTIITq7Jd5YHddBbu5_TU9&iid=MS4wLjABAAAANwkJuWIRFOzg5uCpDRpMj4OX-QryoDgn-yYlXQnRwQQ&with_sec_did=1&video_share_track_ver=&titleType=title&share_sign=.0pxqWyhpVdxMZjSwJAfbPMwX7SESw6nuq19wVph1mc-&share_version=290100&ts=1748223024&from_aid=6383&from_ssr=1",
                "author": "小神仙",
                "title": "人在知足时最幸福",
                "comment": 663,
                "play": 0,
                "like": 40477,
                "pic": "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                "pic_list": [
                    "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                    "https://p9-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=NN2ia%2Ff%2FpKEAyHXfIUJnfwUwjtA%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B"
                ],
                "type": "视频",
                "video_info": {
                    "id": "v0200fg10000cv435mnog65j826sr7og",
                    "pic": "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                    "pic_list": [
                        "https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=7epG7y8Qsr%2Ff0f7rcKwuDxRQnD8%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B",
                        "https://p9-pc-sign.douyinpic.com/tos-cn-p-0015/oUp8Bi9xQINZvgsBHI3nAs2yNyiAAIIIQzgPI~tplv-dy-360p.jpeg?lk3s=138a59ce&x-expires=1749430800&x-signature=NN2ia%2Ff%2FpKEAyHXfIUJnfwUwjtA%3D&from=327834062&s=PackSourceEnum_PUBLISH&se=false&sc=origin_cover&biz_tag=pcweb_cover&l=202505260930231DBC771B80C9F87B513B"
                    ],
                    "height": 635,
                    "width": 360,
                    "size": "1.4 MB",
                    "url": "https://v3-web.douyinvod.com/022c59e81ce506a211255f7363581edc/6833ee6c/video/tos/cn/tos-cn-ve-15/oUDBCbaffIWnFAAmQLWi9PPDgEEACIgRguy6Iy/?a=6383&ch=10010&cr=3&dr=0&lr=all&cd=0%7C0%7C0%7C3&cv=1&br=890&bt=890&cs=0&ds=4&ft=LjhJEL998xsRu.0mD0P5XEhX.xiXO~QjRVJE2wpHpCPD-Ipz&mime_type=video_mp4&qs=0&rc=MzY5Ojs3ZWQ7Zzk2aWU1ZEBpajp2NW05cnA2eTMzNGkzM0A0LzViMDYvNWIxXy4zMy4zYSNsbzM1MmRrMjFgLS1kLS9zcw%3D%3D&btag=80000e00008000&cquery=100x_100z_100o_101r_100B&dy_q=1748223024&feature_id=46a7bb47b4fd1280f3d3825bf2b29388&l=202505260930231DBC771B80C9F87B513B",
                    "download": "https://www.douyin.com/aweme/v1/play/?video_id=v0200fg10000cv435mnog65j826sr7og&line=0&file_id=6a126b6f13b64de88a2b9438e7862370&sign=5d1445fffb4589320262cdc5ac73b32b&is_play_url=1&source=PackSourceEnum_PUBLISH",
                    "download2": "https://www.douyin.com/aweme/v1/play/?video_id=v0200fg10000cv435mnog65j826sr7og&ratio=1080p&line=0"
                },
                "music_info": {
                    "id": 7456268046764739366,
                    "title": "@何存真创作的原声",
                    "author": "何存真",
                    "pic": "https://p3-pc.douyinpic.com/aweme/1080x1080/aweme-avatar/tos-cn-avt-0015_f33e41e1b7ce95a229bdf0d697889fc1.jpeg?from=327834062",
                    "pic_list": [
                        "https://p3-pc.douyinpic.com/aweme/1080x1080/aweme-avatar/tos-cn-avt-0015_f33e41e1b7ce95a229bdf0d697889fc1.jpeg?from=327834062"
                    ],
                    "url": "https://sf5-hl-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3",
                    "url_list": [
                        "https://sf5-hl-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3",
                        "https://sf5-hl-ali-cdn-tos.douyinstatic.com/obj/ies-music/7456268160275073830.mp3"
                    ],
                    "duration": "0分14秒",
                    "height": 720,
                    "width": 720,
                    "owner_nickname": "何存真"
                },
                "images_info": {
                    "images": [
                        "不是图文没有信息"
                    ],
                    "height": "不是图文没有信息",
                    "width": "不是图文没有信息"
                },
                "hot_words": {
                    "text_extra": [],
                    "hashtag_id": None,
                    "start": None
                },
                "time": "2025-03-05"
            }

            sample_description = "完整视频数据样例（包含视频下载链接、音乐信息等）"
        else:
            # 提供简单的示例数据
            sample_data = {
                "aweme_id": "7478284850366090536",
                "nickname": "小神仙",
                "avatar": "https://p3-pc.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_0c674ba9c10210a155778a3b29f2987e.jpeg?from=327834062",
                "share_url": "https://www.iesdouyin.com/share/video/7478284850366090536/",
                "author": "小神仙",
                "title": "人在知足时最幸福",
                "comment": 663,
                "play": 0,
                "like": 40477,
                "type": "视频",
                "time": "2025-03-05"
            }

            sample_description = "简单数据样例（基础字段）"

        # 格式化JSON字符串
        json_str = json.dumps(sample_data, ensure_ascii=False, indent=2)

        help_text = (
            f"📋 抖音调试数据样例 - {sample_description}\n\n"
            f"🔹 使用方法:\n"
            f"1. 复制下面的JSON数据\n"
            f"2. 使用 `/douyin_debug_show` 或 `/douyin_debug_format` 命令\n"
            f"3. 将JSON数据作为参数传入\n\n"
            f"🔹 示例JSON数据:\n"
            f"```json\n{json_str}\n```\n\n"
            f"💡 提示:\n"
            f"• `/douyin_debug_show` - 完整测试（包含媒体发送）\n"
            f"• `/douyin_debug_format` - 只测试格式化\n"
            f"• `/douyin_debug_sample` - 显示简单样例数据\n"
            f"• `/douyin_debug_sample full` - 显示完整样例数据"
        )

        # 如果消息太长，分段发送
        if len(help_text) > 4000:
            # 分段发送
            header_text = (
                f"📋 抖音调试数据样例 - {sample_description}\n\n"
                f"🔹 使用方法:\n"
                f"1. 复制下面的JSON数据\n"
                f"2. 使用 `/douyin_debug_show` 或 `/douyin_debug_format` 命令\n"
                f"3. 将JSON数据作为参数传入\n\n"
                f"🔹 示例JSON数据:"
            )

            footer_text = (
                f"💡 提示:\n"
                f"• `/douyin_debug_show` - 完整测试（包含媒体发送）\n"
                f"• `/douyin_debug_format` - 只测试格式化\n"
                f"• `/douyin_debug_sample` - 显示简单样例数据\n"
                f"• `/douyin_debug_sample full` - 显示完整样例数据"
            )

            await update.message.reply_text(header_text)
            await update.message.reply_text(f"```json\n{json_str}\n```", parse_mode='Markdown')
            await update.message.reply_text(footer_text)
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown')

        logging.info(f"DOUYIN_DEBUG_SAMPLE命令执行成功，类型: {sample_type}")

    except Exception as e:
        logging.error(f"DOUYIN_DEBUG_SAMPLE命令执行失败: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ 命令执行失败: {str(e)}")


def register_douyin_debug_commands(application: Application) -> None:
    """注册抖音调试命令"""
    application.add_handler(CommandHandler("douyin_debug_show", douyin_debug_show_command))
    application.add_handler(CommandHandler("douyin_debug_format", douyin_debug_format_command))
    application.add_handler(CommandHandler("douyin_debug_sample", douyin_debug_sample_command))

    logging.info("✅ 抖音调试命令注册完成")