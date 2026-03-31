import sqlite3
import json
import logging
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


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _parse_inventory(raw_inventory):
    if not raw_inventory:
        return dict(DEFAULT_INVENTORY)
    parsed = json.loads(raw_inventory)
    if isinstance(parsed, dict):
        return parsed
    return dict(DEFAULT_INVENTORY)

def init_db():
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
        
            # Création de la table users
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    actif_id TEXT
                )
            ''')
        
            # Création de la table characters
            c.execute('''
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
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
    except sqlite3.Error as e:
        logger.exception("Erreur lors de l'initialisation de la base de données.")
        raise DatabaseError("Impossible d'initialiser la base de données.") from e



def update_existing_players():
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
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

            c.execute("UPDATE characters SET level = 1 WHERE level IS NULL")
            c.execute("UPDATE characters SET familiers = '[]' WHERE familiers IS NULL OR familiers = ''")
            c.execute(
                "UPDATE characters SET inventory = ? WHERE inventory IS NULL OR inventory = ''",
                (json.dumps(DEFAULT_INVENTORY),),
            )
    except sqlite3.Error as e:
        logger.exception("Erreur lors de la migration des joueurs existants.")
        raise DatabaseError("Impossible de migrer les données existantes.") from e

def add_inventory_column():
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
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
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO users (id, actif_id)
                VALUES (?, ?)
            ''', (user_id, actif_id))
        return True
    except DB_ERRORS as e:
        logger.exception("Erreur lors de l'ajout de l'utilisateur %s.", user_id)
        raise DatabaseError("Impossible d'ajouter l'utilisateur.") from e

def add_character(user_id, character_data):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()

            c.execute('''
                INSERT INTO characters (user_id, name, age, race, level, attributes, skills, magie, pv_actu, pv_max, mana_actu, mana_max, inventory, familiers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, character_data['name'], character_data['age'], character_data['race'], character_data['level'],
                json.dumps(character_data['attributes']), json.dumps(character_data['skills']),
                json.dumps(character_data['magie']), character_data['pv_actu'], character_data['pv_max'],
                character_data['mana_actu'], character_data['mana_max'], json.dumps(character_data['inventory']),
                json.dumps(character_data['familiers'])
            ))
        return True
    except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
        logger.exception("Erreur lors de l'ajout du personnage pour l'utilisateur %s.", user_id)
        raise DatabaseError("Impossible d'ajouter le personnage.") from e


def _execute_update_player(cursor, user_id, player_data):
    cursor.execute('''
        UPDATE characters
        SET age = ?, race = ?, level = ?, attributes = ?, skills = ?, magie = ?, pv_actu = ?, pv_max = ?, mana_actu = ?, mana_max = ?, inventory = ?, familiers = ?
        WHERE id = (SELECT actif_id FROM users WHERE id = ?)
    ''', (
        player_data['age'], player_data['race'], player_data['level'],
        json.dumps(player_data['attributes']), json.dumps(player_data['skills']),
        json.dumps(player_data['magie']), player_data['pv_actu'], player_data['pv_max'],
        player_data['mana_actu'], player_data['mana_max'], json.dumps(player_data['inventory']),
        json.dumps(player_data['familiers']), user_id
    ))

def load_user(user_id):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = c.fetchone()
        
        if row:
            user_data = {
                'id': row[0],
                'actif_id': row[1]
            }
            return user_data
        return None
    except DB_ERRORS as e:
        logger.exception("Erreur lors du chargement de l'utilisateur %s.", user_id)
        return None

