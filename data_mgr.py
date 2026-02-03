import os
import sqlite3

# Path to the SQLite database file.
# If you set an environment variable DATABASE_PATH, that value will be used.
# IMPORTANT: If DATABASE_PATH is a relative path, we resolve it relative to this file
# so running scripts from different folders/IDEs won't accidentally create a new empty DB.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "plotgod.db")

DB_PATH = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, DB_PATH)
DB_PATH = os.path.normpath(DB_PATH)


def get_connection():
    """Open a connection to the SQLite database."""

    # Make sure the folder exists (e.g. "data/") so SQLite can create the file.
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    # SQLite needs this per connection so FOREIGN KEY rules are enforced.
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def init_db():
    """Create the tables if they do not exist yet."""

    conn = get_connection()

    # 1) Campaigns
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        """
    )

    # 2) Sessions (each session belongs to one campaign)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        );
        """
    )

    # 3) Party members (each party member belongs to one campaign)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS party_member (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            player_name TEXT,
            character_species TEXT,
            character_class TEXT,
            level INTEGER,
            notes TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        );
        """
    )

    # 4) NPCs (non-player characters)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS npcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            species TEXT,
            gender TEXT,
            notes TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        );
        """
    )

    # 5) Locations (global world data, not tied to a campaign)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location_type TEXT,
            notes TEXT
        );
        """
    )

    conn.commit()
    conn.close()


# -------------------------
# CREATE (INSERT) FUNCTIONS
# -------------------------

def add_campaign(name):
    """Insert a campaign and return its new ID."""

    conn = get_connection()

    result = conn.execute(
        "INSERT INTO campaigns (name) VALUES (?);",
        (name,),
    )

    conn.commit()
    new_id = result.lastrowid
    conn.close()
    return new_id


def add_session(campaign_id, content):
    """Insert a session and return its new ID."""

    conn = get_connection()

    result = conn.execute(
        """
        INSERT INTO sessions (campaign_id, content)
        VALUES (?, ?);
        """,
        (campaign_id, content),
    )

    conn.commit()
    new_id = result.lastrowid
    conn.close()
    return new_id


def add_party_member(
    campaign_id,
    name,
    player_name=None,
    character_species=None,
    character_class=None,
    level=None,
    notes=None,
):
    """Insert a party member and return its new ID."""

    conn = get_connection()

    result = conn.execute(
        """
        INSERT INTO party_member (
            campaign_id,
            name,
            player_name,
            character_species,
            character_class,
            level,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            campaign_id,
            name,
            player_name,
            character_species,
            character_class,
            level,
            notes,
        ),
    )

    conn.commit()
    new_id = result.lastrowid
    conn.close()
    return new_id


def add_npc(campaign_id, name, species=None, gender=None, notes=None):
    """Insert an NPC and return its new ID."""

    conn = get_connection()

    result = conn.execute(
        """
        INSERT INTO npcs (campaign_id, name, species, gender, notes)
        VALUES (?, ?, ?, ?, ?);
        """,
        (campaign_id, name, species, gender, notes),
    )

    conn.commit()
    new_id = result.lastrowid
    conn.close()
    return new_id


def add_location(name, location_type=None, notes=None):
    """Insert a location and return its new ID."""

    conn = get_connection()

    result = conn.execute(
        """
        INSERT INTO locations (name, location_type, notes)
        VALUES (?, ?, ?);
        """,
        (name, location_type, notes),
    )

    conn.commit()
    new_id = result.lastrowid
    conn.close()
    return new_id


# -------------------------
# READ (SELECT) FUNCTIONS
# -------------------------

def get_all_campaigns():
    """Return all campaigns (id + name)."""

    conn = get_connection()
    rows = conn.execute("SELECT id, name FROM campaigns ORDER BY name ASC;").fetchall()
    conn.close()

    return [{"id": row[0], "name": row[1]} for row in rows]


