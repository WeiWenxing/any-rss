"""
RSS网络工具模块
统一处理网络请求、重试逻辑和缓存
"""

import logging
import asyncio
import time
from typing import Tuple, Optional, Dict, Any
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .config import get_config


class NetworkManager:
    """网络请求管理器，提供重试、缓存等功能"""
    
    def __init__(self):
        """初始化网络管理器"""
        self.config = get_config()
        self.session = self._create_session()
        self._cache: Dict[str, Tuple[Any, float]] = {}  # URL -> (response, timestamp)
        self.cache_ttl = 300  # 缓存5分钟
        
    def _create_session(self) -> requests.Session:
        """
        创建带重试策略的requests会话
        
        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.config.request_retries,
            backoff_factor=self.config.request_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置默认请求头
        session.headers.update(self.config.get_request_headers())
        
        logging.info(f"网络管理器初始化完成: 重试{self.config.request_retries}次, 超时{self.config.request_timeout}秒")
        return session
    
    def _is_cache_valid(self, url: str) -> bool:
        """
        检查缓存是否有效
        
        Args:
            url: 请求URL
            
        Returns:
            bool: 缓存是否有效
        """
        if url not in self._cache:
            return False
        
        _, timestamp = self._cache[url]
        return time.time() - timestamp < self.cache_ttl
    
    def _get_from_cache(self, url: str) -> Optional[Any]:
        """
        从缓存获取响应
        
        Args:
            url: 请求URL
            
        Returns:
            Optional[Any]: 缓存的响应，如果不存在则返回None
        """
        if self._is_cache_valid(url):
            response, _ = self._cache[url]
            logging.debug(f"从缓存获取响应: {url}")
            return response
        return None
    
    def _save_to_cache(self, url: str, response: Any) -> None:
        """
        保存响应到缓存
        
        Args:
            url: 请求URL
            response: 响应对象
        """
        self._cache[url] = (response, time.time())
        logging.debug(f"保存响应到缓存: {url}")
    
    def check_url_accessibility(self, url: str, use_cache: bool = True) -> Tuple[bool, str, float]:
        """
        检查URL可访问性和文件大小
        
        Args:
            url: 要检查的URL
            use_cache: 是否使用缓存
            
        Returns:
            Tuple[bool, str, float]: (是否可访问, 错误信息, 文件大小MB)
        """
        try:
            # 检查缓存
            if use_cache:
                cached_result = self._get_from_cache(f"head_{url}")
                if cached_result:
                    return cached_result
            
            logging.debug(f"检查URL可访问性: {url}")
            
            response = self.session.head(
                url, 
                timeout=self.config.media_check_timeout,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                result = (False, f"HTTP {response.status_code}", 0.0)
            else:
                # 获取文件大小
                content_length = response.headers.get('content-length')
                if content_length:
                    size_bytes = int(content_length)
                    size_mb = size_bytes / (1024 * 1024)
                    result = (True, "", size_mb)
                else:
                    result = (True, "无法获取文件大小", 0.0)
            
            # 保存到缓存
            if use_cache:
                self._save_to_cache(f"head_{url}", result)
            
            return result
            
        except requests.exceptions.RequestException as e:
            result = (False, f"网络错误: {str(e)}", 0.0)
            logging.warning(f"URL可访问性检查失败: {url}, 错误: {str(e)}")
            return result
        except Exception as e:
            result = (False, f"检查失败: {str(e)}", 0.0)
            logging.error(f"URL可访问性检查异常: {url}, 错误: {str(e)}", exc_info=True)
            return result
    
    def download_feed(self, url: str, use_cache: bool = False) -> Tuple[bool, str, Optional[str]]:
        """
        下载Feed内容
        
        Args:
            url: Feed URL
            use_cache: 是否使用缓存
            
        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 错误信息, XML内容)
        """
        try:
            # 检查缓存
            if use_cache:
                cached_result = self._get_from_cache(f"feed_{url}")
                if cached_result:
                    return cached_result
            
            logging.info(f"下载Feed: {url}")
            
            response = self.session.get(
                url,
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            
            xml_content = response.text
            result = (True, "", xml_content)
            
            # 保存到缓存
            if use_cache:
                self._save_to_cache(f"feed_{url}", result)
            
            logging.info(f"Feed下载成功: {url}, 大小: {len(xml_content)} 字符")
            return result
            
        except requests.exceptions.RequestException as e:
            result = (False, f"下载失败: {str(e)}", None)
            logging.error(f"Feed下载失败: {url}, 错误: {str(e)}")
            return result
        except Exception as e:
            result = (False, f"处理失败: {str(e)}", None)
            logging.error(f"Feed处理异常: {url}, 错误: {str(e)}", exc_info=True)
            return result
    
    def download_media_file(self, url: str, file_path: str) -> Tuple[bool, str]:
        """
        下载媒体文件到指定路径
        
        Args:
            url: 媒体URL
            file_path: 保存路径
            
        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            logging.info(f"下载媒体文件: {url} -> {file_path}")
            
            response = self.session.get(
                url,
                timeout=self.config.request_timeout,
                stream=True
            )
            response.raise_for_status()
            
            # 流式写入文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logging.info(f"媒体文件下载成功: {file_path}")
            return (True, "")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"下载失败: {str(e)}"
            logging.error(f"媒体文件下载失败: {url}, 错误: {error_msg}")
            return (False, error_msg)
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            logging.error(f"媒体文件处理异常: {url}, 错误: {error_msg}", exc_info=True)
            return (False, error_msg)
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logging.info("网络缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 缓存统计信息
        """
        current_time = time.time()
        valid_entries = sum(
            1 for _, timestamp in self._cache.values()
            if current_time - timestamp < self.cache_ttl
        )
        
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "cache_ttl": self.cache_ttl
        }


# 全局网络管理器实例
network_manager = NetworkManager()


def get_network_manager() -> NetworkManager:
    """获取网络管理器实例"""
    return network_manager 