def load_player(user_id):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT *
                FROM characters 
                WHERE id = (SELECT actif_id FROM users WHERE id = ?)
            ''', (user_id,))
            row = c.fetchone()

        if row:
            player_data = {
                'id': row[0],
                'user_id': row[1],
                'name': row[2],
                'age': row[3],
                'race': row[4],
                'level': row[5],
                'attributes': json.loads(row[6]),
                'skills': json.loads(row[7]),
                'magie': json.loads(row[8]),
                'pv_actu': row[9],
                'pv_max': row[10],
                'mana_actu': row[11],
                'mana_max': row[12],
                'inventory': _parse_inventory(row[13]),
                'familiers': json.loads(row[14]) if row[14] else []
            }
            return player_data
        else:
            return None
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError) as e:
        logger.exception("Erreur lors du chargement du personnage pour l'utilisateur %s.", user_id)
        return None


def update_player(user_id, player_data):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            _execute_update_player(c, user_id, player_data)
    except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
        logger.exception(
            "Erreur lors de la mise à jour du personnage %s pour l'utilisateur %s.",
            user_id,
            player_data.get("user_id"),
        )


def update_two_players_atomic(user_id_a, player_data_a, user_id_b, player_data_b):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            _execute_update_player(c, user_id_a, player_data_a)
            _execute_update_player(c, user_id_b, player_data_b)
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
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM characters WHERE user_id = ?', (user_id,))
            c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        return True
    except DB_ERRORS as e:
        logger.exception("Erreur lors de la suppression des personnages pour l'utilisateur %s.", user_id)
        return False

def remove_character(user_id, character_name):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM characters WHERE user_id = ? AND name = ?', (user_id, character_name))
            deleted_count = c.rowcount
        return deleted_count > 0
    except DB_ERRORS as e:
        logger.exception(
            "Erreur lors de la suppression du personnage %s pour l'utilisateur %s.",
            character_name,
            user_id,
        )
        return False


def load_all_players():
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT u.id AS user_id, c.*
                FROM users u
                JOIN characters c ON u.actif_id = c.id
            ''')
            rows = c.fetchall()

        players = {}
        for row in rows:
            player_data = {
                'id': row[1],
                'user_id': row[0],
                'name': row[3],
                'age': row[4],
                'race': row[5],
                'level': row[6],
                'attributes': json.loads(row[7]),
                'skills': json.loads(row[8]),
                'magie': json.loads(row[9]),
                'pv_actu': row[10],
                'pv_max': row[11],
                'mana_actu': row[12],
                'mana_max': row[13],
                'inventory': _parse_inventory(row[14]),
                'familiers': json.loads(row[15]) if row[15] else []
            }
            players[row[0]] = player_data
        return players
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError) as e:
        logger.exception("Erreur lors du chargement de tous les joueurs.")
        return {}

def load_all_characters_by_user(user_id):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM characters WHERE user_id = ?", (user_id,))
            rows = c.fetchall()
    except DB_ERRORS as e:
        logger.exception("Erreur lors du chargement des personnages pour l'utilisateur %s.", user_id)
        return []

    characters = []
    for row in rows:
        try:
            character_data = {
                'id': row[0],
                'name': row[2],
                'age': row[3],
                'race': row[4],
                'level': row[5],
                'attributes': json.loads(row[6]),
                'skills': json.loads(row[7]),
                'magie': json.loads(row[8]),
                'pv_actu': row[9],
                'pv_max': row[10],
                'mana_actu': row[11],
                'mana_max': row[12],
                'inventory': _parse_inventory(row[13]),
                'familiers': json.loads(row[14]) if row[14] else []
            }
            characters.append(character_data)
        except DATA_ERRORS as e:
            logger.exception("Erreur lors du traitement du personnage %s.", row[0])
    return characters

def load_character_by_name(user_id, character_name):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM characters WHERE user_id = ? AND name = ?', (user_id, character_name))
            row = c.fetchone()
        
        if row:
            character_data = {
                'id': row[0],
                'user_id': row[1],
                'name': row[2],
                'age': row[3],
                'race': row[4],
                'level': row[5],
                'attributes': json.loads(row[6]),
                'skills': json.loads(row[7]),
                'magie': json.loads(row[8]),
                'pv_actu': row[9],
                'pv_max': row[10],
                'mana_actu': row[11],
                'mana_max': row[12],
                'inventory': _parse_inventory(row[13]),
                'familiers': json.loads(row[14]) if row[14] else []
            }
            return character_data
        return None
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError, KeyError, IndexError) as e:
        logger.exception(
            "Erreur lors du chargement du personnage %s pour l'utilisateur %s.",
            character_name,
            user_id,
        )
        return None

def change_active_character(user_id, character_id):
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET actif_id = ? WHERE id = ?', (character_id, user_id))
    except DB_ERRORS as e:
        logger.exception("Erreur lors du changement du personnage actif pour l'utilisateur %s.", user_id)
