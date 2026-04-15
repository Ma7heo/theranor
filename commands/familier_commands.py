import asyncio
import copy

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from commands.familier_logic import default_familier_skills
from commands.player_views import CreationOwnerView, OpenModalView, SkillCategoryView, SkillDistributionView
from commands.skill_ui import build_skill_table_text, count_allocated_skill_points
from config import ADMIN_IDS
from database import (
    DEFAULT_INVENTORY,
    add_familier_character,
    add_user,
    associate_familier_to_character,
    load_all_characters_by_user,
    load_player,
    load_unassociated_familiers_by_user,
    load_user,
)


class FamilierIdentityModal(discord.ui.Modal, title="Création de familier - Identité"):
    name_input = discord.ui.TextInput(
        label="Nom du familier",
        placeholder="Exemple: Griffe",
        min_length=2,
        max_length=32,
    )
    age_input = discord.ui.TextInput(
        label="Âge du familier",
        placeholder="Exemple: 3",
        min_length=1,
        max_length=3,
    )

    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = str(user_id)

    async def on_submit(self, interaction: Interaction):
        await self.cog.handle_familier_identity_submit(
            interaction,
            self.user_id,
            self.name_input.value,
            self.age_input.value,
        )


class FamilierStatsModal(discord.ui.Modal, title="Création de familier - Niveau & stats"):
    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = str(user_id)

        self.total_level_input = discord.ui.TextInput(
            label="Niveau total",
            placeholder="Exemple: 6",
            required=True,
            max_length=2,
        )
        self.for_input = discord.ui.TextInput(label="FOR", placeholder="0", required=True, max_length=2)
        self.agi_input = discord.ui.TextInput(label="AGI", placeholder="0", required=True, max_length=2)
        self.cha_input = discord.ui.TextInput(label="CHA", placeholder="0", required=True, max_length=2)
        self.int_input = discord.ui.TextInput(label="INT", placeholder="0", required=True, max_length=2)

        self.add_item(self.total_level_input)
        self.add_item(self.for_input)
        self.add_item(self.agi_input)
        self.add_item(self.cha_input)
        self.add_item(self.int_input)

    async def on_submit(self, interaction: Interaction):
        values = {
            "niveau": self.total_level_input.value,
            "for": self.for_input.value,
            "agi": self.agi_input.value,
            "cha": self.cha_input.value,
            "int": self.int_input.value,
        }
        await self.cog.handle_familier_stats_submit(interaction, self.user_id, values)


class _FamilierMagicSelect(discord.ui.Select):
    def __init__(self, cog, user_id, options, step):
        self.cog = cog
        self.user_id = str(user_id)
        self.step = step
        select_options = [discord.SelectOption(label=option, value=option) for option in options]
        placeholder = "Choisissez la première magie" if step == 1 else "Choisissez la deuxième magie"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: Interaction):
        await self.cog.handle_familier_magic_selection(interaction, self.user_id, self.values[0], self.step)


class FamilierMagicSelectionView(CreationOwnerView):
    def __init__(self, cog, user_id, options, step):
        super().__init__(user_id)
        self.add_item(_FamilierMagicSelect(cog, user_id, options, step))


