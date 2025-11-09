import discord
from discord.ext import commands
import asyncio
from config import TOKEN, PREFIX, INTENTS, GUILD_ID

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
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    
    # Synchroniser globalement
    await bot.tree.sync()
    
    # Synchroniser pour une guilde spécifique
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)

@bot.command()
async def sync(ctx: commands.Context):
    guild = discord.Object(id=GUILD_ID)  # Utilisez l'ID de votre guilde
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    await ctx.send(content="Les commandes ont été synchronisées avec succès.")

async def main():
    await load_extensions()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
