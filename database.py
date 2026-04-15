import json
import logging
import sqlite3
from copy import deepcopy

from config import DATABASE_PATH

DB_ERRORS = (sqlite3.Error,)
DATA_ERRORS = (json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError)
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    pass


DEFAULT_INVENTORY = {
    "argent": {"pc": 0, "pa": 0, "po": 0},
    "armures": [],
    "armes": [],
    "autres_objets": [],
}


def _default_inventory_copy():
    return deepcopy(DEFAULT_INVENTORY)


def _connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _parse_inventory(raw_inventory):
    if not raw_inventory:
        return _default_inventory_copy()
    parsed = json.loads(raw_inventory)
    if isinstance(parsed, dict):
        return parsed
    return _default_inventory_copy()


def _parse_json(raw_value, default):
    if raw_value is None or raw_value == "":
        return deepcopy(default)
    parsed = json.loads(raw_value)
    if isinstance(default, dict) and isinstance(parsed, dict):
        return parsed
    if isinstance(default, list) and isinstance(parsed, list):
        return parsed
    return deepcopy(default)


def _row_to_character_data(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "age": row["age"],
        "race": row["race"],
        "level": row["level"],
        "attributes": _parse_json(row["attributes"], {}),
        "skills": _parse_json(row["skills"], {}),
        "magie": _parse_json(row["magie"], []),
        "pv_actu": row["pv_actu"],
        "pv_max": row["pv_max"],
        "mana_actu": row["mana_actu"],
        "mana_max": row["mana_max"],
        "inventory": _parse_inventory(row["inventory"]),
        "familiers": _parse_json(row["familiers"], []),
        "owner_character_id": row["owner_character_id"] if "owner_character_id" in row.keys() else None,
    }


def _character_to_familier_payload(character_data):
    attributes = character_data.get("attributes", {})
    return {
        "id": character_data["id"],
        "owner_character_id": character_data.get("owner_character_id"),
        "nom": character_data.get("name", ""),
        "age": character_data.get("age", 0) or 0,
        "niveau": character_data.get("level", 1),
        "attributes": {
            "for": int(attributes.get("for", 0) or 0),
            "agi": int(attributes.get("agi", 0) or 0),
            "cha": int(attributes.get("cha", 0) or 0),
            "int": int(attributes.get("int", 0) or 0),
            "pv_max": int(character_data.get("pv_max", 0) or 0),
            "mana_max": int(character_data.get("mana_max", 0) or 0),
            "pv_actu": int(character_data.get("pv_actu", 0) or 0),
            "mana_actu": int(character_data.get("mana_actu", 0) or 0),
        },
        "skills": deepcopy(character_data.get("skills", {})),
        "magie": deepcopy(character_data.get("magie", [])),
        "inventory": deepcopy(character_data.get("inventory", _default_inventory_copy())),
    }


def _familier_to_character_payload(user_id, familier_data, owner_character_id=None):
    attributes = familier_data.get("attributes", {})
    for_attr = int(attributes.get("for", 0) or 0)
    agi_attr = int(attributes.get("agi", 0) or 0)
    cha_attr = int(attributes.get("cha", 0) or 0)
    int_attr = int(attributes.get("int", 0) or 0)

    pv_max = int(attributes.get("pv_max", max(1, 5 + for_attr + int(familier_data.get("niveau", 1) or 1))))
    mana_max = int(attributes.get("mana_max", max(0, 5 + int_attr + int(familier_data.get("niveau", 1) or 1))))
    pv_actu = int(attributes.get("pv_actu", pv_max))
    mana_actu = int(attributes.get("mana_actu", mana_max))

    return {
        "id": familier_data.get("id"),
        "user_id": str(user_id),
        "name": familier_data.get("nom", "").strip(),
        "age": int(familier_data.get("age", 0) or 0),
        "race": "Familier",
        "level": int(familier_data.get("niveau", 1) or 1),
        "attributes": {
            "for": for_attr,
            "agi": agi_attr,
            "cha": cha_attr,
            "int": int_attr,
        },
        "skills": deepcopy(familier_data.get("skills", {})),
        "magie": deepcopy(familier_data.get("magie", [])),
        "pv_actu": pv_actu,
        "pv_max": pv_max,
        "mana_actu": mana_actu,
        "mana_max": mana_max,
        "inventory": deepcopy(familier_data.get("inventory", _default_inventory_copy())),
        "familiers": [],
        "owner_character_id": owner_character_id,
    }


