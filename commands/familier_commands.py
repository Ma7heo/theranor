import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from commands.combat_logic import (
    CombatValidationError,
    build_attack_response,
    compute_attack_mana_cost,
    resolve_attack_context,
)
from commands.familier_logic import (
    ATTRIBUTE_CHOICES,
    INVENTORY_CATEGORIES,
    build_familier_view_model,
    create_familier,
    find_familier,
    get_familier_action_choices,
    get_familier_choices,
    get_item_choices,
    get_weapon_choices,
    handle_roll_command,
    parse_familier_skills,
)
from commands.player_logic import build_base_info_embed
from commands.player_views import InfoNavigationView
from config import ADMIN_IDS
from database import load_player, update_player
from utils import parse_dice_expression, roll_d100, roll_d20


class FamilierCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _coerce_field_value(current_value, raw_value):
        if isinstance(current_value, bool):
            normalized = raw_value.strip().lower()
            if normalized in {"true", "1", "yes", "oui"}:
                return True
            if normalized in {"false", "0", "no", "non"}:
                return False
            raise ValueError
        if isinstance(current_value, int):
            return int(raw_value)
        if isinstance(current_value, float):
            return float(raw_value)
        if isinstance(current_value, str):
            return raw_value
        raise TypeError

    def _is_admin(self, user_id):
        return str(user_id) in ADMIN_IDS

    async def _load_player(self, user_id):
        return await asyncio.to_thread(load_player, str(user_id))

    async def familier_autocomplete(self, interaction: discord.Interaction, current: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            return []
        return [
            app_commands.Choice(name=familier, value=familier)
            for familier in get_familier_choices(player_data)
            if current.lower() in familier.lower()
        ]

    async def action_autocomplete(self, interaction: discord.Interaction, current: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            return []
        familier_name = interaction.namespace.nom_familier
        familier = find_familier(player_data, familier_name, case_insensitive=False)
        if not familier:
            return []
        return [
            app_commands.Choice(name=action, value=action)
            for action in get_familier_action_choices(familier)
            if current.lower() in action.lower()
        ]

    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            return []
        nom_familier = interaction.namespace.nom_familier
        familier = find_familier(player_data, nom_familier, case_insensitive=False)
        if not familier:
            return []
        return [
            app_commands.Choice(name=weapon, value=weapon)
            for weapon in get_weapon_choices(familier)
            if current.lower() in weapon.lower()
        ]

    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=category, value=category)
            for category in INVENTORY_CATEGORIES
            if current.lower() in category.lower()
        ]

    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            return []
        categorie = interaction.namespace.categorie
        return [
            app_commands.Choice(name=item, value=item)
            for item in get_item_choices(player_data, categorie)
            if current.lower() in item.lower()
        ]

    async def item_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            return []
        nom_familier = interaction.namespace.nom_familier
        categorie = interaction.namespace.categorie
        familier = find_familier(player_data, nom_familier, case_insensitive=False)
        if not familier:
            return []
        return [
            app_commands.Choice(name=item, value=item)
            for item in get_item_choices(familier, categorie)
            if current.lower() in item.lower()
        ]

    async def modifier_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in ATTRIBUTE_CHOICES
            if current.lower() in choice.lower()
        ]

    @app_commands.command(name="ajouter_familier", description="Ajoute un familier à un joueur.")
    @app_commands.describe(
        joueur="Le joueur à qui ajouter un familier",
        nom="Nom du familier",
        niveau="Niveau du familier",
        for_="Force du familier",
        agi="Agilité du familier",
        cha="Charisme du familier",
        int_="Intelligence du familier",
        pv_max="Points de vie maximum du familier",
        mana_max="Points de mana maximum du familier",
        compétences="Compétences du familier",
    )
    async def ajouter_familier(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        nom: str,
        niveau: int,
        for_: int,
        agi: int,
        cha: int,
        int_: int,
        pv_max: int,
        mana_max: int,
        compétences: str,
    ):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.")
            return

        player_id = str(joueur.id)
        player_data = await self._load_player(player_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        try:
            skills_dict = parse_familier_skills(compétences)
        except ValueError:
            await interaction.response.send_message("Format de compétence invalide. Utilisez le format 'compétence:valeur'.")
            return
        except KeyError as exc:
            await interaction.response.send_message(f"Compétence {exc.args[0]} non reconnue.")
            return

        familier = create_familier(nom, niveau, for_, agi, cha, int_, pv_max, mana_max, skills_dict)
        player_data["familiers"].append(familier)
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(f"Le familier {nom} a été ajouté au joueur {joueur.mention}.")

    @app_commands.command(name="familier", description="Utilise une action avec un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, action=action_autocomplete)
    async def familier(self, interaction: discord.Interaction, nom_familier: str, action: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familier = find_familier(player_data, nom_familier, case_insensitive=False)
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        action_choices = get_familier_action_choices(familier)
        if action not in action_choices:
            await interaction.response.send_message("Action non reconnue.")
            return

        await interaction.response.send_message(handle_roll_command(action, familier))

    @app_commands.command(name="init_familier", description="Effectue un jet d'initiative pour le familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def init_familier(self, interaction: discord.Interaction, nom_familier: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        agi = familier["attributes"].get("agi", 0)
        initiative = roll_d20() + agi
        await interaction.response.send_message(f"Initiative de {familier['nom']}: 1d20 + {agi} = {initiative}")

    @app_commands.command(name="armure_familier", description="Effectue un jet d'armure pour réduire les dégâts du familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def armure_familier(self, interaction: discord.Interaction, nom_familier: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        armure = familier["attributes"].get("armure", 0)
        bonus_armures = sum(item["bonus_value"] for item in familier["inventory"]["armures"])
        bonus_bouclier = sum(
            item["bonus_value"]
            for item in familier["inventory"]["autres_objets"]
            if item["bonus_type"] == "bouclier"
        )
        roll = roll_d100()
        total = roll - armure - bonus_armures - bonus_bouclier

        message = f"Armure de {familier['nom']}: 1d100 - {armure} - {bonus_armures} - {bonus_bouclier} = {total}"
        if total < 0:
            message += "\nSuccès! Le familier prendra moitié moins de dégâts."
        else:
            message += "\nÉchec! Le familier prendra les dégâts complets."
        await interaction.response.send_message(message)

    @app_commands.command(name="info_familier", description="Affiche les informations du familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def info_familier(self, interaction: discord.Interaction, nom_familier: str):
        player_data = await self._load_player(interaction.user.id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return
        familier_view_data = build_familier_view_model(familier)
        embed = build_base_info_embed(familier_view_data)
        view = InfoNavigationView(str(interaction.user.id), familier_view_data)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="attaquer_familier", description="Attaque avec un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, weapon_name=weapon_autocomplete)
    async def attaquer_familier(
        self,
        interaction: discord.Interaction,
        nom_familier: str,
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
        player_data = await self._load_player(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        try:
            attack_ctx = resolve_attack_context(familier, weapon_name)
        except CombatValidationError as exc:
            message = "Arme non trouvée pour le familier." if "Arme non trouvée" in str(exc) else str(exc)
            await interaction.response.send_message(message)
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
        _, points_mana, use_mana = compute_attack_mana_cost(effect_levels)
        skill_level = familier["skills"][attack_ctx.category][attack_ctx.skill_name]

        if points_mana > skill_level:
            await interaction.response.send_message(
                f"Le familier n'a pas assez de points de compétence. Compétence actuelle: {skill_level}, points requis: {points_mana}"
            )
            return
        if familier["attributes"]["mana_actu"] < use_mana:
            await interaction.response.send_message("Mana insuffisant pour le familier.")
            return

        await interaction.response.defer()
        familier["attributes"]["mana_actu"] -= use_mana
        await asyncio.to_thread(update_player, user_id, player_data)

        response_lines = build_attack_response(
            player_data=familier,
            weapon_name=weapon_name,
            attack_ctx=attack_ctx,
            skill_level=skill_level,
            effect_levels=effect_levels,
        )
        response_lines.append(f"Mana consommé: {use_mana}")
        response_lines.append(f"Mana restant: {familier['attributes']['mana_actu']}")
        await interaction.followup.send("\n".join(response_lines))

    @app_commands.command(name="perdre_pv_familier", description="Fait perdre des PV à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def perdre_pv_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, degats: str):
        player_id = str(joueur.id)
        player_data = await self._load_player(player_id)
        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message(
                f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True
            )
            return

        degats_total, _ = parse_dice_expression(degats)
        familier["attributes"]["pv_actu"] = max(familier["attributes"]["pv_actu"] - degats_total, 0)
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{degats_total} PV retirés à {nom_familier}. PV restants: {familier['attributes']['pv_actu']}/{familier['attributes']['pv_max']}.",
            ephemeral=True,
        )

    @app_commands.command(name="soigner_familier", description="Soigne un familier en lui redonnant des PV.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def soigner_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, soin: str):
        player_id = str(joueur.id)
        player_data = await self._load_player(player_id)
        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message(
                f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True
            )
            return

        soin_total, _ = parse_dice_expression(soin)
        familier["attributes"]["pv_actu"] = min(
            familier["attributes"]["pv_actu"] + soin_total,
            familier["attributes"]["pv_max"],
        )
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{soin_total} PV ajoutés à {nom_familier}. PV actuels: {familier['attributes']['pv_actu']}/{familier['attributes']['pv_max']}.",
            ephemeral=True,
        )

    @app_commands.command(name="perdre_mana_familier", description="Fait perdre du mana à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def perdre_mana_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, cout_mana: str):
        player_id = str(joueur.id)
        player_data = await self._load_player(player_id)
        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message(
                f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True
            )
            return

        cout_total, _ = parse_dice_expression(cout_mana)
        familier["attributes"]["mana_actu"] = max(familier["attributes"]["mana_actu"] - cout_total, 0)
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{cout_total} mana retirés à {nom_familier}. Mana restants: {familier['attributes']['mana_actu']}/{familier['attributes']['mana_max']}.",
            ephemeral=True,
        )

    @app_commands.command(name="ajouter_mana_familier", description="Ajoute du mana à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def ajouter_mana_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, mana_ajoute: str):
        player_id = str(joueur.id)
        player_data = await self._load_player(player_id)
        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message(
                f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True
            )
            return

        mana_total, _ = parse_dice_expression(mana_ajoute)
        familier["attributes"]["mana_actu"] = min(
            familier["attributes"]["mana_actu"] + mana_total,
            familier["attributes"]["mana_max"],
        )
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"{mana_total} mana ajoutés à {nom_familier}. Mana actuels: {familier['attributes']['mana_actu']}/{familier['attributes']['mana_max']}.",
            ephemeral=True,
        )

    @app_commands.command(name="donner_objet_familier", description="Donne un objet à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, categorie=category_autocomplete, nom=item_autocomplete)
    async def donner_objet_familier(self, interaction: discord.Interaction, nom_familier: str, categorie: str, nom: str):
        user_id = str(interaction.user.id)
        player_data = await self._load_player(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return
        if categorie not in INVENTORY_CATEGORIES:
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        familier = find_familier(player_data, nom_familier, case_insensitive=False)
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        objet = next((item for item in player_data["inventory"][categorie] if item["nom"] == nom), None)
        if not objet:
            await interaction.response.send_message(f"L'objet {nom} n'a pas été trouvé dans votre inventaire.")
            return

        player_data["inventory"][categorie].remove(objet)
        familier["inventory"][categorie].append(objet)
        await asyncio.to_thread(update_player, user_id, player_data)
        await interaction.response.send_message(f"Vous avez donné {nom} à votre familier {nom_familier}.")

    @app_commands.command(name="rendre_objet_familier", description="Rend un objet du familier au joueur.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, categorie=category_autocomplete, nom=item_familier_autocomplete)
    async def rendre_objet_familier(self, interaction: discord.Interaction, nom_familier: str, categorie: str, nom: str):
        user_id = str(interaction.user.id)
        player_data = await self._load_player(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return
        if categorie not in INVENTORY_CATEGORIES:
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        objet = next((item for item in familier["inventory"][categorie] if item["nom"] == nom), None)
        if not objet:
            await interaction.response.send_message(f"Objet {nom} non trouvé dans l'inventaire du familier {nom_familier}.")
            return

        familier["inventory"][categorie].remove(objet)
        player_data["inventory"][categorie].append(objet)
        await asyncio.to_thread(update_player, user_id, player_data)
        await interaction.response.send_message(f"Objet {nom} rendu du familier {nom_familier} au joueur {interaction.user.mention}.")

    @app_commands.command(name="supprimer_familier", description="Supprime un familier d'un joueur.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def supprimer_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str):
        player_id = str(joueur.id)
        player_data = await self._load_player(player_id)
        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        familier = find_familier(player_data, nom_familier)
        if not familier:
            await interaction.response.send_message(
                f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True
            )
            return

        player_data["familiers"].remove(familier)
        await asyncio.to_thread(update_player, player_id, player_data)
        await interaction.response.send_message(
            f"Le familier {nom_familier} a été supprimé pour le joueur {joueur.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="modifier_familier", description="Modifie les détails d'un familier.")
    @app_commands.describe(joueur="Le joueur à modifier", familier="Le familier à modifier", champ="Champ à modifier", valeur="Nouvelle valeur")
    @app_commands.autocomplete(familier=familier_autocomplete, champ=modifier_familier_autocomplete)
    async def modifier_familier(self, interaction: discord.Interaction, joueur: discord.Member, familier: str, champ: str, valeur: str):
        user_id = str(joueur.id)
        player_data = await self._load_player(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familier_data = find_familier(player_data, familier)
        if not familier_data:
            await interaction.response.send_message("Familier non trouvé.")
            return

        try:
            keys = champ.split(".")
            data = familier_data
            for key in keys[:-1]:
                data = data[key]
            current_value = data[keys[-1]]
            data[keys[-1]] = self._coerce_field_value(current_value, valeur)
        except KeyError:
            await interaction.response.send_message("Champ non valide.")
            return
        except ValueError:
            await interaction.response.send_message("Valeur non valide pour ce champ.")
            return
        except TypeError:
            await interaction.response.send_message("Type de donnée invalide pour ce champ.")
            return

        await asyncio.to_thread(update_player, user_id, player_data)
        await interaction.response.send_message(f"Le champ {champ} a été mis à jour avec succès à {valeur}.")


async def setup(bot):
    await bot.add_cog(FamilierCommands(bot))
