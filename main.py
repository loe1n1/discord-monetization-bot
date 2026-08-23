"""
Главная точка входа - запуск бота и вебхука одновременно
"""
import logging
import asyncio
import threading
from config import config
from webhook_handler import start_webhook_server
from discord_bot import run_bot

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def run_webhook_in_thread():
    """Запустить вебхук сервер в отдельном потоке"""
    logger.info("🚀 Starting webhook server in background thread...")
    start_webhook_server()


def main():
    """Главная функция - запустить всё"""
    logger.info("=" * 50)
    logger.info("🤖 Discord Monetization Bot Starting...")
    logger.info("=" * 50)
    
    # Запустить вебхук сервер в отдельном потоке
    webhook_thread = threading.Thread(target=run_webhook_in_thread, daemon=True)
    webhook_thread.start()
    
    # Небольшая задержка чтобы сервер запустился
    import time
    time.sleep(2)
    
    # Запустить Discord бота в главном потоке
    try:
        logger.info("🎮 Starting Discord bot...")
        run_bot()
    except KeyboardInterrupt:
        logger.info("⛔ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()