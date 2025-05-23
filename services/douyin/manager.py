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
        添加抖音用户订阅
        
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
            
            # 检查是否已存在
            is_new_subscription = douyin_url not in subscriptions
            
            if is_new_subscription:
                # 首次添加，尝试获取内容验证URL有效性
                success, error_msg, content_data = self.fetcher.fetch_user_content(douyin_url)
                if not success:
                    return False, f"无法获取抖音内容: {error_msg}", None
                
                # 提取内容信息
                content_info = self.fetcher.extract_content_info(content_data)
                if not content_info:
                    return False, "解析抖音内容失败", None
                
                # 保存订阅信息
                subscriptions[douyin_url] = {
                    "chat_id": chat_id,
                    "nickname": content_info.get("nickname", ""),
                    "author": content_info.get("author", ""),
                    "created_at": datetime.now().isoformat(),
                    "last_check": datetime.now().isoformat(),
                    "last_content_id": self.fetcher.generate_content_id(content_info)
                }
                
                self._save_subscriptions(subscriptions)
                
                # 保存内容数据
                self._save_content_data(douyin_url, content_info)
                
                logging.info(f"成功添加抖音订阅: {douyin_url} -> 频道: {chat_id}")
                return True, "首次添加", content_info
                
            else:
                # 更新现有订阅的频道ID
                old_chat_id = subscriptions[douyin_url]["chat_id"]
                subscriptions[douyin_url]["chat_id"] = chat_id
                subscriptions[douyin_url]["last_check"] = datetime.now().isoformat()
                
                self._save_subscriptions(subscriptions)
                
                logging.info(f"更新抖音订阅频道: {douyin_url} 从 {old_chat_id} 改为 {chat_id}")
                
                # 尝试获取最新内容
                success, error_msg, content_data = self.fetcher.fetch_user_content(douyin_url)
                if success and content_data:
                    content_info = self.fetcher.extract_content_info(content_data)
                    return True, "更新成功", content_info
                else:
                    return True, "更新成功但获取内容失败", None
                    
        except Exception as e:
            logging.error(f"添加抖音订阅失败: {douyin_url}", exc_info=True)
            return False, f"添加失败: {str(e)}", None

    def remove_subscription(self, douyin_url: str) -> Tuple[bool, str]:
        """
        删除抖音订阅
        
        Args:
            douyin_url: 抖音用户主页链接
            
        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            logging.info(f"尝试删除抖音订阅: {douyin_url}")
            
            subscriptions = self.get_subscriptions()
            
            if douyin_url not in subscriptions:
                return False, "该抖音订阅不存在"
            
            # 获取订阅信息
            subscription_info = subscriptions.pop(douyin_url)
            chat_id = subscription_info.get("chat_id", "")
            
            # 保存更新后的订阅列表
            self._save_subscriptions(subscriptions)
            
            logging.info(f"成功删除抖音订阅: {douyin_url} (原频道: {chat_id})")
            return True, ""
            
        except Exception as e:
            logging.error(f"删除抖音订阅失败: {douyin_url}", exc_info=True)
            return False, f"删除失败: {str(e)}"

    def get_subscriptions(self) -> Dict:
        """
        获取所有抖音订阅
        
        Returns:
            Dict: 订阅字典 {url: subscription_info}
        """
        try:
            content = self.subscriptions_file.read_text(encoding='utf-8')
            return json.loads(content)
        except Exception as e:
            logging.error("读取抖音订阅文件失败", exc_info=True)
            return {}

    def _save_subscriptions(self, subscriptions: Dict):
        """
        保存订阅数据到文件
        
        Args:
            subscriptions: 订阅字典
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

    def check_updates(self, douyin_url: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        检查指定抖音用户的更新
        
        Args:
            douyin_url: 抖音用户主页链接
            
        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 错误信息, 新内容数据)
        """
        try:
            logging.info(f"检查抖音更新: {douyin_url}")
            
            # 获取订阅信息
            subscriptions = self.get_subscriptions()
            if douyin_url not in subscriptions:
                return False, "订阅不存在", None
            
            subscription_info = subscriptions[douyin_url]
            last_content_id = subscription_info.get("last_content_id", "")
            
            # 获取最新内容
            success, error_msg, content_data = self.fetcher.fetch_user_content(douyin_url)
            if not success:
                return False, error_msg, None
            
            # 提取内容信息
            content_info = self.fetcher.extract_content_info(content_data)
            if not content_info:
                return False, "解析内容失败", None
            
            # 生成当前内容ID
            current_content_id = self.fetcher.generate_content_id(content_info)
            
            # 检查是否有新内容
            if current_content_id != last_content_id:
                # 有新内容，更新记录
                subscription_info["last_content_id"] = current_content_id
                subscription_info["last_check"] = datetime.now().isoformat()
                subscriptions[douyin_url] = subscription_info
                self._save_subscriptions(subscriptions)
                
                # 保存内容数据
                self._save_content_data(douyin_url, content_info)
                
                logging.info(f"发现新内容: {content_info.get('title', '无标题')}")
                return True, "发现新内容", content_info
            else:
                # 无新内容，只更新检查时间
                subscription_info["last_check"] = datetime.now().isoformat()
                subscriptions[douyin_url] = subscription_info
                self._save_subscriptions(subscriptions)
                
                logging.info(f"无新内容: {douyin_url}")
                return True, "无新内容", None
                
        except Exception as e:
            logging.error(f"检查抖音更新失败: {douyin_url}", exc_info=True)
            return False, f"检查失败: {str(e)}", None

    def _save_content_data(self, douyin_url: str, content_info: Dict):
        """
        保存内容数据到文件
        
        Args:
            douyin_url: 抖音用户主页链接
            content_info: 内容信息
        """
        try:
            user_dir = self._get_user_dir(douyin_url)
            
            # 保存内容信息
            content_file = user_dir / f"content_{content_info.get('aweme_id', 'unknown')}.json"
            content_file.write_text(
                json.dumps(content_info, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            
            # 保存最新内容引用
            latest_file = user_dir / "latest.json"
            latest_file.write_text(
                json.dumps(content_info, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            
            logging.debug(f"内容数据已保存: {content_file}")
            
        except Exception as e:
            logging.error(f"保存内容数据失败: {douyin_url}", exc_info=True)

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
        获取指定订阅的目标频道ID
        
        Args:
            douyin_url: 抖音用户主页链接
            
        Returns:
            Optional[str]: 频道ID，如果不存在则返回None
        """
        subscriptions = self.get_subscriptions()
        subscription_info = subscriptions.get(douyin_url, {})
        return subscription_info.get("chat_id") 
 