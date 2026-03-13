-- ============================================================
-- Social Live Feed — Database Schema
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    avatar_url  TEXT,
    bio         TEXT,
    location    VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS posts (
    id          SERIAL PRIMARY KEY,
    user_id     INT REFERENCES users(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    image_url   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comments (
    id          SERIAL PRIMARY KEY,
    post_id     INT REFERENCES posts(id) ON DELETE CASCADE,
    user_id     INT REFERENCES users(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS follows (
    follower_id  INT REFERENCES users(id) ON DELETE CASCADE,
    following_id INT REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id)
);

CREATE TABLE IF NOT EXISTS social_events (
    id          SERIAL PRIMARY KEY,
    "user"      VARCHAR(50) NOT NULL,
    action      VARCHAR(50) NOT NULL,
    target      VARCHAR(100) NOT NULL,
    target_user VARCHAR(50),
    timestamp   VARCHAR(20),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast chronological queries
CREATE INDEX IF NOT EXISTS idx_events_created_at ON social_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_target_user ON social_events (target_user);
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts (user_id);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments (post_id);
