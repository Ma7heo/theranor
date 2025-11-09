import sqlite3
import json
from config import DATABASE_PATH

import sqlite3
import json
from config import DATABASE_PATH

def init_db():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
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

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur lors de l'initialisation de la base de données: {e}")



def update_existing_players():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    c.execute("PRAGMA table_info(players)")
    columns = [column[1] for column in c.fetchall()]
    if 'level' not in columns:
        c.execute("ALTER TABLE players ADD COLUMN level INTEGER DEFAULT 1")
    if 'familiers' not in columns:
        c.execute("ALTER TABLE players ADD COLUMN familiers TEXT DEFAULT '[]'")
    if 'user_id' not in columns:
        c.execute("ALTER TABLE players ADD COLUMN user_id TEXT")

    c.execute("SELECT id, level, familiers FROM players")
    rows = c.fetchall()
    for row in rows:
        player_id = row[0]
        level = row[1]
        familiers = row[2]
        if level is None:
            level = 1
        if not isinstance(familiers, str) or familiers == "":
            familiers = '[]'
        c.execute("UPDATE players SET level = ?, familiers = ? WHERE id = ?", (level, familiers, player_id))
    
    conn.commit()
    conn.close()

def add_inventory_column():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(players)")
    columns = [column[1] for column in c.fetchall()]
    if 'inventory' not in columns:
        c.execute("ALTER TABLE players ADD COLUMN inventory TEXT")
    conn.commit()
    conn.close()

def add_user(user_id, actif_id=None):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO users (id, actif_id)
            VALUES (?, ?)
        ''', (user_id, actif_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur lors de l'ajout de l'utilisateur {user_id}: {e}")

def add_character(user_id, character_data):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
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
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur lors de l'ajout du personnage pour l'utilisateur {user_id}: {e}")

def load_user(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            user_data = {
                'id': row[0],
                'actif_id': row[1]
            }
            return user_data
        return None
    except Exception as e:
        print(f"Erreur lors du chargement de l'utilisateur {user_id}: {e}")
        return None

def load_player(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT *
            FROM characters 
            WHERE id = (SELECT actif_id FROM users WHERE id = ?)
        ''', (user_id,))
        row = c.fetchone()
        conn.close()

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
                'inventory': json.loads(row[13]) if row[13] else [],
                'familiers': json.loads(row[14]) if row[14] else []
            }
            return player_data
        else:
            return None
    except Exception as e:
        print(f"Erreur lors du chargement du personnage pour l'utilisateur {user_id}: {e}")
        return None


def update_player(user_id, player_data):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
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
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur lors de la mise à jour du personnage {user_id} pour l'utilisateur {player_data['user_id']}: {e}")

def remove_player(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM characters WHERE user_id = ?', (user_id,))
        c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erreur lors de la suppression des personnages pour l'utilisateur {user_id}: {e}")
        return False

def remove_character(user_id, character_name):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM characters WHERE user_id = ? AND name = ?', (user_id, character_name))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur lors de la suppression du personnage {character_name} pour l'utilisateur {user_id}: {e}")


def load_all_players():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT u.id AS user_id, c.*
            FROM users u
            JOIN characters c ON u.actif_id = c.id
        ''')
        rows = c.fetchall()
        conn.close()

        players = {}
        for row in rows:
            player_data = {
                'id': row[0],
                'user_id': row[1],
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
                'inventory': json.loads(row[14]),
                'familiers': json.loads(row[15]) if row[15] else []
            }
            players[row[0]] = player_data
        return players
    except Exception as e:
        print(f"Erreur lors du chargement de tous les joueurs: {e}")
        return {}

def load_all_characters_by_user(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM characters WHERE user_id = ?", (user_id,))
        rows = c.fetchall()
        conn.close()
    except Exception as e:
        print(f"Erreur lors du chargement des personnages pour l'utilisateur {user_id}: {e}")
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
                'inventory': json.loads(row[13]),
                'familiers': json.loads(row[14]) if row[14] else []
            }
            characters.append(character_data)
        except Exception as e:
            print(f"Erreur lors du traitement du personnage {row[0]}: {e}")
    return characters

def load_character_by_name(user_id, character_name):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('SELECT * FROM characters WHERE user_id = ? AND name = ?', (user_id, character_name))
        row = c.fetchone()
        conn.close()
        
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
                'inventory': json.loads(row[13]),
                'familiers': json.loads(row[14]) if row[14] else []
            }
            return character_data
        return None
    except Exception as e:
        print(f"Erreur lors du chargement du personnage {character_name} pour l'utilisateur {user_id}: {e}")
        return None

def change_active_character(user_id, character_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('UPDATE users SET actif_id = ? WHERE id = ?', (character_id, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur lors du changement du personnage actif pour l'utilisateur {user_id}: {e}")


def affiche():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('SELECT id FROM characters')
    rows = c.fetchall()
    conn.close()
    print(rows)

#affiche()


# Initialisation de la base de données
init_db()
