import aiosqlite
from database.models import DB_PATH


async def save_movie(kp_id: int, name: str, year: int = None,
                     description: str = None, rating: float = None,
                     poster_url: str = None, director: str = None):
    """Сохраняет фильм в общую таблицу movies."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO movies 
            (kp_id, name, year, description, rating, poster_url, director)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (kp_id, name, year, description, rating, poster_url, director))
        await db.commit()


async def save_genres(movie_kp_id: int, genre_names: list):
    """Сохраняет жанры и связывает их с фильмом."""
    async with aiosqlite.connect(DB_PATH) as db:
        for genre_name in genre_names:
            await db.execute(
                "INSERT OR IGNORE INTO genres (name) VALUES (?)",
                (genre_name,)
            )
            cursor = await db.execute(
                "SELECT id FROM genres WHERE name = ?",
                (genre_name,)
            )
            result = await cursor.fetchone()
            if result:
                genre_id = result[0]
                await db.execute("""
                    INSERT OR IGNORE INTO movie_genres (movie_kp_id, genre_id)
                    VALUES (?, ?)
                """, (movie_kp_id, genre_id))
        await db.commit()


async def save_actors(movie_kp_id: int, actor_names: list):
    """Сохраняет актёров и связывает их с фильмом."""
    async with aiosqlite.connect(DB_PATH) as db:
        for actor_name in actor_names:
            await db.execute(
                "INSERT OR IGNORE INTO actors (name) VALUES (?)",
                (actor_name,)
            )
            cursor = await db.execute(
                "SELECT id FROM actors WHERE name = ?",
                (actor_name,)
            )
            result = await cursor.fetchone()
            if result:
                actor_id = result[0]
                await db.execute("""
                    INSERT OR IGNORE INTO movie_actors (movie_kp_id, actor_id)
                    VALUES (?, ?)
                """, (movie_kp_id, actor_id))
        await db.commit()


async def add_to_user_list(user_id: int, kp_id: int):
    """Добавляет фильм в список пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO user_watched (user_id, movie_kp_id)
            VALUES (?, ?)
        """, (user_id, kp_id))
        await db.commit()


async def get_user_movies(user_id: int):
    """Возвращает список фильмов пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT m.name, m.year, m.rating
            FROM user_watched uw
            JOIN movies m ON uw.movie_kp_id = m.kp_id
            WHERE uw.user_id = ?
            ORDER BY uw.watched_date ASC
        """, (user_id,))
        return await cursor.fetchall()


async def is_movie_in_user_list(user_id: int, kp_id: int) -> bool:
    """Проверяет, есть ли фильм в списке пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT 1 FROM user_watched 
            WHERE user_id = ? AND movie_kp_id = ?
        """, (user_id, kp_id))
        return await cursor.fetchone() is not None


async def delete_from_user_list(user_id: int, movie_index: int) -> tuple[bool, str]:
    """
    Удаляет фильм из списка пользователя по порядковому номеру.
    Возвращает (успех, название_фильма).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT m.kp_id, m.name, m.year
            FROM user_watched uw
            JOIN movies m ON uw.movie_kp_id = m.kp_id
            WHERE uw.user_id = ?
            ORDER BY uw.watched_date ASC 
        """, (user_id,))
        movies = await cursor.fetchall()

        if movie_index < 1 or movie_index > len(movies):
            return False, ""

        kp_id, name, year = movies[movie_index - 1]

        await db.execute("""
            DELETE FROM user_watched
            WHERE user_id = ? AND movie_kp_id = ?
        """, (user_id, kp_id))
        await db.commit()

        return True, f"{name} ({year})"


async def get_movie_by_id(kp_id: int):
    """Возвращает полную информацию о фильме по kp_id из базы."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT kp_id, name, year, description, rating, poster_url, director
            FROM movies
            WHERE kp_id = ?
        """, (kp_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "kp_id": row[0],
            "name": row[1],
            "year": row[2],
            "description": row[3],
            "rating": row[4],
            "poster_url": row[5],
            "director": row[6],
        }


async def get_movie_actors(kp_id: int):
    """Возвращает список актёров фильма."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT a.name
            FROM movie_actors ma
            JOIN actors a ON ma.actor_id = a.id
            WHERE ma.movie_kp_id = ?
            ORDER BY a.name
        """, (kp_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_movie_genres(kp_id: int):
    """Возвращает список жанров фильма."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT g.name
            FROM movie_genres mg
            JOIN genres g ON mg.genre_id = g.id
            WHERE mg.movie_kp_id = ?
            ORDER BY g.name
        """, (kp_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_recommendations(user_id: int, skip_kp_ids: list = None, offset: int = 0):
    if skip_kp_ids is None:
        skip_kp_ids = []

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT movie_kp_id FROM user_watched WHERE user_id = ?
        """, (user_id,))
        watched = {row[0] for row in await cursor.fetchall()}

    exclude_ids = watched | set(skip_kp_ids)

    # Собираем предпочтения
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT g.name, COUNT(*) as cnt FROM user_watched uw
            JOIN movie_genres mg ON uw.movie_kp_id = mg.movie_kp_id
            JOIN genres g ON mg.genre_id = g.id WHERE uw.user_id = ?
            GROUP BY g.id ORDER BY cnt DESC, g.name ASC
        """, (user_id,))
        genres = [(row[0], row[1]) for row in await cursor.fetchall()]

        cursor = await db.execute("""
            SELECT m.director, COUNT(*) as cnt FROM user_watched uw
            JOIN movies m ON uw.movie_kp_id = m.kp_id
            WHERE uw.user_id = ? AND m.director != '' AND m.director != 'Неизвестно'
            GROUP BY m.director ORDER BY cnt DESC, m.director ASC
        """, (user_id,))
        directors = [(row[0], row[1]) for row in await cursor.fetchall()]

        cursor = await db.execute("""
            SELECT a.name, COUNT(*) as cnt FROM user_watched uw
            JOIN movie_actors ma ON uw.movie_kp_id = ma.movie_kp_id
            JOIN actors a ON ma.actor_id = a.id WHERE uw.user_id = ?
            GROUP BY a.id ORDER BY cnt DESC, a.name ASC
        """, (user_id,))
        actors = [(row[0], row[1]) for row in await cursor.fetchall()]

    from services.movies_api import search_movies_scored_paginated

    recommendations = await search_movies_scored_paginated(
        genres=genres,
        directors=directors,
        actors=actors,
        exclude_ids=exclude_ids,
        offset=offset,
        limit=3
    )

    return recommendations


async def get_user_stats(user_id: int):
    """Возвращает статистику пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Общее количество фильмов
        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM user_watched
            WHERE user_id = ?
        """, (user_id,))
        total = (await cursor.fetchone())[0]

        if total == 0:
            return {
                "total": 0,
                "favorite_genre": None,
                "favorite_director": None,
                "favorite_actor": None,
                "avg_rating": None
            }

        # 2. Любимые жанры (топ-3, без расширения)
        cursor = await db.execute("""
            SELECT g.name, COUNT(*) as cnt
            FROM user_watched uw
            JOIN movie_genres mg ON uw.movie_kp_id = mg.movie_kp_id
            JOIN genres g ON mg.genre_id = g.id
            WHERE uw.user_id = ?
            GROUP BY g.id
            ORDER BY cnt DESC, g.name ASC
            LIMIT 3
        """, (user_id,))
        top_genres = await cursor.fetchall()

        if top_genres:
            genre_parts = [f"• {name}: {cnt} фильмов" for name, cnt in top_genres]
            favorite_genre = "\n".join(genre_parts)
        else:
            favorite_genre = "Не определён"
        # 3. Любимые режиссёры (максимум 2)
        cursor = await db.execute("""
            SELECT m.director, COUNT(*) as cnt
            FROM user_watched uw
            JOIN movies m ON uw.movie_kp_id = m.kp_id
            WHERE uw.user_id = ? AND m.director != '' AND m.director != 'Неизвестно'
            GROUP BY m.director
            ORDER BY cnt DESC, m.director ASC
            LIMIT 2
        """, (user_id,))
        top_directors = await cursor.fetchall()

        if top_directors:
            lines = [f"• {name}: {cnt} фильмов" for name, cnt in top_directors]
            favorite_director = "\n".join(lines)
        else:
            favorite_director = "Не определён"

        # 4. Любимые актёры (топ-3, расширяется при равенстве)
        cursor = await db.execute("""
            SELECT a.name, COUNT(*) as cnt
            FROM user_watched uw
            JOIN movie_actors ma ON uw.movie_kp_id = ma.movie_kp_id
            JOIN actors a ON ma.actor_id = a.id
            WHERE uw.user_id = ?
            GROUP BY a.id
            ORDER BY cnt DESC, a.name ASC
            LIMIT 3
        """, (user_id,))
        top_actors = await cursor.fetchall()

        if top_actors:
            min_cnt = top_actors[-1][1]
            cursor = await db.execute("""
                SELECT a.name, COUNT(*) as cnt
                FROM user_watched uw
                JOIN movie_actors ma ON uw.movie_kp_id = ma.movie_kp_id
                JOIN actors a ON ma.actor_id = a.id
                WHERE uw.user_id = ?
                GROUP BY a.id
                HAVING cnt >= ?
                ORDER BY cnt DESC, a.name ASC
            """, (user_id, min_cnt))
            all_top = await cursor.fetchall()
            actor_parts = [f"• {name}: {cnt} фильмов" for name, cnt in all_top]
            favorite_actor = "\n".join(actor_parts)
        else:
            favorite_actor = "Не определён"
        # 5. Средний рейтинг
        cursor = await db.execute("""
            SELECT AVG(m.rating)
            FROM user_watched uw
            JOIN movies m ON uw.movie_kp_id = m.kp_id
            WHERE uw.user_id = ? AND m.rating > 0
        """, (user_id,))
        avg_rating = (await cursor.fetchone())[0]

        return {
            "total": total,
            "favorite_genre": favorite_genre,
            "favorite_director": favorite_director,
            "favorite_actor": favorite_actor,
            "avg_rating": round(avg_rating, 1) if avg_rating else None
        }