def _insert_character_row(cursor, user_id, character_data):
    cursor.execute(
        """
        INSERT INTO characters (
            user_id,
            name,
            age,
            race,
            level,
            attributes,
            skills,
            magie,
            pv_actu,
            pv_max,
            mana_actu,
            mana_max,
            inventory,
            familiers,
            owner_character_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(user_id),
            character_data["name"],
            character_data["age"],
            character_data["race"],
            character_data["level"],
            json.dumps(character_data["attributes"]),
            json.dumps(character_data["skills"]),
            json.dumps(character_data["magie"]),
            character_data["pv_actu"],
            character_data["pv_max"],
            character_data["mana_actu"],
            character_data["mana_max"],
            json.dumps(character_data["inventory"]),
            json.dumps(character_data["familiers"]),
            character_data.get("owner_character_id"),
        ),
    )


def _migrate_legacy_familiers(cursor):
    cursor.execute("SELECT id, user_id, familiers FROM characters WHERE race != 'Familier' OR race IS NULL")
    rows = cursor.fetchall()
    for row in rows:
        owner_id = row["id"]
        user_id = row["user_id"]
        raw_familiers = row["familiers"]
        if not raw_familiers:
            continue
        legacy_familiers = _parse_json(raw_familiers, [])
        if not legacy_familiers:
            continue

        for familier_data in legacy_familiers:
            if not isinstance(familier_data, dict):
                continue

            name = str(familier_data.get("nom", "")).strip()
            if not name:
                continue

            cursor.execute(
                """
                SELECT id
                FROM characters
                WHERE user_id = ?
                  AND race = 'Familier'
                  AND owner_character_id = ?
                  AND lower(name) = lower(?)
                """,
                (user_id, owner_id, name),
            )
            if cursor.fetchone():
                continue

            payload = _familier_to_character_payload(user_id, familier_data, owner_character_id=owner_id)
            _insert_character_row(cursor, user_id, payload)

        cursor.execute("UPDATE characters SET familiers = '[]' WHERE id = ?", (owner_id,))


def init_db():
    try:
        with _connect() as conn:
            c = conn.cursor()

            c.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    actif_id TEXT
                )
                """
            )

            c.execute(
                """
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    name TEXT,
                    age INTEGER,
                    race TEXT,
                    level INTEGER DEFAULT 1,
                    attributes TEXT,
                    skills TEXT,
                    magie TEXT,
                    pv_actu INTEGER,
                    pv_max INTEGER,
                    mana_actu INTEGER,
                    mana_max INTEGER,
                    inventory TEXT,
                    familiers TEXT,
                    owner_character_id INTEGER DEFAULT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(owner_character_id) REFERENCES characters(id) ON DELETE SET NULL
                )
                """
            )
    except sqlite3.Error as e:
        logger.exception("Erreur lors de l'initialisation de la base de données.")
        raise DatabaseError("Impossible d'initialiser la base de données.") from e


def update_existing_players():
    try:
        with _connect() as conn:
            c = conn.cursor()

            if not _table_exists(c, "characters"):
                return

            c.execute("PRAGMA table_info(characters)")
            columns = [column[1] for column in c.fetchall()]
            if "level" not in columns:
                c.execute("ALTER TABLE characters ADD COLUMN level INTEGER DEFAULT 1")
            if "familiers" not in columns:
                c.execute("ALTER TABLE characters ADD COLUMN familiers TEXT DEFAULT '[]'")
            if "inventory" not in columns:
                c.execute("ALTER TABLE characters ADD COLUMN inventory TEXT")
            if "owner_character_id" not in columns:
                c.execute("ALTER TABLE characters ADD COLUMN owner_character_id INTEGER DEFAULT NULL")

            c.execute("UPDATE characters SET level = 1 WHERE level IS NULL")
            c.execute("UPDATE characters SET familiers = '[]' WHERE familiers IS NULL OR familiers = ''")
            c.execute(
                "UPDATE characters SET inventory = ? WHERE inventory IS NULL OR inventory = ''",
                (json.dumps(DEFAULT_INVENTORY),),
            )

            _migrate_legacy_familiers(c)
    except sqlite3.Error as e:
        logger.exception("Erreur lors de la migration des joueurs existants.")
        raise DatabaseError("Impossible de migrer les données existantes.") from e


