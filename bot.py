import os, json
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

def load_news(path="news.json", limit=5):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]
        return data[:limit]
    except Exception:
        return []

def fmt(item):
    title = item.get("title","Без названия")
    link = item.get("link","")
    summary = (item.get("summary") or item.get("full_text","") or "")[:400]
    src = item.get("source","")
    tail = f"\n🔗 <a href='{link}'>Источник</a>" if link else ""
    if src:
        tail += f" • {src}"
    return f"📰 <b>{title}</b>\n{summary}{tail}"

@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("Привет! Я бот канала. Команда: /news — пришлю свежие материалы из news.json")

@dp.message(Command("news"))
async def news(m: Message):
    items = load_news()
    if not items:
        await m.answer("Пока нет актуальных записей в news.json")
        return
    for it in items:
        await m.answer(fmt(it))

@dp.message(Command("post"))
async def post(m: Message):
    # /post текст сообщения
    text = m.text.split(" ", 1)
    if len(text) < 2:
        await m.answer("Использование: /post ваш текст")
        return
    await m.answer(text[1])

@dp.message(F.text)
async def fallback(m: Message):
    await m.answer("Напиши /news — пришлю последние материалы из news.json")

if __name__ == "__main__":
    import asyncio
    async def main():
        await dp.start_polling(bot)
    asyncio.run(main())
