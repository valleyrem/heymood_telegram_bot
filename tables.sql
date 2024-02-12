-- users_info
CREATE TABLE users_info (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE, -- или PRIMARY KEY,
    age INTEGER,
    sex TEXT,
    lang CHARACTER VARYING
);

-- user_moods
CREATE TABLE user_moods (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    mood INTEGER,
    date DATE,
    time TIME WITHOUT TIME ZONE,
    day_of_week CHARACTER VARYING,
    FOREIGN KEY (user_id)
    REFERENCES users_info(user_id)
);