def add_inventory_column():
    try:
        with _connect() as conn:
            c = conn.cursor()

            if not _table_exists(c, "characters"):
                return

            c.execute("PRAGMA table_info(characters)")
            columns = [column[1] for column in c.fetchall()]
            if "inventory" not in columns:
                c.execute("ALTER TABLE characters ADD COLUMN inventory TEXT")
            c.execute(
                "UPDATE characters SET inventory = ? WHERE inventory IS NULL OR inventory = ''",
                (json.dumps(DEFAULT_INVENTORY),),
            )
    except sqlite3.Error as e:
        logger.exception("Erreur lors de l'ajout/mise à niveau de la colonne inventory.")
        raise DatabaseError("Impossible de finaliser la colonne inventory.") from e


def bootstrap_database():
    init_db()
    update_existing_players()
    add_inventory_column()


def add_user(user_id, actif_id=None):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO users (id, actif_id)
                VALUES (?, ?)
                """,
                (str(user_id), actif_id),
            )
        return True
    except DB_ERRORS as e:
        logger.exception("Erreur lors de l'ajout de l'utilisateur %s.", user_id)
        raise DatabaseError("Impossible d'ajouter l'utilisateur.") from e


def add_character(user_id, character_data):
    try:
        payload = {
            "name": character_data["name"],
            "age": character_data["age"],
            "race": character_data["race"],
            "level": character_data["level"],
            "attributes": character_data["attributes"],
            "skills": character_data["skills"],
            "magie": character_data.get("magie", []),
            "pv_actu": character_data["pv_actu"],
            "pv_max": character_data["pv_max"],
            "mana_actu": character_data["mana_actu"],
            "mana_max": character_data["mana_max"],
            "inventory": character_data.get("inventory", _default_inventory_copy()),
            "familiers": character_data.get("familiers", []),
            "owner_character_id": character_data.get("owner_character_id"),
        }

        with _connect() as conn:
            c = conn.cursor()
            _insert_character_row(c, user_id, payload)
            return c.lastrowid
    except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
        logger.exception("Erreur lors de l'ajout du personnage pour l'utilisateur %s.", user_id)
        raise DatabaseError("Impossible d'ajouter le personnage.") from e


def _get_active_character_id(cursor, user_id):
    cursor.execute("SELECT actif_id FROM users WHERE id = ?", (str(user_id),))
    row = cursor.fetchone()
    if not row:
        return None
    return row["actif_id"]


def _execute_update_character(cursor, character_id, player_data, legacy_familiers):
    cursor.execute(
        """
        UPDATE characters
        SET age = ?,
            race = ?,
            level = ?,
            attributes = ?,
            skills = ?,
            magie = ?,
            pv_actu = ?,
            pv_max = ?,
            mana_actu = ?,
            mana_max = ?,
            inventory = ?,
            familiers = ?
        WHERE id = ?
        """,
        (
            player_data["age"],
            player_data["race"],
            player_data["level"],
            json.dumps(player_data["attributes"]),
            json.dumps(player_data["skills"]),
            json.dumps(player_data["magie"]),
            player_data["pv_actu"],
            player_data["pv_max"],
            player_data["mana_actu"],
            player_data["mana_max"],
            json.dumps(player_data["inventory"]),
            json.dumps(legacy_familiers),
            character_id,
        ),
    )


def _update_linked_familier_row(cursor, owner_character_id, user_id, familier_data):
    familier_payload = _familier_to_character_payload(user_id, familier_data, owner_character_id=owner_character_id)
    familier_id = familier_payload.get("id")
    if not familier_id:
        return

    cursor.execute(
        """
        UPDATE characters
        SET name = ?,
            age = ?,
            race = 'Familier',
            level = ?,
            attributes = ?,
            skills = ?,
            magie = ?,
            pv_actu = ?,
            pv_max = ?,
            mana_actu = ?,
            mana_max = ?,
            inventory = ?,
            familiers = '[]',
            owner_character_id = ?
        WHERE id = ? AND user_id = ? AND race = 'Familier'
        """,
        (
            familier_payload["name"],
            familier_payload["age"],
            familier_payload["level"],
            json.dumps(familier_payload["attributes"]),
            json.dumps(familier_payload["skills"]),
            json.dumps(familier_payload["magie"]),
            familier_payload["pv_actu"],
            familier_payload["pv_max"],
            familier_payload["mana_actu"],
            familier_payload["mana_max"],
            json.dumps(familier_payload["inventory"]),
            owner_character_id,
            familier_id,
            str(user_id),
        ),
    )


def load_user(user_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE id = ?", (str(user_id),))
            row = c.fetchone()

        if row:
            return {"id": row["id"], "actif_id": row["actif_id"]}
        return None
    except DB_ERRORS:
        logger.exception("Erreur lors du chargement de l'utilisateur %s.", user_id)
        return None


def _load_familiers_by_owner_cursor(cursor, owner_character_id):
    cursor.execute(
        """
        SELECT *
        FROM characters
        WHERE owner_character_id = ?
          AND race = 'Familier'
        ORDER BY name COLLATE NOCASE
        """,
        (owner_character_id,),
    )
    rows = cursor.fetchall()
    familiers = []
    for row in rows:
        try:
            familiers.append(_character_to_familier_payload(_row_to_character_data(row)))
        except DATA_ERRORS:
            logger.exception("Erreur lors du traitement du familier %s.", row["id"])
    return familiers


def _attach_familiers(cursor, player_data):
    owner_id = player_data["id"]
    linked_familiers = _load_familiers_by_owner_cursor(cursor, owner_id)

    legacy_familiers = []
    for familier in player_data.get("familiers", []):
        if isinstance(familier, dict) and familier.get("id"):
            continue
        legacy_familiers.append(familier)

    player_data["familiers"] = linked_familiers + legacy_familiers
    return player_data


def load_player(user_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT *
                FROM characters
                WHERE id = (SELECT actif_id FROM users WHERE id = ?)
                """,
                (str(user_id),),
            )
            row = c.fetchone()
            if not row:
                return None

            player_data = _row_to_character_data(row)
            return _attach_familiers(c, player_data)
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError):
        logger.exception("Erreur lors du chargement du personnage pour l'utilisateur %s.", user_id)
        return None