def get_campaign_by_id(campaign_id):
    """Return one campaign (id + name), or None if not found."""

    conn = get_connection()
    row = conn.execute(
        "SELECT id, name FROM campaigns WHERE id = ?;",
        (campaign_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {"id": row[0], "name": row[1]}


def get_campaign_last_session(campaign_id):
    """Return the campaign plus its newest session (if any)."""

    conn = get_connection()

    campaign = conn.execute(
        "SELECT id, name FROM campaigns WHERE id = ?;",
        (campaign_id,),
    ).fetchone()

    if campaign is None:
        conn.close()
        return None

    session = conn.execute(
        """
        SELECT content, created_at
        FROM sessions
        WHERE campaign_id = ?
        ORDER BY id DESC
        LIMIT 1;
        """,
        (campaign_id,),
    ).fetchone()

    conn.close()

    if session is None:
        return {
            "id": campaign[0],
            "name": campaign[1],
            "last_session_text": None,
            "created_at": None,
        }

    return {
        "id": campaign[0],
        "name": campaign[1],
        "last_session_text": session[0],
        "created_at": session[1],
    }


def get_sessions_for_campaign(campaign_id):
    """Return all sessions for one campaign."""

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, content, created_at
        FROM sessions
        WHERE campaign_id = ?
        ORDER BY id DESC;
        """,
        (campaign_id,),
    ).fetchall()

    conn.close()

    return [{"id": r[0], "content": r[1], "created_at": r[2]} for r in rows]


def get_session_by_id(campaign_id, session_id):
    """Return one session by id for a campaign, or None."""

    conn = get_connection()
    row = conn.execute(
        """
        SELECT id, content, created_at
        FROM sessions
        WHERE campaign_id = ? AND id = ?;
        """,
        (campaign_id, session_id),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {"id": row[0], "content": row[1], "created_at": row[2]}


def get_party_members_for_campaign(campaign_id):
    """Return all party members for one campaign."""

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, name, player_name, character_species, character_class, level, notes
        FROM party_member
        WHERE campaign_id = ?
        ORDER BY name ASC;
        """,
        (campaign_id,),
    ).fetchall()

    conn.close()

    return [
        {
            "id": r[0],
            "name": r[1],
            "player_name": r[2],
            "character_species": r[3],
            "character_class": r[4],
            "level": r[5],
            "notes": r[6],
        }
        for r in rows
    ]


def get_party_member_by_id(campaign_id, member_id):
    """Return one party member by id for a campaign, or None."""

    conn = get_connection()

    row = conn.execute(
        """
        SELECT id, name, player_name, character_species, character_class, level, notes
        FROM party_member
        WHERE campaign_id = ? AND id = ?;
        """,
        (campaign_id, member_id),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "player_name": row[2],
        "character_species": row[3],
        "character_class": row[4],
        "level": row[5],
        "notes": row[6],
    }


def get_npcs_for_campaign(campaign_id):
    """Return all NPCs for one campaign."""

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, name, species, gender, notes
        FROM npcs
        WHERE campaign_id = ?
        ORDER BY name ASC;
        """,
        (campaign_id,),
    ).fetchall()

    conn.close()

    return [
        {
            "id": r[0],
            "name": r[1],
            "species": r[2],
            "gender": r[3],
            "notes": r[4],
        }
        for r in rows
    ]


def get_npc_by_id(campaign_id, npc_id):
    """Return exactly one NPC by its ID (or None if not found)."""

    conn = get_connection()

    row = conn.execute(
        """
        SELECT id, name, species, gender, notes
        FROM npcs
        WHERE campaign_id = ? AND id = ?;
        """,
        (campaign_id, npc_id),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "species": row[2],
        "gender": row[3],
        "notes": row[4],
    }


def get_npcs_by_ids(campaign_id, npc_ids):
    """Return only the NPCs whose IDs are in npc_ids (selected NPCs in your UI)."""

    selected = []
    for npc_id in npc_ids:
        npc = get_npc_by_id(campaign_id, npc_id)
        if npc is not None:
            selected.append(npc)
    return selected


def get_all_locations():
    """Return all locations."""

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, name, location_type, notes
        FROM locations
        ORDER BY name ASC;
        """
    ).fetchall()

    conn.close()

    return [{"id": r[0], "name": r[1], "location_type": r[2], "notes": r[3]} for r in rows]


