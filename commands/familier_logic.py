import copy

from database import DEFAULT_INVENTORY


def default_familier_skills():
    return {
        "force": {
            "pugilat": 0,
            "arme_a_une_main": 0,
            "arme_a_deux_mains": 0,
            "arme_dhast": 0,
            "bouclier": 0,
            "athletisme": 0,
        },
        "agilite": {
            "arc": 0,
            "arbalete": 0,
            "arme_de_jet": 0,
            "esquive": 0,
            "larcin": 0,
            "furtivite": 0,
        },
        "charisme": {
            "persuasion": 0,
            "marchandage": 0,
            "performance": 0,
            "seduction": 0,
            "instinct": 0,
            "observation": 0,
        },
        "intelligence": {
            "connaissance": 0,
            "medecine": 0,
            "alchimie": 0,
            "ingenierie": 0,
            "magie1": 0,
            "magie2": 0,
        },
    }


def find_familier(player_data, nom_familier, case_insensitive=True):
    if case_insensitive:
        normalized = nom_familier.lower()
        return next((f for f in player_data.get("familiers", []) if f["nom"].lower() == normalized), None)
    return next((f for f in player_data.get("familiers", []) if f["nom"] == nom_familier), None)


def build_familier_view_model(familier):
    inventory = familier.get("inventory")
    if not isinstance(inventory, dict):
        inventory = copy.deepcopy(DEFAULT_INVENTORY)

    return {
        "id": None,
        "user_id": None,
        "name": familier["nom"],
        "age": 0,
        "race": "Familier",
        "level": familier["niveau"],
        "attributes": {
            "for": familier["attributes"].get("for", 0),
            "agi": familier["attributes"].get("agi", 0),
            "cha": familier["attributes"].get("cha", 0),
            "int": familier["attributes"].get("int", 0),
        },
        "skills": familier["skills"],
        "magie": familier.get("magie", []),
        "pv_actu": familier["attributes"].get("pv_actu", 0),
        "pv_max": familier["attributes"].get("pv_max", 0),
        "mana_actu": familier["attributes"].get("mana_actu", 0),
        "mana_max": familier["attributes"].get("mana_max", 0),
        "inventory": inventory,
        "familiers": [],
    }
