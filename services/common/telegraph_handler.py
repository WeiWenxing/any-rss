"""
Telegraph处理器模块

该模块提供Telegraph页面的创建和管理功能，
主要用于处理大量图片的场景，将图片批量上传到Telegraph并生成页面链接。

主要功能：
1. Telegraph账号管理
2. 页面创建和编辑
3. 图片内容处理
4. 异常处理和重试机制

作者: Assistant
创建时间: 2024年
"""

import os
import json
import logging
import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from telegraph import Telegraph
from telegraph.exceptions import TelegraphException

# 配置
DEFAULT_AUTHOR_NAME = "RSS Bot"
DEFAULT_AUTHOR_URL = "https://t.me/RSSBot"  # 替换为实际机器人用户名
MAX_RETRIES = 5


class TelegraphHandler:
    """Telegraph处理器，用于管理Telegraph页面的创建和管理"""

    def __init__(self, access_token: Optional[str] = None, config_path: str = "storage/config/telegraph.json"):
        """
        初始化Telegraph处理器
        
        Args:
            access_token: 可选的Telegraph访问令牌
            config_path: 配置文件路径
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path)
        self.access_token = access_token
        self.telegraph = None
        
        # 尝试从配置文件加载token
        if not self.access_token:
            self.access_token = self._load_token_from_config()
            
        # 初始化Telegraph实例
        self._init_telegraph()

    def _init_telegraph(self) -> None:
        """初始化Telegraph实例"""
        if self.access_token:
            self.telegraph = Telegraph(access_token=self.access_token)
            self.logger.info(f"Telegraph实例已初始化，使用现有token")
        else:
            # 初始化无token的实例
            self.telegraph = Telegraph()
            
            # 立即创建账号并获取token
            try:
                self.telegraph.create_account(short_name="AnyRSS")
                self.access_token = self.telegraph.get_access_token()
                self._save_token_to_config(self.access_token)
                self.logger.info(f"Telegraph账号自动创建成功，token: {self.access_token[:10]}...")
            except Exception as e:
                self.logger.warning(f"自动创建Telegraph账号失败: {str(e)}，后续操作可能会失败")

    def _load_token_from_config(self) -> Optional[str]:
        """从配置文件加载token"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    token = config.get('access_token')
                    if token:
                        self.logger.info(f"从配置文件加载Telegraph token成功")
                        return token
        except Exception as e:
            self.logger.error(f"加载Telegraph配置失败: {str(e)}")
        
        return None

    def _save_token_to_config(self, token: str) -> None:
        """保存token到配置文件"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            config = {}
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            config['access_token'] = token
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Telegraph token已保存到配置文件")
        except Exception as e:
            self.logger.error(f"保存Telegraph配置失败: {str(e)}")

    async def create_account(self, short_name: str = "AnyRSS") -> str:
        """
        创建Telegraph账号并获取access_token
        
        Args:
            short_name: 账号短名称
            
        Returns:
            str: 访问令牌
        """
        try:
            # Telegraph API操作是同步的，放在执行线程中运行
            def _create_account():
                self.telegraph.create_account(short_name=short_name)
                return self.telegraph.get_access_token()
            
            token = await asyncio.to_thread(_create_account)
            
            self.access_token = token
            self._save_token_to_config(token)
            self.logger.info(f"Telegraph账号创建成功，token: {token[:10]}...")
            
            return token
        except Exception as e:
            self.logger.error(f"创建Telegraph账号失败: {str(e)}")
            raise

    async def create_page(self, 
                         title: str, 
                         content: str, 
                         author_name: str = DEFAULT_AUTHOR_NAME, 
                         author_url: str = DEFAULT_AUTHOR_URL) -> Tuple[str, str]:
        """
        创建Telegraph页面
        
        Args:
            title: 页面标题
            content: HTML格式的页面内容
            author_name: 作者名称
            author_url: 作者URL
            
        Returns:
            Tuple[str, str]: (页面URL, 页面路径)
        """
        retries = 0
        last_error = None
        
        while retries < MAX_RETRIES:
            try:
                # Telegraph API操作是同步的，放在执行线程中运行
                def _create_page():
                    response = self.telegraph.create_page(
                        title=title,
                        html_content=content,
                        author_name=author_name,
                        author_url=author_url
                    )
                    return response
                
                response = await asyncio.to_thread(_create_page)
                
                page_url = f"https://telegra.ph/{response['path']}"
                page_path = response['path']
                
                self.logger.info(f"Telegraph页面创建成功: {page_url}")
                return page_url, page_path
            
            except Exception as e:
                last_error = e
                retries += 1
                self.logger.warning(f"创建Telegraph页面失败 (尝试 {retries}/{MAX_RETRIES}): {str(e)}")
                
                # 如果失败可能是token问题，尝试创建新账号
                if retries >= 2:
                    try:
                        await self.create_account()
                        self.logger.info("已创建新的Telegraph账号，将重试")
                    except Exception as account_error:
                        self.logger.error(f"创建新Telegraph账号也失败: {str(account_error)}")
                
                # 重试前等待
                await asyncio.sleep(2)
        
        self.logger.error(f"创建Telegraph页面失败，已达最大重试次数: {last_error}")
        raise last_error or Exception("创建Telegraph页面失败，原因未知")

    async def create_media_page(self, 
                               title: str, 
                               media_urls: List[str],
                               description: str = "",
                               author_name: str = DEFAULT_AUTHOR_NAME,
                               author_url: str = DEFAULT_AUTHOR_URL) -> Tuple[str, str]:
        """
        创建包含多个媒体文件的Telegraph页面
        
        Args:
            title: 页面标题
            media_urls: 媒体URL列表
            description: 页面描述文本
            author_name: 作者名称
            author_url: 作者URL
            
        Returns:
            Tuple[str, str]: (页面URL, 页面路径)
        """
        # 构建HTML内容
        html_content = ""
        
        # 添加描述（如果有）
        if description:
            html_content += f"<p>{description}</p>"
        
        # 添加媒体内容
        for url in media_urls:
            # 根据URL判断媒体类型
            if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                html_content += f'<img src="{url}" />'
            elif any(url.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.webm']):
                html_content += f'<video src="{url}" controls></video>'
            else:
                # 默认作为图片处理
                html_content += f'<img src="{url}" />'
        
        # 创建页面
        return await self.create_page(
            title=title,
            content=html_content,
            author_name=author_name,
            author_url=author_url
        )


# 单例模式，提供全局访问点
_telegraph_instance = None

def get_telegraph_handler(access_token: Optional[str] = None) -> TelegraphHandler:
    """
    获取TelegraphHandler实例（单例模式）
    
    Args:
        access_token: 可选的Telegraph访问令牌
        
    Returns:
        TelegraphHandler: Telegraph处理器实例
    """
    global _telegraph_instance
    if _telegraph_instance is None:
        _telegraph_instance = TelegraphHandler(access_token=access_token)
    return _telegraph_instance


async def create_telegraph_media_page(
    title: str,
    media_urls: List[str],
    description: str = "",
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_url: str = DEFAULT_AUTHOR_URL
) -> Tuple[str, str]:
    """
    创建包含多个媒体文件的Telegraph页面（便捷函数）
    
    Args:
        title: 页面标题
        media_urls: 媒体URL列表
        description: 页面描述文本
        author_name: 作者名称
        author_url: 作者URL
        
    Returns:
        Tuple[str, str]: (页面URL, 页面路径)
    """
    handler = get_telegraph_handler()
    return await handler.create_media_page(
        title=title,
        media_urls=media_urls,
        description=description,
        author_name=author_name,
        author_url=author_url
    )


if __name__ == "__main__":
    # 模块测试代码
    import asyncio
    import logging
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test_telegraph_handler():
        handler = get_telegraph_handler()
        
        # 测试创建账号
        if not handler.access_token:
            await handler.create_account()
        
        # 测试创建媒体页面
        test_urls = [
            "https://www.example.com/image1.jpg",
            "https://www.example.com/image2.jpg",
            "https://www.example.com/image3.jpg"
        ]
        
        page_url, page_path = await handler.create_media_page(
            title="测试媒体页面",
            media_urls=test_urls,
            description="这是一个测试媒体页面"
        )
        
        print(f"页面已创建: {page_url}")
    
    # 运行测试
    asyncio.run(test_telegraph_handler()) 