import aiohttp
from config import TMDB_API_KEY

BASE_URL = "https://api.themoviedb.org/3"


async def search_movies(query: str, limit: int = 5):
    """Поиск фильмов через TMDb."""
    url = f"{BASE_URL}/search/movie"
    headers = {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "accept": "application/json"
    }
    params = {
        "query": query,
        "language": "ru-RU",
        "page": 1
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])[:limit]
                    movies = []
                    for m in results:
                        movies.append({
                            "id": m["id"],
                            "name": m["title"],
                            "year": int(m["release_date"][:4]) if m.get("release_date") else None,
                            "rating": {"kp": m.get("vote_average")},
                            "poster": {"url": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get(
                                "poster_path") else None},
                            "description": m.get("overview"),
                            "genres": [],
                            "persons": []
                        })
                    return movies
                else:
                    text = await resp.text()
                    return []
    except Exception as e:
        print(f"❌ TMDb connection error: {e}")
        return []


async def get_movie_details(movie_id: int):
    url = f"{BASE_URL}/movie/{movie_id}"
    headers = {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "accept": "application/json"
    }
    params = {
        "language": "ru-RU",
        "append_to_response": "credits"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    genres = [{"name": g["name"]} for g in data.get("genres", [])]
                    persons = []
                    credits = data.get("credits", {})
                    for crew in credits.get("crew", []):
                        if crew.get("job") == "Director":
                            persons.append({"name": crew["name"], "enProfession": "director"})
                            break
                    for cast in credits.get("cast", [])[:5]:
                        persons.append({"name": cast["name"], "enProfession": "actor"})
                    poster_path = data.get("poster_path")
                    return {
                        "id": data["id"],
                        "name": data["title"],
                        "year": int(data["release_date"][:4]) if data.get("release_date") else None,
                        "rating": {"kp": data.get("vote_average")},
                        "poster": {"url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None},
                        "description": data.get("overview"),
                        "genres": genres,
                        "persons": persons
                    }
                else:
                    return None
    except Exception as e:
        print(f"❌ TMDb details connection error: {e}")
        return None


async def search_movies_scored(fav_genres: dict, fav_directors: dict, fav_actors: dict, exclude_ids: set, limit: int = 20):
    all_candidates = []
    top_genres = dict(sorted(fav_genres.items(), key=lambda x: x[1], reverse=True)[:3])
    top_directors = dict(sorted(fav_directors.items(), key=lambda x: x[1], reverse=True)[:2])
    top_actors = dict(sorted(fav_actors.items(), key=lambda x: x[1], reverse=True)[:2])

    headers = {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "accept": "application/json"
    }

    genre_map = {
        "драма": 18, "комедия": 35, "боевик": 28, "триллер": 53,
        "ужасы": 27, "фантастика": 878, "детектив": 9648,
        "приключения": 12, "фэнтези": 14, "криминал": 80,
        "мелодрама": 10749, "военный": 10752, "история": 36,
        "семейный": 10751, "мультфильм": 16, "документальный": 99
    }

    async with aiohttp.ClientSession() as session:
        for genre_name, weight in top_genres.items():
            genre_id = genre_map.get(genre_name.lower())
            if not genre_id:
                continue
            params = {
                "with_genres": str(genre_id),
                "sort_by": "vote_average.desc",
                "vote_count.gte": 500,
                "language": "ru-RU",
                "page": 1
            }
            try:
                async with session.get(f"{BASE_URL}/discover/movie", headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for m in data.get("results", [])[:3]:
                            mid = m["id"]
                            if mid in exclude_ids:
                                continue
                            found = False
                            for c in all_candidates:
                                if c.get("id") == mid:
                                    c["_score"] += weight
                                    found = True
                                    break
                            if not found:
                                m["_score"] = weight
                                all_candidates.append(m)
            except Exception as e:
                print(f"❌ TMDb genre error: {e}")

        for director, weight in top_directors.items():
            params = {"query": director, "language": "ru-RU", "page": 1}
            try:
                async with session.get(f"{BASE_URL}/search/person", headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            person_id = results[0]["id"]
                            async with session.get(
                                f"{BASE_URL}/discover/movie", headers=headers,
                                params={"with_crew": str(person_id), "sort_by": "vote_average.desc", "vote_count.gte": 500, "language": "ru-RU"}
                            ) as resp2:
                                if resp2.status == 200:
                                    data2 = await resp2.json()
                                    for m in data2.get("results", [])[:2]:
                                        mid = m["id"]
                                        if mid in exclude_ids:
                                            continue
                                        found = False
                                        for c in all_candidates:
                                            if c.get("id") == mid:
                                                c["_score"] += weight * 3
                                                found = True
                                                break
                                        if not found:
                                            m["_score"] = weight * 3
                                            all_candidates.append(m)
            except Exception as e:
                print(f"❌ TMDb director error: {e}")

        for actor, weight in top_actors.items():
            params = {"query": actor, "language": "ru-RU", "page": 1}
            try:
                async with session.get(f"{BASE_URL}/search/person", headers=headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            person_id = results[0]["id"]
                            async with session.get(
                                f"{BASE_URL}/discover/movie", headers=headers,
                                params={"with_cast": str(person_id), "sort_by": "vote_average.desc", "vote_count.gte": 500, "language": "ru-RU"}
                            ) as resp2:
                                if resp2.status == 200:
                                    data2 = await resp2.json()
                                    for m in data2.get("results", [])[:2]:
                                        mid = m["id"]
                                        if mid in exclude_ids:
                                            continue
                                        found = False
                                        for c in all_candidates:
                                            if c.get("id") == mid:
                                                c["_score"] += weight * 2
                                                found = True
                                                break
                                        if not found:
                                            m["_score"] = weight * 2
                                            all_candidates.append(m)
            except Exception as e:
                print(f"❌ TMDb actor error: {e}")

    seen = set()
    unique = []
    for c in all_candidates:
        cid = c.get("id")
        if cid in seen:
            continue
        seen.add(cid)
        rating = c.get("vote_average", 0)
        c["score"] = c.get("_score", 0) * 10 + (rating or 0)
        c["rating"] = {"kp": rating}
        c["name"] = c.get("title", c.get("name", ""))
        c["year"] = int(c["release_date"][:4]) if c.get("release_date") else None
        c["poster"] = {"url": f"https://image.tmdb.org/t/p/w500{c['poster_path']}" if c.get("poster_path") else None}
        unique.append(c)

    unique.sort(key=lambda x: x.get("score", 0), reverse=True)
    return unique[:limit]


async def search_movies_scored_paginated(genres: list, directors: list, actors: list,
                                         exclude_ids: set, offset: int = 0, limit: int = 3):
    """
    Простая логика: три критерия с пагинацией.
    offset 0: жанр[0], режиссёр[0], актёр[0]
    offset 1: жанр[1], режиссёр[1], актёр[1]
    offset 2: жанр[2], режиссёр[2], актёр[2]
    и т.д.
    """
    all_candidates = []
    headers = {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "accept": "application/json"
    }

    genre_map = {
        "драма": 18, "комедия": 35, "боевик": 28, "триллер": 53,
        "ужасы": 27, "фантастика": 878, "детектив": 9648,
        "приключения": 12, "фэнтези": 14, "криминал": 80,
        "мелодрама": 10749, "военный": 10752, "история": 36,
        "семейный": 10751, "мультфильм": 16, "документальный": 99
    }

    async with aiohttp.ClientSession() as session:
        # 1. По жанру
        genre_idx = offset % len(genres) if genres else 0
        if genres:
            genre_name, genre_weight = genres[genre_idx]
            genre_id = genre_map.get(genre_name.lower())
            if genre_id:
                params = {
                    "with_genres": str(genre_id),
                    "sort_by": "vote_average.desc",
                    "vote_count.gte": 5000,
                    "language": "ru-RU",
                    "page": 1
                }
                try:
                    async with session.get(f"{BASE_URL}/discover/movie", headers=headers, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for m in data.get("results", []):
                                mid = m["id"]
                                if mid in exclude_ids:
                                    continue
                                m["_score"] = genre_weight
                                all_candidates.append(m)
                except Exception as e:
                    print(f"❌ Genre error: {e}")

        # 2. По режиссёру
        director_idx = offset % len(directors) if directors else 0
        if directors:
            director_name, director_weight = directors[director_idx]
            try:
                async with session.get(f"{BASE_URL}/search/person", headers=headers,
                                       params={"query": director_name, "language": "ru-RU"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            person_id = results[0]["id"]
                            async with session.get(
                                    f"{BASE_URL}/discover/movie", headers=headers,
                                    params={"with_crew": str(person_id), "sort_by": "vote_average.desc",
                                            "vote_count.gte": 1000, "language": "ru-RU", "page": 1}
                            ) as resp2:
                                if resp2.status == 200:
                                    data2 = await resp2.json()
                                    for m in data2.get("results", []):
                                        mid = m["id"]
                                        if mid in exclude_ids:
                                            continue
                                        m["_score"] = director_weight * 3
                                        all_candidates.append(m)
            except Exception as e:
                print(f"❌ Director error: {e}")

        # 3. По актёру
        actor_idx = offset % len(actors) if actors else 0
        if actors:
            actor_name, actor_weight = actors[actor_idx]
            try:
                async with session.get(f"{BASE_URL}/search/person", headers=headers,
                                       params={"query": actor_name, "language": "ru-RU"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            person_id = results[0]["id"]
                            async with session.get(
                                    f"{BASE_URL}/discover/movie", headers=headers,
                                    params={"with_cast": str(person_id), "sort_by": "vote_average.desc",
                                            "vote_count.gte": 1000, "language": "ru-RU", "page": 1}
                            ) as resp2:
                                if resp2.status == 200:
                                    data2 = await resp2.json()
                                    for m in data2.get("results", []):
                                        mid = m["id"]
                                        if mid in exclude_ids:
                                            continue
                                        m["_score"] = actor_weight * 2
                                        all_candidates.append(m)
            except Exception as e:
                print(f"❌ Actor error: {e}")

    # Убираем дубликаты и считаем score
    seen = set()
    unique = []
    for c in all_candidates:
        cid = c.get("id")
        if cid in seen:
            continue
        seen.add(cid)
        rating = c.get("vote_average", 0)
        c["score"] = c.get("_score", 0) * 10 + (rating or 0)
        c["rating"] = {"kp": rating}
        c["name"] = c.get("title", c.get("name", ""))
        c["year"] = int(c["release_date"][:4]) if c.get("release_date") else None
        c["poster"] = {"url": f"https://image.tmdb.org/t/p/w500{c['poster_path']}" if c.get("poster_path") else None}
        unique.append(c)

    unique.sort(key=lambda x: x.get("score", 0), reverse=True)
    result = unique[:limit]

    print(
        f"DEBUG: offset={offset}, genre_idx={genre_idx if genres else 'N/A'}, director_idx={director_idx if directors else 'N/A'}, actor_idx={actor_idx if actors else 'N/A'}")
    for i, m in enumerate(result):
        print(f"DEBUG:   {i + 1}. {m.get('name')} — score={m.get('score', 0):.1f}")

    return result