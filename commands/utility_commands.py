import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from commands.familier_logic import find_familier
from commands.utility_data import (
    COMMANDS_INFO,
    DEFAULT_ENCOUNTER_POOLS,
    ENCOUNTER_BIOMES,
    ENCOUNTER_POOLS_BY_BIOME,
    FOUILLE_BIOMES,
    FOUILLE_TABLES,
    LOOT_ARGENT_TABLE,
    LOOT_LEVELS,
    LOOT_OBJET_TABLE,
    LOOT_TABLES,
)
from database import load_player
from utils import parse_dice_expression, roll_d100, roll_d20, roll_d12, roll_dice


class UtilityCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def _load_player_or_none(user_id: str):
        return await asyncio.to_thread(load_player, user_id)

    async def _get_familier_choices(self, user_id: str, current: str):
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return []
        return [
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ]

    async def _resolve_init_entity(self, user_id: str, familier_name: str | None):
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return None, None, "Joueur non trouvé."
        if not familier_name:
            return player_data["name"], player_data, None

        familier_data = find_familier(player_data, familier_name)
        if not familier_data:
            return None, None, "Familier non trouvé."
        return familier_data["nom"], familier_data, None

    @staticmethod
    def _pick_table_result(table: dict[str, range], roll_value: int):
        return next((key for key, value in table.items() if roll_value in value), None)

    @staticmethod
    def _get_encounter_pools(biome: str):
        return ENCOUNTER_POOLS_BY_BIOME.get(biome, DEFAULT_ENCOUNTER_POOLS)

    @staticmethod
    def _get_fouille_table(biome: str):
        return FOUILLE_TABLES.get(biome)

    @staticmethod
    def _generate_loot_result(niveau: str):
        table = LOOT_TABLES.get(niveau)
        if not table:
            return "Niveau de loot invalide."

        roll = roll_d100()
        loot_type = next((key for key, value in table.items() if roll in value), "rien")
        if "somme" in loot_type:
            min_val, max_val, unit = LOOT_ARGENT_TABLE[loot_type]
            amount = roll_dice(1, max_val - min_val + 1) + min_val - 1
            return f"Loot {niveau}: {loot_type.capitalize()} - {amount}{unit}"
        if "objet" in loot_type:
            objet_roll = roll_d12()
            objet = next((key for key, value in LOOT_OBJET_TABLE.items() if objet_roll in value), "rien")
            return f"Loot {niveau}: {loot_type.capitalize()} - {objet.capitalize()}"
        return f"Loot {niveau}: {loot_type.capitalize()}"

    @staticmethod
    def _build_help_message(commands_info: dict[str, dict[str, str]]) -> str:
        help_message = "**Liste des commandes :**\n"
        for cmd, info in commands_info.items():
            help_message += f"**{cmd}** - {info['description']}\nUsage: {info['usage']}\n\n"
        return help_message

    @app_commands.command(name="de", description="Lance un dé avec l'expression spécifiée.")
    async def de(self, interaction: discord.Interaction, expression: str):
        try:
            total, details = parse_dice_expression(expression)
            await interaction.response.send_message(f"Résultat de {expression}: {total} ({' + '.join(details)})")
        except ValueError:
            await interaction.response.send_message("Expression invalide. Utilisez le format : 2d6+8d4+1d20+4")

    async def biome_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=biome, value=biome)
            for biome in ENCOUNTER_BIOMES
            if current.lower() in biome.lower()
        ]

    async def biome_autocomplete_2(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=biome, value=biome)
            for biome in FOUILLE_BIOMES
            if current.lower() in biome.lower()
        ]

    @app_commands.command(name="rencontre", description="Génère une rencontre aléatoire.")
    @app_commands.autocomplete(biome=biome_autocomplete)
    async def rencontre(self, interaction: discord.Interaction, biome: str = "plaine"):
        encounter_table = {
            "boss": range(1, 3),
            "monstre": range(3, 16),
            "animaux": range(16, 24),
            "bandits": range(24, 34),
            "rien": range(34, 61),
            "bourse": range(61, 71),
            "objet": range(71, 76),
            "marchand": range(76, 86),
            "PNJ": range(86, 96),
            "event": range(96, 101),
        }
        animals, monsters, bosses = self._get_encounter_pools(biome)
        roll = roll_d100()
        encounter_type = self._pick_table_result(encounter_table, roll)

        if encounter_type == "boss":
            encounter = random.choice(bosses)
            await interaction.response.send_message(f"Rencontre avec un BOSS : {encounter}")
        elif encounter_type == "monstre":
            encounter = random.choice(monsters)
            await interaction.response.send_message(f"Rencontre avec un MONSTRE : {encounter}")
        elif encounter_type == "animaux":
            encounter = random.choice(animals)
            await interaction.response.send_message(f"Rencontre avec un ANIMAL SAUVAGE : {encounter}")
        elif encounter_type == "bandits":
            await interaction.response.send_message("Rencontre avec des BANDITS.")
        elif encounter_type == "rien":
            await interaction.response.send_message("Aucune rencontre.")
        elif encounter_type == "bourse":
            await interaction.response.send_message("Vous trouvez une bourse.")
        elif encounter_type == "objet":
            await interaction.response.send_message("Vous trouvez un objet.")
        elif encounter_type == "marchand":
            await interaction.response.send_message("Vous rencontrez un marchand.")
        elif encounter_type == "PNJ":
            await interaction.response.send_message("Vous rencontrez un PNJ.")
        elif encounter_type == "event":
            await interaction.response.send_message("Un événement se produit.")
        else:
            await interaction.response.send_message("Erreur de rencontre.")

    @app_commands.command(name="fouille", description="Génère une fouille aléatoire.")
    @app_commands.autocomplete(biome=biome_autocomplete_2)
    async def fouille(self, interaction: discord.Interaction, biome: str = "plaine"):
        objet_table = self._get_fouille_table(biome)
        if not objet_table:
            await interaction.response.send_message("biome inconnu")
            return

        roll = roll_d100()
        objet = self._pick_table_result(objet_table, roll)
        await interaction.response.send_message(f"Objet: {objet}")

    @app_commands.command(name="blessure", description="Génère une blessure aléatoire.")
    async def blessure(self, interaction: discord.Interaction):
        blessure_table = {
            "torse": range(1, 25),
            "visage": range(25, 49),
            "bras": range(49, 73),
            "jambe": range(73, 97),
            "borgne": range(97, 101),
        }

        roll = roll_d100()
        bless = None

        for key, value in blessure_table.items():
            if roll in value:
                bless = key
                break

        if bless == "torse":
            await interaction.response.send_message("Blessure au torse: desavantage aux jets concernant la FOR et l'AGI")
        elif bless == "visage":
            await interaction.response.send_message("Blessure au visage visage: desavantage aux jets concernant le CHA et l'INT")
        elif bless == "bras":
            await interaction.response.send_message("Blessure au bras: vous ne pouvez plus entreprendre d'action necessitant l'usage de vos deux bras")
        elif bless == "jambe":
            await interaction.response.send_message("Blessure à la jambe: votre mobilité est réduite de 50%")
        elif bless == "borgne":
            await interaction.response.send_message("Borgne: Désavantage à tous vos jets ciblant quelqu'un ou quelque chose, ainsi qu'à vos jets d'observation et d'esquive")
        else:
            await interaction.response.send_message("Erreur de blessure.")

    async def familier_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        return await self._get_familier_choices(user_id, current)

    @app_commands.command(name="init", description="Effectue un jet d'initiative.")
    @app_commands.describe(familier="Nom du familier à utiliser (optionnel)")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def init(self, interaction: discord.Interaction, familier: str = None):
        user_id = str(interaction.user.id)
        entity_name, entity_data, error = await self._resolve_init_entity(user_id, familier)
        if error:
            await interaction.response.send_message(error)
            return

        agi = entity_data["attributes"].get("agi", 0)
        initiative = roll_d20() + agi
        await interaction.response.send_message(f"Initiative de {entity_name}: 1d20 + {agi} = {initiative}")

    def get_loot_choices(self):
        return LOOT_LEVELS

    async def loot_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_loot_choices() if current.lower() in choice.lower()]
        return choices

    @app_commands.command(name="loot", description="Génère un loot en fonction du niveau spécifié")
    @app_commands.autocomplete(niveau=loot_autocomplete)
    async def loot(self, interaction: discord.Interaction, niveau: str):
        resultat = self._generate_loot_result(niveau)
        await interaction.response.send_message(resultat)

    async def aide_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=cmd, value=cmd) for cmd in self.get_command_choices() if current.lower() in cmd.lower()]
        return choices

    def get_command_choices(self):
        return list(self.get_commands_info().keys())

    def get_commands_info(self):
        return COMMANDS_INFO

    @app_commands.command(name="aide", description="Affiche l'aide pour une commande spécifique")
    @app_commands.autocomplete(command_name=aide_autocomplete)
    async def aide(self, interaction: discord.Interaction, command_name: str = None):
        commands_info = self.get_commands_info()

        if command_name:
            command_name = command_name.lower()
            if command_name in commands_info:
                command_info = commands_info[command_name]
                await interaction.response.send_message(f"**{command_name}**\nDescription: {command_info['description']}\nUsage: {command_info['usage']}")
            else:
                await interaction.response.send_message(f"La commande '{command_name}' n'existe pas.")
        else:
            help_message = self._build_help_message(commands_info)

            if len(help_message) > 2000:
                chunks = [help_message[i:i + 2000] for i in range(0, len(help_message), 2000)]
                await interaction.response.send_message(chunks[0])
                for chunk in chunks[1:]:
                    await interaction.followup.send(chunk)
            else:
                await interaction.response.send_message(help_message)


async def setup(bot):
    await bot.add_cog(UtilityCommands(bot))
