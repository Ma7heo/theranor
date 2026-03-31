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

    async def blague_privee(self, interaction: discord.Interaction):
        if _blague_privee is None:
            return
        try:
            await _blague_privee(interaction)
        except Exception:
            logger.exception("Échec de l'exécution de blague_privee.")
            return

    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return []
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in get_weapon_choices(player_data)
            if current.lower() in choice.lower()
        ]

    @app_commands.command(name="attaquer", description="Effectue une attaque avec une arme ou avec 'pugilat'.")
    @app_commands.autocomplete(weapon_name=weapon_autocomplete)
    async def attaquer(
        self,
        interaction: discord.Interaction,
        weapon_name: str,
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
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
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
            attack_ctx = resolve_attack_context(player_data, weapon_name)
        except CombatValidationError as exc:
            await interaction.response.send_message(str(exc))
            return

        _, points_mana, use_mana = compute_attack_mana_cost(effect_levels)
        skill_level = player_data["skills"][attack_ctx.category][attack_ctx.skill_name]
        if points_mana > skill_level:
            await interaction.response.send_message(
                f"Vous n'avez pas assez de points de compétence. Compétence actuelle: {skill_level}, points requis: {points_mana}"
            )
            return
        if player_data["mana_actu"] < use_mana:
            await interaction.response.send_message("Mana insuffisant.")
            return

        await interaction.response.defer()
        player_data["mana_actu"] -= use_mana
        await asyncio.to_thread(update_player, user_id, player_data)

        response_lines = build_attack_response(
            player_data=player_data,
            weapon_name=weapon_name,
            attack_ctx=attack_ctx,
            skill_level=skill_level,
            effect_levels=effect_levels,
        )
        response_lines.append(f"Mana consommé: {use_mana}")
        response_lines.append(f"Mana restant: {player_data['mana_actu']}")
        await interaction.followup.send("\n".join(response_lines))

    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return [app_commands.Choice(name="perception", value="perception")]

        choices = [
            app_commands.Choice(name=choice, value=choice)
            for choice in get_skill_choices(player_data)
            if current.lower() in choice.lower()
        ]
        choices.append(app_commands.Choice(name="perception", value="perception"))
        return choices

    @app_commands.command(name="l", description="Effectue un jet de compétence ou d'attribut.")
    @app_commands.autocomplete(skill_name=skill_autocomplete)
    async def l(self, interaction: discord.Interaction, skill_name: str):
        user_id = str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        skill_name = skill_name.lower()
        if skill_name == "perception":
            skill_name = "observation"
            await self.blague_privee(interaction)

        if skill_name in player_data["attributes"]:
            base_roll, bonus, total = roll_with_bonus(player_data, skill_name)
            await interaction.response.send_message(
                f"Lancer de dé pour l'attribut {skill_name.upper()} : {base_roll} + {bonus} = {total}"
            )
            return

        category = next(
            (cat for cat, skills in player_data["skills"].items() if skill_name in skills),
            None,
        )
        if category:
            base_roll, bonus, total = roll_with_bonus(player_data, skill_name, category)
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
    @app_commands.autocomplete(magie_type=magic_autocomplete)
    async def utiliser_magie(
        self,
        interaction: discord.Interaction,
        magie_type: str,
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
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
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
            magie_name = validate_and_get_magic(player_data, magie_type)
            magie_level = player_data["skills"]["intelligence"][magie_type]
            ensure_magic_level(magie_name, magie_level, total_effects)
        except CombatValidationError as exc:
            await interaction.response.send_message(str(exc))
            return

        mana_cost = compute_mana_cost(total_effects)
        if player_data["mana_actu"] < mana_cost:
            await interaction.response.send_message("Mana insuffisant.")
            return

        base_roll, bonus, total_roll = roll_with_bonus(player_data, magie_type, "intelligence")
        scaling = get_spell_scaling(magie_name, total_effects)
        response_lines = build_magic_response(player_data, magie_type, scaling, effect_levels)

        player_data["mana_actu"] -= mana_cost
        deplete_message = ""
        if player_data["mana_actu"] < 0:
            deplete_message = " Vous tombez en déplétion de mana."
            player_data["mana_actu"] = 0
        await asyncio.to_thread(update_player, user_id, player_data)

        response_lines.append(f"Jet de magie: {base_roll} + {bonus} = {total_roll}")
        response_lines.append(f"Coût de mana: {mana_cost}. Mana restant: {player_data['mana_actu']}.{deplete_message}")
        await interaction.response.send_message("\n".join(response_lines))

    @app_commands.command(name="damage", description="Inflige des dégâts à un joueur.")
    @app_commands.describe(joueur="Le joueur à qui infliger des dégâts", expression="Expression de dégâts", armure="Divise les dégâts par deux si vrai")
    async def damage(self, interaction: discord.Interaction, joueur: discord.Member, expression: str, armure: bool = False):
        player_id = str(joueur.id)
        player_data = await self._load_player_or_none(player_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        degats, _ = parse_dice_expression(expression)
        if armure:
            degats = (degats + 1) // 2
        player_data["pv_actu"] = max(player_data["pv_actu"] - degats, 0)
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{joueur.mention} a subi {degats} dégâts. PV actuels: {player_data['pv_actu']}"
        )

    @app_commands.command(name="heal", description="Soigne un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour les soins", joueur="Le joueur à soigner")
    async def heal(self, interaction: discord.Interaction, expression: str = "1d1", joueur: discord.Member = None):
        target = joueur or interaction.user
        player_id = str(target.id)
        player_data = await self._load_player_or_none(player_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        soins, _ = parse_dice_expression(expression)
        player_data["pv_actu"] = min(player_data["pv_actu"] + soins, player_data["pv_max"])
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{target.mention} a été soigné de {soins} PV. PV actuels: {player_data['pv_actu']}"
        )

    @app_commands.command(name="submana", description="Retire du mana à un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour retirer du mana", joueur="Le joueur à qui retirer du mana")
    async def submana(self, interaction: discord.Interaction, expression: str, joueur: discord.Member = None):
        target = joueur or interaction.user
        player_id = str(target.id)
        player_data = await self._load_player_or_none(player_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        degats, _ = parse_dice_expression(expression)
        player_data["mana_actu"] = max(player_data["mana_actu"] - degats, 0)
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{target.mention} a perdu {degats} de mana. Mana actuels: {player_data['mana_actu']}"
        )

    @app_commands.command(name="addmana", description="Ajoute du mana à un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour ajouter du mana", joueur="Le joueur à qui ajouter du mana")
    async def addmana(self, interaction: discord.Interaction, expression: str, joueur: discord.Member = None):
        target = joueur or interaction.user
        player_id = str(target.id)
        player_data = await self._load_player_or_none(player_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        soins, _ = parse_dice_expression(expression)
        player_data["mana_actu"] = min(player_data["mana_actu"] + soins, player_data["mana_max"])
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{target.mention} a récupéré {soins} de mana. Mana actuels: {player_data['mana_actu']}"
        )

    @app_commands.command(name="armure", description="Effectue un jet d'armure pour réduire les dégâts")
    async def armure(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        armure = player_data["attributes"].get("armure", 0)
        bonus_armures = sum(item["bonus_value"] for item in player_data["inventory"]["armures"])
        bonus_bouclier = sum(
            item["bonus_value"]
            for item in player_data["inventory"]["autres_objets"]
            if item["bonus_type"] == "bouclier"
        )
        roll = roll_d100()
        total = roll - armure - bonus_armures - bonus_bouclier

        message = f"Armure de {player_data['name']}: 1d100 - {armure} - {bonus_armures} - {bonus_bouclier} = {total}"
        if total <= 0:
            message += "\nSuccès! Vous prendrez moitié moins de dégâts."
        else:
            message += "\nÉchec! Vous prendrez les dégâts complets."
        await interaction.response.send_message(message)


async def setup(bot):
    await bot.add_cog(CombatCommands(bot))
