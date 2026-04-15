import discord
from discord.ext import commands
import asyncio
import logging
from config import TOKEN, PREFIX, INTENTS, GUILD_ID, ADMIN_IDS
from commands.embed_utils import success_embed, warning_embed
from database import DatabaseError, bootstrap_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = commands.Bot(command_prefix=PREFIX, intents=INTENTS)

# Charger les extensions
async def load_extensions():
    await bot.load_extension('commands.player_commands')
    await bot.load_extension('commands.familier_commands')
    await bot.load_extension('commands.combat_commands')
    await bot.load_extension('commands.admin_commands')
    await bot.load_extension('commands.utility_commands')
    await bot.load_extension('commands.inventaire_commands')

@bot.event
async def on_ready():
    logger.info(
        "bot.ready",
        extra={
            "bot_user": bot.user.name if bot.user else None,
            "bot_user_id": bot.user.id if bot.user else None,
            "guild_id": GUILD_ID,
        },
    )
    
    # Synchroniser globalement
    await bot.tree.sync()
    
    # Synchroniser pour une guilde spécifique
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)

@bot.command()
async def sync(ctx: commands.Context):
    if str(ctx.author.id) not in ADMIN_IDS:
        await ctx.send(embed=warning_embed("Vous n'êtes pas autorisé à utiliser cette commande.", title="Sync commandes"))
        return
    guild = discord.Object(id=GUILD_ID)  # Utilisez l'ID de votre guilde
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    await ctx.send(embed=success_embed("Les commandes ont été synchronisées avec succès.", title="Sync commandes"))

async def main():
    try:
        bootstrap_database()
    except DatabaseError:
        logger.critical("Échec du bootstrap de la base de données. Arrêt du bot.")
        raise
    await load_extensions()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
