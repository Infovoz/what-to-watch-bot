import asyncio
from aiogram import Bot, Dispatcher
from handlers.routes import router
from config import BOT_TOKEN
from database.models import init_db

dp = Dispatcher()
dp.include_router(router)


async def main():
    await init_db()
    print("✅ База данных готова")

    bot = Bot(token=BOT_TOKEN)
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
