from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from Forms.list_films import Form
from services.movies_api import search_movies, get_movie_details
from database.models import init_db
from database.crud import (
    save_movie,
    save_genres,
    save_actors,
    add_to_user_list,
    get_user_movies,
    is_movie_in_user_list,
    delete_from_user_list,
    get_user_stats,
    get_recommendations,
    get_movie_by_id,
    get_movie_actors,
    get_movie_genres
)

router = Router()


def format_rating(rating):
    """Приводит рейтинг к читаемому виду."""
    if isinstance(rating, dict):
        val = rating.get('kp', rating.get('vote_average', 0))
    else:
        val = rating
    try:
        return f"{float(val):.1f}"
    except (ValueError, TypeError):
        return '—'


def get_main_reply_keyboard():
    """Клавиатура под строкой ввода (всегда видна)."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню"), KeyboardButton(text="📋 Все команды")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_main_inline_keyboard():
    """Главное меню (под сообщением)."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить фильм", callback_data="add_movie")],
            [InlineKeyboardButton(text="📋 Мой список", callback_data="list_movie")],
            [InlineKeyboardButton(text="🗑 Удалить фильм", callback_data="delete_movie")],
            [InlineKeyboardButton(text="🎲 Рекомендации", callback_data="recommend")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")],
        ]
    )
    return keyboard


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def _show_rec_page(message, recs, offset, shown_ids):
    """Показывает страницу рекомендаций."""
    text = "🎲 <b>Рекомендации для тебя</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for i, rec in enumerate(recs, 1):
        r = format_rating(rec.get('rating'))
        text += f"{i}. {rec['name']} ({rec['year']}) — ⭐ {r}\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📋 Подробнее о «{rec['name']}»",
                callback_data=f"rec_detail_{rec.get('kp_id', rec.get('id'))}_{offset}"
            )
        ])

    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅ Назад", callback_data=f"rec_page_{offset - 1}"))
    if len(recs) >= 3:
        new_shown = shown_ids + [r.get('kp_id', r.get('id')) for r in recs]
        shown_str = "_".join([str(x) for x in new_shown])
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡", callback_data=f"rec_page_{offset + 1}_{shown_str}"))

    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")
    ])

    if isinstance(message, Message):
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def _show_help(message: Message):
    """Показывает список всех команд."""
    text = (
        "📋 <b>Все команды</b>\n\n"
        "🏠 <b>Главное меню</b> — /my_movie\n"
        "   Открыть меню со всеми функциями.\n\n"
        "➕ <b>Добавить фильм</b> — /add\n"
        "   Найти и сохранить фильм в список.\n\n"
        "📋 <b>Мой список</b> — /list\n"
        "   Посмотреть все сохранённые фильмы.\n\n"
        "🗑 <b>Удалить фильм</b> — /delete\n"
        "   Убрать фильм из списка по номеру.\n\n"
        "🎲 <b>Рекомендации</b> — /recommend\n"
        "   Получить персональные рекомендации.\n\n"
        "📊 <b>Статистика</b> — /stats\n"
        "   Твои любимые жанры, режиссёры, актёры.\n\n"
        "ℹ️ <b>О боте</b> — /about\n"
        "   Информация о боте.\n\n"
        "🆘 <b>Помощь</b> — /help\n"
        "   Это сообщение."
    )
    await message.answer(text, parse_mode="HTML")


# ==================== ДОБАВЛЕНИЕ ФИЛЬМА ====================

@router.callback_query(lambda c: c.data == "add_movie")
async def add_movie(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🎬 <b>Добавление фильма</b>\n\n"
        "Введи название фильма для поиска:",
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_movie_name)
    await callback.answer()


@router.message(Command('add'))
async def cmd_add(message: Message, state: FSMContext):
    await message.answer(
        "🎬 <b>Добавление фильма</b>\n\n"
        "Введи название фильма для поиска:",
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_movie_name)


