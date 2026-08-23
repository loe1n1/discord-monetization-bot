"""
Система встроенной рекламы (SaaS модель)
Показывает ненавязчивую рекламу в обмен на бесплатное использование
"""
import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from database import User
from config import config
import discord

logger = logging.getLogger(__name__)


class Advertisement:
    """Структура рекламного объявления"""
    
    def __init__(self, title: str, description: str, link: str = None, emoji: str = "📢"):
        self.title = title
        self.description = description
        self.link = link
        self.emoji = emoji
    
    def to_embed(self) -> discord.Embed:
        """Конвертировать в Discord Embed"""
        embed = discord.Embed(
            title=f"{self.emoji} {self.title}",
            description=self.description,
            color=0xFF6B00
        )
        if self.link:
            embed.add_field(name="📌 Ссылка", value=self.link, inline=False)
        return embed


class AdManager:
    """Менеджер рекламы для бесплатных пользователей"""
    
    def __init__(self):
        # Рекламные объявления
        self.ads: List[Advertisement] = [
            Advertisement(
                title="🎯 Обновите подписку!",
                description="Уберите рекламу и получите доступ к Premium функциям",
                link="Напишите !subscribe для информации"
            ),
            Advertisement(
                title="💎 VIP Доступ Доступен!",
                description="Получите API ключ, приоритет поддержки и эксклюзивный контент",
                link="Напишите !vip для деталей"
            ),
            Advertisement(
                title="🚀 Новые Возможности",
                description="Следите за обновлениями нашего сервиса",
                link="Подписаться на канал обновлений: #announcements"
            ),
            Advertisement(
                title="💰 Заработок На Реферралах",
                description="Приглаше 5 друзей и получите 500 рублей в подарок!",
                link="Напишите !referral для деталей"
            ),
            Advertisement(
                title="📺 Смотрите Наш Контент",
                description="Эксклюзивный контент доступен только для Premium пользователей",
                link="Стань Premium сегодня!"
            ),
        ]
        
        # Частота показа рекламы (1 раз на N команд)
        self.ad_frequency = 3
        self.user_command_count = {}
    
    def add_custom_ad(self, title: str, description: str, link: str = None, emoji: str = "📢"):
        """Добавить собственное объявление"""
        ad = Advertisement(title, description, link, emoji)
        self.ads.append(ad)
        logger.info(f"✅ Added custom ad: {title}")
    
    def should_show_ad(self, user_id: str) -> bool:
        """Проверить должна ли показываться реклама для пользователя"""
        # Инициализировать счётчик если нет
        if user_id not in self.user_command_count:
            self.user_command_count[user_id] = 0
        
        # Увеличить счётчик
        self.user_command_count[user_id] += 1
        
        # Показать рекламу каждый N-й раз
        if self.user_command_count[user_id] % self.ad_frequency == 0:
            return True
        
        return False
    
    def get_random_ad(self) -> Advertisement:
        """Получить случайное объявление"""
        return random.choice(self.ads)
    
    def get_ad_embed(self) -> discord.Embed:
        """Получить рекламное сообщение в виде Embed"""
        ad = self.get_random_ad()
        return ad.to_embed()
    
    async def maybe_show_ad(self, ctx, db: Session) -> Optional[discord.Embed]:
        """
        Возможно показать рекламу при использовании команды
        
        Args:
            ctx: Discord Context
            db: Database session
        
        Returns:
            Embed с рекламой или None
        """
        user_id = str(ctx.author.id)
        
        # Проверить есть ли у пользователя активная подписка
        user = db.query(User).filter_by(discord_id=user_id).first()
        
        # Если у пользователя есть Premium подписка, не показывать рекламу
        if user and hasattr(user, 'premium_until'):
            if user.premium_until and datetime.utcnow() < user.premium_until:
                return None
        
        # Проверить нужно ли показывать рекламу
        if self.should_show_ad(user_id):
            return self.get_ad_embed()
        
        return None
    
    def reset_user_counter(self, user_id: str):
        """Сбросить счётчик команд пользователя (после подписки)"""
        if user_id in self.user_command_count:
            del self.user_command_count[user_id]


class PremiumManager:
    """Управление Premium подписками"""
    
    @staticmethod
    def is_premium(db: Session, user_id: str) -> bool:
        """Проверить есть ли у пользователя активная Premium подписка"""
        user = db.query(User).filter_by(discord_id=user_id).first()
        if not user:
            return False
        
        if hasattr(user, 'premium_until'):
            return datetime.utcnow() < user.premium_until
        
        return False
    
    @staticmethod
    def get_premium_info(db: Session, user_id: str) -> dict:
        """Получить информацию о Premium подписке пользователя"""
        user = db.query(User).filter_by(discord_id=user_id).first()
        
        if not user:
            return {"status": "not_found"}
        
        if hasattr(user, 'premium_until') and user.premium_until:
            remaining = user.premium_until - datetime.utcnow()
            
            if remaining.total_seconds() > 0:
                days = remaining.days
                hours = remaining.seconds // 3600
                return {
                    "status": "active",
                    "expires_at": user.premium_until.isoformat(),
                    "remaining_days": days,
                    "remaining_hours": hours
                }
        
        return {"status": "inactive"}


# Глобальный менеджер рекламы
ad_manager = AdManager()