"""
Модель базы данных для отслеживания платежей и доступа пользователей
"""
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import config

DATABASE_URL = config.DATABASE_URL

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    discord_id = Column(String, primary_key=True, index=True)
    username = Column(String, index=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Purchase(Base):
    """Модель покупки/платежа"""
    __tablename__ = "purchases"
    
    id = Column(String, primary_key=True, index=True)  # FunPay Order ID
    discord_id = Column(String, index=True)
    username = Column(String)
    tariff = Column(String)
    amount = Column(Integer)  # цена в рублях
    status = Column(String, default="pending")  # pending, completed, failed
    funpay_order_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    def is_active(self):
        """Проверить активна ли покупка"""
        if self.status != "completed":
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


class UserAccess(Base):
    """Модель доступа пользователя"""
    __tablename__ = "user_access"
    
    id = Column(String, primary_key=True, index=True)
    discord_id = Column(String, index=True)
    role_id = Column(String)
    channel_id = Column(String)
    purchase_id = Column(String, index=True)
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)


class APIKey(Base):
    """Модель API ключа пользователя"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, index=True)
    discord_id = Column(String, index=True)
    key_hash = Column(String, unique=True)
    key_prefix = Column(String)  # Для отображения: sk_live_1234...
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    permissions = Column(Text)  # JSON с разрешениями


class PaymentLog(Base):
    """Логирование платежей для отладки"""
    __tablename__ = "payment_logs"
    
    id = Column(String, primary_key=True, index=True)
    webhook_data = Column(Text)
    status = Column(String)
    error_message = Column(String, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
    discord_id = Column(String, nullable=True, index=True)


# Создать все таблицы
Base.metadata.create_all(bind=engine)


def get_db():
    """Получить сессию базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()