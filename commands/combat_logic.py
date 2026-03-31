from dataclasses import dataclass

from utils import parse_dice_expression, roll_dice, roll_with_bonus


class CombatValidationError(ValueError):
    pass


MAGIE_CHOICES = ("magie1", "magie2")


@dataclass(frozen=True)
class AttackContext:
    skill_name: str
    category: str
    attribute: str
    weapon: dict | None


@dataclass(frozen=True)
class SpellScaling:
    damage_die: str
    heal_die: str
    buff_debuff_value: int
    shield_die_personal: str
    shield_die_fixed: str
    range_multiplier: int
    move_multiplier: int


def get_weapon_choices(player_data):
    weapons = player_data["inventory"]["armes"]
    return [weapon["nom"] for weapon in weapons] + ["pugilat"]


def get_skill_choices(player_data):
    attributes = list(player_data["attributes"].keys())
    skills = []
    for category in player_data["skills"]:
        skills.extend(player_data["skills"][category].keys())
    return attributes + skills


def _resolve_skill_category(player_data, skill_name):
    if skill_name in player_data["skills"]["force"]:
        return "force", "for"
    if skill_name in player_data["skills"]["agilite"]:
        return "agilite", "agi"
    if skill_name in player_data["skills"]["intelligence"]:
        return "intelligence", "int"
    if skill_name in player_data["skills"]["charisme"]:
        return "charisme", "cha"
    raise CombatValidationError("Compétence non reconnue.")


def resolve_attack_context(player_data, weapon_name):
    if weapon_name.lower() == "pugilat":
        return AttackContext(skill_name="pugilat", category="force", attribute="for", weapon=None)

    weapon = next((item for item in player_data["inventory"]["armes"] if item["nom"] == weapon_name), None)
    if not weapon:
        raise CombatValidationError("Arme non trouvée.")
    skill_name = weapon["bonus_type"]
    category, attribute = _resolve_skill_category(player_data, skill_name)
    return AttackContext(skill_name=skill_name, category=category, attribute=attribute, weapon=weapon)


def compute_attack_mana_cost(effect_levels):
    total_effects = sum(effect_levels)
    points_mana = total_effects * 2
    if total_effects > 0:
        use_mana, _ = parse_dice_expression(f"{total_effects}d6")
    else:
        use_mana = 0
    return total_effects, points_mana, use_mana


def build_attack_response(player_data, weapon_name, attack_ctx, skill_level, effect_levels):
    degats, portee, saignement, modification_zone, cible_supplementaire, etourdissement, parade, deplacement, difficulte_crit = effect_levels
    response_lines = []

    base_roll, bonus, total = roll_with_bonus(player_data, attack_ctx.skill_name, attack_ctx.category)
    response_lines.append(f"Lancer de dé pour toucher avec {weapon_name}: {base_roll} + {bonus} = {total}")

    if weapon_name.lower() == "pugilat":
        damage_expression = f"{skill_level}d4"
    else:
        damage_expression = attack_ctx.weapon.get("degats", "0d0")

    damage_roll, _ = parse_dice_expression(damage_expression)
    attribute_bonus = player_data["attributes"].get(attack_ctx.attribute, 0)
    total_damage = damage_roll + attribute_bonus

    if degats > 0:
        extra_damage_roll, _ = parse_dice_expression(f"{degats}d6")
        total_damage += extra_damage_roll
        response_lines.append(f"Dégâts supplémentaires: {extra_damage_roll} (Niveau: {degats})")
    if portee > 0:
        response_lines.append(f"Portée augmentée de {portee * 10} mètres (Niveau: {portee})")
    if saignement > 0:
        response_lines.append(f"Effet de saignement appliqué (Niveau: {saignement})")
    if modification_zone > 0:
        response_lines.append(f"Zone de combat modifiée (Niveau: {modification_zone})")
    if cible_supplementaire > 0:
        response_lines.append(f"Cible supplémentaire attaquée (Niveau: {cible_supplementaire})")
    if etourdissement > 0:
        response_lines.append(f"Effet d'étourdissement appliqué (Niveau: {etourdissement})")
    if parade > 0:
        response_lines.append(f"Bonus de parade de {parade * 10} appliqué (Niveau: {parade})")
    if deplacement > 0:
        response_lines.append(f"Déplacement augmenté de {deplacement * 10} mètres (Niveau: {deplacement})")
    if difficulte_crit > 0:
        response_lines.append(f"Difficulté de critique réduite de {difficulte_crit * 5} (Niveau: {difficulte_crit})")

    response_lines.append(f"Dégâts totaux avec {weapon_name}: {total_damage}")
    return response_lines


