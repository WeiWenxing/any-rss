"""
RSS状态管理模块
负责管理Feed的发送状态，通过pending文件标记是否已发送
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


class FeedStateManager:
    """Feed状态管理器，负责跟踪Feed的下载和发送状态"""
    
    def __init__(self, feeds_data_dir: Path):
        """
        初始化状态管理器
        
        Args:
            feeds_data_dir: Feed数据存储目录
        """
        self.feeds_data_dir = feeds_data_dir
        logging.info(f"初始化Feed状态管理器，数据目录: {feeds_data_dir}")
    
    def _get_pending_file_path(self, feed_dir: Path) -> Path:
        """
        获取pending文件路径
        
        Args:
            feed_dir: Feed目录
            
        Returns:
            Path: pending文件路径
        """
        today = datetime.now().strftime("%Y%m%d")
        return feed_dir / f"feed-pending-{today}.json"
    
    def create_pending_file(self, feed_dir: Path, entries: List[Dict[Any, Any]], xml_content: str) -> bool:
        """
        创建pending文件，标记有新内容待发送
        
        Args:
            feed_dir: Feed目录
            entries: 待发送的条目列表
            xml_content: 原始XML内容
            
        Returns:
            bool: 是否创建成功
        """
        try:
            pending_file = self._get_pending_file_path(feed_dir)
            
            # 准备pending数据
            pending_data = {
                "timestamp": datetime.now().isoformat(),
                "entries_count": len(entries),
                "xml_content": xml_content,
                "entries": [
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "id": entry.get("id", ""),
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", "")
                    }
                    for entry in entries
                ]
            }
            
            # 保存pending文件
            pending_file.write_text(json.dumps(pending_data, indent=2, ensure_ascii=False))
            logging.info(f"创建pending文件成功: {pending_file}, 条目数: {len(entries)}")
            return True
            
        except Exception as e:
            logging.error(f"创建pending文件失败: {str(e)}")
            return False
    
    def delete_pending_file(self, feed_dir: Path) -> bool:
        """
        删除pending文件，标记已发送完成
        
        Args:
            feed_dir: Feed目录
            
        Returns:
            bool: 是否删除成功
        """
        try:
            pending_file = self._get_pending_file_path(feed_dir)
            
            if pending_file.exists():
                pending_file.unlink()
                logging.info(f"删除pending文件成功: {pending_file}")
                return True
            else:
                logging.debug(f"pending文件不存在，无需删除: {pending_file}")
                return True
                
        except Exception as e:
            logging.error(f"删除pending文件失败: {str(e)}")
            return False
    
    def is_pending(self, feed_dir: Path) -> bool:
        """
        检查是否有pending状态（已下载但未发送）
        
        Args:
            feed_dir: Feed目录
            
        Returns:
            bool: 是否有pending状态
        """
        try:
            pending_file = self._get_pending_file_path(feed_dir)
            exists = pending_file.exists()
            logging.debug(f"检查pending状态: {pending_file} -> {exists}")
            return exists
            
        except Exception as e:
            logging.error(f"检查pending状态失败: {str(e)}")
            return False
    
    def get_pending_data(self, feed_dir: Path) -> Optional[Dict[str, Any]]:
        """
        获取pending文件中的数据
        
        Args:
            feed_dir: Feed目录
            
        Returns:
            Optional[Dict]: pending数据，如果不存在则返回None
        """
        try:
            pending_file = self._get_pending_file_path(feed_dir)
            
            if not pending_file.exists():
                logging.debug(f"pending文件不存在: {pending_file}")
                return None
            
            content = pending_file.read_text(encoding='utf-8')
            data = json.loads(content)
            logging.debug(f"读取pending数据成功: {pending_file}, 条目数: {data.get('entries_count', 0)}")
            return data
            
        except Exception as e:
            logging.error(f"读取pending数据失败: {str(e)}")
            return None
    
    def cleanup_old_pending_files(self, feed_dir: Path, keep_days: int = 7) -> None:
        """
        清理过期的pending文件
        
        Args:
            feed_dir: Feed目录
            keep_days: 保留天数
        """
        try:
            current_date = datetime.now()
            
            for file_path in feed_dir.glob("feed-pending-*.json"):
                try:
                    # 从文件名提取日期
                    date_str = file_path.stem.split("-")[-1]
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    
                    # 如果文件超过保留天数，删除它
                    if (current_date - file_date).days > keep_days:
                        file_path.unlink()
                        logging.info(f"清理过期pending文件: {file_path}")
                        
                except Exception as e:
                    logging.warning(f"清理pending文件时出错: {file_path}, 错误: {str(e)}")
                    
        except Exception as e:
            logging.error(f"清理过期pending文件失败: {str(e)}") 