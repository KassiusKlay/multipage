"""
Ensure SwingVision Postgres tables/columns exist before upload.
"""

from sqlalchemy import text
from db import engine


MATCH_COLUMNS = {
    "end_time": "TIMESTAMP",
    "ad_scoring": "BOOLEAN",
    "match_tiebreak": "BOOLEAN",
    "games_per_set": "INTEGER",
    "sets_per_match": "INTEGER",
    "match_status": "TEXT",
}


def ensure_schema():
    """Create missing tables and add new match columns if needed."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS swingvision_matches (
                    match_id UUID PRIMARY KEY,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    location TEXT,
                    host_team TEXT,
                    guest_team TEXT,
                    match_date DATE,
                    ad_scoring BOOLEAN,
                    match_tiebreak BOOLEAN,
                    games_per_set INTEGER,
                    sets_per_match INTEGER,
                    match_status TEXT
                )
                """
            )
        )
        for col, col_type in MATCH_COLUMNS.items():
            conn.execute(
                text(
                    f"ALTER TABLE swingvision_matches "
                    f"ADD COLUMN IF NOT EXISTS {col} {col_type}"
                )
            )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS swingvision_sets (
                    match_id UUID,
                    "set" INTEGER,
                    host_score INTEGER,
                    guest_score INTEGER,
                    host_tiebreak_score INTEGER,
                    guest_tiebreak_score INTEGER,
                    set_winner TEXT,
                    super_tiebreak BOOLEAN,
                    start_time TEXT,
                    video_time DOUBLE PRECISION,
                    duration DOUBLE PRECISION
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS swingvision_points (
                    match_id UUID,
                    point INTEGER,
                    game INTEGER,
                    set INTEGER,
                    serve_state TEXT,
                    match_server TEXT,
                    host_game_score TEXT,
                    guest_game_score TEXT,
                    point_winner TEXT,
                    detail TEXT,
                    break_point TEXT,
                    set_point TEXT,
                    favorited TEXT,
                    start_time TEXT,
                    video_time DOUBLE PRECISION,
                    duration DOUBLE PRECISION
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS swingvision_shots (
                    match_id UUID,
                    player TEXT,
                    shot INTEGER,
                    type TEXT,
                    stroke TEXT,
                    spin TEXT,
                    speed DOUBLE PRECISION,
                    point INTEGER,
                    game INTEGER,
                    set INTEGER,
                    bounce_depth TEXT,
                    bounce_zone TEXT,
                    bounce_side TEXT,
                    bounce_x DOUBLE PRECISION,
                    bounce_y DOUBLE PRECISION,
                    hit_depth TEXT,
                    hit_zone TEXT,
                    hit_side TEXT,
                    hit_x DOUBLE PRECISION,
                    hit_y DOUBLE PRECISION,
                    hit_z DOUBLE PRECISION,
                    direction TEXT,
                    result TEXT,
                    favorited TEXT,
                    start_time TEXT,
                    video_time DOUBLE PRECISION
                )
                """
            )
        )
