import logging
import os
import asyncio

from apps import telegram_bot, discord_bot
from core.config import discord_config, telegram_config


def main():

    # Setup logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s',
        level=logging.INFO
    )

    # Setup and run Discor/Telegram bot

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # loop = asyncio.get_event_loop()

    tasks = []
    discord_token = str(discord_config['token'])
    telegram_token = str(telegram_config['token'])
    logging.info(f'discord token: {discord_token}')
    logging.info(f'telegram token: {telegram_token}')

    if discord_token:
        tasks.append(discord_bot.start_task())

    if telegram_token:
        tasks.append(telegram_bot.init_task())
        tokens = telegram_token.split(",")
        if len(tokens) >= 1:
            for tel_token in tokens:
                tasks.append(telegram_bot.start_task(tel_token))
                # 为每个bot添加定时任务
                tasks.append(telegram_bot.scheduled_task(tel_token))

    try:
        loop.run_until_complete(asyncio.gather(*tasks))
        # loop.call_later(5, asyncio.ensure_future, telegram_bot.scheduled_task())
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Ctrl-C close!!")
        telegram_bot.close_all()
    finally:
        loop.close()


if __name__ == '__main__':
    main()

