import json
import sqlite3


def get_connection(db_path):
    conn = sqlite3.connect(db_path)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY,
        region TEXT NOT NULL,
        raw_json TEXT NOT NULL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS explored_players (
        puuid TEXT PRIMARY KEY
    )
    """)

    conn.commit()
    return conn


def match_already_collected(conn, match_id):
    cursor = conn.execute("SELECT match_id FROM matches WHERE match_id = ?", (match_id,))
    return cursor.fetchone() is not None


def save_match(conn, match_id, region, match_data):
    conn.execute(
        "INSERT OR IGNORE INTO matches (match_id, region, raw_json) VALUES (?, ?, ?)",
        (match_id, region, json.dumps(match_data)),
    )
    conn.commit()


def player_already_explored(conn, puuid):
    cursor = conn.execute("SELECT puuid FROM explored_players WHERE puuid = ?", (puuid,))
    return cursor.fetchone() is not None


def mark_player_explored(conn, puuid):
    conn.execute("INSERT OR IGNORE INTO explored_players (puuid) VALUES (?)", (puuid,))
    conn.commit()
