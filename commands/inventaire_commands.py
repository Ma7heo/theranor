import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from database import DatabaseError, load_player, update_player, update_two_players_atomic
from config import ADMIN_IDS

class InventoryCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def ajouter_argents(self, inventaire, pc=0, pa=0, po=0):
        total_pc = pc + pa * 100 + po * 10000
        total_pc += inventaire["argent"]["pc"] + inventaire["argent"]["pa"] * 100 + inventaire["argent"]["po"] * 10000
        inventaire["argent"]["po"] = total_pc // 10000
        total_pc %= 10000
        inventaire["argent"]["pa"] = total_pc // 100
        inventaire["argent"]["pc"] = total_pc % 100

    def retirer_argents(self, inventaire, pc=0, pa=0, po=0):
        total_pc = pc + pa * 100 + po * 10000
        total_inventaire_pc = inventaire["argent"]["pc"] + inventaire["argent"]["pa"] * 100 + inventaire["argent"]["po"] * 10000
        if total_inventaire_pc < total_pc:
            return False
        total_inventaire_pc -= total_pc
        inventaire["argent"]["po"] = total_inventaire_pc // 10000
        total_inventaire_pc %= 10000
        inventaire["argent"]["pa"] = total_inventaire_pc // 100
        inventaire["argent"]["pc"] = total_inventaire_pc % 100
        return True

    def get_coin_types(self):
        return ["pc", "pa", "po"]

    def get_inventory_categories(self):
        return ["armures", "armes", "autres_objets"]

    async def coin_type_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_coin_types() if current.lower() in choice.lower()]
        return choices

    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_inventory_categories() if current.lower() in choice.lower()]
        return choices

    async def item_name_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = await asyncio.to_thread(load_player, user_id)
        if not player_data:
            return []
        items = []
        for category in self.get_inventory_categories():
            items.extend([item["nom"] for item in player_data["inventory"][category]])
        return [app_commands.Choice(name=item, value=item) for item in items if current.lower() in item.lower()]

    @app_commands.command(name="donner_argent", description="Donne de l'argent à un autre joueur.")
    @app_commands.autocomplete(type_piece=coin_type_autocomplete)
    async def donner_argent(self, interaction: discord.Interaction, destinataire: discord.Member, montant: int, type_piece: str):
        user_id = str(interaction.user.id)
        if montant <= 0:
            await interaction.response.send_message("Le montant doit être strictement positif.")
            return

        donor = await asyncio.to_thread(load_player, user_id)
        recipient_id = str(destinataire.id)
        recipient = await asyncio.to_thread(load_player, recipient_id)

        if not donor or not recipient:
            await interaction.response.send_message("L'un des joueurs n'existe pas.")
            return

        if type_piece not in ["pc", "pa", "po"]:
            await interaction.response.send_message("Type de pièce invalide. Utilisez 'pc', 'pa' ou 'po'.")
            return

        pc = montant if type_piece == "pc" else 0
        pa = montant if type_piece == "pa" else 0
        po = montant if type_piece == "po" else 0

        if not self.retirer_argents(donor["inventory"], pc, pa, po):
            await interaction.response.send_message("Fonds insuffisants.")
            return

        self.ajouter_argents(recipient["inventory"], pc, pa, po)
        try:
            await asyncio.to_thread(update_two_players_atomic, user_id, donor, recipient_id, recipient)
        except DatabaseError:
            await interaction.response.send_message("Erreur lors du transfert d'argent.")
            return

        await interaction.response.send_message(f"{interaction.user.mention} a donné {montant} {type_piece} à {destinataire.mention}.")

    @app_commands.command(name="retirer_argent", description="Retire de l'argent d'un joueur.")
    @app_commands.autocomplete(type_piece=coin_type_autocomplete)
    async def retirer_argent(self, interaction: discord.Interaction, montant: int = 0, type_piece: str = "pc", joueur: discord.Member = None):
        if montant <= 0:
            await interaction.response.send_message("Le montant doit être strictement positif.")
            return

        if joueur is None:
            joueur = interaction.user
        else:
            if str(interaction.user.id) not in ADMIN_IDS:
                await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.")
                return

        player_id = str(joueur.id)
        player_data = await asyncio.to_thread(load_player, player_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        if type_piece not in ["pc", "pa", "po"]:
            await interaction.response.send_message("Type de pièce invalide. Utilisez 'pc', 'pa' ou 'po'.")
            return

        pc = montant if type_piece == "pc" else 0
        pa = montant if type_piece == "pa" else 0
        po = montant if type_piece == "po" else 0

        if not self.retirer_argents(player_data["inventory"], pc, pa, po):
            await interaction.response.send_message("Fonds insuffisants.")
            return

        await asyncio.to_thread(update_player, player_id, player_data)

        await interaction.response.send_message(f"Retiré {montant} {type_piece} de l'inventaire de {player_data['name']}.")

    @app_commands.command(name="ajouter_argent", description="Ajoute de l'argent à un joueur.")
    @app_commands.autocomplete(type_piece=coin_type_autocomplete)
    async def ajouter_argent(self, interaction: discord.Interaction, joueur: discord.Member, montant: int, type_piece: str):
        if montant <= 0:
            await interaction.response.send_message("Le montant doit être strictement positif.")
            return

        if str(interaction.user.id) not in ADMIN_IDS:
            await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.")
            return
        player_id = str(joueur.id)
        player_data = await asyncio.to_thread(load_player, player_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        if type_piece not in ["pc", "pa", "po"]:
            await interaction.response.send_message("Type de pièce invalide. Utilisez 'pc', 'pa' ou 'po'.")
            return

        pc = montant if type_piece == "pc" else 0
        pa = montant if type_piece == "pa" else 0
        po = montant if type_piece == "po" else 0

        self.ajouter_argents(player_data["inventory"], pc, pa, po)

        await asyncio.to_thread(update_player, player_id, player_data)

        await interaction.response.send_message(f"Ajouté {montant} {type_piece} à l'inventaire de {player_data['name']}.")

    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        skill_choices = await asyncio.to_thread(get_skill_choices, user_id)
        choices = [app_commands.Choice(name=choice, value=choice) for choice in skill_choices if current.lower() in choice.lower()]
        return choices
    
    @app_commands.command(name="ajouter_objet", description="Ajoute un objet à l'inventaire d'un joueur.")
    @app_commands.autocomplete(categorie=category_autocomplete, bonus_type=skill_autocomplete)
    async def ajouter_objet(self, interaction: discord.Interaction, destinataire: discord.Member, categorie: str, nom: str, description: str="", bonus_type: str = "", bonus_value: int = 0, degats: str = "0d0"):
        if str(interaction.user.id) not in ADMIN_IDS:
            await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.")
            return

        recipient_id = str(destinataire.id)
        recipient = await asyncio.to_thread(load_player, recipient_id)

        if not recipient:
            await interaction.response.send_message("Le destinataire n'existe pas.")
            return

        if categorie not in ["armures", "armes", "autres_objets"]:
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        objet = {
            "nom": nom,
            "description": description,
            "bonus_type": bonus_type,
            "bonus_value": bonus_value,
            "degats": degats
        }

        recipient["inventory"][categorie].append(objet)
        await asyncio.to_thread(update_player, recipient_id, recipient)

        await interaction.response.send_message(f"Vous avez ajouté {nom} à l'inventaire de {destinataire.mention}.")

    @app_commands.command(name="donner_objet", description="Donne un objet à un autre joueur.")
    @app_commands.autocomplete(categorie=category_autocomplete, nom=item_name_autocomplete)
    async def donner_objet(self, interaction: discord.Interaction, destinataire: discord.Member, categorie: str, nom: str):
        user_id = str(interaction.user.id)
        recipient_id = str(destinataire.id)

        player = await asyncio.to_thread(load_player, user_id)
        recipient = await asyncio.to_thread(load_player, recipient_id)

        if not player or not recipient:
            await interaction.response.send_message("L'un des joueurs n'existe pas.")
            return

        if categorie not in self.get_inventory_categories():
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        objet_trouve = False
        for objet in player["inventory"][categorie]:
            if objet["nom"] == nom:
                player["inventory"][categorie].remove(objet)
                recipient["inventory"][categorie].append(objet)
                try:
                    await asyncio.to_thread(update_two_players_atomic, user_id, player, recipient_id, recipient)
                except DatabaseError:
                    await interaction.response.send_message("Erreur lors du transfert d'objet.")
                    return
                objet_trouve = True
                break

        if not objet_trouve:
            await interaction.response.send_message(f"Objet {nom} non trouvé dans votre inventaire.")
            return

        await interaction.response.send_message(f"Vous avez donné {nom} à {destinataire.mention}.")

    @app_commands.command(name="retirer_objet", description="Retire un objet de l'inventaire d'un joueur.")
    @app_commands.autocomplete(categorie=category_autocomplete, nom=item_name_autocomplete)
    async def retirer_objet(self, interaction: discord.Interaction, nom: str, categorie: str = "autres_objets", joueur: discord.Member = None):
        if joueur is None:
            joueur = interaction.user
        else:
            if str(interaction.user.id) not in ADMIN_IDS:
                await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.")
                return

        player_id = str(joueur.id)
        player_data = await asyncio.to_thread(load_player, player_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        if categorie not in self.get_inventory_categories():
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        objet_trouve = False
        for objet in player_data["inventory"][categorie]:
            if objet["nom"] == nom:
                player_data["inventory"][categorie].remove(objet)
                await asyncio.to_thread(update_player, player_id, player_data)
                objet_trouve = True
                break

        if not objet_trouve:
            await interaction.response.send_message(f"Objet {nom} non trouvé dans l'inventaire de {joueur.mention}.")
            return

        await interaction.response.send_message(f"Objet {nom} retiré de l'inventaire de {joueur.mention}.")

        
    @app_commands.command(name="modifier_objet", description="Modifie la description d'un objet.")
    @app_commands.autocomplete(nom_objet=item_name_autocomplete)
    async def modifier_objet(self, interaction: discord.Interaction, nom_objet: str, nouvelle_description: str):
        user_id = str(interaction.user.id)
        player_data = await asyncio.to_thread(load_player, user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        for category in ['armures', 'armes', 'autres_objets']:
            for item in player_data['inventory'].get(category, []):
                if item['nom'] == nom_objet:
                    item['description'] = nouvelle_description
                    await asyncio.to_thread(update_player, user_id, player_data)
                    await interaction.response.send_message(f"La description de {nom_objet} a été mise à jour.")
                    return

        await interaction.response.send_message(f"L'objet {nom_objet} n'a pas été trouvé dans votre inventaire.")

def get_skill_choices(user_id):
        player_data = load_player(user_id)
        if not player_data:
            return []
        attributes = list(player_data['attributes'].keys())
        skills = []
        for cat in player_data['skills']:
            skills.extend(player_data['skills'][cat].keys())
        return attributes + skills

async def setup(bot):
    await bot.add_cog(InventoryCommands(bot))
