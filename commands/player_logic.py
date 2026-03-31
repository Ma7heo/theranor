import copy
import random

import discord
from database import DEFAULT_INVENTORY

CREATION_STEPS = [
    {"question": "Choisissez un nom pour votre personnage :", "options": []},
    {"question": "Choisissez un âge pour votre personnage :", "options": []},
    {"question": "Choisissez une race pour votre personnage :", "options": ["Humain", "Nain", "Elfe", "Gnome", "Demi-Orc", "Fée"]},
    {"question": "Distribuez 4 points dans les attributs (FOR, AGI, CHA, INT) :\nFormat: FOR 1, AGI 1, CHA 1, INT 1", "options": []},
    {
        "question": (
            "Distribuez 8 points dans les compétences (ou 9 si vous êtes humain) :\n"
            "Liste des compétences :\n"
            "FORCE: pugilat, arme_a_une_main, arme_a_deux_mains, arme_dhast, bouclier, athletisme\n"
            "AGILITE: arc, arbalete, arme_de_jet, esquive, larcin, furtivite\n"
            "CHARISME: persuasion, marchandage, performance, seduction, instinct, observation\n"
            "INTELLIGENCE: connaissance, medecine, alchimie, ingenierie, magie1, magie2\n"
            "Format: pugilat 1, arc 2, etc."
        ),
        "options": [],
    },
    {"question": "Choisissez votre première magie :", "options": ["Magie arcanique", "Magie élémentaire", "Magie noire", "Magie sacrée", "Druidique", "Sorcellerie"]},
    {"question": "Choisissez votre deuxième magie :", "options": ["Magie arcanique", "Magie élémentaire", "Magie noire", "Magie sacrée", "Druidique", "Sorcellerie"]},
]

RACE_BONUS = {
    "Humain": {"comp_bonus": 1, "attributes": {}, "skills": {}},
    "Nain": {"attributes": {"for": 1}, "skills": {"charisme": {"marchandage": 1}}},
    "Elfe": {"attributes": {"agi": 1}, "skills": {"agilite": {"arc": 1}}},
    "Gnome": {"attributes": {"int": 1}, "skills": {"intelligence": {"ingenierie": 1}}},
    "Demi-Orc": {"attributes": {"for": 1}, "skills": {"force": {"pugilat": 1}}},
    "Fée": {"attributes": {"cha": 1}, "skills": {}},
}

ATTRIBUTE_CHOICES = [
    "attributes.for",
    "attributes.agi",
    "attributes.cha",
    "attributes.int",
    "skills.force.pugilat",
    "skills.force.arme_a_une_main",
    "skills.force.arme_a_deux_mains",
    "skills.force.arme_dhast",
    "skills.force.bouclier",
    "skills.force.athletisme",
    "skills.agilite.arc",
    "skills.agilite.arbalete",
    "skills.agilite.arme_de_jet",
    "skills.agilite.esquive",
    "skills.agilite.larcin",
    "skills.agilite.furtivite",
    "skills.charisme.persuasion",
    "skills.charisme.marchandage",
    "skills.charisme.performance",
    "skills.charisme.seduction",
    "skills.charisme.instinct",
    "skills.charisme.observation",
    "skills.intelligence.connaissance",
    "skills.intelligence.medecine",
    "skills.intelligence.alchimie",
    "skills.intelligence.ingenierie",
    "skills.intelligence.magie1",
    "skills.intelligence.magie2",
    "pv_max",
    "mana_max",
]


def new_character_template():
    return {
        "name": "",
        "age": 0,
        "race": "",
        "level": 1,
        "attributes": {"for": 0, "agi": 0, "cha": 0, "int": 0},
        "skills": {
            "force": {"pugilat": 0, "arme_a_une_main": 0, "arme_a_deux_mains": 0, "arme_dhast": 0, "bouclier": 0, "athletisme": 0},
            "agilite": {"arc": 0, "arbalete": 0, "arme_de_jet": 0, "esquive": 0, "larcin": 0, "furtivite": 0},
            "charisme": {"persuasion": 0, "marchandage": 0, "performance": 0, "seduction": 0, "instinct": 0, "observation": 0},
            "intelligence": {"connaissance": 0, "medecine": 0, "alchimie": 0, "ingenierie": 0, "magie1": 0, "magie2": 0},
        },
        "magie": [],
        "pv_actu": 0,
        "pv_max": 0,
        "mana_actu": 0,
        "mana_max": 0,
        "inventory": copy.deepcopy(DEFAULT_INVENTORY),
        "familiers": [],
    }


