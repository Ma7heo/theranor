import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from commands.familier_logic import find_familier
from database import DatabaseError, load_player, update_player, update_two_players_atomic
from config import ADMIN_IDS

class InventoryCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _entity_name(entity_data, is_familier: bool):
        return entity_data["nom"] if is_familier else entity_data["name"]

    def _resolve_inventory_entity(self, player_data, familier_name: str | None):
        if not familier_name:
            return player_data, False
        familier_data = find_familier(player_data, familier_name)
        if not familier_data:
            return None, None
        return familier_data, True

    async def source_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = await asyncio.to_thread(load_player, user_id)
        if not player_data:
            return []
        return [
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ]

    async def joueur_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        target = getattr(interaction.namespace, "joueur", None)
        target_user_id = str(target.id) if target else str(interaction.user.id)
        player_data = await asyncio.to_thread(load_player, target_user_id)
        if not player_data:
            return []
        return [
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ]

    async def destinataire_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        target = getattr(interaction.namespace, "destinataire", None)
        if not target:
            return []
        player_data = await asyncio.to_thread(load_player, str(target.id))
        if not player_data:
            return []
        return [
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ]

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
        target = getattr(interaction.namespace, "joueur", None)
        user_id = str(target.id) if target else str(interaction.user.id)
        player_data = await asyncio.to_thread(load_player, user_id)
        if not player_data:
            return []
        familier_name = getattr(interaction.namespace, "familier", None) or getattr(interaction.namespace, "familier_source", None)
        entity_data, _ = self._resolve_inventory_entity(player_data, familier_name)
        if familier_name and not entity_data:
            return []
        if not entity_data:
            entity_data = player_data
        items = []
        for category in self.get_inventory_categories():
            items.extend([item["nom"] for item in entity_data["inventory"][category]])
        return [app_commands.Choice(name=item, value=item) for item in items if current.lower() in item.lower()]

    @app_commands.command(name="donner_argent", description="Donne de l'argent à un autre joueur.")
    @app_commands.describe(
        familier_source="Familier source (optionnel)",
        familier_destinataire="Familier destinataire (optionnel)",
    )
    @app_commands.autocomplete(
        type_piece=coin_type_autocomplete,
        familier_source=source_familier_autocomplete,
        familier_destinataire=destinataire_familier_autocomplete,
    )
    async def donner_argent(
        self,
        interaction: discord.Interaction,
        destinataire: discord.Member,
        montant: int,
        type_piece: str,
        familier_source: str = None,
        familier_destinataire: str = None,
    ):
        user_id = str(interaction.user.id)
        if montant <= 0:
            await interaction.response.send_message("Le montant doit être strictement positif.")
            return

        recipient_id = str(destinataire.id)
        if user_id == recipient_id:
            donor = await asyncio.to_thread(load_player, user_id)
            recipient = donor
        else:
            donor = await asyncio.to_thread(load_player, user_id)
            recipient = await asyncio.to_thread(load_player, recipient_id)

        if not donor or not recipient:
            await interaction.response.send_message("L'un des joueurs n'existe pas.")
            return

        donor_entity, donor_is_familier = self._resolve_inventory_entity(donor, familier_source)
        if familier_source and not donor_entity:
            await interaction.response.send_message("Familier source non trouvé.")
            return
        if not donor_entity:
            donor_entity = donor
            donor_is_familier = False

        recipient_entity, recipient_is_familier = self._resolve_inventory_entity(recipient, familier_destinataire)
        if familier_destinataire and not recipient_entity:
            await interaction.response.send_message("Familier destinataire non trouvé.")
            return
        if not recipient_entity:
            recipient_entity = recipient
            recipient_is_familier = False

        if type_piece not in ["pc", "pa", "po"]:
            await interaction.response.send_message("Type de pièce invalide. Utilisez 'pc', 'pa' ou 'po'.")
            return

        pc = montant if type_piece == "pc" else 0
        pa = montant if type_piece == "pa" else 0
        po = montant if type_piece == "po" else 0

        if not self.retirer_argents(donor_entity["inventory"], pc, pa, po):
            await interaction.response.send_message("Fonds insuffisants.")
            return

        self.ajouter_argents(recipient_entity["inventory"], pc, pa, po)
        if user_id == recipient_id:
            await asyncio.to_thread(update_player, user_id, donor)
        else:
            try:
                await asyncio.to_thread(update_two_players_atomic, user_id, donor, recipient_id, recipient)
            except DatabaseError:
                await interaction.response.send_message("Erreur lors du transfert d'argent.")
                return

        await interaction.response.send_message(
            f"{self._entity_name(donor_entity, donor_is_familier)} a donné {montant} {type_piece} à "
            f"{self._entity_name(recipient_entity, recipient_is_familier)} ({destinataire.mention})."
        )

    @app_commands.command(name="retirer_argent", description="Retire de l'argent d'un joueur.")
    @app_commands.autocomplete(type_piece=coin_type_autocomplete, familier=joueur_familier_autocomplete)
    async def retirer_argent(
        self,
        interaction: discord.Interaction,
        montant: int = 0,
        type_piece: str = "pc",
        joueur: discord.Member = None,
        familier: str = None,
    ):
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

        entity_data, is_familier = self._resolve_inventory_entity(player_data, familier)
        if familier and not entity_data:
            await interaction.response.send_message("Familier non trouvé.")
            return
        if not entity_data:
            entity_data = player_data
            is_familier = False

        pc = montant if type_piece == "pc" else 0
        pa = montant if type_piece == "pa" else 0
        po = montant if type_piece == "po" else 0

        if not self.retirer_argents(entity_data["inventory"], pc, pa, po):
            await interaction.response.send_message("Fonds insuffisants.")
            return

        await asyncio.to_thread(update_player, player_id, player_data)

        await interaction.response.send_message(
            f"Retiré {montant} {type_piece} de l'inventaire de {self._entity_name(entity_data, is_familier)}."
        )

    @app_commands.command(name="ajouter_argent", description="Ajoute de l'argent à un joueur.")
    @app_commands.autocomplete(type_piece=coin_type_autocomplete, familier=joueur_familier_autocomplete)
    async def ajouter_argent(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        montant: int,
        type_piece: str,
        familier: str = None,
    ):
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

        entity_data, is_familier = self._resolve_inventory_entity(player_data, familier)
        if familier and not entity_data:
            await interaction.response.send_message("Familier non trouvé.")
            return
        if not entity_data:
            entity_data = player_data
            is_familier = False

        pc = montant if type_piece == "pc" else 0
        pa = montant if type_piece == "pa" else 0
        po = montant if type_piece == "po" else 0

        self.ajouter_argents(entity_data["inventory"], pc, pa, po)

        await asyncio.to_thread(update_player, player_id, player_data)

        await interaction.response.send_message(
            f"Ajouté {montant} {type_piece} à l'inventaire de {self._entity_name(entity_data, is_familier)}."
        )

    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        skill_choices = await asyncio.to_thread(get_skill_choices, user_id)
        choices = [app_commands.Choice(name=choice, value=choice) for choice in skill_choices if current.lower() in choice.lower()]
        return choices
    
    @app_commands.command(name="ajouter_objet", description="Ajoute un objet à l'inventaire d'un joueur.")
    @app_commands.autocomplete(categorie=category_autocomplete, bonus_type=skill_autocomplete, familier=destinataire_familier_autocomplete)
    async def ajouter_objet(
        self,
        interaction: discord.Interaction,
        destinataire: discord.Member,
        categorie: str,
        nom: str,
        description: str = "",
        bonus_type: str = "",
        bonus_value: int = 0,
        degats: str = "0d0",
        familier: str = None,
    ):
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

        recipient_entity, recipient_is_familier = self._resolve_inventory_entity(recipient, familier)
        if familier and not recipient_entity:
            await interaction.response.send_message("Familier non trouvé.")
            return
        if not recipient_entity:
            recipient_entity = recipient
            recipient_is_familier = False

        objet = {
            "nom": nom,
            "description": description,
            "bonus_type": bonus_type,
            "bonus_value": bonus_value,
            "degats": degats
        }

        recipient_entity["inventory"][categorie].append(objet)
        await asyncio.to_thread(update_player, recipient_id, recipient)

        await interaction.response.send_message(
            f"Vous avez ajouté {nom} à l'inventaire de {self._entity_name(recipient_entity, recipient_is_familier)} ({destinataire.mention})."
        )

    @app_commands.command(name="donner_objet", description="Donne un objet à un autre joueur.")
    @app_commands.autocomplete(
        categorie=category_autocomplete,
        nom=item_name_autocomplete,
        familier_source=source_familier_autocomplete,
        familier_destinataire=destinataire_familier_autocomplete,
    )
    async def donner_objet(
        self,
        interaction: discord.Interaction,
        destinataire: discord.Member,
        categorie: str,
        nom: str,
        familier_source: str = None,
        familier_destinataire: str = None,
    ):
        user_id = str(interaction.user.id)
        recipient_id = str(destinataire.id)

        if user_id == recipient_id:
            player = await asyncio.to_thread(load_player, user_id)
            recipient = player
        else:
            player = await asyncio.to_thread(load_player, user_id)
            recipient = await asyncio.to_thread(load_player, recipient_id)

        if not player or not recipient:
            await interaction.response.send_message("L'un des joueurs n'existe pas.")
            return

        if categorie not in self.get_inventory_categories():
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        source_entity, source_is_familier = self._resolve_inventory_entity(player, familier_source)
        if familier_source and not source_entity:
            await interaction.response.send_message("Familier source non trouvé.")
            return
        if not source_entity:
            source_entity = player
            source_is_familier = False

        target_entity, target_is_familier = self._resolve_inventory_entity(recipient, familier_destinataire)
        if familier_destinataire and not target_entity:
            await interaction.response.send_message("Familier destinataire non trouvé.")
            return
        if not target_entity:
            target_entity = recipient
            target_is_familier = False

        objet_trouve = False
        for objet in source_entity["inventory"][categorie]:
            if objet["nom"] == nom:
                source_entity["inventory"][categorie].remove(objet)
                target_entity["inventory"][categorie].append(objet)
                if user_id == recipient_id:
                    await asyncio.to_thread(update_player, user_id, player)
                else:
                    try:
                        await asyncio.to_thread(update_two_players_atomic, user_id, player, recipient_id, recipient)
                    except DatabaseError:
                        await interaction.response.send_message("Erreur lors du transfert d'objet.")
                        return
                objet_trouve = True
                break

        if not objet_trouve:
            await interaction.response.send_message(f"Objet {nom} non trouvé dans l'inventaire source.")
            return

        await interaction.response.send_message(
            f"{self._entity_name(source_entity, source_is_familier)} a donné {nom} à "
            f"{self._entity_name(target_entity, target_is_familier)} ({destinataire.mention})."
        )

    @app_commands.command(name="retirer_objet", description="Retire un objet de l'inventaire d'un joueur.")
    @app_commands.autocomplete(categorie=category_autocomplete, nom=item_name_autocomplete, familier=joueur_familier_autocomplete)
    async def retirer_objet(
        self,
        interaction: discord.Interaction,
        nom: str,
        categorie: str = "autres_objets",
        joueur: discord.Member = None,
        familier: str = None,
    ):
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

        entity_data, is_familier = self._resolve_inventory_entity(player_data, familier)
        if familier and not entity_data:
            await interaction.response.send_message("Familier non trouvé.")
            return
        if not entity_data:
            entity_data = player_data
            is_familier = False

        objet_trouve = False
        for objet in entity_data["inventory"][categorie]:
            if objet["nom"] == nom:
                entity_data["inventory"][categorie].remove(objet)
                await asyncio.to_thread(update_player, player_id, player_data)
                objet_trouve = True
                break

        if not objet_trouve:
            await interaction.response.send_message(
                f"Objet {nom} non trouvé dans l'inventaire de {self._entity_name(entity_data, is_familier)}."
            )
            return

        await interaction.response.send_message(
            f"Objet {nom} retiré de l'inventaire de {self._entity_name(entity_data, is_familier)}."
        )

        
    @app_commands.command(name="modifier_objet", description="Modifie la description d'un objet.")
    @app_commands.autocomplete(nom_objet=item_name_autocomplete, familier=source_familier_autocomplete)
    async def modifier_objet(
        self,
        interaction: discord.Interaction,
        nom_objet: str,
        nouvelle_description: str,
        familier: str = None,
    ):
        user_id = str(interaction.user.id)
        player_data = await asyncio.to_thread(load_player, user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        entity_data, is_familier = self._resolve_inventory_entity(player_data, familier)
        if familier and not entity_data:
            await interaction.response.send_message("Familier non trouvé.")
            return
        if not entity_data:
            entity_data = player_data
            is_familier = False

        for category in ['armures', 'armes', 'autres_objets']:
            for item in entity_data['inventory'].get(category, []):
                if item['nom'] == nom_objet:
                    item['description'] = nouvelle_description
                    await asyncio.to_thread(update_player, user_id, player_data)
                    await interaction.response.send_message(
                        f"La description de {nom_objet} a été mise à jour pour {self._entity_name(entity_data, is_familier)}."
                    )
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
