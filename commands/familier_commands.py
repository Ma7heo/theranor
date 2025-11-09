import discord
from discord import app_commands
from discord.ext import commands
from database import load_player, update_player
from utils import roll_d100, roll_d20, roll_dice, parse_dice_expression, roll_with_bonus
from config import ADMIN_IDS

class FamilierCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ajouter_familier", description="Ajoute un familier à un joueur.")
    @app_commands.describe(joueur="Le joueur à qui ajouter un familier", nom="Nom du familier", niveau="Niveau du familier", for_="Force du familier", agi="Agilité du familier", cha="Charisme du familier", int_="Intelligence du familier", pv_max="Points de vie maximum du familier", mana_max="Points de mana maximum du familier", compétences="Compétences du familier")
    async def ajouter_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom: str, niveau: int, for_: int, agi: int, cha: int, int_: int, pv_max: int, mana_max: int, compétences: str):
        if str(interaction.user.id) not in ADMIN_IDS:
            await interaction.response.send_message("Vous n'êtes pas autorisé à utiliser cette commande.")
            return

        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        skills_dict = {
            "force": {"pugilat": 0, "arme_a_une_main": 0, "arme_a_deux_mains": 0, "arme_dhast": 0, "bouclier": 0, "athletisme": 0},
            "agilite": {"arc": 0, "arbalete": 0, "arme_de_jet": 0, "esquive": 0, "larcin": 0, "furtivite": 0},
            "charisme": {"persuasion": 0, "marchandage": 0, "performance": 0, "seduction": 0, "instinct": 0, "observation": 0},
            "intelligence": {"connaissance": 0, "medecine": 0, "alchimie": 0, "ingenierie": 0, "magie1": 0, "magie2": 0}
        }

        try:
            for competence in compétences.split(","):
                skill_name, skill_value = competence.split(":")
                skill_value = int(skill_value)
                added = False
                for category in skills_dict:
                    if skill_name.strip() in skills_dict[category]:
                        skills_dict[category][skill_name.strip()] = skill_value
                        added = True
                        break
                if not added:
                    await interaction.response.send_message(f"Compétence {skill_name} non reconnue.")
                    return
        except ValueError:
            await interaction.response.send_message("Format de compétence invalide. Utilisez le format 'compétence:valeur'.")
            return

        familier = {
            "nom": nom,
            "niveau": niveau,
            "attributes": {"for": for_, "agi": agi, "cha": cha, "int": int_, "pv_max": pv_max, "mana_max": mana_max, "pv_actu": pv_max, "mana_actu": mana_max},
            "skills": skills_dict,
            "inventory": {"argent": {"pc": 0, "pa": 0, "po": 0}, "armures": [], "armes": [], "autres_objets": []}
        }

        player_data['familiers'].append(familier)
        update_player(player_id, player_data)

        await interaction.response.send_message(f"Le familier {nom} a été ajouté au joueur {joueur.mention}.")

    def get_familier_choices(self, player_data):
        return [f["nom"] for f in player_data.get("familiers", [])]

    def get_familier_action_choices(self, familier):
        attribute_choices = list(familier['attributes'].keys())
        skill_choices = []
        for category, skills in familier['skills'].items():
            skill_choices.extend(skills.keys())
        return attribute_choices + skill_choices

    async def familier_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
        choices = [app_commands.Choice(name=familier, value=familier) for familier in self.get_familier_choices(player_data) if current.lower() in familier.lower()]
        return choices

    async def action_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
        familier_name = interaction.namespace.nom_familier
        familier = next((f for f in player_data.get("familiers", []) if f["nom"] == familier_name), None)

        if familier:
            action_choices = self.get_familier_action_choices(familier)
            choices = [app_commands.Choice(name=action, value=action) for action in action_choices if current.lower() in action.lower()]
            return choices
        else:
            return []

    @app_commands.command(name="familier", description="Utilise une action avec un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, action=action_autocomplete)
    async def familier(self, interaction: discord.Interaction, nom_familier: str, action: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familiers = player_data.get("familiers", [])
        familier = next((f for f in familiers if f["nom"] == nom_familier), None)

        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        action_choices = self.get_familier_action_choices(familier)
        if action not in action_choices:
            await interaction.response.send_message("Action non reconnue.")
            return

        result_message = handle_roll_command(action, familier)

        await interaction.response.send_message(result_message)


    @app_commands.command(name="init_familier", description="Effectue un jet d'initiative pour le familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def init_familier(self, interaction: discord.Interaction, nom_familier: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familiers = player_data.get("familiers", [])
        familier = next((f for f in familiers if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        agi = familier['attributes'].get('agi', 0)
        initiative = roll_d20() + agi
        await interaction.response.send_message(f"Initiative de {familier['nom']}: 1d20 + {agi} = {initiative}")

    @app_commands.command(name="armure_familier", description="Effectue un jet d'armure pour réduire les dégâts du familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def armure_familier(self, interaction: discord.Interaction, nom_familier: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
    
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return
    
        familiers = player_data.get("familiers", [])
        familier = next((f for f in familiers if f["nom"].lower() == nom_familier.lower()), None)
    
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return
    
        armure = familier['attributes'].get('armure', 0)
        bonus_armures = sum(
            item['bonus_value'] for item in familier['inventory']['armures']
        )
        bonus_bouclier = sum(
            item['bonus_value'] for item in familier['inventory']['autres_objets'] if item['bonus_type'] == 'bouclier'
        )
        roll = roll_d100()
        total = roll - armure - bonus_armures - bonus_bouclier
    
        success = total < 0
        message = f"Armure de {familier['nom']}: 1d100 - {armure} - {bonus_armures} - {bonus_bouclier} = {total}"
        if success:
            message += "\nSuccès! Le familier prendra moitié moins de dégâts."
        else:
            message += "\nÉchec! Le familier prendra les dégâts complets."
    
        await interaction.response.send_message(message)
    
    @app_commands.command(name="info_familier", description="Affiche les informations du familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def info_familier(self, interaction: discord.Interaction, nom_familier: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
    
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return
    
        familiers = player_data.get("familiers", [])
        familier = next((f for f in familiers if f["nom"].lower() == nom_familier.lower()), None)
    
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return
    
        embed = discord.Embed(title=f"{familier['nom']}", color=discord.Color.green())
        embed.add_field(name="HP", value=f"{familier['attributes']['pv_actu']}/{familier['attributes']['pv_max']} :heart:", inline=True)
        embed.add_field(name="MANA", value=f"{familier['attributes']['mana_actu']}/{familier['attributes']['mana_max']} :droplet:", inline=True)
        embed.add_field(name="Niveau", value=f"{familier['niveau']}", inline=True)
    
        skills = familier['skills']
        attributes = familier['attributes']
    
        # Compétences et attributs
        force_skills = "\n".join([f"{key}: {value}" for key, value in skills['force'].items()])
        agilite_skills = "\n".join([f"{key}: {value}" for key, value in skills['agilite'].items()])
        charisme_skills = "\n".join([f"{key}: {value}" for key, value in skills['charisme'].items()])
        intelligence_skills = "\n".join([f"{key}: {value}" for key, value in skills['intelligence'].items()])
    
        embed.add_field(name=f"Force: {attributes['for']} :muscle:", value=force_skills, inline=True)
        embed.add_field(name=f"Agilité: {attributes['agi']} :person_running:", value=agilite_skills, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # Champ vide pour équilibrer les colonnes
        embed.add_field(name=f"Charisme: {attributes['cha']} :smiley:", value=charisme_skills, inline=True)
        embed.add_field(name=f"Intelligence: {attributes['int']} :brain:", value=intelligence_skills, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # Champ vide pour équilibrer les colonnes
    
        # Magies
        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Champ vide pour espacement
        magie = "\n".join(familier.get('magie', []))
        embed.add_field(name="Magies", value=magie if magie else "Aucune magie", inline=False)
    
        # Inventaire
        embed.add_field(name="\u200b", value="\u200b", inline=False)  # Champ vide pour espacement
        embed.add_field(name="Inventaire", value="\u200b", inline=False)
        argent = familier['inventory']['argent']
        armures = "\n".join([f"{armor['nom']}: {armor['description']} (Bonus: {armor['bonus_value']} {armor['bonus_type']})" for armor in familier['inventory']['armures']])
        armes = "\n".join([f"{weapon['nom']}: {weapon['description']} (Bonus: {weapon['bonus_value']} {weapon['bonus_type']})" for weapon in familier['inventory']['armes']])
        autres_objets = "\n".join([f"{obj['nom']}: {obj['description']} (Bonus: {obj['bonus_value']} {obj['bonus_type']})" for obj in familier['inventory']['autres_objets']])
    
        embed.add_field(name="Argent", value=f"{argent['pc']} <pc_emoji_id> {argent['pa']} <pa_emoji_id> {argent['po']} <po_emoji_id>", inline=False)
        embed.add_field(name="Armures", value=armures if armures else "Aucune armure", inline=False)
        embed.add_field(name="Armes", value=armes if armes else "Aucune arme", inline=False)
        embed.add_field(name="Autres objets", value=autres_objets if autres_objets else "Aucun autre objet", inline=False)
    
        await interaction.response.send_message(embed=embed)


    def get_weapon_choices(self, familier):
        return [w["nom"] for w in familier.get("inventory", {}).get("armes", [])]+ ["pugilat"]


    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
        nom_familier = interaction.namespace.nom_familier
        familier = next((f for f in player_data.get("familiers", []) if f["nom"] == nom_familier), None)
        if familier:
            choices = [app_commands.Choice(name=weapon, value=weapon) for weapon in self.get_weapon_choices(familier) if current.lower() in weapon.lower()]
        else:
            choices = []
        return choices

    @app_commands.command(name="attaquer_familier", description="Attaque avec un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, weapon_name=weapon_autocomplete)
    async def attaquer_familier(self, interaction: discord.Interaction, nom_familier: str, weapon_name: str, degats: int = 0, portee: int = 0, saignement: int = 0, modification_zone: int = 0, cible_supplementaire: int = 0, etourdissement: int = 0, parade: int = 0, deplacement: int = 0, difficulte_crit: int = 0):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familiers = player_data.get("familiers", [])
        familier = next((f for f in familiers if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        if weapon_name.lower() == "pugilat":
            skill_name = "pugilat"
            category = "force"
            attribute = "for"
        else:
            weapon = next((w for w in familier['inventory']['armes'] if w['nom'] == weapon_name), None)
            if not weapon:
                await interaction.response.send_message("Arme non trouvée pour le familier.")
                return
            skill_name = weapon['bonus_type']
            category = None
            if skill_name in familier['skills']['force']:
                category = 'force'
                attribute = 'for'
            elif skill_name in familier['skills']['agilite']:
                category = 'agilite'
                attribute = 'agi'
            elif skill_name in familier['skills']['intelligence']:
                category = 'intelligence'
                attribute = 'int'
            elif skill_name in familier['skills']['charisme']:
                category = 'charisme'
                attribute = 'cha'
            else:
                await interaction.response.send_message("Compétence non reconnue pour le familier.")
                return

        # Calculer les points de mana nécessaires
        total_effects = sum([degats, portee, saignement, modification_zone, cible_supplementaire, etourdissement, parade, deplacement, difficulte_crit])
        points_mana = total_effects * 2
        if total_effects>0:
            use_mana, _ = parse_dice_expression(f"{total_effects}d6")
        else:
            use_mana = 0
        # Vérifier les points de compétence disponibles
        skill_level = familier['skills'][category][skill_name]
        if points_mana > skill_level:
            await interaction.response.send_message(f"Le familier n'a pas assez de points de compétence. Compétence actuelle: {skill_level}, points requis: {points_mana}")
            return

        # Vérifier les points de mana disponibles
        if familier['attributes']['mana_actu'] < use_mana:
            await interaction.response.send_message("Mana insuffisant pour le familier.")
            return

        # Accuser réception de la commande
        await interaction.response.defer()

        # Réduire le mana du familier
        familier['attributes']['mana_actu'] -= use_mana
        update_player(user_id, player_data)

        # Préparer le message de réponse
        response_message = []

        # Lancer de base
        base_roll, bonus, total = roll_with_bonus(familier, skill_name, category)
        response_message.append(f"Lancer de dé pour toucher avec {weapon_name} par le familier {nom_familier}: {base_roll} + {bonus} = {total}")

        # Calculer les dégâts
        if weapon_name.lower() == "pugilat":
            damage_expression = f"{skill_level}d4"
        else:
            damage_expression = weapon.get('degats', '0d0')

        damage_roll, _ = parse_dice_expression(damage_expression)
        attribute_bonus = familier['attributes'].get(attribute, 0)
        total_damage = damage_roll + attribute_bonus

        # Appliquer les effets des techniques de combat
        if degats > 0:
            extra_damage_roll, _ = parse_dice_expression(f"{degats}d6")
            total_damage += extra_damage_roll
        if portee > 0:
            response_message.append(f"Portée augmentée de {portee * 10} mètres.")
        if saignement > 0:
            response_message.append("Effet de saignement appliqué.")
        if modification_zone > 0:
            response_message.append("Zone de combat modifiée.")
        if cible_supplementaire > 0:
            response_message.append("Cible supplémentaire attaquée.")
        if etourdissement > 0:
            response_message.append("Effet d'étourdissement appliqué.")
        if parade > 0:
            response_message.append(f"Bonus de parade de {parade * 10} appliqué.")
        if deplacement > 0:
            response_message.append(f"Déplacement augmenté de {deplacement * 10} mètres.")
        if difficulte_crit > 0:
            response_message.append(f"Difficulté de critique réduite de {difficulte_crit * 5}.")

        response_message.append(f"Dégâts avec {weapon_name} par le familier {nom_familier}: {total_damage}")
        await interaction.followup.send("\n".join(response_message))

    def get_item_choices(self, player_data, categorie):
        return [item["nom"] for item in player_data["inventory"].get(categorie, [])]
    
    async def familier_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
        choices = [app_commands.Choice(name=familier, value=familier) for familier in self.get_familier_choices(player_data) if current.lower() in familier.lower()]
        return choices
    
    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        categories = ["armures", "armes", "autres_objets"]
        choices = [app_commands.Choice(name=category, value=category) for category in categories if current.lower() in category.lower()]
        return choices
    
    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
        categorie = interaction.namespace.categorie
        choices = [app_commands.Choice(name=item, value=item) for item in self.get_item_choices(player_data, categorie) if current.lower() in item.lower()]
        return choices
    
    @app_commands.command(name="perdre_pv_familier", description="Fait perdre des PV à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def perdre_pv_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, degats: str):
        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        # Rechercher le familier par son nom
        familier = next((f for f in player_data.get('familiers', []) if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message(f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True)
            return

        # Calculer les dégâts
        degats_total, _ = parse_dice_expression(degats)

        # Réduire les PV
        familier['attributes']['pv_actu'] -= degats_total
        if familier['attributes']['pv_actu'] < 0:
            familier['attributes']['pv_actu'] = 0  # Empêcher les PV négatifs

        # Sauvegarder les modifications
        update_player(player_id, player_data)
        await interaction.response.send_message(f"{degats_total} PV retirés à {nom_familier}. PV restants: {familier['attributes']['pv_actu']}/{familier['attributes']['pv_max']}.", ephemeral=True)

    @app_commands.command(name="soigner_familier", description="Soigne un familier en lui redonnant des PV.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def soigner_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, soin: str):
        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        # Rechercher le familier par son nom
        familier = next((f for f in player_data.get('familiers', []) if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message(f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True)
            return

        # Calculer le soin
        soin_total, _ = parse_dice_expression(soin)

        # Augmenter les PV
        familier['attributes']['pv_actu'] += soin_total
        if familier['attributes']['pv_actu'] > familier['attributes']['pv_max']:
            familier['attributes']['pv_actu'] = familier['attributes']['pv_max']  # Empêcher les PV de dépasser le maximum

        # Sauvegarder les modifications
        update_player(player_id, player_data)
        await interaction.response.send_message(f"{soin_total} PV ajoutés à {nom_familier}. PV actuels: {familier['attributes']['pv_actu']}/{familier['attributes']['pv_max']}.", ephemeral=True)

    @app_commands.command(name="perdre_mana_familier", description="Fait perdre du mana à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def perdre_mana_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, cout_mana: str):
        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        # Rechercher le familier par son nom
        familier = next((f for f in player_data.get('familiers', []) if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message(f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True)
            return

        # Calculer le coût en mana
        cout_total, _ = parse_dice_expression(cout_mana)

        # Réduire le mana
        familier['attributes']['mana_actu'] -= cout_total
        if familier['attributes']['mana_actu'] < 0:
            familier['attributes']['mana_actu'] = 0  # Empêcher le mana négatif

        # Sauvegarder les modifications
        update_player(player_id, player_data)
        await interaction.response.send_message(f"{cout_total} mana retirés à {nom_familier}. Mana restants: {familier['attributes']['mana_actu']}/{familier['attributes']['mana_max']}.", ephemeral=True)

    @app_commands.command(name="ajouter_mana_familier", description="Ajoute du mana à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def ajouter_mana_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str, mana_ajoute: str):
        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        # Rechercher le familier par son nom
        familier = next((f for f in player_data.get('familiers', []) if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message(f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True)
            return

        # Calculer le mana ajouté
        mana_total, _ = parse_dice_expression(mana_ajoute)

        # Augmenter le mana
        familier['attributes']['mana_actu'] += mana_total
        if familier['attributes']['mana_actu'] > familier['attributes']['mana_max']:
            familier['attributes']['mana_actu'] = familier['attributes']['mana_max']  # Empêcher le mana de dépasser le maximum

        # Sauvegarder les modifications
        update_player(player_id, player_data)
        await interaction.response.send_message(f"{mana_total} mana ajoutés à {nom_familier}. Mana actuels: {familier['attributes']['mana_actu']}/{familier['attributes']['mana_max']}.", ephemeral=True)

    
    @app_commands.command(name="donner_objet_familier", description="Donne un objet à un familier.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, categorie=category_autocomplete, nom=item_autocomplete)
    async def donner_objet_familier(self, interaction: discord.Interaction, nom_familier: str, categorie: str, nom: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
    
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return
    
        familiers = player_data.get("familiers", [])
        familier = next((f for f in familiers if f["nom"] == nom_familier), None)
    
        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return
    
        if categorie not in ["armures", "armes", "autres_objets"]:
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return
    
        objet_trouve = False
        for objet in player_data["inventory"][categorie]:
            if objet["nom"] == nom:
                player_data["inventory"][categorie].remove(objet)
                objet_trouve = True
                break
            
        if not objet_trouve:
            await interaction.response.send_message(f"L'objet {nom} n'a pas été trouvé dans votre inventaire.")
            return
    
        familier["inventory"][categorie].append(objet)
        update_player(user_id, player_data)
    
        await interaction.response.send_message(f"Vous avez donné {nom} à votre familier {nom_familier}.")

    async def item_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
        nom_familier = interaction.namespace.nom_familier
        categorie = interaction.namespace.categorie
        familier = next((f for f in player_data.get("familiers", []) if f["nom"] == nom_familier), None)
        if familier:
            choices = [app_commands.Choice(name=item, value=item) for item in self.get_item_choices(familier, categorie) if current.lower() in item.lower()]
        else:
            choices = []
        return choices

    @app_commands.command(name="rendre_objet_familier", description="Rend un objet du familier au joueur.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete, categorie=category_autocomplete, nom=item_familier_autocomplete)
    async def rendre_objet_familier(self, interaction: discord.Interaction, nom_familier: str, categorie: str, nom: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        familiers = player_data.get("familiers", [])
        familier = next((f for f in familiers if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message("Familier non trouvé.")
            return

        if categorie not in ["armures", "armes", "autres_objets"]:
            await interaction.response.send_message("Catégorie invalide. Utilisez 'armures', 'armes' ou 'autres_objets'.")
            return

        objet_trouve = False
        for objet in familier["inventory"][categorie]:
            if objet["nom"] == nom:
                familier["inventory"][categorie].remove(objet)
                player_data["inventory"][categorie].append(objet)
                update_player(user_id, player_data)
                objet_trouve = True
                break

        if not objet_trouve:
            await interaction.response.send_message(f"Objet {nom} non trouvé dans l'inventaire du familier {nom_familier}.")
            return

        await interaction.response.send_message(f"Objet {nom} rendu du familier {nom_familier} au joueur {interaction.user.mention}.")

    @app_commands.command(name="supprimer_familier", description="Supprime un familier d'un joueur.")
    @app_commands.autocomplete(nom_familier=familier_autocomplete)
    async def supprimer_familier(self, interaction: discord.Interaction, joueur: discord.Member, nom_familier: str):
        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message(f"Joueur {joueur.mention} non trouvé.", ephemeral=True)
            return

        # Rechercher le familier par son nom
        familiers = player_data.get('familiers', [])
        familier = next((f for f in familiers if f["nom"].lower() == nom_familier.lower()), None)

        if not familier:
            await interaction.response.send_message(f"Familier {nom_familier} non trouvé pour le joueur {joueur.mention}.", ephemeral=True)
            return

        # Supprimer le familier
        player_data['familiers'].remove(familier)

        # Sauvegarder les modifications
        update_player(player_id, player_data)
        await interaction.response.send_message(f"Le familier {nom_familier} a été supprimé pour le joueur {joueur.mention}.", ephemeral=True)

    async def modifier_familier_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in get_attribute_choices() if current.lower() in choice.lower()]
        return choices

    @app_commands.command(name="modifier_familier", description="Modifie les détails d'un familier.")
    @app_commands.describe(joueur="Le joueur à modifier", familier ="Le familier à modifier", champ="Champ à modifier", valeur="Nouvelle valeur")
    @app_commands.autocomplete(familier=familier_autocomplete, champ=modifier_familier_autocomplete)
    async def modifier_familier(self, interaction: discord.Interaction, joueur: discord.Member, familier: str, champ: str, valeur: str):

        user_id = interaction.user.id
        
        player_data = load_player(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return
        familiers = player_data.get('familiers', [])
        familier = next((f for f in familiers if f["nom"].lower() == familier.lower()), None)
        try:
            keys = champ.split('.')
            data = familier
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
    


async def setup(bot):
    await bot.add_cog(FamilierCommands(bot))

def handle_roll_command(action, entity_data):
        # Déterminer si l'action est une compétence ou un attribut
        action = action.lower()

        # Vérifier les attributs
        if action in entity_data['attributes']:
            base_roll, bonus, total = roll_with_bonus(entity_data, action)
            return f"Lancer de dé pour l'attribut {action.upper()}: {base_roll} + {bonus} = {total}"

        # Vérifier les compétences
        for category, skills in entity_data['skills'].items():
            if action in skills:
                base_roll, bonus, total = roll_with_bonus(entity_data, action, category)
                return f"Lancer de dé pour la compétence {action} dans la catégorie {category}: {base_roll} + {bonus} = {total}"

        return f"Compétence ou attribut {action} non reconnu."

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