def update_player(user_id, player_data):
    try:
        with _connect() as conn:
            c = conn.cursor()
            character_id = player_data.get("id") or _get_active_character_id(c, user_id)
            if not character_id:
                return

            legacy_familiers = []
            linked_familiers = []
            for familier in player_data.get("familiers", []):
                if isinstance(familier, dict) and familier.get("id"):
                    linked_familiers.append(familier)
                else:
                    legacy_familiers.append(familier)

            _execute_update_character(c, character_id, player_data, legacy_familiers)
            for familier_data in linked_familiers:
                _update_linked_familier_row(c, character_id, user_id, familier_data)
    except (sqlite3.Error, KeyError, TypeError, ValueError):
        logger.exception(
            "Erreur lors de la mise à jour du personnage %s pour l'utilisateur %s.",
            user_id,
            player_data.get("user_id"),
        )


def update_two_players_atomic(user_id_a, player_data_a, user_id_b, player_data_b):
    try:
        with _connect() as conn:
            c = conn.cursor()

            character_id_a = player_data_a.get("id") or _get_active_character_id(c, user_id_a)
            character_id_b = player_data_b.get("id") or _get_active_character_id(c, user_id_b)
            if not character_id_a or not character_id_b:
                raise DatabaseError("Impossible de résoudre les personnages actifs.")

            legacy_a = [f for f in player_data_a.get("familiers", []) if not (isinstance(f, dict) and f.get("id"))]
            linked_a = [f for f in player_data_a.get("familiers", []) if isinstance(f, dict) and f.get("id")]

            legacy_b = [f for f in player_data_b.get("familiers", []) if not (isinstance(f, dict) and f.get("id"))]
            linked_b = [f for f in player_data_b.get("familiers", []) if isinstance(f, dict) and f.get("id")]

            _execute_update_character(c, character_id_a, player_data_a, legacy_a)
            _execute_update_character(c, character_id_b, player_data_b, legacy_b)

            for familier_data in linked_a:
                _update_linked_familier_row(c, character_id_a, user_id_a, familier_data)
            for familier_data in linked_b:
                _update_linked_familier_row(c, character_id_b, user_id_b, familier_data)

        return True
    except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
        logger.exception(
            "Erreur lors de la mise à jour atomique des joueurs %s et %s.",
            user_id_a,
            user_id_b,
        )
        raise DatabaseError("Impossible de mettre à jour les deux joueurs de manière atomique.") from e


