"""
抖音历史对齐转发模块
负责新频道订阅时的历史内容对齐
"""

import logging
import asyncio
from typing import List
from telegram import Bot

from .manager import DouyinManager


async def perform_historical_alignment(
    bot: Bot, douyin_url: str, known_item_ids: List[str], new_channel: str
) -> bool:
    """
    执行历史对齐转发

    Args:
        bot: Telegram Bot实例
        douyin_url: 抖音URL
        known_item_ids: 需要对齐的内容ID列表
        new_channel: 新频道

    Returns:
        bool: 是否全部转发成功
    """
    if not known_item_ids:
        logging.info("无历史内容需要对齐")
        return True

    from .interval_manager import MessageSendingIntervalManager

    # 初始化间隔管理器（历史对齐场景）
    interval_manager = MessageSendingIntervalManager("alignment")

    douyin_manager = DouyinManager()
    success_count = 0

    logging.info(f"开始历史对齐: 转发 {len(known_item_ids)} 个内容到 {new_channel}")

    for i, item_id in enumerate(known_item_ids, 1):
        item_success = False

        try:
            # 发送前等待（使用配置化间隔管理器）
            await interval_manager.wait_before_send(
                content_index=i-1,  # 转换为0基索引
                total_content=len(known_item_ids),
                recent_error_rate=interval_manager.get_recent_error_rate()
            )

            # 获取所有可用的转发源
            all_available_sources = douyin_manager.get_all_available_message_sources(douyin_url, item_id)
            if not all_available_sources:
                logging.warning(f"历史对齐: 内容 {item_id} 没有可用的转发源，跳过 ({i}/{len(known_item_ids)})")
                # 更新统计信息（转发失败）
                interval_manager.update_statistics(success=False)
                continue

            # 遍历所有可用源，直到成功
            for source_channel, source_message_ids in all_available_sources:
                try:
                    # 转发整个MediaGroup到新频道
                    forwarded_messages = await bot.copy_messages(
                        chat_id=new_channel,
                        from_chat_id=source_channel,
                        message_ids=source_message_ids
                    )

                    # 保存转发后的所有消息ID（处理返回的消息可能是单个消息、消息列表或消息元组）
                    if isinstance(forwarded_messages, (list, tuple)):
                        forwarded_ids = [msg.message_id for msg in forwarded_messages]
                    else:
                        forwarded_ids = [forwarded_messages.message_id]

                    douyin_manager.save_message_ids(douyin_url, item_id, new_channel, forwarded_ids)

                    logging.info(f"历史对齐成功 ({i}/{len(known_item_ids)}): {item_id} 从 {source_channel} 转发到 {new_channel}, 消息ID列表: {forwarded_ids}")
                    item_success = True
                    break  # 成功后跳出源循环，处理下一个内容

                except Exception as e:
                    logging.warning(f"历史对齐转发失败 ({i}/{len(known_item_ids)}): {item_id} 从 {source_channel} 转发失败: {str(e)}")
                    continue  # 尝试下一个转发源

            # 统计成功的内容
            if item_success:
                success_count += 1
                # 更新统计信息（转发成功）
                interval_manager.update_statistics(success=True)
            else:
                logging.error(f"历史对齐失败 ({i}/{len(known_item_ids)}): {item_id} 所有转发源都失败，该内容无法对齐")
                # 更新统计信息（转发失败）
                interval_manager.update_statistics(success=False)

        except Exception as e:
            logging.error(f"历史对齐转发失败 ({i}/{len(known_item_ids)}): {item_id}, 错误: {str(e)}", exc_info=True)
            # 更新统计信息（转发失败）
            interval_manager.update_statistics(success=False)

            # 错误后等待
            if "flood control" in str(e).lower():
                await interval_manager.wait_after_error("flood_control")
            elif "rate limit" in str(e).lower():
                await interval_manager.wait_after_error("rate_limit")
            else:
                await interval_manager.wait_after_error("other")
            continue

    success_rate = success_count / len(known_item_ids) * 100
    logging.info(f"历史对齐完成: {success_count}/{len(known_item_ids)} 成功 ({success_rate:.1f}%)")
    logging.info(f"📊 {interval_manager.get_statistics_summary()}")

    return success_count == len(known_item_ids)

