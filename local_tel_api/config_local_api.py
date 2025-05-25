# 本地Bot API服务器配置
# 用途：配置机器人使用本地Bot API服务器

import os
import logging
from telegram.ext import Application

def create_local_bot_application(bot_token: str, local_api_url: str = "http://localhost:8081") -> Application:
    """
    创建使用本地Bot API服务器的机器人应用
    
    Args:
        bot_token: 机器人Token
        local_api_url: 本地API服务器地址，默认为localhost:8081
        
    Returns:
        Application: 配置好的机器人应用
    """
    # 本地Bot API服务器配置
    LOCAL_API_BASE_URL = f"{local_api_url}/bot"
    LOCAL_API_BASE_FILE_URL = f"{local_api_url}/file/bot"
    
    # 创建应用，指向本地服务器
    application = Application.builder() \
        .token(bot_token) \
        .base_url(LOCAL_API_BASE_URL) \
        .base_file_url(LOCAL_API_BASE_FILE_URL) \
        .build()
    
    logging.info(f"✅ 机器人已配置使用本地Bot API服务器")
    logging.info(f"📍 API地址: {LOCAL_API_BASE_URL}")
    logging.info(f"📁 文件地址: {LOCAL_API_BASE_FILE_URL}")
    
    return application

def create_official_bot_application(bot_token: str) -> Application:
    """
    创建使用官方Bot API服务器的机器人应用（备用方案）
    
    Args:
        bot_token: 机器人Token
        
    Returns:
        Application: 配置好的机器人应用
    """
    application = Application.builder().token(bot_token).build()
    
    logging.info(f"✅ 机器人已配置使用官方Bot API服务器")
    logging.info(f"📍 API地址: https://api.telegram.org/bot")
    
    return application

def get_local_api_info():
    """获取本地API服务器信息"""
    return {
        "api_url": "http://localhost:8081/bot",
        "file_url": "http://localhost:8081/file/bot",
        "advantages": [
            "✅ 文件大小限制: 2GB（vs 官方50MB）",
            "✅ 更快的文件上传速度",
            "✅ 更高的API调用限制",
            "✅ 本地文件缓存",
            "✅ 更好的隐私保护",
            "✅ 支持大视频文件发送"
        ],
        "requirements": [
            "🔧 需要运行本地Bot API服务器",
            "🔑 需要Telegram API ID和API Hash",
            "🌐 服务器需要稳定的网络连接"
        ]
    }

def test_local_api_connection(local_api_url: str = "http://localhost:8081") -> bool:
    """
    测试本地API服务器连接
    
    Args:
        local_api_url: 本地API服务器地址
        
    Returns:
        bool: 连接是否成功
    """
    try:
        import requests
        response = requests.get(f"{local_api_url}/", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"本地API服务器连接失败: {e}", exc_info=True)
        return False

# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 显示配置信息
    info = get_local_api_info()
    print("🏠 本地Bot API服务器配置信息:")
    print(f"📍 API地址: {info['api_url']}")
    print(f"📁 文件地址: {info['file_url']}")
    
    print("\n🎯 优势:")
    for advantage in info["advantages"]:
        print(f"  {advantage}")
    
    print("\n📋 要求:")
    for requirement in info["requirements"]:
        print(f"  {requirement}")
    
    print("\n📝 使用方法:")
    print("1. 在telegram_bot.py中导入: from config_local_api import create_local_bot_application")
    print("2. 替换: application = create_local_bot_application(BOT_TOKEN)")
    print("3. 确保本地API服务器正在运行")
    
    # 测试连接
    print("\n🔍 测试本地API连接...")
    if test_local_api_connection():
        print("✅ 本地API服务器连接成功")
    else:
        print("❌ 本地API服务器连接失败，请检查服务器是否运行") 