def get_location_by_id(location_id):
    """Return one location by id, or None."""

    conn = get_connection()

    row = conn.execute(
        """
        SELECT id, name, location_type, notes
        FROM locations
        WHERE id = ?;
        """,
        (location_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return {"id": row[0], "name": row[1], "location_type": row[2], "notes": row[3]}


# -------------------------
# UPDATE FUNCTIONS
# -------------------------

def update_campaign(campaign_id, name):
    """Update a campaign's name. Returns True if updated."""

    conn = get_connection()
    result = conn.execute(
        "UPDATE campaigns SET name = ? WHERE id = ?;",
        (name, campaign_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def update_session(campaign_id, session_id, content):
    """Update one session's content. Returns True if updated."""

    conn = get_connection()
    result = conn.execute(
        """
        UPDATE sessions
        SET content = ?
        WHERE campaign_id = ? AND id = ?;
        """,
        (content, campaign_id, session_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def update_party_member(
    campaign_id,
    member_id,
    name,
    player_name=None,
    character_species=None,
    character_class=None,
    level=None,
    notes=None,
):
    """Update one party member. Returns True if updated."""

    conn = get_connection()
    result = conn.execute(
        """
        UPDATE party_member
        SET
            name = ?,
            player_name = ?,
            character_species = ?,
            character_class = ?,
            level = ?,
            notes = ?
        WHERE campaign_id = ? AND id = ?;
        """,
        (
            name,
            player_name,
            character_species,
            character_class,
            level,
            notes,
            campaign_id,
            member_id,
        ),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def update_npc(campaign_id, npc_id, name, species=None, gender=None, notes=None):
    """Update one NPC. Returns True if updated."""

    conn = get_connection()
    result = conn.execute(
        """
        UPDATE npcs
        SET name = ?, species = ?, gender = ?, notes = ?
        WHERE campaign_id = ? AND id = ?;
        """,
        (name, species, gender, notes, campaign_id, npc_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def update_location(location_id, name, location_type=None, notes=None):
    """Update one location. Returns True if updated."""

    conn = get_connection()
    result = conn.execute(
        """
        UPDATE locations
        SET name = ?, location_type = ?, notes = ?
        WHERE id = ?;
        """,
        (name, location_type, notes, location_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


# -------------------------
# DELETE FUNCTIONS
# -------------------------

def delete_campaign(campaign_id):
    """Delete one campaign.

    Because we did not use ON DELETE CASCADE in the schema, we delete the
    related rows first (sessions, party members, NPCs).

    Returns True if the campaign was deleted.
    """

    conn = get_connection()

    conn.execute("DELETE FROM sessions WHERE campaign_id = ?;", (campaign_id,))
    conn.execute("DELETE FROM party_member WHERE campaign_id = ?;", (campaign_id,))
    conn.execute("DELETE FROM npcs WHERE campaign_id = ?;", (campaign_id,))

    result = conn.execute("DELETE FROM campaigns WHERE id = ?;", (campaign_id,))

    conn.commit()
    conn.close()
    return result.rowcount > 0


def delete_session(campaign_id, session_id):
    """Delete one session. Returns True if deleted."""

    conn = get_connection()
    result = conn.execute(
        "DELETE FROM sessions WHERE campaign_id = ? AND id = ?;",
        (campaign_id, session_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def delete_party_member(campaign_id, member_id):
    """Delete one party member. Returns True if deleted."""

    conn = get_connection()
    result = conn.execute(
        "DELETE FROM party_member WHERE campaign_id = ? AND id = ?;",
        (campaign_id, member_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def delete_npc(campaign_id, npc_id):
    """Delete one NPC. Returns True if deleted."""

    conn = get_connection()
    result = conn.execute(
        "DELETE FROM npcs WHERE campaign_id = ? AND id = ?;",
        (campaign_id, npc_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def delete_location(location_id):
    """Delete one location. Returns True if deleted."""

    conn = get_connection()
    result = conn.execute("DELETE FROM locations WHERE id = ?;", (location_id,))
    conn.commit()
    conn.close()
    return result.rowcount > 0


if __name__ == "__main__":
    init_db()