@router.message(Form.waiting_for_movie_name, F.text)
async def waiting_for_movie(message: Message, state: FSMContext):
    query = message.text.strip()
    movies = await search_movies(query, limit=5)

    if not movies:
        await message.answer(
            "❌ По вашему запросу ничего не найдено.\n"
            "Попробуйте другое название или нажмите кнопку ниже:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        return

    await state.update_data(search_results=movies)
    await state.set_state(Form.waiting_for_movie_selection)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for movie in movies:
        name = movie.get("name")
        year = movie.get("year")
        kp_id = movie.get("id")
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{name} ({year})",
                callback_data=f"select_{kp_id}"
            )
        ])

    await message.answer(
        "Выберите нужный фильм:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("select_"), Form.waiting_for_movie_selection)
async def movies_selection(callback: CallbackQuery, state: FSMContext):
    kp_id = int(callback.data.replace("select_", ""))
    user_id = callback.from_user.id

    if await is_movie_in_user_list(user_id, kp_id):
        await callback.message.edit_text(
            "❌ Этот фильм уже есть в твоём списке",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        await state.clear()
        await callback.answer()
        return

    await callback.message.edit_text("⏳ Загружаю информацию о фильме...")

    details = await get_movie_details(kp_id)

    if not details:
        await callback.message.edit_text(
            "❌ Не удалось загрузить информацию о фильме",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        await state.clear()
        await callback.answer()
        return

    persons = details.get("persons", [])

    name = details.get("name", "Без названия")
    year = details.get("year")
    description = details.get("description", "")
    rating = details.get("rating", {}).get("kp")
    poster_url = details.get("poster", {}).get("url", "")

    director = "Неизвестно"
    for person in persons:
        if person.get("enProfession") == "director":
            director = person.get("name", "Неизвестно")
            break

    genres = [g.get("name", "") for g in details.get("genres", [])]

    actor_names = []
    for person in persons:
        if person.get("enProfession") == "actor":
            actor_names.append(person.get("name", ""))
    actor_names = actor_names[:5]

    await save_movie(kp_id, name, year, description, rating, poster_url, director)
    if genres:
        await save_genres(kp_id, genres)
    if actor_names:
        await save_actors(kp_id, actor_names)
    await add_to_user_list(user_id, kp_id)

    if poster_url:
        await callback.message.edit_text(
            f"✅ <b>{name}</b> ({year}) добавлен в твой список!",
            parse_mode="HTML"
        )
        await callback.message.answer_photo(
            photo=poster_url,
            caption=f"🎬 <b>{name}</b> ({year})\n"
                    f"⭐ Рейтинг: {format_rating(rating)}\n"
                    f"🎭 Жанры: {', '.join(genres) if genres else '—'}\n"
                    f"🎥 Режиссёр: {director}",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"✅ <b>{name}</b> ({year}) добавлен в твой список!\n\n"
            f"⭐ Рейтинг: {format_rating(rating)}\n"
            f"🎭 Жанры: {', '.join(genres) if genres else '—'}\n"
            f"🎥 Режиссёр: {director}",
            parse_mode="HTML"
        )

    await callback.message.answer(
        "Что делаем дальше?",
        reply_markup=get_main_inline_keyboard()
    )
    await state.clear()
    await callback.answer(f"✅ {name} добавлен!")


# ==================== РЕКОМЕНДАЦИИ ====================

@router.callback_query(lambda c: c.data == "recommend")
async def show_recommendations(callback: CallbackQuery):
    user_id = callback.from_user.id
    recs = await get_recommendations(user_id, offset=0)

    if not recs:
        await callback.message.answer(
            "🎲 <b>Рекомендации</b>\n\n"
            "Не удалось подобрать рекомендации.\n"
            "Попробуй добавить больше фильмов в список!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return

    await _show_rec_page(callback.message, recs, offset=0, shown_ids=[])
    await callback.answer()


@router.message(Command('recommend'))
async def cmd_recommend(message: Message):
    user_id = message.from_user.id
    recs = await get_recommendations(user_id, offset=0)

    if not recs:
        await message.answer(
            "🎲 <b>Рекомендации</b>\n\n"
            "Не удалось подобрать рекомендации.",
            parse_mode="HTML"
        )
        return

    await _show_rec_page(message, recs, offset=0, shown_ids=[])


@router.callback_query(lambda c: c.data.startswith("rec_page_"))
async def rec_page(callback: CallbackQuery):
    parts = callback.data.replace("rec_page_", "").split("_")
    offset = int(parts[0])
    shown_ids = [int(x) for x in parts[1:] if x] if len(parts) > 1 else []

    user_id = callback.from_user.id
    recs = await get_recommendations(user_id, offset=offset, skip_kp_ids=shown_ids)

    if not recs:
        await callback.message.edit_text(
            "🎲 <b>Рекомендации</b>\n\n"
            "Больше нет фильмов для рекомендаций.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return

    await _show_rec_page(callback.message, recs, offset=offset, shown_ids=shown_ids)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("rec_detail_"))
async def show_rec_detail(callback: CallbackQuery):
    parts = callback.data.replace("rec_detail_", "").split("_")
    kp_id = int(parts[0])
    offset = int(parts[1]) if len(parts) > 1 else 0

    movie = await get_movie_by_id(kp_id)

    if movie:
        actors = await get_movie_actors(kp_id)
        genres = await get_movie_genres(kp_id)
        name = movie['name']
        year = movie['year']
        rating = movie['rating']
        poster_url = movie['poster_url']
        director = movie['director']
        description = movie['description']
    else:
        details = await get_movie_details(kp_id)
        if not details:
            await callback.answer("Не удалось загрузить информацию о фильме")
            return

        name = details.get("name", "Без названия")
        year = details.get("year")
        rating = details.get("rating", {}).get("kp")
        poster_url = details.get("poster", {}).get("url", "")
        description = details.get("description", "")

        director = "Неизвестно"
        persons = details.get("persons", [])
        for person in persons:
            if person.get("enProfession") == "director":
                director = person.get("name", "Неизвестно")
                break

        genres = [g.get("name", "") for g in details.get("genres", [])]
        actors = []
        for person in persons:
            if person.get("enProfession") == "actor":
                actors.append(person.get("name", ""))
        actors = actors[:5]

    text = (
        f"🎬 <b>{name}</b> ({year}) — ⭐ {format_rating(rating)}\n\n"
        f"🎭 Жанры: {', '.join(genres) if genres else '—'}\n"
        f"🎥 Режиссёр: {director or '—'}\n"
        f"👤 Актёры: {', '.join(actors) if actors else '—'}\n"
    )
    if description:
        desc = description[:300]
        if len(description) > 300:
            desc += "..."
        text += f"\n📝 {desc}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К рекомендациям", callback_data=f"rec_page_{offset}")]
    ])

    if poster_url:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=poster_url,
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


