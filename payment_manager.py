"""
Менеджер платежей - обработка покупок и выдача доступа
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from database import Purchase, UserAccess, User, APIKey, PaymentLog
from config import config
from funpay_client import funpay_client

logger = logging.getLogger(__name__)


class PaymentManager:
    """Управление платежами и выдачей доступа"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_payment(self, webhook_data: dict, discord_id: str) -> bool:
        """
        Обработать платеж от FunPay
        
        Args:
            webhook_data: Данные из вебхука FunPay
            discord_id: ID пользователя Discord
        
        Returns:
            True если платеж успешно обработан
        """
        try:
            # Создать запись о платеже
            purchase = Purchase(
                id=str(uuid.uuid4()),
                discord_id=discord_id,
                username=webhook_data.get("username", "Unknown"),
                tariff=self._determine_tariff(webhook_data.get("amount", 0)),
                amount=webhook_data.get("amount", 0),
                status="completed",
                funpay_order_id=webhook_data.get("order_id"),
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            
            # Определить время истечения доступа
            tariff_config = config.TARIFFS.get(purchase.tariff)
            if tariff_config:
                purchase.expires_at = datetime.utcnow() + timedelta(
                    days=tariff_config.get("duration_days", 30)
                )
            
            self.db.add(purchase)
            self.db.commit()
            
            logger.info(f"✅ Payment processed: {purchase.id} for user {discord_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing payment: {e}")
            self.db.rollback()
            return False
    
    def _determine_tariff(self, amount: int) -> str:
        """Определить тариф по сумме платежа"""
        tariffs = config.TARIFFS
        
        for tariff_id, tariff_data in tariffs.items():
            if tariff_data.get("price") == amount:
                return tariff_id
        
        # По умолчанию базовый тариф
        return "premium_1month"
    
    def grant_access(self, discord_id: str, purchase_id: str, guild_id: int) -> bool:
        """
        Выдать доступ пользователю (роль, каналы, API ключ)
        
        Args:
            discord_id: ID пользователя Discord
            purchase_id: ID покупки
            guild_id: ID гильдии Discord
        
        Returns:
            True если доступ выдан успешно
        """
        try:
            purchase = self.db.query(Purchase).filter_by(id=purchase_id).first()
            if not purchase:
                logger.error(f"Purchase not found: {purchase_id}")
                return False
            
            tariff_config = config.TARIFFS.get(purchase.tariff, {})
            
            # Выдать роли
            for role_name in tariff_config.get("roles", []):
                access = UserAccess(
                    id=str(uuid.uuid4()),
                    discord_id=discord_id,
                    role_id=role_name,
                    channel_id=None,
                    purchase_id=purchase_id,
                    expires_at=purchase.expires_at
                )
                self.db.add(access)
            
            # Выдать доступ к каналам
            for channel_name in tariff_config.get("channels", []):
                access = UserAccess(
                    id=str(uuid.uuid4()),
                    discord_id=discord_id,
                    role_id=None,
                    channel_id=channel_name,
                    purchase_id=purchase_id,
                    expires_at=purchase.expires_at
                )
                self.db.add(access)
            
            # Выдать API ключ если это VIP
            if purchase.tariff == "vip":
                api_key = self._generate_api_key(discord_id, purchase_id)
                self.db.add(api_key)
            
            self.db.commit()
            logger.info(f"✅ Access granted to {discord_id} for purchase {purchase_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error granting access: {e}")
            self.db.rollback()
            return False
    
    def _generate_api_key(self, discord_id: str, purchase_id: str) -> APIKey:
        """Генерировать API ключ"""
        import secrets
        import hashlib
        
        # Генерировать случайный ключ
        random_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(random_key.encode()).hexdigest()
        key_prefix = f"sk_live_{random_key[:8]}"
        
        api_key = APIKey(
            id=str(uuid.uuid4()),
            discord_id=discord_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            permissions='{"read": true, "write": false}'
        )
        
        return api_key
    
    def revoke_access(self, discord_id: str, purchase_id: str) -> bool:
        """
        Отозвать доступ (истёк период подписки)
        
        Args:
            discord_id: ID пользователя Discord
            purchase_id: ID покупки
        
        Returns:
            True если доступ отозван
        """
        try:
            accesses = self.db.query(UserAccess).filter_by(
                discord_id=discord_id,
                purchase_id=purchase_id
            ).all()
            
            for access in accesses:
                access.is_active = False
            
            self.db.commit()
            logger.info(f"✅ Access revoked for {discord_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error revoking access: {e}")
            self.db.rollback()
            return False
    
    def get_user_active_purchases(self, discord_id: str) -> List[Purchase]:
        """Получить активные покупки пользователя"""
        return self.db.query(Purchase).filter_by(
            discord_id=discord_id,
            status="completed"
        ).filter(
            Purchase.expires_at > datetime.utcnow()
        ).all()
    
    def check_expired_accesses(self) -> int:
        """
        Проверить и отозвать истёкшие доступы
        
        Returns:
            Количество отозванных доступов
        """
        try:
            expired = self.db.query(UserAccess).filter(
                UserAccess.expires_at < datetime.utcnow(),
                UserAccess.is_active == True
            ).all()
            
            count = 0
            for access in expired:
                access.is_active = False
                count += 1
            
            self.db.commit()
            logger.info(f"✅ Revoked {count} expired accesses")
            return count
            
        except Exception as e:
            logger.error(f"❌ Error checking expired accesses: {e}")
            return 0