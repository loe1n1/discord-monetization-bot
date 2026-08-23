"""
Конфигурация приложения
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Основная конфигурация"""
    
    # Discord
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))
    PREFIX = os.getenv("PREFIX", "!")
    ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))
    
    # FunPay
    FUNPAY_MERCHANT_ID = os.getenv("FUNPAY_MERCHANT_ID")
    FUNPAY_SECRET_KEY = os.getenv("FUNPAY_SECRET_KEY")
    FUNPAY_API_TOKEN = os.getenv("FUNPAY_API_TOKEN")
    FUNPAY_API_URL = "https://api.funpay.ru"
    
    # Webhook
    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8000))
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"http://localhost:{WEBHOOK_PORT}")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./monetization.db")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Tariffs (Тарифы)
    TARIFFS = {
        "premium_1month": {
            "name": "Premium 1 месяц",
            "price": 99,
            "duration_days": 30,
            "roles": ["Premium"],
            "channels": ["premium-content", "exclusive-news"],
            "perks": ["Доступ к VIP каналам", "Приоритет поддержки"]
        },
        "premium_3months": {
            "name": "Premium 3 месяца",
            "price": 249,
            "duration_days": 90,
            "roles": ["Premium"],
            "channels": ["premium-content", "exclusive-news"],
            "perks": ["Доступ к VIP каналам", "Приоритет поддержки"]
        },
        "vip": {
            "name": "VIP Доступ",
            "price": 499,
            "duration_days": 30,
            "roles": ["VIP"],
            "channels": ["premium-content", "exclusive-news", "vip-zone", "api-access"],
            "perks": ["Полный доступ", "API ключ", "Приоритет поддержки"]
        }
    }


config = Config()