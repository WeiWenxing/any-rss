"""
抖音订阅管理器

负责抖音用户订阅管理、内容检查和数据存储
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib
import os

from .fetcher import DouyinFetcher


class DouyinManager:
    """抖音订阅管理器"""

    def __init__(self):
        """初始化抖音管理器"""
        self.config_dir = Path("storage/douyin/config")
        self.data_dir = Path("storage/douyin/data")
        self.media_dir = Path("storage/douyin/media")
        self.subscriptions_file = self.config_dir / "subscriptions.json"
        self.message_mappings_file = self.config_dir / "message_mappings.json"

        self.fetcher = DouyinFetcher()
        self._init_directories()
        logging.info("抖音订阅管理器初始化完成")

    def _init_directories(self):
        """初始化必要的目录"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

        if not self.subscriptions_file.exists():
            self.subscriptions_file.write_text("{}")
            logging.info("创建抖音订阅配置文件")

        if not self.message_mappings_file.exists():
            self.message_mappings_file.write_text("{}")
            logging.info("创建抖音消息映射配置文件")

    def _get_user_dir(self, douyin_url: str) -> Path:
        """
        根据抖音URL生成用户数据目录

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            Path: 用户数据目录路径
        """
        # 使用URL的哈希值作为目录名
        url_hash = hashlib.sha256(douyin_url.encode()).hexdigest()[:16]
        user_dir = self.data_dir / url_hash
        user_dir.mkdir(parents=True, exist_ok=True)

        # 保存原始URL到文件
        url_file = user_dir / "url.txt"
        if not url_file.exists():
            url_file.write_text(douyin_url)

        return user_dir

    def _get_media_dir(self, douyin_url: str) -> Path:
        """
        根据抖音URL生成媒体文件目录

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            Path: 媒体文件目录路径
        """
        url_hash = hashlib.sha256(douyin_url.encode()).hexdigest()[:16]
        media_dir = self.media_dir / url_hash
        media_dir.mkdir(parents=True, exist_ok=True)
        return media_dir

    def add_subscription(self, douyin_url: str, chat_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        添加抖音用户订阅（支持多频道和历史对齐）

        Args:
            douyin_url: 抖音用户主页链接
            chat_id: 目标频道ID

        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 错误信息, 内容数据)
        """
        try:
            logging.info(f"尝试添加抖音订阅: {douyin_url} -> 频道: {chat_id}")

            # 验证URL格式
            if not self.fetcher.validate_douyin_url(douyin_url):
                return False, "无效的抖音URL格式", None

            # 获取当前订阅列表
            subscriptions = self.get_subscriptions()

            # 检查是否已存在相同的URL+频道组合
            existing_channels = subscriptions.get(douyin_url, [])
            if chat_id in existing_channels:
                return True, "订阅已存在", None

            # 判断是否为该URL的首个频道
            is_first_channel = len(existing_channels) == 0

            if is_first_channel:
                # 首个频道：正常获取内容并初始化
                success, error_msg, all_content_data = self.fetcher.fetch_user_content(douyin_url)
                if not success:
                    return False, f"无法获取抖音内容: {error_msg}", None

                if not all_content_data or len(all_content_data) == 0:
                    return False, "获取到的内容数据为空", None

                # 提取第一个（最新）内容的信息用于验证
                latest_content_data = all_content_data[0]
                content_info = self.fetcher.extract_content_info(latest_content_data)
                if not content_info:
                    return False, "解析抖音内容失败", None

                # 添加到订阅列表
                subscriptions[douyin_url] = [chat_id]
                self._save_subscriptions(subscriptions)

                # 保存全部内容数据（按URL存储，与频道无关）
                self._save_all_content_data(douyin_url, all_content_data)

                # 初始化空的已知列表（让check_updates自然处理所有历史内容）
                self._save_known_item_ids(douyin_url, [])

                logging.info(f"成功添加首个频道订阅: {douyin_url} -> 频道: {chat_id}，获取了 {len(all_content_data)} 个内容")
                return True, "添加成功", content_info

            else:
                # 非首个频道：需要历史对齐
                logging.info(f"为现有URL添加新频道，需要历史对齐: {douyin_url} -> {chat_id}")

                # 添加到订阅列表
                existing_channels.append(chat_id)
                subscriptions[douyin_url] = existing_channels
                self._save_subscriptions(subscriptions)

                # 获取已知内容列表（用于历史对齐）
                known_item_ids = self._get_known_item_ids(douyin_url)

                # 返回特殊标记，表示需要历史对齐
                alignment_info = {
                    "need_alignment": True,
                    "known_item_ids": known_item_ids,
                    "primary_channel": existing_channels[0],  # 第一个频道作为主频道
                    "new_channel": chat_id
                }

                logging.info(f"成功添加新频道订阅: {douyin_url} -> 频道: {chat_id}，需要对齐 {len(known_item_ids)} 个历史内容")
                return True, "需要历史对齐", alignment_info

        except Exception as e:
            logging.error(f"添加抖音订阅失败: {douyin_url}", exc_info=True)
            return False, f"添加失败: {str(e)}", None

    def remove_subscription(self, douyin_url: str, chat_id: str = None) -> Tuple[bool, str]:
        """
        删除抖音订阅（支持多频道）

        Args:
            douyin_url: 抖音用户主页链接
            chat_id: 目标频道ID，如果为None则删除该URL的所有订阅

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            logging.info(f"尝试删除抖音订阅: {douyin_url} -> 频道: {chat_id}")

            subscriptions = self.get_subscriptions()

            if douyin_url not in subscriptions:
                return False, "该抖音订阅不存在"

            existing_channels = subscriptions[douyin_url]

            if chat_id is None:
                # 删除该URL的所有订阅
                removed_channels = subscriptions.pop(douyin_url)
                self._save_subscriptions(subscriptions)
                logging.info(f"成功删除抖音URL的所有订阅: {douyin_url} (原频道: {removed_channels})")
                return True, f"已删除所有频道: {removed_channels}"

            else:
                # 删除指定频道
                if chat_id not in existing_channels:
                    return False, f"该URL未订阅到频道 {chat_id}"

                # 从频道列表中移除
                existing_channels.remove(chat_id)

                if len(existing_channels) == 0:
                    # 如果没有剩余频道，删除整个URL条目
                    subscriptions.pop(douyin_url)
                    logging.info(f"删除最后一个频道，移除整个URL订阅: {douyin_url}")
                else:
                    # 更新频道列表
                    subscriptions[douyin_url] = existing_channels

                self._save_subscriptions(subscriptions)
                logging.info(f"成功删除抖音订阅: {douyin_url} -> {chat_id}，剩余频道: {existing_channels}")
                return True, ""

        except Exception as e:
            logging.error(f"删除抖音订阅失败: {douyin_url}", exc_info=True)
            return False, f"删除失败: {str(e)}"

    def get_subscriptions(self) -> Dict:
        """
        获取所有抖音订阅

        Returns:
            Dict: 订阅字典 {url: [chat_id1, chat_id2]} 或兼容旧格式 {url: chat_id}
        """
        try:
            content = self.subscriptions_file.read_text(encoding='utf-8')
            data = json.loads(content)

            # 兼容旧格式：如果是复杂对象，转换为简单映射
            if data and isinstance(list(data.values())[0], dict):
                logging.info("检测到旧格式的subscriptions.json，正在转换为新格式")
                # 将复杂对象转换为简单映射
                simple_subscriptions = {}
                for url, subscription_info in data.items():
                    chat_id = subscription_info.get("chat_id")
                    if chat_id:
                        simple_subscriptions[url] = [chat_id]  # 转换为数组格式

                # 保存新格式
                self._save_subscriptions(simple_subscriptions)
                logging.info(f"已转换 {len(simple_subscriptions)} 个订阅到新格式")
                return simple_subscriptions

            # 兼容一对一格式：如果值是字符串，转换为数组
            converted_data = {}
            for url, value in data.items():
                if isinstance(value, str):
                    # 一对一格式，转换为数组
                    converted_data[url] = [value]
                elif isinstance(value, list):
                    # 已经是数组格式
                    converted_data[url] = value
                else:
                    logging.warning(f"未知的订阅格式: {url} -> {value}")
                    continue

            # 如果有转换，保存新格式
            if converted_data != data:
                self._save_subscriptions(converted_data)
                logging.info(f"已转换订阅格式为数组格式")

            return converted_data
        except Exception as e:
            logging.error("读取抖音订阅文件失败", exc_info=True)
            return {}

    def _save_subscriptions(self, subscriptions: Dict):
        """
        保存订阅数据到文件

        Args:
            subscriptions: 订阅字典 {url: [chat_id1, chat_id2]} 或兼容旧格式 {url: chat_id}
        """
        try:
            self.subscriptions_file.write_text(
                json.dumps(subscriptions, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logging.debug("抖音订阅数据已保存")
        except Exception as e:
            logging.error("保存抖音订阅数据失败", exc_info=True)
            raise

    def check_updates(self, douyin_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        检查指定抖音用户的更新（支持多频道高效转发）

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 新内容数据列表)
        """
        try:
            logging.info(f"检查抖音更新: {douyin_url}")

            # 获取订阅信息
            subscriptions = self.get_subscriptions()
            if douyin_url not in subscriptions:
                return False, "订阅不存在", None

            # 获取订阅的频道列表
            subscribed_channels = subscriptions[douyin_url]
            if not subscribed_channels:
                return False, "该URL没有订阅频道", None

            # 获取当前全部内容
            success, error_msg, all_content_data = self.fetcher.fetch_user_content(douyin_url)
            if not success:
                return False, error_msg, None

            if not all_content_data or len(all_content_data) == 0:
                return False, "获取到的内容数据为空", None

            # 获取已知的item IDs（全局已发送的）
            known_item_ids = self._get_known_item_ids(douyin_url)

            # 找出新的items
            new_items = []

            for content_data in all_content_data:
                content_info = self.fetcher.extract_content_info(content_data)
                if content_info:
                    item_id = self.fetcher.generate_content_id(content_info)

                    # 如果这个item ID不在已知列表中，说明是新的
                    if item_id not in known_item_ids:
                        # 添加item_id和频道信息到内容中，用于后续发送
                        content_info["item_id"] = item_id
                        content_info["target_channels"] = subscribed_channels.copy()
                        content_info["primary_channel"] = subscribed_channels[0]  # 第一个频道作为主频道
                        new_items.append(content_info)
                        logging.info(f"发现新内容: {content_info.get('title', '无标题')} (ID: {item_id}) -> 频道: {subscribed_channels}")

            if new_items:
                # 保存完整数据
                self._save_all_content_data(douyin_url, all_content_data)

                logging.info(f"发现 {len(new_items)} 个新内容，将发送到 {len(subscribed_channels)} 个频道")
                return True, f"发现 {len(new_items)} 个新内容", new_items
            else:
                logging.info(f"无新内容: {douyin_url}")
                return True, "无新内容", None

        except Exception as e:
            logging.error(f"检查抖音更新失败: {douyin_url}", exc_info=True)
            return False, f"检查失败: {str(e)}", None

    def mark_item_as_sent(self, douyin_url: str, content_info: Dict) -> bool:
        """
        标记某个item为已成功发送

        Args:
            douyin_url: 抖音用户主页链接
            content_info: 内容信息

        Returns:
            bool: 是否标记成功
        """
        try:
            item_id = self.fetcher.generate_content_id(content_info)
            known_item_ids = self._get_known_item_ids(douyin_url)

            # 如果不在已知列表中，添加进去
            if item_id not in known_item_ids:
                known_item_ids.append(item_id)
                self._save_known_item_ids(douyin_url, known_item_ids)
                logging.info(f"标记item为已发送: {content_info.get('title', '无标题')} (ID: {item_id})")
                return True
            else:
                logging.debug(f"item已在已知列表中: {item_id}")
                return True

        except Exception as e:
            logging.error(f"标记item为已发送失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return False

    def _get_known_item_ids(self, douyin_url: str) -> List[str]:
        """
        获取已知的item IDs列表

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            List[str]: 已知的item IDs列表
        """
        try:
            user_dir = self._get_user_dir(douyin_url)
            known_ids_file = user_dir / "known_item_ids.json"

            if known_ids_file.exists():
                content = known_ids_file.read_text(encoding='utf-8')
                return json.loads(content)
            else:
                return []

        except Exception as e:
            logging.error(f"读取已知item IDs失败: {douyin_url}", exc_info=True)
            return []

    def _save_known_item_ids(self, douyin_url: str, item_ids: List[str]):
        """
        保存已知的item IDs列表

        Args:
            douyin_url: 抖音用户主页链接
            item_ids: item IDs列表
        """
        try:
            user_dir = self._get_user_dir(douyin_url)
            known_ids_file = user_dir / "known_item_ids.json"

            known_ids_file.write_text(
                json.dumps(item_ids, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            logging.debug(f"已知item IDs已保存: {len(item_ids)} 个")

        except Exception as e:
            logging.error(f"保存已知item IDs失败: {douyin_url}", exc_info=True)

    def _save_all_content_data(self, douyin_url: str, all_content_data: List[Dict]):
        """
        保存全部内容数据到文件

        Args:
            douyin_url: 抖音用户主页链接
            all_content_data: 全部内容数据列表
        """
        try:
            user_dir = self._get_user_dir(douyin_url)

            # 保存全部原始数据
            all_data_file = user_dir / "all_content.json"
            all_data_file.write_text(
                json.dumps(all_content_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            # 保存最新内容引用（第一个）
            if all_content_data:
                latest_content_info = self.fetcher.extract_content_info(all_content_data[0])
                if latest_content_info:
                    latest_file = user_dir / "latest.json"
                    latest_file.write_text(
                        json.dumps(latest_content_info, indent=2, ensure_ascii=False),
                        encoding='utf-8'
                    )

            logging.info(f"成功保存 {len(all_content_data)} 个内容数据到: {all_data_file}")

        except Exception as e:
            logging.error(f"保存全部内容数据失败: {douyin_url}", exc_info=True)

    def download_and_save_media(self, content_info: Dict, douyin_url: str) -> Tuple[bool, str, Optional[str]]:
        """
        下载并保存媒体文件

        Args:
            content_info: 内容信息
            douyin_url: 抖音用户主页链接

        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 错误信息, 本地文件路径)
        """
        try:
            media_dir = self._get_media_dir(douyin_url)
            content_id = content_info.get("aweme_id", "unknown")
            media_type = content_info.get("media_type", "")

            if media_type == "video":
                # 下载视频文件
                media_url = content_info.get("media_url", "")
                if not media_url:
                    return False, "视频URL为空", None

                # 确定文件扩展名
                file_ext = ".mp4"  # 默认为mp4
                local_path = media_dir / f"{content_id}{file_ext}"

                # 下载文件
                success, error_msg = self.fetcher.download_media(media_url, str(local_path))
                if success:
                    logging.info(f"视频下载完成: {local_path}")
                    return True, "", str(local_path)
                else:
                    return False, error_msg, None

            elif media_type == "images":
                # 下载图片文件（多张）
                images = content_info.get("images", [])
                if not images:
                    return False, "图片列表为空", None

                # 下载第一张图片作为代表
                image_url = images[0]
                file_ext = ".jpg"  # 默认为jpg
                local_path = media_dir / f"{content_id}_1{file_ext}"

                success, error_msg = self.fetcher.download_media(image_url, str(local_path))
                if success:
                    logging.info(f"图片下载完成: {local_path}")
                    return True, "", str(local_path)
                else:
                    return False, error_msg, None

            elif media_type == "image":
                # 下载单张图片
                media_url = content_info.get("media_url", "")
                if not media_url:
                    return False, "图片URL为空", None

                file_ext = ".jpg"  # 默认为jpg
                local_path = media_dir / f"{content_id}{file_ext}"

                success, error_msg = self.fetcher.download_media(media_url, str(local_path))
                if success:
                    logging.info(f"图片下载完成: {local_path}")
                    return True, "", str(local_path)
                else:
                    return False, error_msg, None
            else:
                return False, f"不支持的媒体类型: {media_type}", None

        except Exception as e:
            logging.error(f"下载媒体文件失败: {douyin_url}", exc_info=True)
            return False, f"下载失败: {str(e)}", None

    def get_subscription_chat_id(self, douyin_url: str) -> Optional[str]:
        """
        获取指定URL的订阅频道ID（兼容方法，返回第一个频道）

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            Optional[str]: 第一个频道ID，如果不存在则返回None
        """
        subscriptions = self.get_subscriptions()
        channels = subscriptions.get(douyin_url, [])
        return channels[0] if channels else None

    def get_subscription_channels(self, douyin_url: str) -> List[str]:
        """
        获取指定URL的所有订阅频道

        Args:
            douyin_url: 抖音用户主页链接

        Returns:
            List[str]: 频道ID列表
        """
        subscriptions = self.get_subscriptions()
        return subscriptions.get(douyin_url, [])

    def get_message_mappings(self) -> Dict:
        """
        获取所有消息映射

        Returns:
            Dict: 消息映射字典 {url: {item_id: {chat_id: message_id}}}
        """
        try:
            content = self.message_mappings_file.read_text(encoding='utf-8')
            return json.loads(content)
        except Exception as e:
            logging.error("读取消息映射文件失败", exc_info=True)
            return {}

    def _save_message_mappings(self, mappings: Dict):
        """
        保存消息映射到文件

        Args:
            mappings: 消息映射字典
        """
        try:
            self.message_mappings_file.write_text(
                json.dumps(mappings, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            logging.debug("消息映射已保存")
        except Exception as e:
            logging.error("保存消息映射失败", exc_info=True)

    def save_message_id(self, douyin_url: str, item_id: str, chat_id: str, message_id: int):
        """
        保存消息ID映射

        Args:
            douyin_url: 抖音用户主页链接
            item_id: 内容项ID
            chat_id: 频道ID
            message_id: Telegram消息ID
        """
        try:
            mappings = self.get_message_mappings()

            if douyin_url not in mappings:
                mappings[douyin_url] = {}

            if item_id not in mappings[douyin_url]:
                mappings[douyin_url][item_id] = {}

            mappings[douyin_url][item_id][chat_id] = message_id
            self._save_message_mappings(mappings)

            logging.debug(f"保存消息ID映射: {douyin_url} -> {item_id} -> {chat_id} -> {message_id}")
        except Exception as e:
            logging.error(f"保存消息ID映射失败: {str(e)}", exc_info=True)

    def save_message_ids(self, douyin_url: str, item_id: str, chat_id: str, message_ids: List[int]):
        """
        保存MediaGroup消息ID列表映射

        Args:
            douyin_url: 抖音用户主页链接
            item_id: 内容项ID
            chat_id: 频道ID
            message_ids: Telegram消息ID列表
        """
        try:
            mappings = self.get_message_mappings()

            if douyin_url not in mappings:
                mappings[douyin_url] = {}

            if item_id not in mappings[douyin_url]:
                mappings[douyin_url][item_id] = {}

            mappings[douyin_url][item_id][chat_id] = message_ids
            self._save_message_mappings(mappings)

            logging.debug(f"保存MediaGroup消息ID映射: {douyin_url} -> {item_id} -> {chat_id} -> {message_ids}")
        except Exception as e:
            logging.error(f"保存MediaGroup消息ID映射失败: {str(e)}", exc_info=True)

    def get_message_id(self, douyin_url: str, item_id: str, chat_id: str) -> Optional[int]:
        """
        获取消息ID

        Args:
            douyin_url: 抖音用户主页链接
            item_id: 内容项ID
            chat_id: 频道ID

        Returns:
            Optional[int]: 消息ID，如果不存在则返回None
        """
        try:
            mappings = self.get_message_mappings()
            return mappings.get(douyin_url, {}).get(item_id, {}).get(chat_id)
        except Exception as e:
            logging.error(f"获取消息ID失败: {str(e)}", exc_info=True)
            return None

    def get_message_ids(self, douyin_url: str, item_id: str, chat_id: str) -> List[int]:
        """
        获取MediaGroup消息ID列表

        Args:
            douyin_url: 抖音用户主页链接
            item_id: 内容项ID
            chat_id: 频道ID

        Returns:
            List[int]: 消息ID列表，如果不存在则返回空列表
        """
        try:
            mappings = self.get_message_mappings()
            result = mappings.get(douyin_url, {}).get(item_id, {}).get(chat_id, [])
            # 确保返回列表格式
            if isinstance(result, int):
                return [result]  # 兼容单个消息ID的情况
            elif isinstance(result, list):
                return result
            else:
                return []
        except Exception as e:
            logging.error(f"获取MediaGroup消息ID失败: {str(e)}", exc_info=True)
            return []

    def get_primary_channel_message_id(self, douyin_url: str, item_id: str) -> Tuple[Optional[str], Optional[int]]:
        """
        获取主频道的消息ID（用于转发）

        Args:
            douyin_url: 抖音用户主页链接
            item_id: 内容项ID

        Returns:
            Tuple[Optional[str], Optional[int]]: (主频道ID, 消息ID)
        """
        try:
            mappings = self.get_message_mappings()
            item_mappings = mappings.get(douyin_url, {}).get(item_id, {})

            if not item_mappings:
                return None, None

            # 返回第一个可用的频道和消息ID作为主频道
            for chat_id, message_id in item_mappings.items():
                return chat_id, message_id

            return None, None
        except Exception as e:
            logging.error(f"获取主频道消息ID失败: {str(e)}", exc_info=True)
            return None, None

    def get_primary_channel_message_ids(self, douyin_url: str, item_id: str) -> Tuple[Optional[str], List[int]]:
        """
        获取主频道的MediaGroup消息ID列表（用于转发）

        Args:
            douyin_url: 抖音用户主页链接
            item_id: 内容项ID

        Returns:
            Tuple[Optional[str], List[int]]: (主频道ID, 消息ID列表)
        """
        try:
            mappings = self.get_message_mappings()
            item_mappings = mappings.get(douyin_url, {}).get(item_id, {})

            if not item_mappings:
                return None, []

            # 返回第一个可用的频道和消息ID列表作为主频道
            for chat_id, message_data in item_mappings.items():
                if isinstance(message_data, list):
                    return chat_id, message_data
                elif isinstance(message_data, int):
                    return chat_id, [message_data]  # 兼容单个消息ID
                else:
                    continue

            return None, []
        except Exception as e:
            logging.error(f"获取主频道MediaGroup消息ID失败: {str(e)}", exc_info=True)
            return None, []

    async def send_content_batch(self, bot, content_items: List[Dict], douyin_url: str, target_channels: List[str]) -> int:
        """
        批量发送抖音内容到多个频道（多频道高效转发算法）

        Args:
            bot: Telegram Bot实例
            content_items: 要发送的内容列表
            douyin_url: 抖音用户链接
            target_channels: 目标频道列表

        Returns:
            int: 成功发送的内容数量
        """
        import asyncio
        from .sender import send_douyin_content

        logging.info(f"开始批量发送 {len(content_items)} 个内容到 {len(target_channels)} 个频道")

        # 多频道转发机制（单频道时other_channels自动为空数组）
        primary_channel = target_channels[0]
        other_channels = target_channels[1:]
        sent_count = 0

        # 按时间排序（从旧到新）
        sorted_items = self._sort_content_by_time(content_items)

        for content in sorted_items:
            # 为当前内容项维护成功记录（内存中）
            successful_channels = {}  # {channel_id: [message_id1, message_id2, ...]}

            try:
                # 确保content有item_id字段
                if 'item_id' not in content:
                    content['item_id'] = self.fetcher.generate_content_id(content)
                    logging.warning(f"内容缺少item_id，动态生成: {content['item_id']}")

                # 步骤1：主频道发送
                logging.info(f"发送到主频道 {primary_channel}: {content.get('title', '无标题')}")
                messages = await send_douyin_content(bot, content, douyin_url, primary_channel)
                if not messages:
                    logging.warning(f"主频道发送失败，跳过内容: {content.get('title', '无标题')}")
                    continue

                # 处理返回的消息（可能是单个消息或消息列表）
                if isinstance(messages, list):
                    # MediaGroup情况：多个消息
                    primary_message_ids = [msg.message_id for msg in messages]
                    self.save_message_ids(douyin_url, content['item_id'], primary_channel, primary_message_ids)
                    successful_channels[primary_channel] = primary_message_ids  # 内存记录
                    logging.info(f"主频道MediaGroup发送成功，消息ID列表: {primary_message_ids}")
                else:
                    # 单个消息情况
                    primary_message_ids = [messages.message_id]
                    self.save_message_ids(douyin_url, content['item_id'], primary_channel, primary_message_ids)
                    successful_channels[primary_channel] = primary_message_ids  # 内存记录
                    logging.info(f"主频道发送成功，消息ID: {messages.message_id}")

                # 步骤2：其他频道转发（单频道时自动跳过）
                for channel in other_channels:
                    success = False

                    # 尝试从主频道转发
                    try:
                        logging.info(f"转发到频道 {channel}")
                        forwarded_messages = await bot.forward_messages(
                            chat_id=channel,
                            from_chat_id=primary_channel,
                            message_ids=primary_message_ids
                        )
                        forwarded_ids = [msg.message_id for msg in forwarded_messages]
                        self.save_message_ids(douyin_url, content['item_id'], channel, forwarded_ids)
                        successful_channels[channel] = forwarded_ids  # 内存记录
                        logging.info(f"转发成功: {primary_channel} -> {channel}, 消息ID列表: {forwarded_ids}")
                        success = True
                    except Exception as forward_error:
                        logging.warning(f"从主频道转发失败: {channel}, 错误: {forward_error}", exc_info=True)

                    # 转发失败，从内存中的成功频道转发
                    if not success:
                        for existing_channel, existing_msg_ids in successful_channels.items():
                            if existing_channel != channel:  # 不从自己转发
                                try:
                                    logging.info(f"尝试从 {existing_channel} 转发到 {channel}")
                                    forwarded_messages = await bot.forward_messages(
                                        chat_id=channel,
                                        from_chat_id=existing_channel,
                                        message_ids=existing_msg_ids
                                    )
                                    forwarded_ids = [msg.message_id for msg in forwarded_messages]
                                    self.save_message_ids(douyin_url, content['item_id'], channel, forwarded_ids)
                                    successful_channels[channel] = forwarded_ids  # 内存记录
                                    logging.info(f"转发成功: {existing_channel} -> {channel}, 消息ID列表: {forwarded_ids}")
                                    success = True
                                    break
                                except Exception as retry_error:
                                    logging.warning(f"从 {existing_channel} 转发失败: {retry_error}", exc_info=True)
                                    continue

                    # 所有转发都失败，最后降级为直接发送
                    if not success:
                        logging.warning(f"所有转发都失败，降级发送: {channel}")
                        try:
                            fallback_messages = await send_douyin_content(bot, content, douyin_url, channel)
                            if fallback_messages:
                                if isinstance(fallback_messages, list):
                                    fallback_ids = [msg.message_id for msg in fallback_messages]
                                else:
                                    fallback_ids = [fallback_messages.message_id]
                                self.save_message_ids(douyin_url, content['item_id'], channel, fallback_ids)
                                successful_channels[channel] = fallback_ids  # 内存记录
                                logging.info(f"降级发送成功: {channel}")
                        except Exception as send_error:
                            logging.error(f"降级发送也失败: {channel}, 错误: {send_error}", exc_info=True)
                            continue

                # 步骤3：标记内容已发送
                self.mark_item_as_sent(douyin_url, content)
                sent_count += 1

                # 发送间隔，避免频率限制
                await asyncio.sleep(1)

            except Exception as e:
                logging.error(f"发送内容失败: {content.get('title', '无标题')}, 错误: {e}", exc_info=True)
                continue

        logging.info(f"批量发送完成: 成功 {sent_count}/{len(content_items)} 个内容到 {len(target_channels)} 个频道")
        return sent_count

    def _sort_content_by_time(self, content_items: List[Dict]) -> List[Dict]:
        """
        按时间排序内容（从旧到新）

        Args:
            content_items: 内容列表

        Returns:
            List[Dict]: 排序后的内容列表
        """
        try:
            return sorted(content_items, key=lambda x: x.get('time', ''))
        except Exception as e:
            logging.warning(f"内容排序失败，使用原顺序: {e}")
            return content_items
