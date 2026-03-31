import copy

from commands.player_logic import ATTRIBUTE_CHOICES
from database import DEFAULT_INVENTORY
from utils import roll_with_bonus

INVENTORY_CATEGORIES = ("armures", "armes", "autres_objets")


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


def parse_familier_skills(competences):
    skills = default_familier_skills()
    for competence in competences.split(","):
        skill_name, skill_value = competence.split(":")
        skill_name = skill_name.strip()
        skill_value = int(skill_value)
        for category in skills:
            if skill_name in skills[category]:
                skills[category][skill_name] = skill_value
                break
        else:
            raise KeyError(skill_name)
    return skills


def create_familier(nom, niveau, for_, agi, cha, int_, pv_max, mana_max, skills):
    return {
        "nom": nom,
        "niveau": niveau,
        "attributes": {
            "for": for_,
            "agi": agi,
            "cha": cha,
            "int": int_,
            "pv_max": pv_max,
            "mana_max": mana_max,
            "pv_actu": pv_max,
            "mana_actu": mana_max,
        },
        "skills": skills,
        "inventory": copy.deepcopy(DEFAULT_INVENTORY),
    }


def get_familier_choices(player_data):
    return [familier["nom"] for familier in player_data.get("familiers", [])]


def get_familier_action_choices(familier):
    attribute_choices = list(familier["attributes"].keys())
    skill_choices = []
    for _, skills in familier["skills"].items():
        skill_choices.extend(skills.keys())
    return attribute_choices + skill_choices


def find_familier(player_data, nom_familier, case_insensitive=True):
    if case_insensitive:
        normalized = nom_familier.lower()
        return next((f for f in player_data.get("familiers", []) if f["nom"].lower() == normalized), None)
    return next((f for f in player_data.get("familiers", []) if f["nom"] == nom_familier), None)


def get_weapon_choices(familier):
    return [weapon["nom"] for weapon in familier.get("inventory", {}).get("armes", [])] + ["pugilat"]


def get_item_choices(container_data, categorie):
    return [item["nom"] for item in container_data["inventory"].get(categorie, [])]


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


def handle_roll_command(action, entity_data):
    action = action.lower()
    if action in entity_data["attributes"]:
        base_roll, bonus, total = roll_with_bonus(entity_data, action)
        return f"Lancer de dé pour l'attribut {action.upper()}: {base_roll} + {bonus} = {total}"
    for category, skills in entity_data["skills"].items():
        if action in skills:
            base_roll, bonus, total = roll_with_bonus(entity_data, action, category)
            return f"Lancer de dé pour la compétence {action} dans la catégorie {category}: {base_roll} + {bonus} = {total}"
    return f"Compétence ou attribut {action} non reconnu."
