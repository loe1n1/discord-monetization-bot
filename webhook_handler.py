"""
FastAPI вебхук сервер для обработки платежей от FunPay
"""
import logging
import json
from fastapi import FastAPI, Request, HTTPException
from uvicorn import run
from datetime import datetime
from config import config
from funpay_client import funpay_client
from database import SessionLocal, PaymentLog
import uuid

logger = logging.getLogger(__name__)
logging.basicConfig(level=config.LOG_LEVEL)

app = FastAPI(title="Discord Monetization Bot - Webhook Server")

# Словарь для хранения callback-функций
payment_callbacks = {}


def register_payment_callback(callback):
    """Зарегистрировать callback функцию для обработки платежей"""
    payment_callbacks['on_payment'] = callback


@app.post("/webhook/funpay")
async def handle_funpay_webhook(request: Request):
    """
    Обработчик вебхука от FunPay
    
    FunPay отправляет POST запрос при завершении платежа
    """
    try:
        # Получить тело запроса
        body = await request.body()
        
        # Проверить подпись
        signature = request.headers.get("X-Funpay-Signature", "")
        if not funpay_client.verify_webhook(body.decode(), signature):
            logger.warning("❌ Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Парсить данные
        data = json.loads(body)
        webhook_data = funpay_client.parse_webhook_data(data)
        
        if not webhook_data:
            raise HTTPException(status_code=400, detail="Invalid data format")
        
        # Логировать платеж
        db = SessionLocal()
        payment_log = PaymentLog(
            id=str(uuid.uuid4()),
            webhook_data=json.dumps(webhook_data),
            status="received",
            processed_at=datetime.utcnow()
        )
        db.add(payment_log)
        db.commit()
        
        # Вызвать callback функцию (обработчик в Discord боте)
        if 'on_payment' in payment_callbacks:
            callback = payment_callbacks['on_payment']
            # Передать данные в асинхронную функцию бота
            await callback(webhook_data)
            
            # Обновить статус лога
            payment_log.status = "processed"
            db.commit()
        
        logger.info(f"✅ Payment webhook processed: {webhook_data.get('order_id')}")
        
        return {
            "status": "success",
            "order_id": webhook_data.get("order_id"),
            "message": "Payment processed"
        }
        
    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON in webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Проверка здоровья сервера"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/tariffs")
async def get_tariffs():
    """Получить список доступных тарифов"""
    return {
        "tariffs": config.TARIFFS
    }


def start_webhook_server():
    """Запустить FastAPI сервер"""
    logger.info(f"🚀 Starting webhook server on {config.WEBHOOK_HOST}:{config.WEBHOOK_PORT}")
    run(
        app,
        host=config.WEBHOOK_HOST,
        port=config.WEBHOOK_PORT,
        log_level=config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    start_webhook_server()