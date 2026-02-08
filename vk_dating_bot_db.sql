
CREATE DATABASE vk_dating_bot_db
    CONNECTION LIMIT = -1;

   \c vk_dating_bot_db;

-- Таблица пользователей
CREATE TABLE users (
    vk_id INTEGER PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    bdate DATE,
    city VARCHAR(50),
    has_photo BOOLEAN DEFAULT FALSE,
    sex INTEGER CHECK (sex IN (0, 1)),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Таблица кандидатов
CREATE TABLE candidates(
    vk_id INTEGER PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    bdate DATE,
    city VARCHAR(50),
    has_photo BOOLEAN DEFAULT FALSE,
    sex INTEGER CHECK (sex IN (0, 1)),
    popularity INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Черный список
CREATE TABLE blacklist(
    id SERIAL PRIMARY KEY,
    user_vk_id INTEGER NOT NULL REFERENCES users(vk_id) ON DELETE CASCADE,
    candidate_vk_id INTEGER NOT NULL REFERENCES candidates(vk_id) ON DELETE CASCADE,
    blocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_vk_id, candidate_vk_id)
);

-- Избранное
CREATE TABLE favotites(
    id SERIAL PRIMARY KEY,
    user_vk_id INTEGER NOT NULL REFERENCES user(vk_id) ON DELETE CASCADE,
    candidate_vk_id INTEGER NOT NULL REFERENCES candidates(vk_id) ON DELETE CASCADE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_vk_id, candidate_vk_id)
);

-- Таблица просмотров(не повторялся вывод)
CREATE TABLE search_history(
    id SERIAL PRIMARY KEY,
    user_vk_id INTEGER NOT NULL REFERENCES users(vk_id) ON DELETE CASCADE,
    candidate_vk_id INTEGER NOT NULL REFERENCES candidates(vk_id) ON DELETE CASCADE,
    shown_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reaction VARCHAR(20) CHECK (reaction IN ('liked', 'blocked', NULL)),
    UNIQUE (user_vk_id, candidate_vk_id, DATE(shown_at))
);

--Индексы для поиска
CREATE INDEX idx_users_city ON users(city);
CREATE INDEX idx_candidates_city ON candidates(city);
CREATE INDEX idx_candidates_sex ON candidates(sex);
CREATE INDEX idx_candidates_has_photo ON candidates(has_photo);
CREATE INDEX idx_blacklist_user ON blacklist(user_vk_id);
CREATE INDEX idx_favotites_user ON favotites(user_vk_id);
CREATE INDEX idx_search_history_user ON search_history(user_vk_id);
CREATE INDEX idx_search_history_shown_at ON search_history(shown_at);