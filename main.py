import asyncio
from aiogram import Bot, Dispatcher
from handlers.routes import router
from config import BOT_TOKEN

dp = Dispatcher()
dp.include_router(router)


async def main():
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

