"""
FunPay API клиент для работы с платежами
"""
import hashlib
import hmac
import json
import logging
from typing import Dict, Optional
import aiohttp
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)


class FunPayClient:
    """Клиент для работы с FunPay API"""
    
    def __init__(self):
        self.base_url = config.FUNPAY_API_URL
        self.merchant_id = config.FUNPAY_MERCHANT_ID
        self.secret_key = config.FUNPAY_SECRET_KEY
        self.api_token = config.FUNPAY_API_TOKEN
    
    def _generate_signature(self, data: str) -> str:
        """Генерировать подпись для вебхука"""
        return hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify_webhook(self, data: str, signature: str) -> bool:
        """Проверить подпись вебхука"""
        expected_signature = self._generate_signature(data)
        return hmac.compare_digest(expected_signature, signature)
    
    async def get_order(self, order_id: str) -> Optional[Dict]:
        """Получить информацию о заказе"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.get(
                    f"{self.base_url}/orders/{order_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"FunPay API error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching order from FunPay: {e}")
            return None
    
    async def check_payment_status(self, funpay_order_id: str) -> Optional[Dict]:
        """Проверить статус платежа в FunPay"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.get(
                    f"{self.base_url}/api/v1/orders/{funpay_order_id}/",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "order_id": data.get("id"),
                            "status": data.get("status"),
                            "amount": data.get("amount"),
                            "user_id": data.get("user_id"),
                            "username": data.get("username"),
                            "comment": data.get("comment")
                        }
                    else:
                        logger.warning(f"Order not found: {funpay_order_id}")
                        return None
        except Exception as e:
            logger.error(f"Error checking payment status: {e}")
            return None
    
    def parse_webhook_data(self, data: Dict) -> Optional[Dict]:
        """Парсить данные вебхука от FunPay"""
        try:
            return {
                "order_id": str(data.get("order_id")),
                "status": data.get("status"),
                "amount": int(data.get("amount", 0)),
                "username": data.get("username", "Unknown"),
                "user_id": data.get("user_id"),
                "comment": data.get("comment", ""),
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error parsing webhook data: {e}")
            return None


funpay_client = FunPayClient()