def validate_and_get_magic(player_data, magie_type):
    if magie_type not in MAGIE_CHOICES:
        raise CombatValidationError("Veuillez spécifier 'magie1' ou 'magie2'.")
    if len(player_data["magie"]) < 2:
        raise CombatValidationError("Magies du personnage incomplètes.")
    return player_data["magie"][0] if magie_type == "magie1" else player_data["magie"][1]


def ensure_magic_level(magie_name, magie_level, total_effects):
    if magie_name == "Magie arcanique" and magie_level > 2:
        if (magie_level + 1) < total_effects:
            raise CombatValidationError(f"Niveau de magie insuffisant pour utiliser {total_effects} effets.")
        return
    if magie_level < total_effects:
        raise CombatValidationError(f"Niveau de magie insuffisant pour utiliser {total_effects} effets.")


def get_spell_scaling(magie_name, total_effects):
    if magie_name == "Magie sacrée":
        if total_effects <= 4:
            return SpellScaling("d4", "d6", 5, "d6", "d10", 5, 2)
        if total_effects <= 9:
            return SpellScaling("d6", "d8", 10, "d8", "d12", 10, 5)
        return SpellScaling("d8", "d10", 15, "d10", "d14", 15, 10)

    if total_effects <= 4:
        return SpellScaling("d4", "d4", 5, "d4", "d8", 5, 2)
    if total_effects <= 9:
        return SpellScaling("d6", "d6", 10, "d6", "d10", 10, 5)
    return SpellScaling("d8", "d8", 15, "d8", "d12", 15, 10)


def build_magic_response(player_data, magie_type, scaling, effect_levels):
    degats, heal, buff, debuff, effet_negatif, zone_effet, amelioration_effet_negatif, portee, bouclier_perso, bouclier_fixe, deplacement = effect_levels
    response_lines = []
    range_increment = 20

    if degats > 0:
        damage_roll, _ = parse_dice_expression(f"{degats}{scaling.damage_die}")
        intelligence_bonus = player_data["attributes"]["int"]

        object_bonus = 0
        for item in player_data["inventory"]["armes"] + player_data["inventory"]["armures"] + player_data["inventory"]["autres_objets"]:
            if item["bonus_type"] == magie_type:
                object_damage_roll, _ = parse_dice_expression(item["degats"])
                object_bonus += object_damage_roll

        total_damage = damage_roll + intelligence_bonus + object_bonus
        response_lines.append(f"Dégâts infligés: {total_damage} (Roll: {damage_roll} + Intelligence: {intelligence_bonus} + Bonus des objets: {object_bonus})")

    if heal > 0:
        heal_roll, _ = parse_dice_expression(f"{heal}{scaling.heal_die}")
        intelligence_bonus = player_data["attributes"]["int"]
        response_lines.append(f"Soins: {heal_roll + intelligence_bonus} (= {heal_roll} + {intelligence_bonus})")
    if buff > 0:
        response_lines.append(f"Buff appliqué: +{buff * scaling.buff_debuff_value} pendant {buff} tour (Niveau: {buff})")
    if debuff > 0:
        response_lines.append(f"Debuff appliqué: -{debuff * scaling.buff_debuff_value} pendant {debuff} tour (Niveau: {debuff})")
    if effet_negatif > 0:
        response_lines.append(f"Effet négatif appliqué de niveau {effet_negatif}")
    if zone_effet > 0:
        response_lines.append(f"Zone d'effet augmentée de {zone_effet * 10} mètres (Niveau: {zone_effet})")
    if amelioration_effet_negatif > 0:
        difficulty_increase = amelioration_effet_negatif * (scaling.buff_debuff_value + 5)
        response_lines.append(f"Effet négatif amélioré: +{difficulty_increase} difficulté d'annulation.")
    if portee > 0:
        range_increase = portee * scaling.range_multiplier
        range_increment += range_increase
        response_lines.append(f"Portée augmentée de {range_increase} mètres (Niveau: {portee})")
    if bouclier_perso > 0:
        shield_roll, _ = parse_dice_expression(f"{bouclier_perso}{scaling.shield_die_personal}")
        intelligence_bonus = player_data["attributes"]["int"]
        response_lines.append(f"Bouclier personnel: {shield_roll + intelligence_bonus} Shield bonus ({shield_roll} + {intelligence_bonus})")
    if bouclier_fixe > 0:
        fixed_shield_roll, _ = parse_dice_expression(f"{bouclier_fixe}{scaling.shield_die_fixed}")
        intelligence_bonus = player_data["attributes"]["int"]
        response_lines.append(f"Bouclier fixe: {fixed_shield_roll + intelligence_bonus} Shield bonus ({fixed_shield_roll} + {intelligence_bonus})")
    if deplacement > 0:
        response_lines.append(f"Déplacement augmenté de {deplacement * scaling.move_multiplier} mètres (Niveau: {deplacement})")
    return response_lines


def compute_mana_cost(total_effects):
    return sum(roll_dice(1, 4) for _ in range(total_effects))