# ==================== СТАТИСТИКА ====================

@router.callback_query(lambda c: c.data == "show_stats")
async def show_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)

    if stats["total"] == 0:
        await callback.message.edit_text(
            "📊 <b>Статистика</b>\n\n"
            "У тебя пока нет фильмов в списке.\n"
            "Добавь первый фильм!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return

    text = (
        f"📊 <b>Твоя статистика</b>\n\n"
        f"🎬 Всего просмотрено: <b>{stats['total']}</b>\n\n"
        f"🎭 Любимые жанры:\n{stats['favorite_genre']}\n\n"
        f"🎥 Любимые режиссёры:\n{stats['favorite_director']}\n\n"
        f"👤 Любимые актёры:\n{stats['favorite_actor']}"
    )

    if stats["avg_rating"]:
        text += f"\n\n⭐ Средний рейтинг: <b>{stats['avg_rating']}</b>"
    else:
        text += f"\n\n⭐ Средний рейтинг: <b>—</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==================== НАВИГАЦИЯ ====================

@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.answer(
        "Главное меню",
        reply_markup=get_main_inline_keyboard()
    )
    await callback.answer()


# ==================== ПРОСМОТР СПИСКА ====================

@router.callback_query(lambda c: c.data == "list_movie")
async def list_movie(callback: CallbackQuery):
    await _show_list(callback.message, edit=True)
    await callback.answer()


@router.message(Command('list'))
async def cmd_list(message: Message):
    await _show_list(message)


async def _show_list(message_or_callback, edit=False):
    # Определяем user_id
    if hasattr(message_or_callback, 'chat'):
        user_id = message_or_callback.chat.id
    elif hasattr(message_or_callback, 'message') and hasattr(message_or_callback.message, 'chat'):
        user_id = message_or_callback.message.chat.id
    else:
        user_id = message_or_callback.from_user.id

    films = await get_user_movies(user_id)

    if not films:
        text = "📋 Список пока пустой"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
        ])
        if edit and hasattr(message_or_callback, 'message'):
            await message_or_callback.message.edit_text(text, reply_markup=markup)
        else:
            await message_or_callback.answer(text, reply_markup=markup)
        return

    # Разбиваем на части по 50 фильмов (безопасный лимит)
    parts = []
    current_part = ""
    current_count = 0

    for i, (name, year, rating) in enumerate(films, 1):
        rating_text = format_rating(rating)
        line = f"{i}. {name} ({year}) - ⭐{rating_text}\n"

        if len(current_part) + len(line) > 3500:  # запас до лимита 4096
            parts.append(current_part)
            current_part = line
        else:
            current_part += line
        current_count += 1

    if current_part:
        parts.append(current_part)

    # Отправляем первую часть
    total = len(films)
    first_text = f"📋 Твой список фильмов\n{parts[0]}\nВсего: {total}"
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
    ])

    if edit and hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(first_text, reply_markup=markup, parse_mode="HTML")
    else:
        await message_or_callback.answer(first_text, reply_markup=markup, parse_mode="HTML")

    # Отправляем остальные части (если есть) без кнопок
    for part in parts[1:]:
        if hasattr(message_or_callback, 'message'):
            await message_or_callback.message.answer(part, parse_mode="HTML")
        else:
            await message_or_callback.answer(part, parse_mode="HTML")