def remove_player(user_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM characters WHERE user_id = ?", (str(user_id),))
            c.execute("DELETE FROM users WHERE id = ?", (str(user_id),))
        return True
    except DB_ERRORS:
        logger.exception("Erreur lors de la suppression des personnages pour l'utilisateur %s.", user_id)
        return False


def remove_character(user_id, character_name):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id FROM characters WHERE user_id = ? AND name = ?",
                (str(user_id), character_name),
            )
            row = c.fetchone()
            if not row:
                return False

            character_id = row["id"]
            c.execute("UPDATE characters SET owner_character_id = NULL WHERE owner_character_id = ?", (character_id,))
            c.execute("DELETE FROM characters WHERE id = ? AND user_id = ?", (character_id, str(user_id)))
            return c.rowcount > 0
    except DB_ERRORS:
        logger.exception(
            "Erreur lors de la suppression du personnage %s pour l'utilisateur %s.",
            character_name,
            user_id,
        )
        return False


def load_all_players():
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT u.id AS user_id, c.*
                FROM users u
                JOIN characters c ON u.actif_id = c.id
                """
            )
            rows = c.fetchall()

            players = {}
            for row in rows:
                player_data = _row_to_character_data(row)
                player_data["user_id"] = row["user_id"]
                players[row["user_id"]] = _attach_familiers(c, player_data)
            return players
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError):
        logger.exception("Erreur lors du chargement de tous les joueurs.")
        return {}


def load_all_characters_by_user(user_id, include_familiers=False):
    try:
        with _connect() as conn:
            c = conn.cursor()
            if include_familiers:
                c.execute("SELECT * FROM characters WHERE user_id = ? ORDER BY name COLLATE NOCASE", (str(user_id),))
            else:
                c.execute(
                    "SELECT * FROM characters WHERE user_id = ? AND (race IS NULL OR race != 'Familier') ORDER BY name COLLATE NOCASE",
                    (str(user_id),),
                )
            rows = c.fetchall()

            characters = []
            for row in rows:
                character_data = _row_to_character_data(row)
                if (character_data.get("race") or "") == "Familier":
                    characters.append(_character_to_familier_payload(character_data))
                else:
                    characters.append(_attach_familiers(c, character_data))
            return characters
    except DB_ERRORS:
        logger.exception("Erreur lors du chargement des personnages pour l'utilisateur %s.", user_id)
        return []


def load_character_by_name(user_id, character_name, include_familiers=False):
    try:
        with _connect() as conn:
            c = conn.cursor()
            if include_familiers:
                c.execute(
                    "SELECT * FROM characters WHERE user_id = ? AND name = ?",
                    (str(user_id), character_name),
                )
            else:
                c.execute(
                    "SELECT * FROM characters WHERE user_id = ? AND name = ? AND (race IS NULL OR race != 'Familier')",
                    (str(user_id), character_name),
                )
            row = c.fetchone()
            if not row:
                return None

            character_data = _row_to_character_data(row)
            if (character_data.get("race") or "") == "Familier":
                return _character_to_familier_payload(character_data)
            return _attach_familiers(c, character_data)
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError):
        logger.exception(
            "Erreur lors du chargement du personnage %s pour l'utilisateur %s.",
            character_name,
            user_id,
        )
        return None


def load_familiers_by_owner(user_id, owner_character_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT *
                FROM characters
                WHERE user_id = ?
                  AND race = 'Familier'
                  AND owner_character_id = ?
                ORDER BY name COLLATE NOCASE
                """,
                (str(user_id), owner_character_id),
            )
            rows = c.fetchall()
            return [_character_to_familier_payload(_row_to_character_data(row)) for row in rows]
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError):
        logger.exception(
            "Erreur lors du chargement des familiers du personnage %s pour l'utilisateur %s.",
            owner_character_id,
            user_id,
        )
        return []


