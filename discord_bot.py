"""
Основной Discord Bot с командами для монетизации
"""
import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
from config import config
from database import SessionLocal, User, Purchase, UserAccess
from payment_manager import PaymentManager
from ad_manager import ad_manager, PremiumManager
from webhook_handler import register_payment_callback
import asyncio

logger = logging.getLogger(__name__)
logging.basicConfig(level=config.LOG_LEVEL)

# Настройка бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)

# Глобальная сессия БД
db = SessionLocal()


@bot.event
async def on_ready():
    """При запуске бота"""
    logger.info(f"✅ Bot logged in as {bot.user}")
    check_expired_subscriptions.start()
    sync_access.start()


@tasks.loop(hours=1)
async def check_expired_subscriptions():
    """Проверять истёкшие подписки каждый час"""
    try:
        pm = PaymentManager(db)
        expired_count = pm.check_expired_accesses()
        if expired_count > 0:
            logger.info(f"🔄 Checked and revoked {expired_count} expired accesses")
    except Exception as e:
        logger.error(f"❌ Error in scheduled task: {e}")


@tasks.loop(minutes=5)
async def sync_access():
    """Синхронизировать доступ в Discord (роли, каналы)"""
    try:
        guild = bot.get_guild(config.DISCORD_GUILD_ID)
        if not guild:
            return
        
        # Получить всех пользователей с активным доступом
        active_accesses = db.query(UserAccess).filter_by(is_active=True).all()
        
        for access in active_accesses:
            user_id = int(access.discord_id)
            member = guild.get_member(user_id)
            
            if not member:
                continue
            
            # Выдать роль если нужно
            if access.role_id:
                role = discord.utils.get(guild.roles, name=access.role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        logger.info(f"✅ Assigned role {access.role_id} to {member}")
                    except Exception as e:
                        logger.error(f"❌ Error assigning role: {e}")
    
    except Exception as e:
        logger.error(f"❌ Error in sync_access task: {e}")


# ==================== КОМАНДЫ ====================

@bot.command(name="subscribe")
async def cmd_subscribe(ctx):
    """Показать доступные подписки"""
    embed = discord.Embed(
        title="💳 Доступные подписки",
        description="Выберите подписку для получения доступа к контенту",
        color=discord.Color.gold()
    )
    
    for tariff_id, tariff_data in config.TARIFFS.items():
        price = tariff_data.get("price")
        duration = tariff_data.get("duration_days")
        perks = "\n".join(f"✓ {perk}" for perk in tariff_data.get("perks", []))
        
        embed.add_field(
            name=f"{tariff_data.get('name')} - {price}₽",
            value=f"⏱️ Срок: {duration} дней\n{perks}",
            inline=False
        )
    
    embed.set_footer(text="Напишите !buy <tariff_id> для покупки")
    
    # Показать рекламу если нужно
    ad_embed = await ad_manager.maybe_show_ad(ctx, db)
    if ad_embed:
        await ctx.send(embed=ad_embed)
    
    await ctx.send(embed=embed)


@bot.command(name="buy")
async def cmd_buy(ctx, tariff_id: str = None):
    """Купить подписку"""
    if not tariff_id:
        await ctx.send("❌ Укажите ID тарифа. Пример: `!buy premium_1month`")
        return
    
    if tariff_id not in config.TARIFFS:
        await ctx.send(f"❌ Неизвестный тариф: {tariff_id}")
        return
    
    tariff = config.TARIFFS[tariff_id]
    price = tariff.get("price")
    
    # Создать личное сообщение с инструкциями
    try:
        embed = discord.Embed(
            title="💰 Инструкция по покупке",
            description=f"Вы выбрали: {tariff.get('name')}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="💵 Сумма платежа",
            value=f"{price}₽",
            inline=False
        )
        
        embed.add_field(
            name="📝 Как оплатить",
            value=(
                "1. Перейдите на FunPay\n"
                "2. Найдите товар в магазине\n"
                "3. В комментарии введите ваш Discord ID\n"
                f"4. Отправьте платёж на {price}₽\n"
                "5. Дождитесь автоматического одобрения"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🆔 Ваш Discord ID",
            value=f"`{ctx.author.id}`",
            inline=False
        )
        
        embed.add_field(
            name="📌 Примечание",
            value="Скопируйте ваш Discord ID и используйте его в комментарии платежа",
            inline=False
        )
        
        await ctx.author.send(embed=embed)
        await ctx.send(f"✅ Проверьте личные сообщения!")
        
    except discord.Forbidden:
        await ctx.send(f"❌ Не удалось отправить личное сообщение. Откройте личные сообщения от серверных участников.")


@bot.command(name="status")
async def cmd_status(ctx):
    """Проверить статус подписки"""
    user_id = str(ctx.author.id)
    
    embed = discord.Embed(
        title="📊 Статус вашей подписки",
        color=discord.Color.blue()
    )
    
    # Получить активные покупки
    pm = PaymentManager(db)
    purchases = pm.get_user_active_purchases(user_id)
    
    if not purchases:
        embed.description = "❌ У вас нет активных подписок"
        embed.add_field(
            name="Приобрести подписку",
            value="Напишите `!subscribe` для просмотра доступных тарифов",
            inline=False
        )
    else:
        for purchase in purchases:
            tariff_name = config.TARIFFS.get(purchase.tariff, {}).get("name", "Unknown")
            remaining_days = (purchase.expires_at - datetime.utcnow()).days
            
            embed.add_field(
                name=f"✅ {tariff_name}",
                value=f"Осталось: {remaining_days} дней\nИстекает: {purchase.expires_at.strftime('%d.%m.%Y')}",
                inline=False
            )
    
    # Показать рекламу
    ad_embed = await ad_manager.maybe_show_ad(ctx, db)
    if ad_embed:
        await ctx.send(embed=ad_embed)
    
    await ctx.send(embed=embed)


@bot.command(name="vip")
async def cmd_vip(ctx):
    """Информация о VIP подписке и API ключе"""
    embed = discord.Embed(
        title="👑 VIP Подписка",
        description="Получите полный доступ к платформе",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="💎 Преимущества VIP",
        value=(
            "✓ Доступ ко всем каналам\n"
            "✓ API ключ для интеграций\n"
            "✓ Приоритетная поддержка\n"
            "✓ Эксклюзивный контент\n"
            "✓ Без рекламы"
        ),
        inline=False
    )
    
    vip_price = config.TARIFFS.get("vip", {}).get("price", 499)
    embed.add_field(
        name="💰 Цена",
        value=f"{vip_price}₽ за месяц",
        inline=False
    )
    
    embed.add_field(
        name="🔑 API Ключ",
        value="Получите уникальный API ключ для доступа к нашему API",
        inline=False
    )
    
    embed.add_field(
        name="🛍️ Как купить",
        value="Напишите `!buy vip` для покупки VIP подписки",
        inline=False
    )
    
    # Показать рекламу
    ad_embed = await ad_manager.maybe_show_ad(ctx, db)
    if ad_embed:
        await ctx.send(embed=ad_embed)
    
    await ctx.send(embed=embed)


@bot.command(name="referral")
async def cmd_referral(ctx):
    """Программа рефереров"""
    embed = discord.Embed(
        title="🎁 Программа рефереров",
        description="Зарабатывайте на приглашении друзей",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="💰 Система заработка",
        value=(
            "• За каждого приглашённого друга: 100₽\n"
            "• За Premium подписку друга: 50₽\n"
            "• За VIP подписку друга: 100₽"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔗 Ваша реферальная ссылка",
        value=f"`https://discord.gg/your-server?ref={ctx.author.id}`",
        inline=False
    )
    
    embed.add_field(
        name="📊 Минимум для вывода",
        value="500₽ (можно вывести на карту или как бонус в магазине)",
        inline=False
    )
    
    await ctx.send(embed=embed)


@bot.command(name="joke")
async def cmd_joke(ctx):
    """Получить случайную шутку"""
    from joke_generator import JokeGenerator
    
    generator = JokeGenerator()
    joke = await generator.get_formatted_joke()
    
    # Показать рекламу
    ad_embed = await ad_manager.maybe_show_ad(ctx, db)
    if ad_embed:
        await ctx.send(embed=ad_embed)
    
    await ctx.send(joke)


@bot.command(name="help")
async def cmd_help(ctx):
    """Справка по командам"""
    embed = discord.Embed(
        title="📖 Справка по командам",
        color=discord.Color.blue()
    )
    
    commands_list = {
        "!subscribe": "Просмотреть доступные подписки",
        "!buy <tariff>": "Купить подписку",
        "!status": "Проверить статус своей подписки",
        "!vip": "Информация о VIP подписке",
        "!referral": "Программа рефереров",
        "!joke": "Получить случайную шутку",
        "!help": "Справка по командам"
    }
    
    for command, description in commands_list.items():
        embed.add_field(name=command, value=description, inline=False)
    
    await ctx.send(embed=embed)


# ==================== ADMIN КОМАНДЫ ====================

@bot.command(name="admin_grant")
@commands.has_role(config.ADMIN_ROLE_ID)
async def cmd_admin_grant(ctx, user_id: int, tariff: str):
    """[АДМИН] Выдать доступ пользователю вручную"""
    try:
        user_id_str = str(user_id)
        pm = PaymentManager(db)
        
        # Создать фиксированную покупку
        from database import Purchase
        import uuid
        
        purchase = Purchase(
            id=str(uuid.uuid4()),
            discord_id=user_id_str,
            username="admin_grant",
            tariff=tariff,
            amount=0,
            status="completed",
            funpay_order_id=f"admin_{uuid.uuid4()}",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        
        tariff_config = config.TARIFFS.get(tariff)
        if tariff_config:
            from datetime import timedelta
            purchase.expires_at = datetime.utcnow() + timedelta(
                days=tariff_config.get("duration_days", 30)
            )
        
        db.add(purchase)
        db.commit()
        
        # Выдать доступ
        pm.grant_access(user_id_str, purchase.id, config.DISCORD_GUILD_ID)
        
        await ctx.send(f"✅ Выдал доступ пользователю {user_id} ({tariff})")
        
    except Exception as e:
        logger.error(f"❌ Admin grant error: {e}")
        await ctx.send(f"❌ Ошибка: {e}")


# ==================== ОБРАБОТЧИК ПЛАТЕЖЕЙ ====================

async def on_payment_received(webhook_data):
    """Callback функция при получении платежа"""
    try:
        order_id = webhook_data.get("order_id")
        username = webhook_data.get("username")
        status = webhook_data.get("status")
        
        logger.info(f"💳 Payment received: {order_id} from {username} - {status}")
        
        # TODO: Связать Discord ID с платежом через комментарий или БД
        # Пока пример обработки платежа
        
    except Exception as e:
        logger.error(f"❌ Error processing payment callback: {e}")


# Зарегистрировать callback
register_payment_callback(on_payment_received)


def run_bot():
    """Запустить бота"""
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    run_bot()