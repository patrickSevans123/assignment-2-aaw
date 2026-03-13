-- ============================================================
-- Social Live Feed — Seed Data
-- ============================================================

-- Users
INSERT INTO users (username, display_name, avatar_url, bio, location) VALUES
    ('alice',   'Alice Johnson',  'https://ui-avatars.com/api/?name=Alice+Johnson&background=6366f1&color=fff', 'Software Engineer who loves Python.', 'San Francisco, CA'),
    ('bob',     'Bob Smith',      'https://ui-avatars.com/api/?name=Bob+Smith&background=f59e0b&color=fff', 'Digital Artist & Creator.', 'New York, NY'),
    ('charlie', 'Charlie Brown',  'https://ui-avatars.com/api/?name=Charlie+Brown&background=10b981&color=fff', 'Coffee enthusiast and traveler.', 'Seattle, WA'),
    ('david',   'David Lee',      'https://ui-avatars.com/api/?name=David+Lee&background=ef4444&color=fff', 'Photographer and tech geek.', 'Austin, TX')
ON CONFLICT (username) DO UPDATE SET 
    display_name = EXCLUDED.display_name,
    avatar_url = EXCLUDED.avatar_url,
    bio = EXCLUDED.bio,
    location = EXCLUDED.location;

-- Posts
INSERT INTO posts (user_id, content) VALUES
    (1, 'Hello world! Just started my social media journey.'),
    (2, 'Check out my new digital masterpiece!'),
    (3, 'Best coffee in Seattle found at Pike Place.'),
    (1, 'Building cool stuff with FastAPI and React.');

-- Comments
INSERT INTO comments (post_id, user_id, content) VALUES
    (1, 2, 'Welcome to the platform, Alice!'),
    (2, 1, 'Wow, this looks incredible, Bob.'),
    (1, 3, 'Great to see you here!');

-- Follows
INSERT INTO follows (follower_id, following_id) VALUES
    (1, 2), -- Alice follows Bob
    (1, 3), -- Alice follows Charlie
    (2, 1), -- Bob follows Alice
    (3, 1); -- Charlie follows Alice

-- Sample social events (historic feed)
INSERT INTO social_events ("user", action, target, target_user, timestamp) VALUES
    ('alice',   'liked',        'Post #101', 'bob',     '08:01:00'),
    ('bob',     'commented on', 'Post #202', 'charlie', '08:03:15'),
    ('charlie', 'shared',       'Post #303', 'alice',   '08:05:42'),
    ('david',   'liked',        'Post #101', 'alice',   '08:10:00'),
    ('alice',   'shared',       'Post #202', 'david',   '08:12:30'),
    ('bob',     'liked',        'Post #303', 'david',   '08:15:10'),
    ('charlie', 'commented on', 'Post #101', 'bob',     '08:20:00'),
    ('david',   'shared',       'Post #202', 'charlie', '08:22:45'),
    ('alice',   'commented on', 'Post #303', 'charlie', '08:25:00'),
    ('bob',     'shared',       'Post #101', 'alice',   '08:30:00'),
    ('charlie', 'liked',        'Post #202', 'alice',   '08:35:00'),
    ('david',   'commented on', 'Post #303', 'bob',     '08:40:00');
