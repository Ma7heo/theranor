import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from commands.embed_utils import error_embed, info_embed, success_embed, warning_embed
from commands.familier_logic import find_familier
from database import DatabaseError, load_player, update_player, update_two_players_atomic
from config import ADMIN_IDS


COIN_TYPES = ("pc", "pa", "po")
INVENTORY_CATEGORIES = ("armures", "armes", "autres_objets")
COIN_TO_PC_FACTOR = {"pc": 1, "pa": 100, "po": 10000}


class InventoryCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def _load_player_or_none(user_id: str):
        return await asyncio.to_thread(load_player, user_id)

    @staticmethod
    def _entity_name(entity_data, is_familier: bool):
        return entity_data["nom"] if is_familier else entity_data["name"]

    async def _send_error(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(embed=error_embed(message, title="Inventaire"))

    async def _send_warning(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(embed=warning_embed(message, title="Inventaire"))

    async def _send_info(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(embed=info_embed(message, title="Inventaire"))

    async def _send_success(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(embed=success_embed(message, title="Inventaire"))

    @staticmethod
    def _is_admin(user_id: str) -> bool:
        return user_id in ADMIN_IDS

    @staticmethod
    def _is_valid_coin_type(coin_type: str) -> bool:
        return coin_type in COIN_TYPES

    @staticmethod
    def _is_valid_inventory_category(category: str) -> bool:
        return category in INVENTORY_CATEGORIES

    @staticmethod
    def _amount_to_coin_breakdown(montant: int, type_piece: str) -> tuple[int, int, int]:
        pc = montant if type_piece == "pc" else 0
        pa = montant if type_piece == "pa" else 0
        po = montant if type_piece == "po" else 0
        return pc, pa, po

    @staticmethod
    def _coin_values_to_pc(pc: int = 0, pa: int = 0, po: int = 0) -> int:
        return (pc * COIN_TO_PC_FACTOR["pc"]) + (pa * COIN_TO_PC_FACTOR["pa"]) + (po * COIN_TO_PC_FACTOR["po"])

    @staticmethod
    def _set_inventory_money_from_pc(inventaire: dict, total_pc: int):
        inventaire["argent"]["po"] = total_pc // COIN_TO_PC_FACTOR["po"]
        total_pc %= COIN_TO_PC_FACTOR["po"]
        inventaire["argent"]["pa"] = total_pc // COIN_TO_PC_FACTOR["pa"]
        inventaire["argent"]["pc"] = total_pc % COIN_TO_PC_FACTOR["pa"]

    @staticmethod
    def _find_item_by_name(items: list[dict], item_name: str):
        return next((item for item in items if item.get("nom") == item_name), None)

    def _resolve_inventory_entity(self, player_data, familier_name: str | None):
        if not familier_name:
            return player_data, False
        if familier_name.lower() == player_data["name"].lower():
            return player_data, False
        familier_data = find_familier(player_data, familier_name)
        if not familier_data:
            return None, None
        return familier_data, True

    @staticmethod
    def _resolve_entity_or_default(entity_data, is_familier, player_data):
        if entity_data:
            return entity_data, is_familier
        return player_data, False

    async def source_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return []
        choices = []
        player_name = player_data.get("name")
        if player_name and current.lower() in player_name.lower():
            choices.append(app_commands.Choice(name=player_name, value=player_name))
        choices.extend([
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ])
        return choices

    async def joueur_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        target = getattr(interaction.namespace, "joueur", None)
        target_user_id = str(target.id) if target else str(interaction.user.id)
        player_data = await self._load_player_or_none(target_user_id)
        if not player_data:
            return []
        choices = []
        player_name = player_data.get("name")
        if player_name and current.lower() in player_name.lower():
            choices.append(app_commands.Choice(name=player_name, value=player_name))
        choices.extend([
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ])
        return choices

    async def destinataire_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        target = getattr(interaction.namespace, "destinataire", None)
        if not target:
            return []
        player_data = await self._load_player_or_none(str(target.id))
        if not player_data:
            return []
        choices = []
        player_name = player_data.get("name")
        if player_name and current.lower() in player_name.lower():
            choices.append(app_commands.Choice(name=player_name, value=player_name))
        choices.extend([
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in player_data.get("familiers", [])
            if current.lower() in familier["nom"].lower()
        ])
        return choices

    def ajouter_argents(self, inventaire, pc=0, pa=0, po=0):
        total_pc = self._coin_values_to_pc(pc, pa, po)
        total_pc += self._coin_values_to_pc(
            inventaire["argent"]["pc"],
            inventaire["argent"]["pa"],
            inventaire["argent"]["po"],
        )
        self._set_inventory_money_from_pc(inventaire, total_pc)

    def retirer_argents(self, inventaire, pc=0, pa=0, po=0):
        total_pc = self._coin_values_to_pc(pc, pa, po)
        total_inventaire_pc = self._coin_values_to_pc(
            inventaire["argent"]["pc"],
            inventaire["argent"]["pa"],
            inventaire["argent"]["po"],
        )
        if total_inventaire_pc < total_pc:
            return False
        total_inventaire_pc -= total_pc
        self._set_inventory_money_from_pc(inventaire, total_inventaire_pc)
        return True

    def get_coin_types(self):
        return list(COIN_TYPES)

    def get_inventory_categories(self):
        return list(INVENTORY_CATEGORIES)

    async def coin_type_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_coin_types() if current.lower() in choice.lower()]
        return choices

    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_inventory_categories() if current.lower() in choice.lower()]
        return choices

    async def item_name_autocomplete(self, interaction: discord.Interaction, current: str):
        target = getattr(interaction.namespace, "joueur", None)
        user_id = str(target.id) if target else str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return []
        familier_name = (
            getattr(interaction.namespace, "entite", None)
            or getattr(interaction.namespace, "entite_source", None)
            or getattr(interaction.namespace, "familier", None)
            or getattr(interaction.namespace, "familier_source", None)
        )
        entity_data, _ = self._resolve_inventory_entity(player_data, familier_name)
        if familier_name and not entity_data:
            return []
        if not entity_data:
            entity_data = player_data
        items = []
        for category in INVENTORY_CATEGORIES:
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
            await self._send_warning(interaction, "Le montant doit être strictement positif.")
            return

        recipient_id = str(destinataire.id)
        if user_id == recipient_id:
            donor = await self._load_player_or_none(user_id)
            recipient = donor
        else:
            donor = await self._load_player_or_none(user_id)
            recipient = await self._load_player_or_none(recipient_id)

        if not donor or not recipient:
            await self._send_error(interaction, "L'un des joueurs n'existe pas.")
            return

        donor_entity, donor_is_familier = self._resolve_inventory_entity(donor, familier_source)
        if familier_source and not donor_entity:
            await self._send_error(interaction, "Familier source non trouvé.")
            return
        donor_entity, donor_is_familier = self._resolve_entity_or_default(donor_entity, donor_is_familier, donor)

        recipient_entity, recipient_is_familier = self._resolve_inventory_entity(recipient, familier_destinataire)
        if familier_destinataire and not recipient_entity:
            await self._send_error(interaction, "Familier destinataire non trouvé.")
            return
        recipient_entity, recipient_is_familier = self._resolve_entity_or_default(
            recipient_entity, recipient_is_familier, recipient
        )

        if not self._is_valid_coin_type(type_piece):
            await self._send_warning(interaction, "Type de pièce invalide. Utilisez 'pc', 'pa' ou 'po'.")
            return

        pc, pa, po = self._amount_to_coin_breakdown(montant, type_piece)

        if not self.retirer_argents(donor_entity["inventory"], pc, pa, po):
            await self._send_warning(interaction, "Fonds insuffisants.")
            return

        self.ajouter_argents(recipient_entity["inventory"], pc, pa, po)
        if user_id == recipient_id:
            await asyncio.to_thread(update_player, user_id, donor)
        else:
            try:
                await asyncio.to_thread(update_two_players_atomic, user_id, donor, recipient_id, recipient)
            except DatabaseError:
                await self._send_error(interaction, "Erreur lors du transfert d'argent.")
                return

        await self._send_success(
            interaction,
            f"{self._entity_name(donor_entity, donor_is_familier)} a donné {montant} {type_piece} à "
            f"{self._entity_name(recipient_entity, recipient_is_familier)} ({destinataire.mention}).",
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
            await self._send_warning(interaction, "Le montant doit être strictement positif.")
            return

        if joueur is None:
            joueur = interaction.user
        else:
            if not self._is_admin(str(interaction.user.id)):
                await self._send_warning(interaction, "Vous n'êtes pas autorisé à utiliser cette commande.")
                return

        player_id = str(joueur.id)
        player_data = await self._load_player_or_none(player_id)

        if not player_data:
            await self._send_error(interaction, "Joueur non trouvé.")
            return

        if not self._is_valid_coin_type(type_piece):
            await self._send_warning(interaction, "Type de pièce invalide. Utilisez 'pc', 'pa' ou 'po'.")
            return

        entity_data, is_familier = self._resolve_inventory_entity(player_data, familier)
        if familier and not entity_data:
            await self._send_error(interaction, "Familier non trouvé.")
            return
        entity_data, is_familier = self._resolve_entity_or_default(entity_data, is_familier, player_data)

        pc, pa, po = self._amount_to_coin_breakdown(montant, type_piece)

        if not self.retirer_argents(entity_data["inventory"], pc, pa, po):
            await self._send_warning(interaction, "Fonds insuffisants.")
            return

        await asyncio.to_thread(update_player, player_id, player_data)

        await self._send_success(
            interaction,
            f"Retiré {montant} {type_piece} de l'inventaire de {self._entity_name(entity_data, is_familier)}.",
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
            await self._send_warning(interaction, "Le montant doit être strictement positif.")
            return

        if not self._is_admin(str(interaction.user.id)):
            await self._send_warning(interaction, "Vous n'êtes pas autorisé à utiliser cette commande.")
            return
        player_id = str(joueur.id)
        player_data = await self._load_player_or_none(player_id)

        if not player_data:
            await self._send_error(interaction, "Joueur non trouvé.")
            return

        if not self._is_valid_coin_type(type_piece):
            await self._send_warning(interaction, "Type de pièce invalide. Utilisez 'pc', 'pa' ou 'po'.")
            return

        entity_data, is_familier = self._resolve_inventory_entity(player_data, familier)
        if familier and not entity_data:
            await self._send_error(interaction, "Familier non trouvé.")
            return
        entity_data, is_familier = self._resolve_entity_or_default(entity_data, is_familier, player_data)

        pc, pa, po = self._amount_to_coin_breakdown(montant, type_piece)

        self.ajouter_argents(entity_data["inventory"], pc, pa, po)

        await asyncio.to_thread(update_player, player_id, player_data)

        await self._send_success(
            interaction,
            f"Ajouté {montant} {type_piece} à l'inventaire de {self._entity_name(entity_data, is_familier)}.",
        )

    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        target = getattr(interaction.namespace, "destinataire", None)
        user_id = str(target.id) if target else str(interaction.user.id)
        entity_selector = getattr(interaction.namespace, "entite", None)
        skill_choices = await self._get_skill_choices(user_id, entity_selector)
        choices = [app_commands.Choice(name=choice, value=choice) for choice in skill_choices if current.lower() in choice.lower()]
        return choices

    async def _get_skill_choices(self, user_id: str, entity_selector: str | None = None):
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return []
        entity_data, _ = self._resolve_inventory_entity(player_data, entity_selector)
        if entity_selector and not entity_data:
            return []
        entity_data = entity_data or player_data
        attributes = list(entity_data["attributes"].keys())
        skills = []
        for category_name in entity_data["skills"]:
            skills.extend(entity_data["skills"][category_name].keys())
        return attributes + skills

    @app_commands.command(name="ajouter_objet", description="Ajoute un objet à l'inventaire d'un joueur.")
    @app_commands.describe(
        destinataire="Joueur qui recevra l'objet",
        entite="Nom du familier ou du personnage du destinataire",
    )
    @app_commands.autocomplete(categorie=category_autocomplete, bonus_type=skill_autocomplete, entite=destinataire_familier_autocomplete)
    async def ajouter_objet(
        self,
        interaction: discord.Interaction,
        destinataire: discord.Member,
        entite: str,
        categorie: str,
        nom: str,
        description: str = "",
        bonus_type: str = "",
        bonus_value: int = 0,
        degats: str = "0d0",
    ):
        if not self._is_admin(str(interaction.user.id)):
            await self._send_warning(interaction, "Vous n'êtes pas autorisé à utiliser cette commande.")
            return

        recipient_id = str(destinataire.id)
        recipient = await self._load_player_or_none(recipient_id)

        if not recipient:
            await self._send_error(interaction, "Le destinataire n'existe pas.")
            return

        if not self._is_valid_inventory_category(categorie):
            await self._send_warning(interaction, "Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        recipient_entity, recipient_is_familier = self._resolve_inventory_entity(recipient, entite)
        if entite and not recipient_entity:
            await self._send_error(interaction, "Entité non trouvée.")
            return
        recipient_entity, recipient_is_familier = self._resolve_entity_or_default(
            recipient_entity, recipient_is_familier, recipient
        )

        objet = {
            "nom": nom,
            "description": description,
            "bonus_type": bonus_type,
            "bonus_value": bonus_value,
            "degats": degats
        }

        recipient_entity["inventory"][categorie].append(objet)
        await asyncio.to_thread(update_player, recipient_id, recipient)

        await self._send_success(
            interaction,
            f"Vous avez ajouté {nom} à l'inventaire de {self._entity_name(recipient_entity, recipient_is_familier)} ({destinataire.mention}).",
        )

    @app_commands.command(name="donner_objet", description="Donne un objet à un autre joueur.")
    @app_commands.describe(
        entite_source="Nom du familier ou du personnage source",
        entite_destinataire="Nom du familier ou du personnage destinataire",
    )
    @app_commands.autocomplete(
        entite_source=source_familier_autocomplete,
        entite_destinataire=destinataire_familier_autocomplete,
        categorie=category_autocomplete,
        nom=item_name_autocomplete,
    )
    async def donner_objet(
        self,
        interaction: discord.Interaction,
        entite_source: str,
        destinataire: discord.Member,
        entite_destinataire: str,
        categorie: str,
        nom: str,
    ):
        user_id = str(interaction.user.id)
        recipient_id = str(destinataire.id)

        if user_id == recipient_id:
            player = await self._load_player_or_none(user_id)
            recipient = player
        else:
            player = await self._load_player_or_none(user_id)
            recipient = await self._load_player_or_none(recipient_id)

        if not player or not recipient:
            await self._send_error(interaction, "L'un des joueurs n'existe pas.")
            return

        if not self._is_valid_inventory_category(categorie):
            await self._send_warning(interaction, "Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        source_entity, source_is_familier = self._resolve_inventory_entity(player, entite_source)
        if entite_source and not source_entity:
            await self._send_error(interaction, "Entité source non trouvée.")
            return
        source_entity, source_is_familier = self._resolve_entity_or_default(source_entity, source_is_familier, player)

        target_entity, target_is_familier = self._resolve_inventory_entity(recipient, entite_destinataire)
        if entite_destinataire and not target_entity:
            await self._send_error(interaction, "Entité destinataire non trouvée.")
            return
        target_entity, target_is_familier = self._resolve_entity_or_default(target_entity, target_is_familier, recipient)

        source_items = source_entity["inventory"][categorie]
        objet = self._find_item_by_name(source_items, nom)
        if not objet:
            await self._send_warning(interaction, f"Objet {nom} non trouvé dans l'inventaire source.")
            return

        source_items.remove(objet)
        target_entity["inventory"][categorie].append(objet)
        if user_id == recipient_id:
            await asyncio.to_thread(update_player, user_id, player)
        else:
            try:
                await asyncio.to_thread(update_two_players_atomic, user_id, player, recipient_id, recipient)
            except DatabaseError:
                await self._send_error(interaction, "Erreur lors du transfert d'objet.")
                return

        await self._send_success(
            interaction,
            f"{self._entity_name(source_entity, source_is_familier)} a donné {nom} à "
            f"{self._entity_name(target_entity, target_is_familier)} ({destinataire.mention}).",
        )

    @app_commands.command(name="retirer_objet", description="Retire un objet de l'inventaire d'un joueur.")
    @app_commands.describe(entite="Nom du familier ou du personnage joueur")
    @app_commands.autocomplete(categorie=category_autocomplete, nom=item_name_autocomplete, entite=joueur_familier_autocomplete)
    async def retirer_objet(
        self,
        interaction: discord.Interaction,
        entite: str,
        nom: str,
        categorie: str = "autres_objets",
        joueur: discord.Member = None,
    ):
        if joueur is None:
            joueur = interaction.user
        else:
            if not self._is_admin(str(interaction.user.id)):
                await self._send_warning(interaction, "Vous n'êtes pas autorisé à utiliser cette commande.")
                return

        player_id = str(joueur.id)
        player_data = await self._load_player_or_none(player_id)

        if not player_data:
            await self._send_error(interaction, "Joueur non trouvé.")
            return

        if not self._is_valid_inventory_category(categorie):
            await self._send_warning(interaction, "Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        entity_data, is_familier = self._resolve_inventory_entity(player_data, entite)
        if entite and not entity_data:
            await self._send_error(interaction, "Entité non trouvée.")
            return
        entity_data, is_familier = self._resolve_entity_or_default(entity_data, is_familier, player_data)

        category_items = entity_data["inventory"][categorie]
        objet = self._find_item_by_name(category_items, nom)
        if not objet:
            await self._send_warning(
                interaction,
                f"Objet {nom} non trouvé dans l'inventaire de {self._entity_name(entity_data, is_familier)}."
            )
            return
        category_items.remove(objet)
        await asyncio.to_thread(update_player, player_id, player_data)

        await self._send_success(
            interaction,
            f"Objet {nom} retiré de l'inventaire de {self._entity_name(entity_data, is_familier)}.",
        )

    @app_commands.command(name="modifier_objet", description="Modifie la description d'un objet.")
    @app_commands.describe(entite="Nom du familier ou du personnage joueur")
    @app_commands.autocomplete(entite=source_familier_autocomplete, nom_objet=item_name_autocomplete)
    async def modifier_objet(
        self,
        interaction: discord.Interaction,
        entite: str,
        nom_objet: str,
        nouvelle_description: str,
    ):
        user_id = str(interaction.user.id)
        player_data = await self._load_player_or_none(user_id)

        if not player_data:
            await self._send_error(interaction, "Joueur non trouvé.")
            return

        entity_data, is_familier = self._resolve_inventory_entity(player_data, entite)
        if entite and not entity_data:
            await self._send_error(interaction, "Entité non trouvée.")
            return
        entity_data, is_familier = self._resolve_entity_or_default(entity_data, is_familier, player_data)

        for category in INVENTORY_CATEGORIES:
            item = self._find_item_by_name(entity_data["inventory"].get(category, []), nom_objet)
            if item:
                item["description"] = nouvelle_description
                await asyncio.to_thread(update_player, user_id, player_data)
                await self._send_success(
                    interaction,
                    f"La description de {nom_objet} a été mise à jour pour {self._entity_name(entity_data, is_familier)}."
                )
                return

        await self._send_warning(interaction, f"L'objet {nom_objet} n'a pas été trouvé dans votre inventaire.")


async def setup(bot):
    await bot.add_cog(InventoryCommands(bot))
