import discord

# Copiez ce fichier en config.py et remplissez les valeurs sensibles localement.
TOKEN = "YOUR_DISCORD_TOKEN"
PREFIX = "!"

INTENTS = discord.Intents.default()
INTENTS.message_content = True

GUILD_ID = 123456789012345678  # Remplacez par l'ID de votre serveur
ADMIN_IDS = ["123456789012345678"]  # IDs des admins autorisés
DATABASE_PATH = "players.db"
