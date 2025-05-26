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
    bot: Bot, douyin_url: str, known_item_ids: List[str], 
    primary_channel: str, new_channel: str
) -> bool:
    """
    执行历史对齐转发
    
    Args:
        bot: Telegram Bot实例
        douyin_url: 抖音URL
        known_item_ids: 需要对齐的内容ID列表
        primary_channel: 主频道
        new_channel: 新频道
        
    Returns:
        bool: 是否全部转发成功
    """
    if not known_item_ids:
        logging.info("无历史内容需要对齐")
        return True
        
    douyin_manager = DouyinManager()
    success_count = 0
    
    logging.info(f"开始历史对齐: 从 {primary_channel} 转发 {len(known_item_ids)} 个内容到 {new_channel}")
    
    for i, item_id in enumerate(known_item_ids, 1):
        try:
            # 获取主频道的消息ID
            primary_message_id = douyin_manager.get_message_id(douyin_url, item_id, primary_channel)
            
            if primary_message_id:
                # 转发消息
                forwarded_message = await bot.forward_message(
                    chat_id=new_channel,
                    from_chat_id=primary_channel,
                    message_id=primary_message_id
                )
                
                # 存储转发后的消息ID
                if hasattr(forwarded_message, 'message_id'):
                    douyin_manager.save_message_id(
                        douyin_url, item_id, new_channel, forwarded_message.message_id
                    )
                
                success_count += 1
                logging.info(f"历史对齐转发成功 ({i}/{len(known_item_ids)}): {item_id}")
                
                # 转发间隔，避免flood control
                await asyncio.sleep(1)
            else:
                logging.warning(f"无法获取历史内容的消息ID ({i}/{len(known_item_ids)}): {item_id}")
                
        except Exception as e:
            logging.error(f"历史对齐转发失败 ({i}/{len(known_item_ids)}): {item_id}, 错误: {str(e)}")
            continue
    
    success_rate = success_count / len(known_item_ids) * 100
    logging.info(f"历史对齐完成: {success_count}/{len(known_item_ids)} 成功 ({success_rate:.1f}%)")
    
    return success_count == len(known_item_ids)

 