from dotenv import load_dotenv
import os

load_dotenv()

telegram_config = {
    "token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "target_chat": os.environ.get("TELEGRAM_TARGET_CHAT"),  # 不设默认值，强制要求配置
}

discord_config = {
    "token": os.environ.get("DISCORD_TOKEN", ""),
}
