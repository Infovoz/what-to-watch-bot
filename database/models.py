import aiosqlite

DB_PATH = "movies.db"


async def init_db():
    """Создаёт все таблицы, если их ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Таблица фильмов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kp_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                year INTEGER,
                description TEXT,
                rating REAL,
                poster_url TEXT,
                director TEXT
            )
        """)

        # 2. Таблица жанров
        await db.execute("""
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # 3. Связь фильм-жанры
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movie_genres (
                movie_kp_id INTEGER,
                genre_id INTEGER,
                FOREIGN KEY (movie_kp_id) REFERENCES movies(kp_id),
                FOREIGN KEY (genre_id) REFERENCES genres(id),
                PRIMARY KEY (movie_kp_id, genre_id)
            )
        """)

        # 4. Таблица актёров
        await db.execute("""
            CREATE TABLE IF NOT EXISTS actors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # 5. Связь фильм-актёры
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movie_actors (
                movie_kp_id INTEGER,
                actor_id INTEGER,
                FOREIGN KEY (movie_kp_id) REFERENCES movies(kp_id),
                FOREIGN KEY (actor_id) REFERENCES actors(id),
                PRIMARY KEY (movie_kp_id, actor_id)
            )
        """)

        # 6. Список пользователя
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_watched (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                movie_kp_id INTEGER NOT NULL,
                watched_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (movie_kp_id) REFERENCES movies(kp_id),
                UNIQUE (user_id, movie_kp_id)
            )
        """)

        await db.commit()