# ==================== УДАЛЕНИЕ ФИЛЬМА ====================

@router.callback_query(lambda c: c.data == "delete_movie")
async def delete_movie(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    films = await get_user_movies(user_id)

    if not films:
        await callback.message.edit_text(
            "📋 Список пока пустой",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return

    await state.update_data(delete_films=films)
    await state.set_state(Form.waiting_for_delete_number)

    text = "🗑 Удаление фильма\n\n"
    for i, (name, year, rating) in enumerate(films, 1):
        text += f"{i}. {name} ({year})\n"
    text += "\n✏️ Напиши номер фильма, который хочешь удалить:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(Command('delete'))
async def cmd_delete(message: Message, state: FSMContext):
    user_id = message.from_user.id
    films = await get_user_movies(user_id)

    if not films:
        await message.answer("📋 Список пока пустой")
        return

    await state.update_data(delete_films=films)
    await state.set_state(Form.waiting_for_delete_number)

    text = "🗑 Удаление фильма\n\n"
    for i, (name, year, rating) in enumerate(films, 1):
        text += f"{i}. {name} ({year})\n"
    text += "\n✏️ Напиши номер фильма, который хочешь удалить:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")]
    ])
    await message.answer(text, reply_markup=keyboard)


@router.message(Form.waiting_for_delete_number, F.text)
async def process_delete_number(message: Message, state: FSMContext):
    data = await state.get_data()
    films = data.get("delete_films", [])

    try:
        index = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Это не число! Введи номер фильма цифрами.")
        return

    if index < 1:
        await message.answer("❌ Номер должен быть больше 0!")
        return

    if index > len(films):
        await message.answer(f"❌ В твоём списке всего {len(films)} фильмов. Введи число от 1 до {len(films)}.")
        return

    name, year, _ = films[index - 1]
    await state.update_data(delete_index=index, delete_name=name, delete_year=year)
    await state.set_state(Form.waiting_for_delete_confirm)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete")],
        [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete")]
    ])
    await message.answer(
        f"🗑 <b>Удалить фильм «{name}» ({year})?</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data == "confirm_delete", Form.waiting_for_delete_confirm)
async def delete_movie_confirm(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()

    index = data.get("delete_index")
    name = data.get("delete_name")
    year = data.get("delete_year")

    success, _ = await delete_from_user_list(user_id, index)

    if success:
        await callback.message.edit_text(
            f"✅ <b>«{name}» ({year}) удалён из твоего списка!</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Не удалось удалить фильм.")

    await callback.message.answer(
        "Что делаем дальше?",
        reply_markup=get_main_inline_keyboard()
    )
    await state.clear()


@router.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Удаление отменено")
    await callback.message.answer(
        "Что делаем дальше?",
        reply_markup=get_main_inline_keyboard()
    )
    await callback.answer()


# ==================== КОМАНДЫ ====================

@router.message(Command('stats'))
async def stats_cmd(message: Message):
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)

    if stats["total"] == 0:
        await message.answer(
            "📊 <b>Статистика</b>\n\n"
            "У тебя пока нет фильмов в списке.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")]
            ])
        )
        return

    text = (
        f"📊 <b>Твоя статистика</b>\n\n"
        f"🎬 Всего просмотрено: <b>{stats['total']}</b>\n\n"
        f"🎭 Любимые жанры:\n{stats['favorite_genre']}\n\n"
        f"🎥 Любимые режиссёры:\n{stats['favorite_director']}\n\n"
        f"👤 Любимые актёры:\n{stats['favorite_actor']}"
    )

    if stats["avg_rating"]:
        text += f"\n\n⭐ Средний рейтинг: <b>{stats['avg_rating']}</b>"
    else:
        text += f"\n\n⭐ Средний рейтинг: <b>—</b>"

    await message.answer(text, parse_mode="HTML")


