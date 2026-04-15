import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands

from commands.combat_logic import (
    MAGIE_CHOICES,
    CombatValidationError,
    build_attack_response,
    build_magic_response,
    compute_attack_mana_cost,
    compute_mana_cost,
    ensure_magic_level,
    get_skill_choices,
    get_spell_scaling,
    get_weapon_choices,
    resolve_attack_context,
    validate_and_get_magic,
)
from commands.familier_logic import find_familier
from database import load_player, update_player
from utils import parse_dice_expression, roll_d100, roll_with_bonus

try:
    from blague_privee import blague_privee as _blague_privee
except (ImportError, AttributeError):
    _blague_privee = None

logger = logging.getLogger(__name__)


class CombatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _load_player_or_none(self, user_id):
        return await asyncio.to_thread(load_player, user_id)

    async def _resolve_entity_for_autocomplete(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return None
        familier_name = getattr(interaction.namespace, "familier", None)
        if not familier_name:
            return player_data
        familier_data = find_familier(player_data, familier_name)
        return familier_data or player_data

    @staticmethod
    def _entity_name(entity_data, is_familier: bool):
        return entity_data["nom"] if is_familier else entity_data["name"]

    @staticmethod
    def _get_mana(entity_data, is_familier: bool):
        if is_familier:
            return entity_data["attributes"]["mana_actu"]
        return entity_data["mana_actu"]

    @staticmethod
    def _set_mana(entity_data, is_familier: bool, value: int):
        if is_familier:
            entity_data["attributes"]["mana_actu"] = value
            return
        entity_data["mana_actu"] = value

    @staticmethod
    def _get_mana_max(entity_data, is_familier: bool):
        if is_familier:
            return entity_data["attributes"]["mana_max"]
        return entity_data["mana_max"]

    @staticmethod
    def _get_pv(entity_data, is_familier: bool):
        if is_familier:
            return entity_data["attributes"]["pv_actu"]
        return entity_data["pv_actu"]

    @staticmethod
    def _set_pv(entity_data, is_familier: bool, value: int):
        if is_familier:
            entity_data["attributes"]["pv_actu"] = value
            return
        entity_data["pv_actu"] = value

    @staticmethod
    def _get_pv_max(entity_data, is_familier: bool):
        if is_familier:
            return entity_data["attributes"]["pv_max"]
        return entity_data["pv_max"]

    async def _resolve_entity(self, owner_user_id: str, familier_name: str | None):
        player_data = await self._load_player_or_none(owner_user_id)
        if not player_data:
            return None, None, None, "Joueur non trouvé."
        if not familier_name:
            return player_data, player_data, False, None

        familier_data = find_familier(player_data, familier_name)
        if not familier_data:
            return player_data, None, None, f"Familier {familier_name} non trouvé."
        return player_data, familier_data, True, None

    @staticmethod
    def _bounded_delta(current_value: int, delta: int, min_value: int = 0, max_value: int | None = None):
        next_value = current_value + delta
        if max_value is not None:
            next_value = min(next_value, max_value)
        return max(next_value, min_value)

    async def _apply_pv_delta(self, owner_user_id: str, player_data, entity_data, is_familier: bool, delta: int):
        current_pv = self._get_pv(entity_data, is_familier)
        updated_pv = self._bounded_delta(
            current_pv,
            delta,
            min_value=0,
            max_value=self._get_pv_max(entity_data, is_familier) if delta > 0 else None,
        )
        self._set_pv(entity_data, is_familier, updated_pv)
        await asyncio.to_thread(update_player, owner_user_id, player_data)
        return updated_pv

    async def _apply_mana_delta(self, owner_user_id: str, player_data, entity_data, is_familier: bool, delta: int):
        current_mana = self._get_mana(entity_data, is_familier)
        updated_mana = self._bounded_delta(
            current_mana,
            delta,
            min_value=0,
            max_value=self._get_mana_max(entity_data, is_familier) if delta > 0 else None,
        )
        self._set_mana(entity_data, is_familier, updated_mana)
        await asyncio.to_thread(update_player, owner_user_id, player_data)
        return updated_mana

    async def blague_privee(self, interaction: discord.Interaction):
        if _blague_privee is None:
            return
        try:
            await _blague_privee(interaction)
        except Exception:
            logger.exception("Échec de l'exécution de blague_privee.")
            return

    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        entity_data = await self._resolve_entity_for_autocomplete(interaction)
        if not entity_data:
            return []
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in get_weapon_choices(entity_data)
            if current.lower() in choice.lower()
        ]

    async def familier_autocomplete(self, interaction: discord.Interaction, current: str):
        target_user = getattr(interaction.namespace, "joueur", None)
        target_user_id = str(target_user.id) if target_user else str(interaction.user.id)
        player_data = await self._load_player_or_none(target_user_id)
        if not player_data:
            return []
        return [
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ]

    @app_commands.command(name="attaquer", description="Effectue une attaque avec une arme ou avec 'pugilat'.")
    @app_commands.describe(familier="Nom du familier à utiliser (optionnel)")
    @app_commands.autocomplete(weapon_name=weapon_autocomplete, familier=familier_autocomplete)
    async def attaquer(
        self,
        interaction: discord.Interaction,
        weapon_name: str,
        familier: str = None,
        degats: int = 0,
        portee: int = 0,
        saignement: int = 0,
        modification_zone: int = 0,
        cible_supplementaire: int = 0,
        etourdissement: int = 0,
        parade: int = 0,
        deplacement: int = 0,
        difficulte_crit: int = 0,
    ):
        user_id = str(interaction.user.id)
        player_data, entity_data, is_familier, error = await self._resolve_entity(user_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        effect_levels = (
            degats,
            portee,
            saignement,
            modification_zone,
            cible_supplementaire,
            etourdissement,
            parade,
            deplacement,
            difficulte_crit,
        )

        try:
            attack_ctx = resolve_attack_context(entity_data, weapon_name)
        except CombatValidationError as exc:
            await interaction.response.send_message(str(exc))
            return

        _, points_mana, use_mana = compute_attack_mana_cost(effect_levels)
        skill_level = entity_data["skills"][attack_ctx.category][attack_ctx.skill_name]
        if points_mana > skill_level:
            await interaction.response.send_message(
                f"Vous n'avez pas assez de points de compétence. Compétence actuelle: {skill_level}, points requis: {points_mana}"
            )
            return
        entity_mana = self._get_mana(entity_data, is_familier)
        if entity_mana < use_mana:
            await interaction.response.send_message("Mana insuffisant.")
            return

        await interaction.response.defer()
        self._set_mana(entity_data, is_familier, entity_mana - use_mana)
        await asyncio.to_thread(update_player, user_id, player_data)

        response_lines = build_attack_response(
            player_data=entity_data,
            weapon_name=weapon_name,
            attack_ctx=attack_ctx,
            skill_level=skill_level,
            effect_levels=effect_levels,
        )
        response_lines.append(f"Mana consommé: {use_mana}")
        response_lines.append(f"Mana restant ({self._entity_name(entity_data, is_familier)}): {self._get_mana(entity_data, is_familier)}")
        await interaction.followup.send("\n".join(response_lines))

    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        entity_data = await self._resolve_entity_for_autocomplete(interaction)
        if not entity_data:
            return [app_commands.Choice(name="perception", value="perception")]

        choices = [
            app_commands.Choice(name=choice, value=choice)
            for choice in get_skill_choices(entity_data)
            if current.lower() in choice.lower()
        ]
        choices.append(app_commands.Choice(name="perception", value="perception"))
        return choices

    @app_commands.command(name="l", description="Effectue un jet de compétence ou d'attribut.")
    @app_commands.describe(familier="Nom du familier à utiliser (optionnel)")
    @app_commands.autocomplete(skill_name=skill_autocomplete, familier=familier_autocomplete)
    async def l(self, interaction: discord.Interaction, skill_name: str, familier: str = None):
        user_id = str(interaction.user.id)
        _, entity_data, _, error = await self._resolve_entity(user_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        skill_name = skill_name.lower()
        if skill_name == "perception":
            skill_name = "observation"
            await self.blague_privee(interaction)

        if skill_name in entity_data["attributes"]:
            base_roll, bonus, total = roll_with_bonus(entity_data, skill_name)
            await interaction.response.send_message(
                f"Lancer de dé pour l'attribut {skill_name.upper()} : {base_roll} + {bonus} = {total}"
            )
            return

        category = next(
            (cat for cat, skills in entity_data["skills"].items() if skill_name in skills),
            None,
        )
        if category:
            base_roll, bonus, total = roll_with_bonus(entity_data, skill_name, category)
            await interaction.response.send_message(
                f"Lancer de dé pour la compétence {skill_name} ({category}) : {base_roll} + {bonus} = {total}"
            )
            return

        await interaction.response.send_message(f"Compétence ou attribut {skill_name} non reconnu.")

    async def magic_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in MAGIE_CHOICES
            if current.lower() in choice.lower()
        ]

    @app_commands.command(name="utiliser_magie", description="Utilise une magie spécifique.")
    @app_commands.describe(
        familier="Nom du familier à utiliser (optionnel)",
        magie_type="Type de magie à utiliser",
        degats="Nombre de d4 pour les dégâts",
        heal="Nombre de d4 pour les soins",
        buff="Niveau du buff (+5/10/15)",
        debuff="Niveau du debuff (-5/10/15)",
        effet_negatif="Niveau de l'effet négatif",
        zone_effet="Nombre de d4 pour l'augmentation de la zone d'effet",
        amelioration_effet_negatif="Niveau de l'amélioration de l'effet négatif",
        portee="Nombre de d4 pour l'augmentation de la portée",
        bouclier_perso="Nombre de d4 pour le bouclier personnel",
        bouclier_fixe="Nombre de d4 pour le bouclier fixe",
        deplacement="Nombre de d4 pour l'augmentation du déplacement",
    )
    @app_commands.autocomplete(magie_type=magic_autocomplete, familier=familier_autocomplete)
    async def utiliser_magie(
        self,
        interaction: discord.Interaction,
        magie_type: str,
        familier: str = None,
        degats: int = 0,
        heal: int = 0,
        buff: int = 0,
        debuff: int = 0,
        effet_negatif: int = 0,
        zone_effet: int = 0,
        amelioration_effet_negatif: int = 0,
        portee: int = 0,
        bouclier_perso: int = 0,
        bouclier_fixe: int = 0,
        deplacement: int = 0,
    ):
        user_id = str(interaction.user.id)
        player_data, entity_data, is_familier, error = await self._resolve_entity(user_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        effect_levels = (
            degats,
            heal,
            buff,
            debuff,
            effet_negatif,
            zone_effet,
            amelioration_effet_negatif,
            portee,
            bouclier_perso,
            bouclier_fixe,
            deplacement,
        )
        total_effects = sum(effect_levels)

        try:
            magie_name = validate_and_get_magic(entity_data, magie_type)
            magie_level = entity_data["skills"]["intelligence"][magie_type]
            ensure_magic_level(magie_name, magie_level, total_effects)
        except CombatValidationError as exc:
            await interaction.response.send_message(str(exc))
            return

        mana_cost = compute_mana_cost(total_effects)
        entity_mana = self._get_mana(entity_data, is_familier)
        if entity_mana < mana_cost:
            await interaction.response.send_message("Mana insuffisant.")
            return

        base_roll, bonus, total_roll = roll_with_bonus(entity_data, magie_type, "intelligence")
        scaling = get_spell_scaling(magie_name, total_effects)
        response_lines = build_magic_response(entity_data, magie_type, scaling, effect_levels)

        self._set_mana(entity_data, is_familier, entity_mana - mana_cost)
        await asyncio.to_thread(update_player, user_id, player_data)

        response_lines.append(f"Jet de magie: {base_roll} + {bonus} = {total_roll}")
        response_lines.append(
            f"Coût de mana: {mana_cost}. Mana restant ({self._entity_name(entity_data, is_familier)}): {self._get_mana(entity_data, is_familier)}."
        )
        await interaction.response.send_message("\n".join(response_lines))

    @app_commands.command(name="damage", description="Inflige des dégâts à un joueur.")
    @app_commands.describe(joueur="Le joueur à qui infliger des dégâts", familier="Nom du familier ciblé (optionnel)", expression="Expression de dégâts", armure="Divise les dégâts par deux si vrai")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def damage(self, interaction: discord.Interaction, joueur: discord.Member, expression: str, armure: bool = False, familier: str = None):
        player_id = str(joueur.id)
        player_data, entity_data, is_familier, error = await self._resolve_entity(player_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        degats, _ = parse_dice_expression(expression)
        if armure:
            degats = (degats + 1) // 2
        await self._apply_pv_delta(player_id, player_data, entity_data, is_familier, -degats)
        await interaction.response.send_message(
            f"{self._entity_name(entity_data, is_familier)} ({joueur.mention}) a subi {degats} dégâts. PV actuels: {self._get_pv(entity_data, is_familier)}"
        )

    @app_commands.command(name="heal", description="Soigne un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour les soins", joueur="Le joueur à soigner", familier="Nom du familier à soigner (optionnel)")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def heal(self, interaction: discord.Interaction, expression: str = "1d1", joueur: discord.Member = None, familier: str = None):
        target = joueur or interaction.user
        player_id = str(target.id)
        player_data, entity_data, is_familier, error = await self._resolve_entity(player_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        soins, _ = parse_dice_expression(expression)
        await self._apply_pv_delta(player_id, player_data, entity_data, is_familier, soins)
        await interaction.response.send_message(
            f"{self._entity_name(entity_data, is_familier)} ({target.mention}) a été soigné de {soins} PV. PV actuels: {self._get_pv(entity_data, is_familier)}"
        )

    @app_commands.command(name="submana", description="Retire du mana à un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour retirer du mana", joueur="Le joueur à qui retirer du mana", familier="Nom du familier ciblé (optionnel)")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def submana(self, interaction: discord.Interaction, expression: str, joueur: discord.Member = None, familier: str = None):
        target = joueur or interaction.user
        player_id = str(target.id)
        player_data, entity_data, is_familier, error = await self._resolve_entity(player_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        degats, _ = parse_dice_expression(expression)
        await self._apply_mana_delta(player_id, player_data, entity_data, is_familier, -degats)
        await interaction.response.send_message(
            f"{self._entity_name(entity_data, is_familier)} ({target.mention}) a perdu {degats} de mana. Mana actuels: {self._get_mana(entity_data, is_familier)}"
        )

    @app_commands.command(name="addmana", description="Ajoute du mana à un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour ajouter du mana", joueur="Le joueur à qui ajouter du mana", familier="Nom du familier ciblé (optionnel)")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def addmana(self, interaction: discord.Interaction, expression: str, joueur: discord.Member = None, familier: str = None):
        target = joueur or interaction.user
        player_id = str(target.id)
        player_data, entity_data, is_familier, error = await self._resolve_entity(player_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        soins, _ = parse_dice_expression(expression)
        await self._apply_mana_delta(player_id, player_data, entity_data, is_familier, soins)
        await interaction.response.send_message(
            f"{self._entity_name(entity_data, is_familier)} ({target.mention}) a récupéré {soins} de mana. Mana actuels: {self._get_mana(entity_data, is_familier)}"
        )

    @app_commands.command(name="armure", description="Effectue un jet d'armure pour réduire les dégâts")
    @app_commands.describe(familier="Nom du familier à utiliser (optionnel)")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def armure(self, interaction: discord.Interaction, familier: str = None):
        user_id = str(interaction.user.id)
        _, entity_data, is_familier, error = await self._resolve_entity(user_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        armure = entity_data["attributes"].get("armure", 0)
        bonus_armures = sum(item["bonus_value"] for item in entity_data["inventory"]["armures"])
        bonus_bouclier = sum(
            item["bonus_value"]
            for item in entity_data["inventory"]["autres_objets"]
            if item["bonus_type"] == "bouclier"
        )
        roll = roll_d100()
        total = roll - armure - bonus_armures - bonus_bouclier

        message = f"Armure de {self._entity_name(entity_data, is_familier)}: 1d100 - {armure} - {bonus_armures} - {bonus_bouclier} = {total}"
        if total <= 0:
            message += "\nSuccès! Vous prendrez moitié moins de dégâts."
        else:
            message += "\nÉchec! Vous prendrez les dégâts complets."
        await interaction.response.send_message(message)


async def setup(bot):
    await bot.add_cog(CombatCommands(bot))
