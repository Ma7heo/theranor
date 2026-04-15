import asyncio
import copy

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from commands.player_logic import (
    ATTRIBUTE_CHOICES,
    CREATION_STEPS,
    RACE_BONUS,
    apply_race_bonus,
    build_base_info_embed,
    build_character_list_message,
    compute_level_up_gain,
    finalize_character_stats,
    new_character_template,
)
from commands.familier_logic import build_familier_view_model, find_familier
from commands.embed_utils import coerce_content_to_embed, error_embed, info_embed, success_embed, warning_embed
from commands.player_views import (
    AttributeDistributionModal,
    CharacterIdentityModal,
    InfoNavigationView,
    LevelUpAttributeView,
    MagicSelectionView,
    OpenModalView,
    RaceSelectionView,
    SkillCategoryView,
    SkillDistributionView,
)
from commands.skill_ui import build_skill_table_text, count_allocated_skill_points, display_skill_name
from database import (
    DatabaseError,
    add_character,
    add_user,
    change_active_character,
    load_all_characters_by_user,
    load_character_by_name,
    load_player,
    load_user,
    remove_character,
    remove_player,
    update_player,
)


class PlayerCommands(commands.Cog):
    ATTRIBUTE_LABELS = {"for": "FOR", "agi": "AGI", "cha": "CHA", "int": "INT"}
    SKILL_CATEGORY_LABELS = {
        "force": "FORCE",
        "agilite": "AGILITE",
        "charisme": "CHARISME",
        "intelligence": "INTELLIGENCE",
    }

    def __init__(self, bot):
        self.bot = bot
        self.creation_sessions = {}
        self.level_up_sessions = {}
        self.creation_steps = CREATION_STEPS
        self.race_bonus = RACE_BONUS

    @staticmethod
    async def _load_player_or_none(user_id: str):
        return await asyncio.to_thread(load_player, user_id)

    @staticmethod
    async def _load_user_or_none(user_id: str):
        return await asyncio.to_thread(load_user, user_id)

    async def _resolve_player_and_familier(self, user_id: str, familier: str | None):
        player_data = await self._load_player_or_none(user_id)
        if not player_data:
            return None, None, None, "Joueur non trouvé."
        if not familier:
            return player_data, player_data, False, None

        familier_data = find_familier(player_data, familier)
        if not familier_data:
            return player_data, None, None, "Familier non trouvé."
        return player_data, familier_data, True, None

    def _resolve_familier_for_level_session(self, owner_player_data, session):
        familier_id = session.get("familier_id")
        if familier_id is not None:
            familier_data = self._find_familier_by_id(owner_player_data, familier_id)
            if familier_data:
                return familier_data
        familier_name = session.get("familier_name")
        if familier_name:
            return find_familier(owner_player_data, familier_name)
        return None

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

    @staticmethod
    def _build_level_up_data_from_familier(familier_data):
        return {
            "id": familier_data.get("id"),
            "name": familier_data["nom"],
            "age": familier_data.get("age", 0),
            "race": "Familier",
            "level": familier_data["niveau"],
            "attributes": {
                "for": familier_data["attributes"].get("for", 0),
                "agi": familier_data["attributes"].get("agi", 0),
                "cha": familier_data["attributes"].get("cha", 0),
                "int": familier_data["attributes"].get("int", 0),
            },
            "skills": copy.deepcopy(familier_data["skills"]),
            "magie": copy.deepcopy(familier_data.get("magie", [])),
            "pv_actu": familier_data["attributes"].get("pv_actu", 0),
            "pv_max": familier_data["attributes"].get("pv_max", 0),
            "mana_actu": familier_data["attributes"].get("mana_actu", 0),
            "mana_max": familier_data["attributes"].get("mana_max", 0),
            "inventory": copy.deepcopy(familier_data["inventory"]),
            "familiers": [],
        }

    @staticmethod
    def _apply_level_up_data_to_familier(familier_data, level_data):
        familier_data["niveau"] = level_data["level"]
        familier_data["attributes"]["for"] = level_data["attributes"]["for"]
        familier_data["attributes"]["agi"] = level_data["attributes"]["agi"]
        familier_data["attributes"]["cha"] = level_data["attributes"]["cha"]
        familier_data["attributes"]["int"] = level_data["attributes"]["int"]
        familier_data["skills"] = copy.deepcopy(level_data["skills"])
        familier_data["magie"] = copy.deepcopy(level_data.get("magie", []))
        familier_data["attributes"]["pv_actu"] = level_data["pv_actu"]
        familier_data["attributes"]["pv_max"] = level_data["pv_max"]
        familier_data["attributes"]["mana_actu"] = level_data["mana_actu"]
        familier_data["attributes"]["mana_max"] = level_data["mana_max"]
        familier_data["inventory"] = copy.deepcopy(level_data["inventory"])

    @staticmethod
    def _find_familier_by_id(player_data, familier_id):
        for familier_data in player_data.get("familiers", []):
            if familier_data.get("id") == familier_id:
                return familier_data
        return None

    async def _send_interaction_message(self, interaction: Interaction, content=None, view=None, embed=None, ephemeral=True):
        content, embed = coerce_content_to_embed(content, embed, title="Personnage")
        if interaction.response.is_done():
            await interaction.followup.send(content=content, view=view, embed=embed, ephemeral=ephemeral)
            return
        await interaction.response.send_message(content=content, view=view, embed=embed, ephemeral=ephemeral)

    def _initialize_skill_step(self, session):
        if "skill_step" in session:
            return

        values = {}
        for category, skills_dict in session["data"]["skills"].items():
            values[category] = {skill_name: 0 for skill_name in skills_dict}
        session["skill_step"] = {"values": values}

    def _build_skill_embed(
        self,
        player_data,
        allocated_values: dict[str, dict[str, int]],
        required_points: int,
        selected_category: str | None = None,
        title_prefix: str = "Répartition des compétences",
    ):
        allocated_points = count_allocated_skill_points(allocated_values)
        remaining_points = required_points - allocated_points

        title = title_prefix
        if selected_category:
            title += f" - {self.SKILL_CATEGORY_LABELS.get(selected_category, selected_category.upper())}"

        embed = discord.Embed(title=title, color=discord.Color.blurple())
        embed.description = build_skill_table_text(player_data, allocated_values, self.SKILL_CATEGORY_LABELS)
        embed.add_field(name="Points", value=f"{allocated_points}/{required_points} (restants: {remaining_points})", inline=False)
        if selected_category:
            attr_value = player_data["attributes"][selected_category[:3]]
            embed.add_field(name="Règle de catégorie", value=f"Chaque compétence <= {attr_value}", inline=False)
        else:
            embed.add_field(name="Règles", value="Chaque compétence doit rester <= au niveau de sa stat.", inline=False)
        return embed

    async def _send_creation_step_prompt(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune création en cours. Lancez `/creer_personnage`.")
            return

        step = session["step"]
        if step in (0, 1):
            await interaction.response.send_modal(CharacterIdentityModal(self, user_id))
            return

        if step == 2:
            view = RaceSelectionView(self, user_id, self.creation_steps[2]["options"])
            await self._send_interaction_message(interaction, self.creation_steps[2]["question"], view=view)
            return

        if step == 3:
            await interaction.response.send_modal(AttributeDistributionModal(self, user_id))
            return

        if step == 4:
            await self.show_skill_main_menu(interaction, user_id)
            return

        if step == 5:
            view = MagicSelectionView(self, user_id, self.creation_steps[5]["options"], step=5)
            await self._send_interaction_message(interaction, self.creation_steps[5]["question"], view=view)
            return

        if step == 6:
            already_selected = set(session["data"]["magie"])
            options = [option for option in self.creation_steps[6]["options"] if option not in already_selected]
            view = MagicSelectionView(self, user_id, options, step=6)
            await self._send_interaction_message(interaction, self.creation_steps[6]["question"], view=view)
            return

        await self._finalize_creation(interaction, user_id)

    async def _finalize_creation(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune création en cours. Lancez `/creer_personnage`.")
            return

        player_data = session["data"]
        finalize_character_stats(player_data)
        try:
            await asyncio.to_thread(add_character, user_id, player_data)
        except DatabaseError:
            del self.creation_sessions[user_id]
            await self._send_interaction_message(interaction, "Erreur lors de la sauvegarde du personnage.")
            return

        del self.creation_sessions[user_id]
        await self._send_interaction_message(
            interaction,
            (
                f"Création terminée: **{player_data['name']}** ({player_data['race']})\n"
                f"HP: {player_data['pv_actu']}/{player_data['pv_max']} | "
                f"MANA: {player_data['mana_actu']}/{player_data['mana_max']}\n"
                f"Magies: {', '.join(player_data['magie'])}"
            ),
        )

    async def handle_creation_identity_submit(self, interaction: Interaction, user_id: str, name: str, age_raw: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 0:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        name = name.strip()
        if not name:
            retry_view = OpenModalView(
                user_id,
                lambda: CharacterIdentityModal(self, user_id),
                "Re-saisir nom et âge",
            )
            await self._send_interaction_message(interaction, "Le nom du personnage ne peut pas être vide.", view=retry_view)
            return

        try:
            age = int(age_raw.strip())
            if age <= 0:
                raise ValueError
        except ValueError:
            retry_view = OpenModalView(
                user_id,
                lambda: CharacterIdentityModal(self, user_id),
                "Re-saisir nom et âge",
            )
            await self._send_interaction_message(interaction, "Veuillez entrer un âge valide (nombre entier positif).", view=retry_view)
            return

        session["data"]["name"] = name
        session["data"]["age"] = age
        session["step"] = 2
        await self._send_creation_step_prompt(interaction, user_id)

    async def handle_creation_race_selection(self, interaction: Interaction, user_id: str, selected_race: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 2:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        apply_race_bonus(session["data"], selected_race)
        session["step"] = 3
        await self._send_creation_step_prompt(interaction, user_id)

    async def handle_creation_attribute_submit(self, interaction: Interaction, user_id: str, values: dict[str, str]):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 3:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        try:
            increments = {}
            total_points = 0
            for attr_key in ("for", "agi", "cha", "int"):
                raw_value = values.get(attr_key, "").strip()
                parsed_value = int(raw_value)
                if parsed_value < 0:
                    raise ValueError
                increments[attr_key] = parsed_value
                total_points += parsed_value
            if total_points != 4:
                raise ValueError
        except (ValueError, TypeError):
            retry_view = OpenModalView(user_id, lambda: AttributeDistributionModal(self, user_id), "Re-saisir les attributs")
            await self._send_interaction_message(interaction, "Vous devez distribuer exactement 4 points dans les attributs.", view=retry_view)
            return

        updated_attributes = session["data"]["attributes"].copy()
        for attr_key, increment in increments.items():
            updated_attributes[attr_key] += increment
        session["data"]["attributes"] = updated_attributes

        session["step"] = 4
        await self._send_creation_step_prompt(interaction, user_id)

    async def show_skill_main_menu(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 4:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        self._initialize_skill_step(session)
        required_points = 9 if session["data"]["race"] == "Humain" else 8
        embed = self._build_skill_embed(
            session["data"],
            session["skill_step"]["values"],
            required_points,
            title_prefix="Création - Compétences",
        )
        content = (
            f"Répartissez exactement {required_points} points.\n"
            "Cliquez sur une stat pour ajuster ses compétences avec des boutons `+/-`, puis cliquez sur `Valider`."
        )
        view = SkillDistributionView(
            self,
            user_id,
            open_category_handler=self.open_skill_category_panel,
            validate_handler=self.handle_skill_validate,
        )
        if interaction.response.is_done():
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(content=content, embed=embed, view=view)
            return
        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)

    async def open_skill_category_panel(self, interaction: Interaction, user_id: str, category: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 4:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        self._initialize_skill_step(session)
        if category not in session["data"]["skills"]:
            await self._send_interaction_message(interaction, "Catégorie de compétence inconnue.")
            return

        skills = list(session["data"]["skills"][category].keys())
        required_points = 9 if session["data"]["race"] == "Humain" else 8
        embed = self._build_skill_embed(
            session["data"],
            session["skill_step"]["values"],
            required_points,
            selected_category=category,
            title_prefix="Création - Compétences",
        )
        content = "Utilisez les boutons pour modifier les compétences de cette catégorie, puis `Retour`."
        view = SkillCategoryView(
            self,
            user_id,
            category,
            skills,
            adjust_handler=self.handle_skill_adjust,
            back_handler=self.show_skill_main_menu,
        )
        await interaction.response.edit_message(content=content, embed=embed, view=view)

    async def handle_skill_adjust(
        self,
        interaction: Interaction,
        user_id: str,
        category: str,
        skill_name: str,
        delta: int,
    ):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 4:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        self._initialize_skill_step(session)
        if category not in session["skill_step"]["values"] or skill_name not in session["skill_step"]["values"][category]:
            await self._send_interaction_message(interaction, "Catégorie de compétence inconnue.")
            return

        values = session["skill_step"]["values"]
        current_value = values[category][skill_name]
        updated_value = current_value + delta

        if updated_value < 0:
            await self._send_interaction_message(interaction, "Impossible de descendre en dessous de 0.", ephemeral=True)
            return

        required_points = 9 if session["data"]["race"] == "Humain" else 8
        allocated_points = count_allocated_skill_points(values)
        if delta > 0 and allocated_points >= required_points:
            await self._send_interaction_message(
                interaction,
                f"Tous les points sont déjà distribués ({required_points}/{required_points}).",
                ephemeral=True,
            )
            return

        category_attr = session["data"]["attributes"][category[:3]]
        if updated_value > category_attr:
            await self._send_interaction_message(
                interaction,
                f"{display_skill_name(skill_name)} ne peut pas dépasser {category_attr} ({self.SKILL_CATEGORY_LABELS.get(category, category.upper())}).",
                ephemeral=True,
            )
            return

        values[category][skill_name] = updated_value

        skills = list(session["data"]["skills"][category].keys())
        required_points = 9 if session["data"]["race"] == "Humain" else 8
        embed = self._build_skill_embed(
            session["data"],
            session["skill_step"]["values"],
            required_points,
            selected_category=category,
            title_prefix="Création - Compétences",
        )
        content = "Utilisez les boutons pour modifier les compétences de cette catégorie, puis `Retour`."
        view = SkillCategoryView(
            self,
            user_id,
            category,
            skills,
            adjust_handler=self.handle_skill_adjust,
            back_handler=self.show_skill_main_menu,
        )
        await interaction.response.edit_message(content=content, embed=embed, view=view)

    def _apply_skill_distribution_values(self, player_data, values, required_points: int):
        total_points = sum(skill_value for category_values in values.values() for skill_value in category_values.values())
        if total_points != required_points:
            raise ValueError("skill_points")

        updated_skills = copy.deepcopy(player_data["skills"])
        for category, category_values in values.items():
            attr_key = category[:3]
            attr_value = player_data["attributes"][attr_key]
            for skill_name, skill_value in category_values.items():
                if skill_value > attr_value:
                    raise ValueError(f"skill_cap:{skill_name}:{category}")
                updated_skills[category][skill_name] += skill_value

        player_data["skills"] = updated_skills

    async def handle_skill_validate(self, interaction: Interaction, user_id: str):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != 4:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        self._initialize_skill_step(session)
        required_points = 9 if session["data"]["race"] == "Humain" else 8

        try:
            self._apply_skill_distribution_values(session["data"], session["skill_step"]["values"], required_points)
        except ValueError as exc:
            reason = exc.args[0]
            if reason == "skill_points":
                await self._send_interaction_message(
                    interaction,
                    f"Vous devez distribuer exactement {required_points} points dans les compétences.",
                )
                return
            if isinstance(reason, str) and reason.startswith("skill_cap:"):
                _, skill_name, category = reason.split(":")
                await self._send_interaction_message(
                    interaction,
                    f"Le niveau de {skill_name} ne peut pas dépasser le niveau de {category[:3].upper()}.",
                )
                return
            await self._send_interaction_message(interaction, "Valeurs de compétences invalides.")
            return

        session.pop("skill_step", None)
        session["step"] = 5
        await self._send_creation_step_prompt(interaction, user_id)

    def _new_level_up_session(self, player_data):
        required_skill_points = 3 if player_data["race"] == "Humain" else 2
        skill_values = {}
        for category, skills_dict in player_data["skills"].items():
            skill_values[category] = {skill_name: 0 for skill_name in skills_dict}
        return {
            "data": copy.deepcopy(player_data),
            "target_level": player_data["level"] + 1,
            "selected_attribute": None,
            "required_skill_points": required_skill_points,
            "skill_values": skill_values,
        }

    def _build_level_up_attribute_embed(self, session):
        player_data = session["data"]
        target_level = session["target_level"]
        embed = discord.Embed(title=f"Montée de niveau vers {target_level}", color=discord.Color.gold())
        lines = []
        for attr_key in ("for", "agi", "cha", "int"):
            lines.append(f"{self.ATTRIBUTE_LABELS[attr_key]}: {player_data['attributes'][attr_key]}")
        embed.description = "Choisissez l'attribut à augmenter de +1.\n```text\n" + "\n".join(lines) + "\n```"
        return embed

    async def show_level_up_attribute_menu(self, interaction: Interaction, user_id: str):
        session = self.level_up_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune montée de niveau en cours. Lancez `/monter_niveau`.")
            return

        embed = self._build_level_up_attribute_embed(session)
        content = f"Distribuez 1 point d'attribut pour le niveau {session['target_level']}."
        view = LevelUpAttributeView(self, user_id)

        if interaction.response.is_done():
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(content=content, embed=embed, view=view)
            return
        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)

    async def handle_level_up_attribute_selection(self, interaction: Interaction, user_id: str, attr_key: str):
        session = self.level_up_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune montée de niveau en cours. Lancez `/monter_niveau`.")
            return

        if attr_key not in session["data"]["attributes"]:
            await self._send_interaction_message(interaction, "Attribut invalide.")
            return

        if session["selected_attribute"] is not None:
            await self._send_interaction_message(interaction, "Le point d'attribut est déjà distribué.", ephemeral=True)
            return

        session["data"]["attributes"][attr_key] += 1
        session["selected_attribute"] = attr_key
        await self.show_level_up_skill_main_menu(interaction, user_id)

    async def show_level_up_skill_main_menu(self, interaction: Interaction, user_id: str):
        session = self.level_up_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune montée de niveau en cours. Lancez `/monter_niveau`.")
            return

        if session["selected_attribute"] is None:
            await self.show_level_up_attribute_menu(interaction, user_id)
            return

        embed = self._build_skill_embed(
            session["data"],
            session["skill_values"],
            session["required_skill_points"],
            title_prefix=f"Niveau {session['target_level']} - Compétences",
        )
        attr_label = self.ATTRIBUTE_LABELS[session["selected_attribute"]]
        content = (
            f"Attribut choisi: {attr_label} +1.\n"
            f"Répartissez {session['required_skill_points']} points de compétence."
        )
        view = SkillDistributionView(
            self,
            user_id,
            open_category_handler=self.open_level_up_skill_category_panel,
            validate_handler=self.handle_level_up_validate,
        )

        if interaction.response.is_done():
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True)
            return
        if interaction.message:
            await interaction.response.edit_message(content=content, embed=embed, view=view)
            return
        await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)

    async def open_level_up_skill_category_panel(self, interaction: Interaction, user_id: str, category: str):
        session = self.level_up_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune montée de niveau en cours. Lancez `/monter_niveau`.")
            return

        if session["selected_attribute"] is None:
            await self.show_level_up_attribute_menu(interaction, user_id)
            return

        if category not in session["data"]["skills"]:
            await self._send_interaction_message(interaction, "Catégorie de compétence inconnue.")
            return

        embed = self._build_skill_embed(
            session["data"],
            session["skill_values"],
            session["required_skill_points"],
            selected_category=category,
            title_prefix=f"Niveau {session['target_level']} - Compétences",
        )
        skills = list(session["data"]["skills"][category].keys())
        content = "Utilisez les boutons pour modifier les compétences de cette catégorie, puis `Retour`."
        view = SkillCategoryView(
            self,
            user_id,
            category,
            skills,
            adjust_handler=self.handle_level_up_skill_adjust,
            back_handler=self.show_level_up_skill_main_menu,
        )
        await interaction.response.edit_message(content=content, embed=embed, view=view)

    async def handle_level_up_skill_adjust(
        self,
        interaction: Interaction,
        user_id: str,
        category: str,
        skill_name: str,
        delta: int,
    ):
        session = self.level_up_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune montée de niveau en cours. Lancez `/monter_niveau`.")
            return

        if session["selected_attribute"] is None:
            await self.show_level_up_attribute_menu(interaction, user_id)
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

        if delta > 0:
            allocated_points = count_allocated_skill_points(values)
            if allocated_points >= session["required_skill_points"]:
                await self._send_interaction_message(
                    interaction,
                    f"Tous les points sont déjà distribués ({session['required_skill_points']}/{session['required_skill_points']}).",
                    ephemeral=True,
                )
                return

        category_attr = session["data"]["attributes"][category[:3]]
        if updated_value > category_attr:
            await self._send_interaction_message(
                interaction,
                f"{display_skill_name(skill_name)} ne peut pas dépasser {category_attr} ({self.SKILL_CATEGORY_LABELS.get(category, category.upper())}).",
                ephemeral=True,
            )
            return

        values[category][skill_name] = updated_value
        embed = self._build_skill_embed(
            session["data"],
            session["skill_values"],
            session["required_skill_points"],
            selected_category=category,
            title_prefix=f"Niveau {session['target_level']} - Compétences",
        )
        skills = list(session["data"]["skills"][category].keys())
        content = "Utilisez les boutons pour modifier les compétences de cette catégorie, puis `Retour`."
        view = SkillCategoryView(
            self,
            user_id,
            category,
            skills,
            adjust_handler=self.handle_level_up_skill_adjust,
            back_handler=self.show_level_up_skill_main_menu,
        )
        await interaction.response.edit_message(content=content, embed=embed, view=view)

    async def handle_level_up_validate(self, interaction: Interaction, user_id: str):
        session = self.level_up_sessions.get(user_id)
        if not session:
            await self._send_interaction_message(interaction, "Aucune montée de niveau en cours. Lancez `/monter_niveau`.")
            return

        if session["selected_attribute"] is None:
            await self.show_level_up_attribute_menu(interaction, user_id)
            return

        try:
            self._apply_skill_distribution_values(
                session["data"],
                session["skill_values"],
                session["required_skill_points"],
            )
        except ValueError as exc:
            reason = exc.args[0]
            if reason == "skill_points":
                await self._send_interaction_message(
                    interaction,
                    f"Vous devez distribuer exactement {session['required_skill_points']} points dans les compétences.",
                )
                return
            if isinstance(reason, str) and reason.startswith("skill_cap:"):
                _, skill_name, category = reason.split(":")
                await self._send_interaction_message(
                    interaction,
                    f"Le niveau de {skill_name} ne peut pas dépasser le niveau de {category[:3].upper()}.",
                )
                return
            await self._send_interaction_message(interaction, "Valeurs de compétences invalides.")
            return

        player_data = session["data"]
        player_data["level"] = session["target_level"]
        for_attr = player_data["attributes"].get("for", 0)
        int_attr = player_data["attributes"].get("int", 0)
        pv_gain, pm_gain = compute_level_up_gain(player_data["level"], for_attr, int_attr)
        player_data["pv_max"] += pv_gain
        player_data["mana_max"] += pm_gain
        player_data["pv_actu"] = player_data["pv_max"]
        player_data["mana_actu"] = player_data["mana_max"]

        entity_label = player_data.get("name", "Le personnage")
        try:
            if session.get("scope") == "familier":
                owner_player_data = await self._load_player_or_none(user_id)
                if not owner_player_data:
                    await self._send_interaction_message(interaction, "Personnage propriétaire introuvable.")
                    return

                familier_data = self._resolve_familier_for_level_session(owner_player_data, session)
                if not familier_data:
                    await self._send_interaction_message(interaction, "Familier introuvable pour la sauvegarde.")
                    return

                self._apply_level_up_data_to_familier(familier_data, player_data)
                entity_label = familier_data["nom"]
                await asyncio.to_thread(update_player, user_id, owner_player_data)
            else:
                await asyncio.to_thread(update_player, user_id, player_data)
        except DatabaseError:
            await self._send_interaction_message(interaction, "Erreur lors de la sauvegarde du niveau gagné.")
            return
        self.level_up_sessions.pop(user_id, None)

        await interaction.response.edit_message(
            content=(
                f"Le niveau de {entity_label} passe à {player_data['level']}.\n"
                f"PV +{pv_gain}, PM +{pm_gain} | "
                f"PV max: {player_data['pv_max']} | PM max: {player_data['mana_max']}"
            ),
            embed=None,
            view=None,
        )

    async def handle_creation_magic_selection(self, interaction: Interaction, user_id: str, selected_magic: str, step: int):
        session = self.creation_sessions.get(user_id)
        if not session or session["step"] != step:
            await self._send_interaction_message(interaction, "Session de création invalide. Relancez `/creer_personnage`.")
            return

        if selected_magic in session["data"]["magie"]:
            await self._send_interaction_message(
                interaction,
                f"La magie {selected_magic} a déjà été choisie. Veuillez en choisir une autre.",
            )
            return

        session["data"]["magie"].append(selected_magic)
        session["step"] += 1
        await self._send_creation_step_prompt(interaction, user_id)

    @app_commands.command(name="creer", description="Crée un utilisateur joueur.")
    async def creer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        if not await asyncio.to_thread(load_user, user_id):
            try:
                await asyncio.to_thread(add_user, user_id)
            except DatabaseError:
                await interaction.response.send_message(embed=error_embed("Erreur lors de la création de l'utilisateur.", title="Personnage"))
                return
            await interaction.response.send_message(
                embed=success_embed(f"Utilisateur {interaction.user.mention} créé avec succès.", title="Personnage")
            )
            return
        await interaction.response.send_message(
            embed=warning_embed(f"Utilisateur {interaction.user.mention} existe déjà.", title="Personnage")
        )

    @app_commands.command(name="creer_personnage", description="Crée un nouveau personnage.")
    async def creer_personnage(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.creation_sessions:
            await self._send_creation_step_prompt(interaction, user_id)
            return
        self.creation_sessions[user_id] = {"step": 0, "data": new_character_template()}
        await self._send_creation_step_prompt(interaction, user_id)

    async def choisir_personnage_autocomplete(self, interaction: Interaction, current: str):
        user_id = interaction.user.id
        characters = await asyncio.to_thread(load_all_characters_by_user, user_id)
        names = [character["name"] for character in characters]
        return [app_commands.Choice(name=choice, value=choice) for choice in names if current.lower() in choice.lower()]

    async def familier_autocomplete(self, interaction: Interaction, current: str):
        target = getattr(interaction.namespace, "joueur", None)
        target_user_id = str(target.id) if target else str(interaction.user.id)
        player_data = await self._load_player_or_none(target_user_id)
        if not player_data:
            return []
        return [
            app_commands.Choice(name=familier_data["nom"], value=familier_data["nom"])
            for familier_data in player_data.get("familiers", [])
            if current.lower() in familier_data["nom"].lower()
        ]

    @app_commands.command(name="supprimer_personnage", description="Supprime un personnage.")
    @app_commands.describe(nom_personnage="Le nom du personnage à supprimer")
    @app_commands.autocomplete(nom_personnage=choisir_personnage_autocomplete)
    async def supprimer_personnage(self, interaction: Interaction, nom_personnage: str):
        user_id = str(interaction.user.id)
        if await asyncio.to_thread(remove_character, user_id, nom_personnage):
            await interaction.response.send_message(
                embed=success_embed(f"Le personnage {nom_personnage} a été supprimé.", title="Personnage")
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(f"Le personnage {nom_personnage} n'existe pas.", title="Personnage")
            )

    @app_commands.command(name="supprimer", description="Supprime un utilisateur et tous ses personnages.")
    async def supprimer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        user_data = await asyncio.to_thread(load_user, user_id)
        if not user_data:
            await interaction.response.send_message(
                embed=error_embed(f"Aucun utilisateur trouvé pour {interaction.user.mention}.", title="Personnage")
            )
            return
        if await asyncio.to_thread(remove_player, user_id):
            await interaction.response.send_message(
                embed=success_embed(f"Utilisateur {interaction.user.mention} supprimé avec succès.", title="Personnage")
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(f"Erreur lors de la suppression de {interaction.user.mention}.", title="Personnage")
            )

    @app_commands.command(name="liste_personnages", description="Affiche la liste de vos personnages.")
    async def liste_personnages(self, interaction: Interaction):
        user_id = interaction.user.id
        players = await asyncio.to_thread(load_all_characters_by_user, user_id)
        if not players:
            await interaction.response.send_message(
                embed=warning_embed("Vous n'avez aucun personnage.", title="Personnage")
            )
            return
        await interaction.response.send_message(
            embed=info_embed(build_character_list_message(players), title="Liste des personnages")
        )

    @app_commands.command(name="choisir_personnage", description="Choisit un personnage actif.")
    @app_commands.describe(nom_personnage="Le nom du personnage à choisir")
    @app_commands.autocomplete(nom_personnage=choisir_personnage_autocomplete)
    async def choisir_personnage(self, interaction: Interaction, nom_personnage: str):
        user_id = str(interaction.user.id)
        player = await asyncio.to_thread(load_character_by_name, user_id, nom_personnage)
        if not player:
            await interaction.response.send_message(embed=error_embed("Personnage non trouvé.", title="Personnage"))
            return
        await asyncio.to_thread(change_active_character, user_id, player["id"])
        await interaction.response.send_message(
            embed=success_embed(f"Le personnage {nom_personnage} est maintenant actif.", title="Personnage")
        )

    async def modifier_joueur_autocomplete(self, interaction: Interaction, current: str):
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in ATTRIBUTE_CHOICES
            if current.lower() in choice.lower()
        ]

    @app_commands.command(name="modifier_joueur", description="Modifie les détails d'un joueur.")
    @app_commands.describe(joueur="Le joueur à modifier (optionnel)", familier="Familier ciblé (optionnel)", champ="Champ à modifier", valeur="Nouvelle valeur")
    @app_commands.autocomplete(champ=modifier_joueur_autocomplete, familier=familier_autocomplete)
    async def modifier_joueur(
        self,
        interaction: Interaction,
        champ: str,
        valeur: str,
        joueur: discord.Member = None,
        familier: str = None,
    ):
        user_id = str(joueur.id) if joueur else str(interaction.user.id)
        player_data, data_root, _, error = await self._resolve_player_and_familier(user_id, familier)
        if error:
            await interaction.response.send_message(embed=error_embed(error, title="Personnage"))
            return

        if familier and champ in {"pv_actu", "pv_max", "mana_actu", "mana_max"}:
            champ = f"attributes.{champ}"

        try:
            keys = champ.split(".")
            data = data_root
            for key in keys[:-1]:
                data = data[key]
            current_value = data[keys[-1]]
            data[keys[-1]] = self._coerce_field_value(current_value, valeur)
        except KeyError:
            await interaction.response.send_message(embed=error_embed("Champ non valide.", title="Personnage"))
            return
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Valeur non valide pour ce champ.", title="Personnage"))
            return
        except TypeError:
            await interaction.response.send_message(embed=error_embed("Type de donnée invalide pour ce champ.", title="Personnage"))
            return

        await asyncio.to_thread(update_player, user_id, player_data)
        await interaction.response.send_message(
            embed=success_embed(f"Le champ {champ} a été mis à jour avec succès à {valeur}.", title="Personnage")
        )

    @app_commands.command(name="monter_niveau", description="Augmente le niveau d'un personnage actif.")
    @app_commands.describe(familier="Familier à faire monter de niveau (optionnel)")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def monter_niveau(self, interaction: Interaction, familier: str = None):
        user_id = str(interaction.user.id)
        if not await self._load_user_or_none(user_id):
            await interaction.response.send_message(embed=error_embed("Utilisateur non trouvé.", title="Niveau"))
            return

        if user_id in self.level_up_sessions:
            session = self.level_up_sessions[user_id]
            if familier and session.get("scope") == "familier" and session.get("familier_name") != familier:
                await interaction.response.send_message(
                    embed=warning_embed(
                        "Une autre montée de niveau de familier est déjà en cours. Terminez-la d'abord.",
                        title="Niveau",
                    ),
                    ephemeral=True,
                )
                return
            if familier and session.get("scope") == "joueur":
                await interaction.response.send_message(
                    embed=warning_embed(
                        "Une montée de niveau du personnage est déjà en cours. Terminez-la d'abord.",
                        title="Niveau",
                    ),
                    ephemeral=True,
                )
                return
            if session["selected_attribute"] is None:
                await self.show_level_up_attribute_menu(interaction, user_id)
            else:
                await self.show_level_up_skill_main_menu(interaction, user_id)
            return

        player_data, familier_data, _, error = await self._resolve_player_and_familier(user_id, familier)
        if error:
            if error == "Joueur non trouvé.":
                await interaction.response.send_message(embed=error_embed("Personnage non trouvé.", title="Niveau"))
            else:
                await interaction.response.send_message(embed=error_embed(error, title="Niveau"))
            return

        if familier_data is not player_data:
            session_data = self._build_level_up_data_from_familier(familier_data)
            new_session = self._new_level_up_session(session_data)
            new_session["scope"] = "familier"
            new_session["familier_id"] = familier_data.get("id")
            new_session["familier_name"] = familier_data["nom"]
        else:
            new_session = self._new_level_up_session(player_data)
            new_session["scope"] = "joueur"

        self.level_up_sessions[user_id] = new_session
        await self.show_level_up_attribute_menu(interaction, user_id)

    @app_commands.command(name="info", description="Affiche les informations du personnage actif.")
    @app_commands.describe(joueur="Le joueur dont vous voulez voir les informations", familier="Familier ciblé (optionnel)")
    @app_commands.autocomplete(familier=familier_autocomplete)
    async def info(self, interaction: Interaction, joueur: discord.Member = None, familier: str = None):
        user_id = str(joueur.id) if joueur else str(interaction.user.id)
        if not await self._load_user_or_none(user_id):
            await interaction.response.send_message(embed=error_embed("Utilisateur non trouvé.", title="Personnage"))
            return

        player_data, entity_data, is_familier, error = await self._resolve_player_and_familier(user_id, familier)
        if error:
            if error == "Joueur non trouvé.":
                await interaction.response.send_message(embed=error_embed("Personnage actif non trouvé.", title="Personnage"))
            else:
                await interaction.response.send_message(embed=error_embed(error, title="Personnage"))
            return

        try:
            displayed_data = build_familier_view_model(entity_data) if is_familier else player_data

            embed = build_base_info_embed(displayed_data)
            view = InfoNavigationView(user_id, displayed_data)
            await interaction.response.send_message(embed=embed, view=view)
        except (KeyError, TypeError):
            await interaction.response.send_message(
                embed=error_embed("Les données du personnage sont invalides.", title="Personnage")
            )


async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))
