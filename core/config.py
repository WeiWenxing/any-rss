from dotenv import load_dotenv
import os

load_dotenv()

telegram_config = {
    "token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "target_chat": os.environ.get("TELEGRAM_TARGET_CHAT"),  # 不设默认值，强制要求配置
    "api_base_url": os.environ.get("TELEGRAM_API_BASE_URL"),  # 本地API服务器地址，可选
}

discord_config = {
    "token": os.environ.get("DISCORD_TOKEN", ""),
}

# 调试配置
debug_config = {
    "enabled": os.environ.get("DEBUG_MODE", "false").lower() in ("true", "1", "yes", "on"),
}