class FamilierCommands(commands.Cog):
    MAGIC_OPTIONS = [
        "Magie arcanique",
        "Magie élémentaire",
        "Magie noire",
        "Magie sacrée",
        "Druidique",
        "Sorcellerie",
    ]
    SKILL_CATEGORY_LABELS = {
        "force": "FOR",
        "agilite": "AGI",
        "charisme": "CHA",
        "intelligence": "INT",
    }

    def __init__(self, bot):
        self.bot = bot
        self.creation_sessions = {}

    @staticmethod
    def _is_mj(user_id) -> bool:
        return str(user_id) in ADMIN_IDS

    async def _send_interaction_message(self, interaction: Interaction, content=None, view=None, embed=None, ephemeral=True):
        if interaction.response.is_done():
            await interaction.followup.send(content=content, view=view, embed=embed, ephemeral=ephemeral)
            return
        await interaction.response.send_message(content=content, view=view, embed=embed, ephemeral=ephemeral)

    @staticmethod
    def _new_familier_template():
        return {
            "nom": "",
            "age": 0,
            "niveau": 1,
            "attributes": {
                "for": 0,
                "agi": 0,
                "cha": 0,
                "int": 0,
                "pv_max": 0,
                "mana_max": 0,
                "pv_actu": 0,
                "mana_actu": 0,
            },
            "skills": default_familier_skills(),
            "magie": [],
            "inventory": copy.deepcopy(DEFAULT_INVENTORY),
        }

    def _new_creation_session(self, owner_character):
        return {
            "step": 0,
            "owner_character_id": owner_character["id"] if owner_character else None,
            "owner_character_name": owner_character["name"] if owner_character else None,
            "data": self._new_familier_template(),
            "skill_values": {
                category: {skill_name: 0 for skill_name in skills}
                for category, skills in default_familier_skills().items()
            },
        }

    def _build_skill_embed(
        self,
        familier_data,
        allocated_values: dict[str, dict[str, int]],
        selected_category: str | None = None,
    ):
        allocated_points = count_allocated_skill_points(allocated_values)

        title = "Création du familier - Compétences"
        if selected_category:
            title += f" ({self.SKILL_CATEGORY_LABELS.get(selected_category, selected_category.upper())})"

        embed = discord.Embed(title=title, color=discord.Color.blurple())
        embed.description = build_skill_table_text(familier_data, allocated_values, self.SKILL_CATEGORY_LABELS)
        embed.add_field(name="Points alloués", value=f"{allocated_points} (répartition libre)", inline=False)
        embed.add_field(name="Règles", value="Aucune limitation automatique.", inline=False)
        return embed

    async def _prompt_identity_step(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune création de familier en cours.")
            return

        owner_name = session.get("owner_character_name")
        owner_line = f"Association prévue: **{owner_name}**" if owner_name else "Association: **aucune** (à faire plus tard avec `/associer_familier`)"

        embed = discord.Embed(title="Ajout d'un familier - Étape 1/4", color=discord.Color.green())
        embed.description = (
            "Cliquez sur le bouton pour saisir le **nom** et l'**âge** du familier.\n"
            f"{owner_line}"
        )
        view = OpenModalView(user_id, lambda: FamilierIdentityModal(self, user_id), "Saisir nom et âge")

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(embed=embed, view=view, content=None)
            return
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _prompt_stats_step(self, interaction: Interaction, user_id: str):
        embed = discord.Embed(title="Ajout d'un familier - Étape 2/4", color=discord.Color.green())
        embed.description = "Saisissez le **niveau total** et les 4 stats dans le pop-up."
        view = OpenModalView(user_id, lambda: FamilierStatsModal(self, user_id), "Saisir niveau et stats")

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(embed=embed, view=view, content=None)
            return
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _show_skill_main_menu(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 2:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        embed = self._build_skill_embed(session["data"], session["skill_values"])
        content = "Répartissez les compétences librement. Cliquez sur une stat puis `Valider`."
        view = SkillDistributionView(
            self,
            user_id,
            open_category_handler=self._open_skill_category_panel,
            validate_handler=self._handle_skill_validate,
        )

        if interaction.response.is_done():
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(content=content, embed=embed, view=view)
            return
        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)

    async def _open_skill_category_panel(self, interaction: Interaction, user_id: str, category: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 2:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        if category not in session["data"]["skills"]:
            await self._send_interaction_message(interaction, "Catégorie de compétence inconnue.")
            return

        embed = self._build_skill_embed(session["data"], session["skill_values"], selected_category=category)
        content = "Ajustez les compétences de cette catégorie avec `+/-`, puis cliquez sur `Retour`."
        skills = list(session["data"]["skills"][category].keys())
        view = SkillCategoryView(
            self,
            user_id,
            category,
            skills,
            adjust_handler=self._handle_skill_adjust,
            back_handler=self._show_skill_main_menu,
        )
        await interaction.response.edit_message(content=content, embed=embed, view=view)

    async def _handle_skill_adjust(
        self,
        interaction: Interaction,
        user_id: str,
        category: str,
        skill_name: str,
        delta: int,
    ):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 2:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        values = session["skill_values"]
        if category not in values or skill_name not in values[category]:
            await self._send_interaction_message(interaction, "Compétence inconnue.")
            return

        current_value = values[category][skill_name]
        updated_value = current_value + delta
        if updated_value < 0:
            await self._send_interaction_message(interaction, "Impossible de descendre en dessous de 0.", ephemeral=True)
            return

        values[category][skill_name] = updated_value

        embed = self._build_skill_embed(session["data"], session["skill_values"], selected_category=category)
        skills = list(session["data"]["skills"][category].keys())
        view = SkillCategoryView(
            self,
            user_id,
            category,
            skills,
            adjust_handler=self._handle_skill_adjust,
            back_handler=self._show_skill_main_menu,
        )
        await interaction.response.edit_message(
            content="Ajustez les compétences de cette catégorie avec `+/-`, puis cliquez sur `Retour`.",
            embed=embed,
            view=view,
        )

    def _apply_skill_distribution_values(self, session):
        values = session["skill_values"]
        for category, category_values in values.items():
            for skill_name, skill_value in category_values.items():
                session["data"]["skills"][category][skill_name] = skill_value

    async def _handle_skill_validate(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 2:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        self._apply_skill_distribution_values(session)
        session["step"] = 3
        await self._show_magic_selection(interaction, user_id, step=1)

    async def _show_magic_selection(self, interaction: Interaction, user_id: str, step: int):
        session = self.creation_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        selected_magies = set(session["data"]["magie"])
        options = [option for option in self.MAGIC_OPTIONS if option not in selected_magies]
        if not options:
            await self._finalize_familier_creation(interaction, user_id)
            return

        embed = discord.Embed(title="Ajout d'un familier - Étape 4/4", color=discord.Color.green())
        embed.description = "Choisissez la première magie du familier." if step == 1 else "Choisissez la deuxième magie du familier."
        view = FamilierMagicSelectionView(self, user_id, options, step)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(content=None, embed=embed, view=view)
            return
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def handle_familier_identity_submit(self, interaction: Interaction, user_id: str, name: str, age_raw: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 0:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        name = name.strip()
        if not name:
            retry_view = OpenModalView(user_id, lambda: FamilierIdentityModal(self, user_id), "Re-saisir nom et âge")
            await self._send_interaction_message(interaction, "Le nom du familier ne peut pas être vide.", view=retry_view)
            return

        try:
            age = int(age_raw.strip())
        except ValueError:
            retry_view = OpenModalView(user_id, lambda: FamilierIdentityModal(self, user_id), "Re-saisir nom et âge")
            await self._send_interaction_message(interaction, "Veuillez entrer un âge valide (entier).", view=retry_view)
            return

        session["data"]["nom"] = name
        session["data"]["age"] = age
        session["step"] = 1
        await self._prompt_stats_step(interaction, user_id)

    async def handle_familier_stats_submit(self, interaction: Interaction, user_id: str, values: dict[str, str]):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 1:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        try:
            niveau = int(values["niveau"].strip())
            for_ = int(values["for"].strip())
            agi = int(values["agi"].strip())
            cha = int(values["cha"].strip())
            int_ = int(values["int"].strip())
        except ValueError:
            retry_view = OpenModalView(user_id, lambda: FamilierStatsModal(self, user_id), "Re-saisir niveau/stats")
            await self._send_interaction_message(
                interaction,
                "Valeurs invalides. Entrez uniquement des nombres entiers.",
                view=retry_view,
            )
            return

        pv_max = 5 + niveau + for_
        mana_max = 5 + niveau + int_

        session["data"]["niveau"] = niveau
        session["data"]["attributes"].update(
            {
                "for": for_,
                "agi": agi,
                "cha": cha,
                "int": int_,
                "pv_max": pv_max,
                "mana_max": mana_max,
                "pv_actu": pv_max,
                "mana_actu": mana_max,
            }
        )
        session["step"] = 2
        await self._show_skill_main_menu(interaction, user_id)

    async def handle_familier_magic_selection(self, interaction: Interaction, user_id: str, selected_magic: str, step: int):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] < 3:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        if selected_magic in session["data"]["magie"]:
            await self._send_interaction_message(interaction, "Cette magie est déjà sélectionnée.", ephemeral=True)
            return

        session["data"]["magie"].append(selected_magic)
        if len(session["data"]["magie"]) >= 2:
            await self._finalize_familier_creation(interaction, user_id)
            return

        session["step"] = 4
        await self._show_magic_selection(interaction, user_id, step=2)

    async def _finalize_familier_creation(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/ajouter_familier`.")
            return

        familier_data = session["data"]
        owner_character_id = session.get("owner_character_id")
        owner_character_name = session.get("owner_character_name")

        familier_id = await asyncio.to_thread(
            add_familier_character,
            user_id,
            familier_data,
            owner_character_id,
        )

        self.creation_sessions.pop(user_id, None)

        association_text = (
            f"Associé à **{owner_character_name}**."
            if owner_character_id
            else "Aucune association pour le moment. Utilisez `/associer_familier`."
        )
        content = (
            f"Familier **{familier_data['nom']}** créé (ID: `{familier_id}`).\n"
            f"Niveau: {familier_data['niveau']} | PV: {familier_data['attributes']['pv_max']} | Mana: {familier_data['attributes']['mana_max']}\n"
            f"Magies: {', '.join(familier_data['magie'])}\n"
            f"{association_text}"
        )

        if interaction.response.is_done():
            await interaction.followup.send(content=content, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(content=content, embed=None, view=None)
            return
        await interaction.response.send_message(content=content, ephemeral=True)

    async def character_autocomplete(self, interaction: discord.Interaction, current: str):
        characters = await asyncio.to_thread(load_all_characters_by_user, str(interaction.user.id), False)
        return [
            app_commands.Choice(name=character["name"], value=character["name"])
            for character in characters
            if current.lower() in character["name"].lower()
        ]

    async def unowned_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        familiers = await asyncio.to_thread(load_unassociated_familiers_by_user, str(interaction.user.id))
        return [
            app_commands.Choice(name=familier["nom"], value=familier["nom"])
            for familier in familiers
            if current.lower() in familier["nom"].lower()
        ]

    @app_commands.command(
        name="ajouter_familier",
        description="Crée un familier, avec association optionnelle à un personnage.",
    )
    @app_commands.describe(personnage="Personnage auquel associer le familier (optionnel)")
    @app_commands.autocomplete(personnage=character_autocomplete)
    async def ajouter_familier(self, interaction: discord.Interaction, personnage: str = None):
        if not self._is_mj(interaction.user.id):
            await interaction.response.send_message("Seul un MJ peut utiliser cette commande.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if not await asyncio.to_thread(load_user, user_id):
            await asyncio.to_thread(add_user, user_id)

        owner_character = None
        if personnage:
            characters = await asyncio.to_thread(load_all_characters_by_user, user_id, False)
            owner_character = next((c for c in characters if c["name"].lower() == personnage.lower()), None)
            if not owner_character:
                await interaction.response.send_message("Personnage introuvable pour l'association.", ephemeral=True)
                return

        if user_id not in self.creation_sessions:
            self.creation_sessions[user_id] = self._new_creation_session(owner_character)
        elif owner_character:
            self.creation_sessions[user_id]["owner_character_id"] = owner_character["id"]
            self.creation_sessions[user_id]["owner_character_name"] = owner_character["name"]

        session = self.creation_sessions[user_id]
        if session["step"] == 0:
            await self._prompt_identity_step(interaction, user_id)
            return
        if session["step"] == 1:
            await self._prompt_stats_step(interaction, user_id)
            return
        if session["step"] == 2:
            await self._show_skill_main_menu(interaction, user_id)
            return
        await self._show_magic_selection(interaction, user_id, step=1 if len(session["data"]["magie"]) == 0 else 2)

    @app_commands.command(name="associer_familier", description="Associe un familier existant à un personnage.")
    @app_commands.describe(nom_familier="Nom du familier non associé", personnage="Personnage propriétaire")
    @app_commands.autocomplete(nom_familier=unowned_familier_autocomplete, personnage=character_autocomplete)
    async def associer_familier(self, interaction: discord.Interaction, nom_familier: str, personnage: str):
        user_id = str(interaction.user.id)

        unowned_familiers = await asyncio.to_thread(load_unassociated_familiers_by_user, user_id)
        familier = next((f for f in unowned_familiers if f["nom"].lower() == nom_familier.lower()), None)
        if not familier:
            await interaction.response.send_message("Familier non associé introuvable.", ephemeral=True)
            return

        characters = await asyncio.to_thread(load_all_characters_by_user, user_id, False)
        owner_character = next((c for c in characters if c["name"].lower() == personnage.lower()), None)
        if not owner_character:
            await interaction.response.send_message("Personnage introuvable.", ephemeral=True)
            return

        updated = await asyncio.to_thread(
            associate_familier_to_character,
            user_id,
            familier["id"],
            owner_character["id"],
        )
        if not updated:
            await interaction.response.send_message("Association impossible.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Le familier **{familier['nom']}** est maintenant associé à **{owner_character['name']}**.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(FamilierCommands(bot))
