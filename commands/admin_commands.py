import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from commands.embed_utils import error_embed, success_embed, warning_embed
from database import load_all_players, update_player, update_existing_players, add_inventory_column, load_player
from config import ADMIN_IDS


class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="repos_long", description="Effectue un repos long pour un joueur et ses familiers, ou pour tous les joueurs et leurs familiers.")
    async def repos_long(self, interaction: discord.Interaction, joueur: discord.Member = None):
        if str(interaction.user.id) not in ADMIN_IDS:
            await interaction.response.send_message(
                embed=warning_embed("Vous n'êtes pas autorisé à utiliser cette commande.", title="Administration"),
                ephemeral=True,
            )
            return

        if joueur is not None:
            # Repos long pour un joueur spécifique et ses familiers
            player_id = str(joueur.id)
            player_data = await asyncio.to_thread(load_player, player_id)

            if player_data:
                # Réinitialiser PV et mana du joueur
                player_data['pv_actu'] = player_data['pv_max']
                player_data['mana_actu'] = player_data['mana_max']

                # Réinitialiser PV et mana des familiers
                familiers = player_data.get('familiers', [])
                for familier in familiers:
                    familier['attributes']['pv_actu'] = familier['attributes']['pv_max']
                    familier['attributes']['mana_actu'] = familier['attributes']['mana_max']

                # Sauvegarder les modifications
                await asyncio.to_thread(update_player, player_id, player_data)
                await interaction.response.send_message(
                    embed=success_embed(
                        f"Repos long effectué pour {joueur.mention} et ses familiers.",
                        title="Administration",
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=error_embed(f"Le joueur {joueur.mention} n'a pas été trouvé.", title="Administration"),
                    ephemeral=True,
                )
        else:
            # Repos long pour tous les joueurs et leurs familiers
            players = await asyncio.to_thread(load_all_players)
            for player_id, player_data in players.items():
                # Réinitialiser PV et mana du joueur
                player_data['pv_actu'] = player_data['pv_max']
                player_data['mana_actu'] = player_data['mana_max']

                # Réinitialiser PV et mana des familiers
                for familier in player_data.get('familiers', []):
                    familier['attributes']['pv_actu'] = familier['attributes']['pv_max']
                    familier['attributes']['mana_actu'] = familier['attributes']['mana_max']

                # Sauvegarder les modifications
                await asyncio.to_thread(update_player, player_id, player_data)

            await interaction.response.send_message(
                embed=success_embed(
                    "Repos long effectué. Tous les joueurs et leurs familiers ont récupéré leurs PV et leur mana.",
                    title="Administration",
                ),
                ephemeral=True,
            )

    @app_commands.command(name="update_db", description="Met à jour la base de données.")
    async def update_db(self, interaction: discord.Interaction):
        if str(interaction.user.id) not in ADMIN_IDS:
            await interaction.response.send_message(
                embed=warning_embed("Vous n'êtes pas autorisé à utiliser cette commande.", title="Administration"),
                ephemeral=True,
            )
            return

        await asyncio.to_thread(update_existing_players)
        await asyncio.to_thread(add_inventory_column)
        await interaction.response.send_message(
            embed=success_embed("Base de données mise à jour.", title="Administration"),
            ephemeral=True,
        )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
