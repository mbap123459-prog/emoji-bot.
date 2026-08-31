import io
import time
import random
import string
import asyncio
from PIL import Image
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    BufferedInputFile, 
    InputSticker, 
    LabeledPrice, 
    PreCheckoutQuery,
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

BOT_TOKEN = "7835673518:AAG8q5usdEkBHIiw-fmIwNdpukuwARSq8Tw"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

USER_LIMITS = {}
PRICE_STARS = 15
PACK_AMOUNT = 10

# Ссылки на документы от платёжной системы
DOCS_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", url="https://telegra.ph/PUBLICHNAYA-OFERTA-08-12-15")],
        [InlineKeyboardButton(text="🔒 Политика конфиденциальности", url="https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-08-12-99")],
        [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/EmojiBanner_bot")]
    ]
)

def split_image_into_emojis(image_bytes: bytes, cols: int = 3, rows: int = 1) -> list[bytes]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size
    cell_w, cell_h = w // cols, h // rows
    
    crops = []
    for r in range(rows):
        for c in range(cols):
            piece = img.crop((c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h))
            piece = piece.resize((100, 100), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            piece.save(out, format="PNG")
            crops.append(out.getvalue())
    return crops

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    if uid not in USER_LIMITS:
        USER_LIMITS[uid] = 2

    await message.answer(
        f"👋 Привет! Я создаю эмодзи-баннеры для постов.\n\n"
        f"🎁 Доступно бесплатных генераций: **{USER_LIMITS[uid]}**\n\n"
        "Отправь картинку, и я соберу её в готовый эмодзи-пак!\n\n"
        "ℹ️ Документы сервиса доступны по кнопкам ниже:",
        reply_markup=DOCS_KEYBOARD
    )

@dp.message(F.photo | F.document)
async def handle_image(message: types.Message):
    uid = message.from_user.id
    if uid not in USER_LIMITS:
        USER_LIMITS[uid] = 2

    if USER_LIMITS[uid] <= 0:
        pay_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"Купить {PACK_AMOUNT} паков за {PRICE_STARS} ⭐️", callback_data="buy_stars")],
                [InlineKeyboardButton(text="📜 Документы сервиса", callback_data="show_docs")]
            ]
        )
        await message.answer(
            "🔒 **Бесплатные попытки закончились!**\n\n"
            f"Пополни баланс: {PRICE_STARS} Telegram Stars за {PACK_AMOUNT} паков.",
            reply_markup=pay_kb
        )
        return

    wait_msg = await message.answer("✂️ Скачиваю и нарезаю...")
    
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        await wait_msg.edit_text("Пожалуйста, отправь картинку.")
        return

    file = await bot.get_file(file_id)
    file_bytes = io.BytesIO()
    await bot.download_file(file.file_path, file_bytes)

    try:
        pieces = split_image_into_emojis(file_bytes.getvalue(), cols=3, rows=1)
        await wait_msg.edit_text("⚡️ Собираю эмодзи-пак в Telegram...")
        
        bot_user = await bot.get_me()
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        pack_name = f"emoji_{int(time.time())}_{rand_str}_by_{bot_user.username}"
        pack_title = f"Баннер от @{bot_user.username}"
        
        stickers_list = [
            InputSticker(
                sticker=BufferedInputFile(p, filename=f"emoji_{i}.png"),
                format="static",
                emoji_list=["▫️"]
            )
            for i, p in enumerate(pieces, start=1)
        ]
        
        await bot.create_new_sticker_set(
            user_id=message.from_user.id,
            name=pack_name,
            title=pack_title,
            stickers=stickers_list,
            sticker_type="custom_emoji"
        )
        
        USER_LIMITS[uid] -= 1
        link = f"https://t.me/addemoji/{pack_name}"
        
        await wait_msg.edit_text(
            f"🎉 **Готово! Твой эмодзи-пак:**\n{link}\n\n"
            f"Осталось генераций: **{USER_LIMITS[uid]}**"
        )
        
    except Exception as e:
        await wait_msg.edit_text(f"⚠️ Ошибка: {e}")

@dp.callback_query(F.data == "show_docs")
async def show_docs_callback(callback: types.CallbackQuery):
    await callback.message.answer("Официальная документация сервиса:", reply_markup=DOCS_KEYBOARD)
    await callback.answer()

@dp.callback_query(F.data == "buy_stars")
async def send_invoice(callback: types.CallbackQuery):
    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Пакет генераций",
        description=f"Пакет на {PACK_AMOUNT} эмодзи-паков",
        payload="buy_10_packs",
        currency="XTR",
        prices=[LabeledPrice(label=f"{PACK_AMOUNT} паков", amount=PRICE_STARS)]
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    uid = message.from_user.id
    if uid not in USER_LIMITS:
        USER_LIMITS[uid] = 0
    USER_LIMITS[uid] += PACK_AMOUNT

    await message.answer(
        f"⭐️ Оплата прошла! Начислено: **{PACK_AMOUNT}** генераций.\n"
        f"Всего на балансе: **{USER_LIMITS[uid]}**."
    )

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    print(f"🚀 Бот @{me.username} запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
        
