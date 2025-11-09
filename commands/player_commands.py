import discord
from discord import app_commands, Interaction
from discord.ext import commands
from database import load_user,add_user, load_character_by_name,remove_player ,load_player, update_player, remove_player, load_all_characters_by_user, add_character, change_active_character, load_all_players, remove_character
import json
import discord.ui
import random
from config import ADMIN_IDS

class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.creation_sessions = {}
        self.creation_steps = [
            {"question": "Choisissez un nom pour votre personnage :", "options": []},
            {"question": "Choisissez un âge pour votre personnage :", "options": []},
            {"question": "Choisissez une race pour votre personnage :", "options": ["Humain", "Nain", "Elfe", "Gnome", "Demi-Orc", "Fée"]},
            {"question": "Distribuez 4 points dans les attributs (FOR, AGI, CHA, INT) :\nFormat: FOR 1, AGI 1, CHA 1, INT 1", "options": []},
            {"question": (
                "Distribuez 8 points dans les compétences (ou 9 si vous êtes humain) :\n"
                "Liste des compétences :\n"
                "FORCE: pugilat, arme_a_une_main, arme_a_deux_mains, arme_dhast, bouclier, athletisme\n"
                "AGILITE: arc, arbalete, arme_de_jet, esquive, larcin, furtivite\n"
                "CHARISME: persuasion, marchandage, performance, seduction, instinct, observation\n"
                "INTELLIGENCE: connaissance, medecine, alchimie, ingenierie, magie1, magie2\n"
                "Format: pugilat 1, arc 2, etc."
            ), "options": []},
            {"question": "Choisissez votre première magie :", "options": ["Magie arcanique", "Magie élémentaire", "Magie noire", "Magie sacrée", "Druidique", "Sorcellerie"]},
            {"question": "Choisissez votre deuxième magie :", "options": ["Magie arcanique", "Magie élémentaire", "Magie noire", "Magie sacrée", "Druidique", "Sorcellerie"]}
        ]
        self.RACE_BONUS = {
            "Humain": {"comp_bonus": 1, "attributes": {}, "skills": {}},
            "Nain": {"attributes": {"for": 1}, "skills": {"charisme": {"marchandage": 1}}},
            "Elfe": {"attributes": {"agi": 1}, "skills": {"agilite": {"arc": 1}}},
            "Gnome": {"attributes": {"int": 1}, "skills": {"intelligence": {"ingenierie": 1}}},
            "Demi-Orc": {"attributes": {"for": 1}, "skills": {"force": {"pugilat": 1}}},
            "Fée": {"attributes": {"cha": 1}, "skills": {}}
        }
    
    async def next_creation_step_new(self, channel, user_id):
        session = self.creation_sessions[user_id]
        step = session["step"]

        if step < len(self.creation_steps):
            question = self.creation_steps[step]["question"]
            options = self.creation_steps[step]["options"]

            if options:
                message = await channel.send(question + "\n" + "\n".join([f"{i+1}. {option}" for i, option in enumerate(options)]))
                for i in range(len(options)):
                    await message.add_reaction(str(i+1) + '\u20E3')
            else:
                await channel.send(question)
        else:
            player_data = session['data']
            level = player_data['level']
            for_attr = player_data['attributes'].get('for', 0)
            int_attr = player_data['attributes'].get('int', 0)

            player_data['pv_max'] = 5 + random.randint(1, 6) + for_attr + level
            player_data['mana_max'] = 5 + random.randint(1, 6) + int_attr + level
            player_data['pv_actu'] = player_data['pv_max']
            player_data['mana_actu'] = player_data['mana_max']

            add_character(user_id, player_data)
            await channel.send(f"Création de personnage terminée pour <@{user_id}> : {player_data}")
            del self.creation_sessions[user_id]

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
                if step == 0:
                    session["data"]["name"] = message.content
                elif step == 1:
                    try:
                        session["data"]["age"] = int(message.content)
                    except ValueError:
                        await message.channel.send("Veuillez entrer un nombre valide pour l'âge.")
                        return
                elif step == 3:
                    attributes = message.content.split(", ")
                    total_points = 0
                    temp_attributes = session["data"]["attributes"].copy()
                    try:
                        for attr in attributes:
                            attr_name, attr_value = attr.split()
                            attr_value = int(attr_value)
                            total_points += attr_value
                            if attr_name.lower() not in temp_attributes:
                                await message.channel.send(f"Attribut {attr_name} non reconnu.")
                                return
                            temp_attributes[attr_name.lower()] += attr_value
                    except ValueError:
                        await message.channel.send("Veuillez entrer des points valides pour les attributs.")
                        return
                    if total_points != 4:
                        await message.channel.send("Vous devez distribuer exactement 4 points dans les attributs.")
                        return
                    session["data"]["attributes"] = temp_attributes
                elif step == 4:
                    skills = message.content.lower().split(", ")
                    total_points = 0
                    skill_values = {}
                    try:
                        for skill in skills:
                            skill_name, skill_value = skill.split()
                            skill_value = int(skill_value)
                            total_points += skill_value

                            if skill_name not in skill_values:
                                skill_values[skill_name] = 0
                            skill_values[skill_name] += skill_value

                        required_points = 9 if session["data"]["race"] == "Humain" else 8
                        if total_points != required_points:
                            await message.channel.send(f"Vous devez distribuer exactement {required_points} points dans les compétences.")
                            return

                        temp_skills = session["data"]["skills"].copy()
                        for skill_name, skill_value in skill_values.items():
                            added = False
                            for category in temp_skills:
                                if skill_name in temp_skills[category]:
                                    if skill_value > session["data"]["attributes"][category[:3]]:
                                        await message.channel.send(f"Le niveau de {skill_name} ne peut pas dépasser le niveau de {category[:3].upper()}.")
                                        return
                                    temp_skills[category][skill_name] += skill_value
                                    added = True
                                    break
                            if not added:
                                await message.channel.send(f"Compétence {skill_name} non reconnue.")
                                return
                        session["data"]["skills"] = temp_skills
                    except ValueError:
                        await message.channel.send("Veuillez entrer des points valides pour les compétences.")
                        return

                session["step"] += 1
                await self.next_creation_step_new(message.channel, user_id)

        await self.bot.process_commands(message)
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        user_id = str(user.id)
        if user_id in self.creation_sessions:
            session = self.creation_sessions[user_id]
            step = session["step"]
            if step < len(self.creation_steps) and self.creation_steps[step]["options"]:
                options = self.creation_steps[step]["options"]
                emoji = reaction.emoji

                if emoji in [str(i + 1) + '\u20E3' for i in range(len(options))]:
                    selected_option = options[int(emoji[0]) - 1]
                    if step == 2:
                        session["data"]["race"] = selected_option
                        race_bonus = self.RACE_BONUS.get(selected_option, {})
                        for attr, bonus in race_bonus.get("attributes", {}).items():
                            session["data"]["attributes"][attr] += bonus
                        for category, skills in race_bonus.get("skills", {}).items():
                            for skill, bonus in skills.items():
                                session["data"]["skills"][category][skill] += bonus
                    elif step == 5 or step == 6:
                        if selected_option in session["data"]["magie"]:
                            await reaction.message.channel.send(f"La magie {selected_option} a déjà été choisie. Veuillez en choisir une autre.")
                            return
                        session["data"]["magie"].append(selected_option)

                    session["step"] += 1
                    await self.next_creation_step_new(reaction.message.channel, user_id)



    @app_commands.command(name="creer", description="Crée un utilisateur joueur.")
    async def creer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        if not load_user(user_id):
            add_user(user_id)
            await interaction.response.send_message(f"Utilisateur {interaction.user.mention} créé avec succès.")
        else:
            await interaction.response.send_message(f"Utilisateur {interaction.user.mention} existe déjà.")

    @app_commands.command(name="creer_personnage", description="Crée un nouveau personnage.")
    async def creer_personnage(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        self.creation_sessions[user_id] = {
            "step": 0,
            "data": {
                "name": "",
                "age": 0,
                "race": "",
                "level": 1,
                "attributes": {"for": 0, "agi": 0, "cha": 0, "int": 0},
                "skills": {
                    "force": {"pugilat": 0, "arme_a_une_main": 0, "arme_a_deux_mains": 0, "arme_dhast": 0, "bouclier": 0, "athletisme": 0},
                    "agilite": {"arc": 0, "arbalete": 0, "arme_de_jet": 0, "esquive": 0, "larcin": 0, "furtivite": 0},
                    "charisme": {"persuasion": 0, "marchandage": 0, "performance": 0, "seduction": 0, "instinct": 0, "observation": 0},
                    "intelligence": {"connaissance": 0, "medecine": 0, "alchimie": 0, "ingenierie": 0, "magie1": 0, "magie2": 0}
                },
                "magie": [],
                "pv_actu": 0,
                "pv_max": 0,
                "mana_actu": 0,
                "mana_max": 0,
                "inventory": {"argent": {"pc": 0, "pa": 0, "po": 0}, "armures": [], "armes": [], "autres_objets": []},
                "familiers": []
            }
        }
        await self.next_creation_step_new(interaction.channel, user_id)
    
    async def choisir_personnage_autocomplete(self, interaction: Interaction, current: str):
        user_id = interaction.user.id
        personnages = get_personnages(user_id)
        choices = [app_commands.Choice(name=choice, value=choice) for choice in personnages if current.lower() in choice.lower()]
        return choices
    
    @app_commands.command(name="supprimer_personnage", description="Supprime un personnage.")
    @app_commands.describe(nom_personnage="Le nom du personnage à supprimer")
    @app_commands.autocomplete(nom_personnage=choisir_personnage_autocomplete)
    async def supprimer_personnage(self, interaction: Interaction, nom_personnage: str):
        user_id = str(interaction.user.id)
        if remove_character(user_id, nom_personnage):
            await interaction.response.send_message(f"Le personnage {nom_personnage} a été supprimé.")
        else:
            await interaction.response.send_message(f"Le personnage {nom_personnage} n'existe pas.")
    
    @app_commands.command(name="supprimer", description="Supprime un utilisateur et tous ses personnages.")
    async def supprimer(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        
        user_data = load_user(user_id)
        if user_data:
            if remove_player(user_id):
                await interaction.response.send_message(f"Utilisateur {interaction.user.mention} supprimé avec succès.")
            else:
                await interaction.response.send_message(f"Erreur lors de la suppression de {interaction.user.mention}.")
        else:
            await interaction.response.send_message(f"Aucun utilisateur trouvé pour {interaction.user.mention}.")

    @app_commands.command(name="liste_personnages", description="Affiche la liste de vos personnages.")
    async def liste_personnages(self, interaction: Interaction):
        user_id = interaction.user.id
        players = load_all_characters_by_user(user_id)
        if not players:
            await interaction.response.send_message("Vous n'avez aucun personnage.")
            return

        message = "Voici la liste de vos personnages :\n"
        for player_data in players:
            message += f"- {player_data['name']} (Niveau {player_data['level']}, Race: {player_data['race']})\n"

        await interaction.response.send_message(message)


    @app_commands.command(name="choisir_personnage", description="Choisit un personnage actif.")
    @app_commands.describe(nom_personnage="Le nom du personnage à choisir")
    @app_commands.autocomplete(nom_personnage=choisir_personnage_autocomplete)
    async def choisir_personnage(self, interaction: Interaction, nom_personnage: str):
        user_id = str(interaction.user.id)
        player = load_character_by_name(user_id, nom_personnage)

        if not player:
            await interaction.response.send_message("Personnage non trouvé.")
            return

        change_active_character(user_id, player['id'])
        await interaction.response.send_message(f"Le personnage {nom_personnage} est maintenant actif.")


    async def modifier_joueur_autocomplete(self, interaction: Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in get_attribute_choices() if current.lower() in choice.lower()]
        return choices

    @app_commands.command(name="modifier_joueur", description="Modifie les détails d'un joueur.")
    @app_commands.describe(joueur="Le joueur à modifier (optionnel)", champ="Champ à modifier", valeur="Nouvelle valeur")
    @app_commands.autocomplete(champ=modifier_joueur_autocomplete)
    async def modifier_joueur(self, interaction: Interaction, champ: str, valeur: str, joueur: discord.Member = None):
        if joueur:
            user_id = joueur.id
        else:
            user_id = interaction.user.id
        
        player_data = load_player(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return
        try:
            keys = champ.split('.')
            data = player_data
            for key in keys[:-1]:
                data = data[key]
            data[keys[-1]] = type(data[keys[-1]])(valeur)
            update_player(user_id, player_data)
            await interaction.response.send_message(f"Le champ {champ} a été mis à jour avec succès à {valeur}.")
        except KeyError:
            await interaction.response.send_message(f"Champ non valide.{data}")
        except ValueError:
            await interaction.response.send_message("Valeur non valide pour ce champ.")
        except Exception as e:
            await interaction.response.send_message(f"Une erreur est survenue : {e}")


    @app_commands.command(name="monter_niveau", description="Augmente le niveau d'un personnage actif.")
    async def monter_niveau(self, interaction: Interaction):
        try:
            user_id = str(interaction.user.id)
            user_data = load_user(user_id)
            
            actif_id = user_data['actif_id']
            player_data = load_player(user_id)

            if not player_data:
                await interaction.response.send_message("Personnage non trouvé.")
                return

            # Augmenter le niveau
            player_data['level'] += 1
            niveau = player_data['level']

            await interaction.response.send_message(f"Vous avez monté au niveau {niveau}. Distribuez 1 point d'attribut et {2 if player_data['race'] != 'Humain' else 3} points de compétence.")

            # Demander l'attribut à augmenter
            await interaction.channel.send("Entrez l'attribut à augmenter (for, agi, cha, int) et la valeur à ajouter (1): exemple: int 1")
            msg = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
            attr, value = msg.content.split()
            player_data['attributes'][attr] += int(value)

            # Demander les compétences à augmenter
            await interaction.channel.send(f"Entrez les compétences à augmenter et les valeurs à ajouter ({2 if player_data['race'] != 'Humain' else 3} points) (par ex. pugilat 1, athletisme 1):")
            msg = await self.bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
            skills = msg.content.split(", ")
            total_points = 0

            try:
                for skill in skills:
                    skill_name, skill_value = skill.split()
                    skill_value = int(skill_value)
                    total_points += skill_value
                    added = False
                    for category in player_data['skills']:
                        if skill_name in player_data['skills'][category]:
                            if skill_value > player_data['attributes'][category[:3]]:
                                await interaction.channel.send(f"Le niveau de {skill_name} ne peut pas dépasser le niveau de {category[:3].upper()}.")
                                return
                            player_data['skills'][category][skill_name] += skill_value
                            added = True
                            break
                    if not added:
                        await interaction.channel.send(f"Compétence {skill_name} non reconnue.")
                        return
            except ValueError as ve:
                print(f"ValueError in skill processing: {ve}")
                await interaction.channel.send("Veuillez entrer des points valides pour les compétences.")
                return

            required_points = 3 if player_data['race'] == "Humain" else 2
            if total_points != required_points:
                await interaction.channel.send(f"Vous devez distribuer exactement {required_points} points dans les compétences.")
                return

            # Calcul des gains de PV et de mana
            for_attr = player_data['attributes'].get('for', 0)
            int_attr = player_data['attributes'].get('int', 0)

            if niveau <= 4:
                pv_gain = random.randint(1, 6) + for_attr + niveau
                pm_gain = random.randint(1, 6) + int_attr + niveau
            elif niveau <= 9:
                pv_gain = random.randint(1, 8) + 2 * for_attr + niveau
                pm_gain = random.randint(1, 8) + 2 * int_attr + niveau
            elif niveau <= 14:
                pv_gain = random.randint(1, 12) + 3 * for_attr + niveau
                pm_gain = random.randint(1, 12) + 3 * int_attr + niveau
            else:
                pv_gain = random.randint(1, 20) + 4 * for_attr + niveau
                pm_gain = random.randint(1, 20) + 4 * int_attr + niveau

            player_data['pv_max'] += pv_gain
            player_data['mana_max'] += pm_gain
            player_data['pv_actu'] = player_data['pv_max']
            player_data['mana_actu'] = player_data['mana_max']

            update_player(user_id, player_data)
            await interaction.channel.send(f"Le niveau de {player_data['name']} a été augmenté avec succès à {niveau}. PV max: {player_data['pv_max']}, PM max: {player_data['mana_max']}.")
        except Exception as e:
            print(f"Error in monter_niveau: {e}")
            await interaction.response.send_message("Une erreur est survenue lors de l'augmentation du niveau.")

    @app_commands.command(name="info", description="Affiche les informations du personnage actif.")
    @app_commands.describe(joueur="Le joueur dont vous voulez voir les informations")
    async def info(self, interaction: Interaction, joueur: discord.Member = None):
        try:
            user_id = str(joueur.id) if joueur else str(interaction.user.id)
            user_data = load_user(user_id)
            if not user_data:
                await interaction.response.send_message("Utilisateur non trouvé.")
                return

            player_data = load_player(user_id)
            if not player_data:
                await interaction.response.send_message("Personnage actif non trouvé.")
                return

            embed = get_base_info_embed(player_data)
            view = InfoNavigationView(user_id, player_data)
            await interaction.response.send_message(embed=embed, view=view)
        except Exception as e:
            print(f"Erreur: {e}")
            await interaction.response.send_message("Une erreur est survenue.")

def get_personnages(user_id):
        characters = load_all_characters_by_user(user_id)
        return [character['name'] for character in characters]

def get_attribute_choices():
        return [
            # Attributs de base
            "attributes.for", "attributes.agi", "attributes.cha", "attributes.int",
            # Compétences de force
            "skills.force.pugilat", "skills.force.arme_a_une_main", "skills.force.arme_a_deux_mains", 
            "skills.force.arme_dhast", "skills.force.bouclier", "skills.force.athletisme",
            # Compétences d'agilité
            "skills.agilite.arc", "skills.agilite.arbalete", "skills.agilite.arme_de_jet", 
            "skills.agilite.esquive", "skills.agilite.larcin", "skills.agilite.furtivite",
            # Compétences de charisme
            "skills.charisme.persuasion", "skills.charisme.marchandage", "skills.charisme.performance", 
            "skills.charisme.seduction", "skills.charisme.instinct", "skills.charisme.observation",
            # Compétences d'intelligence
            "skills.intelligence.connaissance", "skills.intelligence.medecine", "skills.intelligence.alchimie", 
            "skills.intelligence.ingenierie", "skills.intelligence.magie1", "skills.intelligence.magie2",
            # Points de vie et mana
            "pv_max", "mana_max"
        ]

def get_base_info_embed(player_data):
    embed = discord.Embed(title=f"{player_data['name']} - {player_data['race']}", color=discord.Color.blue())
    embed.add_field(name="HP", value=f"{player_data['pv_actu']}/{player_data['pv_max']} :heart:", inline=True)
    embed.add_field(name="MANA", value=f"{player_data['mana_actu']}/{player_data['mana_max']} :droplet:", inline=True)
    embed.add_field(name="Niveau", value=player_data['level'], inline=True)
    embed.add_field(name="Force", value=player_data['attributes']['for'], inline=True)
    embed.add_field(name="Intelligence", value=player_data['attributes']['int'], inline=True)
    embed.add_field(name="Agilité", value=player_data['attributes']['agi'], inline=True)
    embed.add_field(name="Charisme", value=player_data['attributes']['cha'], inline=True)

    argent = player_data['inventory']['argent']
    embed.add_field(
        name="Argent",
        value=f"{argent['pc']} <:copper_coin:1258085404779876422>  {argent['pa']} <:silver_coin:1258086833644896336>  {argent['po']} <:gold_coin:1258087444147077161>",
        inline=False
    )
    return embed

class InfoNavigationView(discord.ui.View):
    def __init__(self, user_id, player_data):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.player_data = player_data

    @discord.ui.button(label="📋 Stats", style=discord.ButtonStyle.success)
    async def stats_button(self, interaction: Interaction, button: discord.ui.Button):
        embed = get_base_info_embed(self.player_data)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🐾 Familiers", style=discord.ButtonStyle.primary)
    async def familiers_button(self, interaction: Interaction, button: discord.ui.Button):
        familiers = self.player_data['familiers']
        description = "\n".join([f"- {f['nom']}" for f in familiers]) or "Aucun familier"
        embed = discord.Embed(title="Familiers", description=description, color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🧠 Skills", style=discord.ButtonStyle.primary)
    async def skills_button(self, interaction: Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Compétences", color=discord.Color.green())
        for stat, values in self.player_data['skills'].items():
            content = "\n".join([f"{name}: {val}" for name, val in values.items()])
            embed.add_field(name=stat.capitalize(), value=content or "Aucune", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚔️ Équipement", style=discord.ButtonStyle.primary)
    async def equip_button(self, interaction: Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Équipement", color=discord.Color.green())
        armes = self.player_data['inventory']['armes']
        armures = self.player_data['inventory']['armures']
        armes_text = "\n".join([f"{a['nom']}: {a['description']} (+{a['bonus_value']} {a['bonus_type']})" for a in armes]) or "Aucune arme"
        armures_text = "\n".join([f"{a['nom']}: {a['description']} (+{a['bonus_value']} {a['bonus_type']})" for a in armures]) or "Aucune armure"
        embed.add_field(name="Armes", value=armes_text, inline=False)
        embed.add_field(name="Armures", value=armures_text, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🎒 Inventaire", style=discord.ButtonStyle.primary)
    async def inventaire_button(self, interaction: Interaction, button: discord.ui.Button):
        objets = self.player_data['inventory']['autres_objets']
        pages = [objets[i:i+20] for i in range(0, len(objets), 20)] or [[]]
        embed = self._get_inventory_embed(pages, 0)
        await interaction.response.edit_message(embed=embed, view=InventoryView(self.user_id, self.player_data, pages, 0))

    def _get_inventory_embed(self, pages, page):
        embed = discord.Embed(title=f"Inventaire - Page {page+1}/{len(pages)}", color=discord.Color.green())
        lines = [
            f"• {obj['nom']} : {obj['description']} (+{obj['bonus_value']} {obj['bonus_type']})"
            for obj in pages[page]
        ]
        embed.description = "\n".join(lines)
        return embed

class InventoryView(InfoNavigationView):
    def __init__(self, user_id, player_data, pages, current_page):
        super().__init__(user_id, player_data)
        self.pages = pages
        self.current_page = current_page

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def previous(self, interaction: Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page - 1) % len(self.pages)
        embed = self._get_inventory_embed(self.pages, self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=1)
    async def next(self, interaction: Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page + 1) % len(self.pages)
        embed = self._get_inventory_embed(self.pages, self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))