@router.message(Command('start'))
@router.message(F.text.lower() == "старт")
async def start(message: Message):
    await init_db()
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        f"Я бот для настоящих киноманов!\n"
        f"Чтобы узнать что я могу напиши /help",
        reply_markup=get_main_reply_keyboard()
    )


@router.message(Command('help'))
@router.message(F.text == "📋 Все команды")
async def help_cmd(message: Message):
    await _show_help(message)


@router.message(Command('about'))
@router.message(F.text.lower() == "о боте")
async def about(message: Message):
    await message.answer(
        "🍿 <b>Лучший бот для киномана</b>\n\n"
        "Привет, киноман! Этот бот создан, чтобы ты никогда не забыл, "
        "что смотрел вчера, и знал, что смотреть завтра.\n\n"
        "🎲 <b>Особенности:</b>\n"
        "• Умные рекомендации на основе твоих вкусов\n"
        "• Детальная статистика (любимый актер, жанр, год)\n"
        "• Удобное ведение списка просмотренного\n\n"
        "👤 <b>Автор:</b> @Inf0voz\n"
        "📦 <b>Версия:</b> Beta 0.1\n\n"
        "Приятного просмотра! 🎥",
        parse_mode="HTML"
    )


@router.message(Command('my_movie'))
@router.message(F.text == "🏠 Главное меню")
async def my_movie(message: Message):
    await message.answer(
        "Главное меню",
        reply_markup=get_main_inline_keyboard()
    )


@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "Текст не распознан.\n"
        "Используйте кнопки или /help для списка команд."
    )