def load_unassociated_familiers_by_user(user_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT *
                FROM characters
                WHERE user_id = ?
                  AND race = 'Familier'
                  AND owner_character_id IS NULL
                ORDER BY name COLLATE NOCASE
                """,
                (str(user_id),),
            )
            rows = c.fetchall()
            return [_character_to_familier_payload(_row_to_character_data(row)) for row in rows]
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError):
        logger.exception("Erreur lors du chargement des familiers non associés pour l'utilisateur %s.", user_id)
        return []


def load_familier_by_name(user_id, familier_name):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT *
                FROM characters
                WHERE user_id = ?
                  AND race = 'Familier'
                  AND lower(name) = lower(?)
                ORDER BY id DESC
                LIMIT 1
                """,
                (str(user_id), familier_name),
            )
            row = c.fetchone()
            if not row:
                return None
            return _character_to_familier_payload(_row_to_character_data(row))
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError):
        logger.exception(
            "Erreur lors du chargement du familier %s pour l'utilisateur %s.",
            familier_name,
            user_id,
        )
        return None


def load_all_familiers_by_user(user_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT *
                FROM characters
                WHERE user_id = ?
                  AND race = 'Familier'
                ORDER BY name COLLATE NOCASE
                """,
                (str(user_id),),
            )
            rows = c.fetchall()
            return [_character_to_familier_payload(_row_to_character_data(row)) for row in rows]
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError):
        logger.exception("Erreur lors du chargement de tous les familiers pour l'utilisateur %s.", user_id)
        return []


def add_familier_character(user_id, familier_data, owner_character_id=None):
    payload = _familier_to_character_payload(str(user_id), familier_data, owner_character_id=owner_character_id)
    character_payload = {
        "name": payload["name"],
        "age": payload["age"],
        "race": "Familier",
        "level": payload["level"],
        "attributes": payload["attributes"],
        "skills": payload["skills"],
        "magie": payload["magie"],
        "pv_actu": payload["pv_actu"],
        "pv_max": payload["pv_max"],
        "mana_actu": payload["mana_actu"],
        "mana_max": payload["mana_max"],
        "inventory": payload["inventory"],
        "familiers": [],
        "owner_character_id": owner_character_id,
    }
    return add_character(user_id, character_payload)


def associate_familier_to_character(user_id, familier_id, owner_character_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                """
                UPDATE characters
                SET owner_character_id = ?
                WHERE id = ?
                  AND user_id = ?
                  AND race = 'Familier'
                """,
                (owner_character_id, familier_id, str(user_id)),
            )
            return c.rowcount > 0
    except DB_ERRORS:
        logger.exception(
            "Erreur lors de l'association du familier %s au personnage %s pour l'utilisateur %s.",
            familier_id,
            owner_character_id,
            user_id,
        )
        return False


def update_familier(user_id, familier_data):
    try:
        with _connect() as conn:
            c = conn.cursor()
            familier_id = familier_data.get("id")
            if not familier_id:
                return False

            existing_owner = familier_data.get("owner_character_id")
            if existing_owner is None:
                c.execute(
                    "SELECT owner_character_id FROM characters WHERE id = ? AND user_id = ? AND race = 'Familier'",
                    (familier_id, str(user_id)),
                )
                row = c.fetchone()
                if not row:
                    return False
                existing_owner = row["owner_character_id"]

            _update_linked_familier_row(c, existing_owner, str(user_id), familier_data)
            return c.rowcount > 0
    except DB_ERRORS:
        logger.exception(
            "Erreur lors de la mise à jour du familier %s pour l'utilisateur %s.",
            familier_data.get("id"),
            user_id,
        )
        return False


def remove_familier(user_id, familier_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute(
                "DELETE FROM characters WHERE id = ? AND user_id = ? AND race = 'Familier'",
                (familier_id, str(user_id)),
            )
            return c.rowcount > 0
    except DB_ERRORS:
        logger.exception("Erreur lors de la suppression du familier %s pour l'utilisateur %s.", familier_id, user_id)
        return False


def change_active_character(user_id, character_id):
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET actif_id = ? WHERE id = ?", (character_id, str(user_id)))
    except DB_ERRORS:
        logger.exception("Erreur lors du changement du personnage actif pour l'utilisateur %s.", user_id)
