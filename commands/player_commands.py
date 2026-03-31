import asyncio

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from commands.player_logic import (
    ATTRIBUTE_CHOICES,
    CREATION_STEPS,
    RACE_BONUS,
    apply_attribute_distribution,
    apply_race_bonus,
    apply_skill_distribution,
    build_base_info_embed,
    build_character_list_message,
    compute_level_up_gain,
    finalize_character_stats,
    new_character_template,
)
from commands.player_views import InfoNavigationView
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
    LEVEL_UP_TIMEOUT_SECONDS = 120

    def __init__(self, bot):
        self.bot = bot
        self.creation_sessions = {}
        self.creation_steps = CREATION_STEPS
        self.race_bonus = RACE_BONUS

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

    async def next_creation_step(self, channel, user_id):
        session = self.creation_sessions[user_id]
        step = session["step"]
        if step < len(self.creation_steps):
            question = self.creation_steps[step]["question"]
            options = self.creation_steps[step]["options"]
            if options:
                message = await channel.send(question + "\n" + "\n".join([f"{i + 1}. {option}" for i, option in enumerate(options)]))
                session["reaction_message_id"] = message.id
                session["channel_id"] = channel.id
                for i in range(len(options)):
                    await message.add_reaction(str(i + 1) + "\u20E3")
            else:
                session["reaction_message_id"] = None
                session["channel_id"] = channel.id
                await channel.send(question)
            return

        player_data = session["data"]
        finalize_character_stats(player_data)
        try:
            await asyncio.to_thread(add_character, user_id, player_data)
        except DatabaseError:
            await channel.send("Erreur lors de la sauvegarde du personnage.")
            del self.creation_sessions[user_id]
            return
        await channel.send(f"Création de personnage terminée pour <@{user_id}> : {player_data}")
        del self.creation_sessions[user_id]

    async def _handle_creation_text_step(self, message, session, step):
        if step == 0:
            session["data"]["name"] = message.content
            return True
        if step == 1:
            try:
                session["data"]["age"] = int(message.content)
            except ValueError:
                await message.channel.send("Veuillez entrer un nombre valide pour l'âge.")
                return False
            return True
        if step == 3:
            try:
                apply_attribute_distribution(session["data"], message.content)
            except ValueError:
                await message.channel.send("Vous devez distribuer exactement 4 points dans les attributs.")
                return False
            except KeyError as exc:
                await message.channel.send(f"Attribut {exc.args[0]} non reconnu.")
                return False
            return True
        if step == 4:
            try:
                apply_skill_distribution(session["data"], message.content)
            except ValueError as exc:
                reason = exc.args[0]
                if reason == "skill_points":
                    required_points = 9 if session["data"]["race"] == "Humain" else 8
                    await message.channel.send(f"Vous devez distribuer exactement {required_points} points dans les compétences.")
                    return False
                if isinstance(reason, str) and reason.startswith("skill_cap:"):
                    _, skill_name, category = reason.split(":")
                    await message.channel.send(
                        f"Le niveau de {skill_name} ne peut pas dépasser le niveau de {category[:3].upper()}."
                    )
                    return False
                await message.channel.send("Veuillez entrer des points valides pour les compétences.")
                return False
            except KeyError as exc:
                await message.channel.send(f"Compétence {exc.args[0]} non reconnue.")
                return False
            return True
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_id = str(message.author.id)
        if user_id in self.creation_sessions:
            session = self.creation_sessions[user_id]
            step = session["step"]
            current_step = self.creation_steps[step]
            if not current_step["options"]:
                is_valid = await self._handle_creation_text_step(message, session, step)
                if is_valid:
                    session["step"] += 1
                    await self.next_creation_step(message.channel, user_id)

        await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        user_id = str(user.id)
        if user_id not in self.creation_sessions:
            return

        session = self.creation_sessions[user_id]
        if reaction.message.channel.id != session.get("channel_id"):
            return
        if reaction.message.id != session.get("reaction_message_id"):
            return

        step = session["step"]
        if step >= len(self.creation_steps) or not self.creation_steps[step]["options"]:
            return

        options = self.creation_steps[step]["options"]
        emoji_choices = [str(i + 1) + "\u20E3" for i in range(len(options))]
        if reaction.emoji not in emoji_choices:
            return

        selected_option = options[int(reaction.emoji[0]) - 1]
        if step == 2:
            apply_race_bonus(session["data"], selected_option)
        elif step in (5, 6):
            if selected_option in session["data"]["magie"]:
                await reaction.message.channel.send(
                    f"La magie {selected_option} a déjà été choisie. Veuillez en choisir une autre."
                )
                return
            session["data"]["magie"].append(selected_option)

        session["step"] += 1
        await self.next_creation_step(reaction.message.channel, user_id)

    @app_commands.command(name="creer", description="Crée un utilisateur joueur.")
    async def creer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        if not await asyncio.to_thread(load_user, user_id):
            try:
                await asyncio.to_thread(add_user, user_id)
            except DatabaseError:
                await interaction.response.send_message("Erreur lors de la création de l'utilisateur.")
                return
            await interaction.response.send_message(f"Utilisateur {interaction.user.mention} créé avec succès.")
            return
        await interaction.response.send_message(f"Utilisateur {interaction.user.mention} existe déjà.")

    @app_commands.command(name="creer_personnage", description="Crée un nouveau personnage.")
    async def creer_personnage(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        self.creation_sessions[user_id] = {"step": 0, "data": new_character_template()}
        await self.next_creation_step(interaction.channel, user_id)

    async def choisir_personnage_autocomplete(self, interaction: Interaction, current: str):
        user_id = interaction.user.id
        characters = await asyncio.to_thread(load_all_characters_by_user, user_id)
        names = [character["name"] for character in characters]
        return [app_commands.Choice(name=choice, value=choice) for choice in names if current.lower() in choice.lower()]

    @app_commands.command(name="supprimer_personnage", description="Supprime un personnage.")
    @app_commands.describe(nom_personnage="Le nom du personnage à supprimer")
    @app_commands.autocomplete(nom_personnage=choisir_personnage_autocomplete)
    async def supprimer_personnage(self, interaction: Interaction, nom_personnage: str):
        user_id = str(interaction.user.id)
        if await asyncio.to_thread(remove_character, user_id, nom_personnage):
            await interaction.response.send_message(f"Le personnage {nom_personnage} a été supprimé.")
        else:
            await interaction.response.send_message(f"Le personnage {nom_personnage} n'existe pas.")

    @app_commands.command(name="supprimer", description="Supprime un utilisateur et tous ses personnages.")
    async def supprimer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        user_data = await asyncio.to_thread(load_user, user_id)
        if not user_data:
            await interaction.response.send_message(f"Aucun utilisateur trouvé pour {interaction.user.mention}.")
            return
        if await asyncio.to_thread(remove_player, user_id):
            await interaction.response.send_message(f"Utilisateur {interaction.user.mention} supprimé avec succès.")
        else:
            await interaction.response.send_message(f"Erreur lors de la suppression de {interaction.user.mention}.")

    @app_commands.command(name="liste_personnages", description="Affiche la liste de vos personnages.")
    async def liste_personnages(self, interaction: Interaction):
        user_id = interaction.user.id
        players = await asyncio.to_thread(load_all_characters_by_user, user_id)
        if not players:
            await interaction.response.send_message("Vous n'avez aucun personnage.")
            return
        await interaction.response.send_message(build_character_list_message(players))

    @app_commands.command(name="choisir_personnage", description="Choisit un personnage actif.")
    @app_commands.describe(nom_personnage="Le nom du personnage à choisir")
    @app_commands.autocomplete(nom_personnage=choisir_personnage_autocomplete)
    async def choisir_personnage(self, interaction: Interaction, nom_personnage: str):
        user_id = str(interaction.user.id)
        player = await asyncio.to_thread(load_character_by_name, user_id, nom_personnage)
        if not player:
            await interaction.response.send_message("Personnage non trouvé.")
            return
        await asyncio.to_thread(change_active_character, user_id, player["id"])
        await interaction.response.send_message(f"Le personnage {nom_personnage} est maintenant actif.")

    async def modifier_joueur_autocomplete(self, interaction: Interaction, current: str):
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in ATTRIBUTE_CHOICES
            if current.lower() in choice.lower()
        ]

    @app_commands.command(name="modifier_joueur", description="Modifie les détails d'un joueur.")
    @app_commands.describe(joueur="Le joueur à modifier (optionnel)", champ="Champ à modifier", valeur="Nouvelle valeur")
    @app_commands.autocomplete(champ=modifier_joueur_autocomplete)
    async def modifier_joueur(self, interaction: Interaction, champ: str, valeur: str, joueur: discord.Member = None):
        user_id = joueur.id if joueur else interaction.user.id
        player_data = await asyncio.to_thread(load_player, user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        try:
            keys = champ.split(".")
            data = player_data
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

    @app_commands.command(name="monter_niveau", description="Augmente le niveau d'un personnage actif.")
    async def monter_niveau(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        if not await asyncio.to_thread(load_user, user_id):
            await interaction.response.send_message("Utilisateur non trouvé.")
            return

        player_data = await asyncio.to_thread(load_player, user_id)
        if not player_data:
            await interaction.response.send_message("Personnage non trouvé.")
            return

        player_data["level"] += 1
        niveau = player_data["level"]
        await interaction.response.send_message(
            f"Vous avez monté au niveau {niveau}. Distribuez 1 point d'attribut et {2 if player_data['race'] != 'Humain' else 3} points de compétence."
        )

        try:
            await interaction.channel.send("Entrez l'attribut à augmenter (for, agi, cha, int) et la valeur à ajouter (1): exemple: int 1")
            msg = await self.bot.wait_for(
                "message",
                timeout=self.LEVEL_UP_TIMEOUT_SECONDS,
                check=lambda m: m.author == interaction.user and m.channel == interaction.channel,
            )
            attr, value = msg.content.split()
            player_data["attributes"][attr] += int(value)

            await interaction.channel.send(
                f"Entrez les compétences à augmenter et les valeurs à ajouter ({2 if player_data['race'] != 'Humain' else 3} points) (par ex. pugilat 1, athletisme 1):"
            )
            msg = await self.bot.wait_for(
                "message",
                timeout=self.LEVEL_UP_TIMEOUT_SECONDS,
                check=lambda m: m.author == interaction.user and m.channel == interaction.channel,
            )
            skills = msg.content.split(", ")
            total_points = 0
            for skill in skills:
                skill_name, skill_value = skill.split()
                skill_value = int(skill_value)
                total_points += skill_value
                for category in player_data["skills"]:
                    if skill_name in player_data["skills"][category]:
                        if skill_value > player_data["attributes"][category[:3]]:
                            await interaction.channel.send(
                                f"Le niveau de {skill_name} ne peut pas dépasser le niveau de {category[:3].upper()}."
                            )
                            return
                        player_data["skills"][category][skill_name] += skill_value
                        break
                else:
                    await interaction.channel.send(f"Compétence {skill_name} non reconnue.")
                    return
        except ValueError:
            await interaction.channel.send("Veuillez entrer des points valides pour l'attribut et les compétences.")
            return
        except asyncio.TimeoutError:
            await interaction.channel.send(
                f"Temps écoulé ({self.LEVEL_UP_TIMEOUT_SECONDS}s). Recommencez la commande /monter_niveau."
            )
            return
        except (KeyError, TypeError):
            await interaction.channel.send("Format de données joueur invalide.")
            return

        required_points = 3 if player_data["race"] == "Humain" else 2
        if total_points != required_points:
            await interaction.channel.send(f"Vous devez distribuer exactement {required_points} points dans les compétences.")
            return

        for_attr = player_data["attributes"].get("for", 0)
        int_attr = player_data["attributes"].get("int", 0)
        pv_gain, pm_gain = compute_level_up_gain(niveau, for_attr, int_attr)
        player_data["pv_max"] += pv_gain
        player_data["mana_max"] += pm_gain
        player_data["pv_actu"] = player_data["pv_max"]
        player_data["mana_actu"] = player_data["mana_max"]
        await asyncio.to_thread(update_player, user_id, player_data)
        await interaction.channel.send(
            f"Le niveau de {player_data['name']} a été augmenté avec succès à {niveau}. PV max: {player_data['pv_max']}, PM max: {player_data['mana_max']}."
        )

    @app_commands.command(name="info", description="Affiche les informations du personnage actif.")
    @app_commands.describe(joueur="Le joueur dont vous voulez voir les informations")
    async def info(self, interaction: Interaction, joueur: discord.Member = None):
        user_id = str(joueur.id) if joueur else str(interaction.user.id)
        if not await asyncio.to_thread(load_user, user_id):
            await interaction.response.send_message("Utilisateur non trouvé.")
            return

        player_data = await asyncio.to_thread(load_player, user_id)
        if not player_data:
            await interaction.response.send_message("Personnage actif non trouvé.")
            return

        try:
            embed = build_base_info_embed(player_data)
            view = InfoNavigationView(user_id, player_data)
            await interaction.response.send_message(embed=embed, view=view)
        except (KeyError, TypeError):
            await interaction.response.send_message("Les données du personnage sont invalides.")


async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))