def apply_race_bonus(player_data, race):
    player_data["race"] = race
    race_bonus = RACE_BONUS.get(race, {})
    for attr, bonus in race_bonus.get("attributes", {}).items():
        player_data["attributes"][attr] += bonus
    for category, skills in race_bonus.get("skills", {}).items():
        for skill, bonus in skills.items():
            player_data["skills"][category][skill] += bonus


def apply_attribute_distribution(player_data, raw_value):
    attributes = raw_value.split(", ")
    total_points = 0
    temp_attributes = player_data["attributes"].copy()
    for attr in attributes:
        attr_name, attr_value = attr.split()
        attr_value = int(attr_value)
        total_points += attr_value
        attr_key = attr_name.lower()
        if attr_key not in temp_attributes:
            raise KeyError(attr_name)
        temp_attributes[attr_key] += attr_value
    if total_points != 4:
        raise ValueError("attribute_points")
    player_data["attributes"] = temp_attributes


def apply_skill_distribution(player_data, raw_value):
    skills = raw_value.lower().split(", ")
    total_points = 0
    skill_values = {}
    for skill in skills:
        skill_name, skill_value = skill.split()
        skill_value = int(skill_value)
        total_points += skill_value
        skill_values[skill_name] = skill_values.get(skill_name, 0) + skill_value

    required_points = 9 if player_data["race"] == "Humain" else 8
    if total_points != required_points:
        raise ValueError("skill_points")

    temp_skills = copy.deepcopy(player_data["skills"])
    for skill_name, skill_value in skill_values.items():
        for category in temp_skills:
            if skill_name in temp_skills[category]:
                if skill_value > player_data["attributes"][category[:3]]:
                    raise ValueError(f"skill_cap:{skill_name}:{category}")
                temp_skills[category][skill_name] += skill_value
                break
        else:
            raise KeyError(skill_name)
    player_data["skills"] = temp_skills


def finalize_character_stats(player_data):
    level = player_data["level"]
    for_attr = player_data["attributes"].get("for", 0)
    int_attr = player_data["attributes"].get("int", 0)
    player_data["pv_max"] = 5 + random.randint(1, 6) + for_attr + level
    player_data["mana_max"] = 5 + random.randint(1, 6) + int_attr + level
    player_data["pv_actu"] = player_data["pv_max"]
    player_data["mana_actu"] = player_data["mana_max"]


def compute_level_up_gain(level, for_attr, int_attr):
    if level <= 4:
        pv_gain = random.randint(1, 6) + for_attr + level
        pm_gain = random.randint(1, 6) + int_attr + level
    elif level <= 9:
        pv_gain = random.randint(1, 8) + 2 * for_attr + level
        pm_gain = random.randint(1, 8) + 2 * int_attr + level
    elif level <= 14:
        pv_gain = random.randint(1, 12) + 3 * for_attr + level
        pm_gain = random.randint(1, 12) + 3 * int_attr + level
    else:
        pv_gain = random.randint(1, 20) + 4 * for_attr + level
        pm_gain = random.randint(1, 20) + 4 * int_attr + level
    return pv_gain, pm_gain


def build_character_list_message(players):
    message = "Voici la liste de vos personnages :\n"
    for player_data in players:
        message += f"- {player_data['name']} (Niveau {player_data['level']}, Race: {player_data['race']})\n"
    return message


def build_base_info_embed(player_data):
    embed = discord.Embed(title=f"{player_data['name']} - {player_data['race']}", color=discord.Color.blue())
    embed.add_field(name="HP", value=f"{player_data['pv_actu']}/{player_data['pv_max']} :heart:", inline=True)
    embed.add_field(name="MANA", value=f"{player_data['mana_actu']}/{player_data['mana_max']} :droplet:", inline=True)
    embed.add_field(name="Niveau", value=player_data["level"], inline=True)
    embed.add_field(name="Force", value=player_data["attributes"]["for"], inline=True)
    embed.add_field(name="Intelligence", value=player_data["attributes"]["int"], inline=True)
    embed.add_field(name="Agilité", value=player_data["attributes"]["agi"], inline=True)
    embed.add_field(name="Charisme", value=player_data["attributes"]["cha"], inline=True)

    argent = player_data["inventory"]["argent"]
    embed.add_field(
        name="Argent",
        value=f"{argent['pc']} <:copper_coin:1258085404779876422>  {argent['pa']} <:silver_coin:1258086833644896336>  {argent['po']} <:gold_coin:1258087444147077161>",
        inline=False,
    )
    return embed
