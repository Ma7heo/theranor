import discord
from discord import app_commands
from discord.ext import commands
from database import load_player, update_player
from utils import roll_d100, roll_d20, roll_d4, roll_dice, parse_dice_expression, roll_with_bonus


class CombatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Ajoutez ici vos commandes et événements

    def get_weapon_choices(self, user_id):
        player_data = load_player(user_id)
        if not player_data:
            return []
        weapons = player_data['inventory']['armes']
        return [weapon['nom'] for weapon in weapons] + ["pugilat"]

    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_weapon_choices(user_id) if current.lower() in choice.lower()]
        return choices

    @app_commands.command(name="attaquer", description="Effectue une attaque avec une arme ou avec 'pugilat'.")
    @app_commands.autocomplete(weapon_name=weapon_autocomplete)
    async def attaquer(self, interaction: discord.Interaction, weapon_name: str, degats: int = 0, portee: int = 0, saignement: int = 0, modification_zone: int = 0, cible_supplementaire: int = 0, etourdissement: int = 0, parade: int = 0, deplacement: int = 0, difficulte_crit: int = 0):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)
        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        if weapon_name.lower() == "pugilat":
            skill_name = "pugilat"
            category = "force"
            attribute = "for"
        else:
            weapon = next((w for w in player_data['inventory']['armes'] if w['nom'] == weapon_name), None)
            if not weapon:
                await interaction.response.send_message("Arme non trouvée.")
                return
            skill_name = weapon['bonus_type']
            category = None
            if skill_name in player_data['skills']['force']:
                category = 'force'
                attribute = 'for'
            elif skill_name in player_data['skills']['agilite']:
                category = 'agilite'
                attribute = 'agi'
            elif skill_name in player_data['skills']['intelligence']:
                category = 'intelligence'
                attribute = 'int'
            elif skill_name in player_data['skills']['charisme']:
                category = 'charisme'
                attribute = 'cha'
            else:
                await interaction.response.send_message("Compétence non reconnue.")
                return

        # Calculer les points de mana nécessaires
        total_effects = sum([degats, portee, saignement, modification_zone, cible_supplementaire, etourdissement, parade, deplacement, difficulte_crit])
        points_mana = total_effects * 2
        if total_effects>0:
            use_mana, _ = parse_dice_expression(f"{total_effects}d6")
        else:
            use_mana = 0

        # Vérifier les points de compétence disponibles
        skill_level = player_data['skills'][category][skill_name]
        if points_mana > skill_level:
            await interaction.response.send_message(f"Vous n'avez pas assez de points de compétence. Compétence actuelle: {skill_level}, points requis: {points_mana}")
            return

        # Vérifier les points de mana disponibles
        if player_data['mana_actu'] < use_mana:
            await interaction.response.send_message("Mana insuffisant.")
            return

        # Accuser réception de la commande
        await interaction.response.defer()

        # Réduire le mana du joueur
        player_data['mana_actu'] -= use_mana
        update_player(user_id, player_data)

        # Préparer le message de réponse
        response_message = []

        # Lancer de base
        base_roll, bonus, total = roll_with_bonus(player_data, skill_name, category)
        response_message.append(f"Lancer de dé pour toucher avec {weapon_name}: {base_roll} + {bonus} = {total}")

        # Calculer les dégâts
        if weapon_name.lower() == "pugilat":
            damage_expression = f"{skill_level}d4"
        else:
            damage_expression = weapon.get('degats', '0d0')
            print(damage_expression, weapon)
        damage_roll, _ = parse_dice_expression(damage_expression)
        print(damage_roll)
        attribute_bonus = player_data['attributes'].get(attribute, 0)
        total_damage = damage_roll + attribute_bonus

        # Appliquer les effets des techniques de combat
        if degats > 0:
            extra_damage_roll, _ = parse_dice_expression(f"{degats}d6")
            total_damage += extra_damage_roll
            response_message.append(f"Dégâts supplémentaires: {extra_damage_roll} (Niveau: {degats})")

        if portee > 0:
            range_increase = portee * 10
            response_message.append(f"Portée augmentée de {range_increase} mètres (Niveau: {portee})")

        if saignement > 0:
            response_message.append(f"Effet de saignement appliqué (Niveau: {saignement})")

        if modification_zone > 0:
            response_message.append(f"Zone de combat modifiée (Niveau: {modification_zone})")

        if cible_supplementaire > 0:
            response_message.append(f"Cible supplémentaire attaquée (Niveau: {cible_supplementaire})")

        if etourdissement > 0:
            response_message.append(f"Effet d'étourdissement appliqué (Niveau: {etourdissement})")

        if parade > 0:
            response_message.append(f"Bonus de parade de {parade * 10} appliqué (Niveau: {parade})")

        if deplacement > 0:
            move_increase = deplacement * 10
            response_message.append(f"Déplacement augmenté de {move_increase} mètres (Niveau: {deplacement})")

        if difficulte_crit > 0:
            response_message.append(f"Difficulté de critique réduite de {difficulte_crit * 5} (Niveau: {difficulte_crit})")

        # Afficher le total des dégâts
        response_message.append(f"Dégâts totaux avec {weapon_name}: {total_damage}")

        # Afficher le mana consommé
        response_message.append(f"Mana consommé: {use_mana}")
        response_message.append(f"Mana restant: {player_data['mana_actu']}")

        await interaction.followup.send("\n".join(response_message))


        # Remplace ta fonction autocomplete
    async def skill_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        choices = [app_commands.Choice(name=choice, value=choice) for choice in get_skill_choices(user_id) if current.lower() in choice.lower()]
        choices.append(app_commands.Choice(name="perception", value="perception"))
        return choices

    # Remplace ta commande /l
    @app_commands.command(name="l", description="Effectue un jet de compétence ou d'attribut.")
    @app_commands.autocomplete(skill_name=skill_autocomplete)
    async def l(self, interaction: discord.Interaction, skill_name: str):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        skill_name = skill_name.lower()

        # --- Blague perception
        if skill_name == "perception":
            skill_name = "observation"  # Redirige vers la bonne compétence

            # Message troll MJ
            channel_id = 1125761257581068384  # <-- remplace par l’ID du salon
            mj_id = 288009483358044170       # <-- remplace par l’ID du MJ
            channel = interaction.client.get_channel(channel_id)
            if channel:
                await channel.send(f"<@{mj_id}> bah nan ça existe pas perception, c'est observation CONNARD !")

        # Jet d’attribut
        if skill_name in player_data['attributes']:
            base_roll, bonus, total = roll_with_bonus(player_data, skill_name)
            await interaction.response.send_message(f"Lancer de dé pour l'attribut {skill_name.upper()} : {base_roll} + {bonus} = {total}")
            return

        # Jet de compétence
        category = None
        for cat, skills in player_data['skills'].items():
            if skill_name in skills:
                category = cat
                break

        if category:
            base_roll, bonus, total = roll_with_bonus(player_data, skill_name, category)
            await interaction.response.send_message(f"Lancer de dé pour la compétence {skill_name} ({category}) : {base_roll} + {bonus} = {total}")
        else:
            await interaction.response.send_message(f"Compétence ou attribut {skill_name} non reconnu.")

    def get_magic_choices(self, user_id):
        return ["magie1", "magie2"]

    async def magic_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = str(interaction.user.id)
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_magic_choices(user_id) if current.lower() in choice.lower()]
        return choices

    @app_commands.command(name="utiliser_magie", description="Utilise une magie spécifique.")
    @app_commands.describe(magie_type="Type de magie à utiliser",
                            degats="Nombre de d4 pour les dégâts",
                            heal="Nombre de d4 pour les soins",
                            buff="Niveau du buff (+5/10/15)",
                            debuff="Niveau du debuff (-5/10/15)",
                            effet_negatif="Niveau de l'effet négatif",
                            zone_effet="Nombre de d4 pour l'augmentation de la zone d'effet",
                            amelioration_effet_negatif="Niveau de l'amélioration de l'effet négatif",
                            portee="Nombre de d4 pour l'augmentation de la portée",
                            bouclier_perso="Nombre de d4 pour le bouclier personnel",
                            bouclier_fixe="Nombre de d4 pour le bouclier fixe",
                            deplacement="Nombre de d4 pour l'augmentation du déplacement")
    @app_commands.autocomplete(magie_type=magic_autocomplete)
    async def utiliser_magie(self, interaction: discord.Interaction, magie_type: str, 
                            degats: int = 0, heal: int = 0, buff: int = 0, debuff: int = 0,
                            effet_negatif: int = 0, zone_effet: int = 0,
                             amelioration_effet_negatif: int = 0,
                            portee: int = 0, bouclier_perso: int = 0, bouclier_fixe: int = 0,
                            deplacement: int = 0):
        
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        if magie_type not in ['magie1', 'magie2']:
            await interaction.response.send_message("Veuillez spécifier 'magie1' ou 'magie2'.")
            return
            
        magie = player_data['magie'][0] if magie_type == 'magie1' else player_data['magie'][1]

        total_effects = sum([degats, heal, buff, debuff, effet_negatif, zone_effet,
                            amelioration_effet_negatif,
                            portee, bouclier_perso, bouclier_fixe, deplacement])

        # Vérifier le niveau de compétence en magie
        magie_level = player_data['skills']['intelligence'][magie_type]
        if magie=='Magie arcanique' and magie_level>2:
            if (magie_level +1) < total_effects :
                await interaction.response.send_message(f"Niveau de magie insuffisant pour utiliser {total_effects} effets.")
                return
        else:
            if magie_level < total_effects or ():
                await interaction.response.send_message(f"Niveau de magie insuffisant pour utiliser {total_effects} effets.")
                return

        # Calculer le coût total en mana (1d4 par effet)
        mana_cost = sum(roll_dice(1, 4) for _ in range(total_effects))

        # Vérifier les points de mana disponibles
        if player_data['mana_actu'] < mana_cost:
            await interaction.response.send_message("Mana insuffisant.")
            return

        # Jet de compétence en magie avec bonus (lié à la compétence magique utilisée)
        base_roll, bonus, total_roll = roll_with_bonus(player_data, magie_type, "intelligence")

        if magie=='Magie sacrée':
            # Déterminer le niveau du sort
            if total_effects <= 4:
                # Sort de niveau faible
                damage_die = "d4"
                heal_die="d6"
                buff_debuff_value = 5
                shield_die_personal = "d6"
                shield_die_fixed = "d10"
                range_multiplier = 5
                move_multiplier = 2
            elif total_effects <= 9:
                # Sort de niveau intermédiaire
                damage_die = "d6"
                heal_die="d8"
                buff_debuff_value = 10
                shield_die_personal = "d8"
                shield_die_fixed = "d12"
                range_multiplier = 10
                move_multiplier = 5
            else:
                # Sort de niveau avancé
                damage_die = "d8"
                heal_die="d10"
                buff_debuff_value = 15
                shield_die_personal = "d10"
                shield_die_fixed = "d14"
                range_multiplier = 15
                move_multiplier = 10
        # Déterminer le niveau du sort
        else:
            if total_effects <= 4:
                # Sort de niveau faible
                damage_die = "d4"
                heal_die="d4"
                buff_debuff_value = 5
                shield_die_personal = "d4"
                shield_die_fixed = "d8"
                range_multiplier = 5
                move_multiplier = 2
            elif total_effects <= 9:
                # Sort de niveau intermédiaire
                damage_die = "d6"
                heal_die="d6"
                buff_debuff_value = 10
                shield_die_personal = "d6"
                shield_die_fixed = "d10"
                range_multiplier = 10
                move_multiplier = 5
            else:
                # Sort de niveau avancé
                damage_die = "d8"
                heal_die="d8"
                buff_debuff_value = 15
                shield_die_personal = "d8"
                shield_die_fixed = "d12"
                range_multiplier = 15
                move_multiplier = 10

        # Appliquer les effets de la magie
        response_message = []
        total_damage = 0
        range_increment = 20  # Portée de base en mètres

        # Dégâts/Soins
        if degats > 0:
            damage_dice = f"{degats}{damage_die}"
            damage_roll, _ = parse_dice_expression(damage_dice)

            # Ajouter l'intelligence aux dégâts
            intelligence_bonus = player_data['attributes']['int']

            # Calcul des bonus des objets
            object_bonus = 0
            for item in player_data['inventory']['armes']+player_data['inventory']['armures'] + player_data['inventory']['autres_objets']:
                if item['bonus_type'] == magie_type:
                    object_damage_roll, _ = parse_dice_expression(item['degats'])
                    object_bonus += object_damage_roll

            total_damage = damage_roll + intelligence_bonus + object_bonus
            response_message.append(f"Dégâts infligés: {total_damage} (Roll: {damage_roll} + Intelligence: {intelligence_bonus} + Bonus des objets: {object_bonus})")

        if heal > 0:
            heal_dice = f"{heal}{heal_die}"
            heal_roll, _ = parse_dice_expression(heal_dice)
            intelligence_bonus = player_data['attributes']['int']
            heal_tot = heal_roll + intelligence_bonus
            response_message.append(f"Soins: {heal_tot} (= {heal_roll} + {intelligence_bonus})")

        # Buff/Debuff
        if buff > 0:
            buff_amount = buff * buff_debuff_value
            response_message.append(f"Buff appliqué: +{buff_amount} pendant {buff} tour (Niveau: {buff})")

        if debuff > 0:
            debuff_amount = debuff * buff_debuff_value
            response_message.append(f"Debuff appliqué: -{debuff_amount} pendant {debuff} tour (Niveau: {debuff})")

        # Effet négatif
        if effet_negatif > 0:
            response_message.append(f"Effet négatif appliqué de niveau {effet_negatif}")

        # Zone d'effet
        if zone_effet > 0:
            area_increase = zone_effet * 10
            response_message.append(f"Zone d'effet augmentée de {area_increase} mètres (Niveau: {zone_effet})")

        if amelioration_effet_negatif > 0:
            difficulty_increase = amelioration_effet_negatif * (buff_debuff_value + 5)
            response_message.append(f"Effet négatif amélioré: +{difficulty_increase} difficulté d'annulation.")

        # Portée augmentée
        if portee > 0:
            range_increase = portee * range_multiplier
            range_increment += range_increase
            response_message.append(f"Portée augmentée de {range_increase} mètres (Niveau: {portee})")

        # Bouclier personnel
        if bouclier_perso > 0:
            shield_dice = f"{bouclier_perso}{shield_die_personal}"
            shield_roll, _ = parse_dice_expression(shield_dice)
            intelligence_bonus = player_data['attributes']['int']
            tot_shield=shield_roll+intelligence_bonus
            response_message.append(f"Bouclier personnel: {tot_shield} Shield bonus ({shield_roll} + {intelligence_bonus})")

        # Bouclier fixe
        if bouclier_fixe > 0:
            fixed_shield_dice = f"{bouclier_fixe}{shield_die_fixed}"
            fixed_shield_roll, _ = parse_dice_expression(fixed_shield_dice)
            intelligence_bonus = player_data['attributes']['int']
            fixed_tot_shield=fixed_shield_roll+intelligence_bonus
            response_message.append(f"Bouclier fixe: {fixed_tot_shield} Shield bonus ({fixed_shield_roll} + {intelligence_bonus})")

        # Déplacement
        if deplacement > 0:
            move_increase = deplacement * move_multiplier
            response_message.append(f"Déplacement augmenté de {move_increase} mètres (Niveau: {deplacement})")

        # Réduire le mana du joueur et vérifier si déplétion de mana
        player_data['mana_actu'] -= mana_cost
        deplete_message = ""
        if player_data['mana_actu'] < 0:
            deplete_message = " Vous tombez en déplétion de mana."
            player_data['mana_actu'] = 0  # Le joueur tombe à 0 mana

        update_player(user_id, player_data)

        response_message.append(f"Jet de magie: {base_roll} + {bonus} = {total_roll}")
        response_message.append(f"Coût de mana: {mana_cost}. Mana restant: {player_data['mana_actu']}.{deplete_message}")

        await interaction.response.send_message("\n".join(response_message))

    @app_commands.command(name="damage", description="Inflige des dégâts à un joueur.")
    @app_commands.describe(joueur="Le joueur à qui infliger des dégâts", expression="Expression de dégâts", armure="Divise les dégâts par deux si vrai")
    async def damage(self, interaction: discord.Interaction, joueur: discord.Member, expression: str, armure: bool = False):
            player_id = str(joueur.id)
            player_data = load_player(player_id)

            if not player_data:
                await interaction.response.send_message("Joueur non trouvé.")
                return

            degats, details = parse_dice_expression(expression)

            if armure:
                degats = (degats+1) // 2

            player_data['pv_actu'] -= degats
            if player_data['pv_actu'] < 0:
                player_data['pv_actu'] = 0

            update_player(player_id, player_data)

            await interaction.response.send_message(f"{joueur.mention} a subi {degats} dégâts. PV actuels: {player_data['pv_actu']}")

    @app_commands.command(name="heal", description="Soigne un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour les soins", joueur="Le joueur à soigner")
    async def heal(self, interaction: discord.Interaction, expression: str = "1d1", joueur: discord.Member = None):
        if joueur is None:
            joueur = interaction.user

        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        soins, details = parse_dice_expression(expression)

        player_data['pv_actu'] += soins
        if player_data['pv_actu'] > player_data['pv_max']:
            player_data['pv_actu'] = player_data['pv_max']

        update_player(player_id, player_data)

        await interaction.response.send_message(f"{joueur.mention} a été soigné de {soins} PV. PV actuels: {player_data['pv_actu']}")

    @app_commands.command(name="submana", description="Retire du mana à un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour retirer du mana", joueur="Le joueur à qui retirer du mana")
    async def submana(self, interaction: discord.Interaction, expression: str, joueur: discord.Member = None):
        if joueur is None:
            joueur = interaction.user

        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        degats, details = parse_dice_expression(expression)

        player_data['mana_actu'] -= degats
        if player_data['mana_actu'] < 0:
            player_data['mana_actu'] = 0

        update_player(player_id, player_data)

        await interaction.response.send_message(f"{joueur.mention} a perdu {degats} de mana. Mana actuels: {player_data['mana_actu']}")

    @app_commands.command(name="addmana", description="Ajoute du mana à un joueur avec l'expression de dés spécifiée")
    @app_commands.describe(expression="Expression de dés pour ajouter du mana", joueur="Le joueur à qui ajouter du mana")
    async def addmana(self, interaction: discord.Interaction, expression: str, joueur: discord.Member = None):
        if joueur is None:
            joueur = interaction.user

        player_id = str(joueur.id)
        player_data = load_player(player_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        soins, details = parse_dice_expression(expression)

        player_data['mana_actu'] += soins
        if player_data['mana_actu'] > player_data['mana_max']:
            player_data['mana_actu'] = player_data['mana_max']

        update_player(player_id, player_data)

        await interaction.response.send_message(f"{joueur.mention} a récupéré {soins} de mana. Mana actuels: {player_data['mana_actu']}")

    @app_commands.command(name="armure", description="Effectue un jet d'armure pour réduire les dégâts")
    async def armure(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        armure = player_data['attributes'].get('armure', 0)
        bonus_armures = sum(
            item['bonus_value'] for item in player_data['inventory']['armures']
        )
        bonus_bouclier = sum(
            item['bonus_value'] for item in player_data['inventory']['autres_objets'] if item['bonus_type'] == 'bouclier'
        )
        roll = roll_d100()
        total = roll - armure - bonus_armures - bonus_bouclier

        success = total <= 0
        message = f"Armure de {player_data['name']}: 1d100 - {armure} - {bonus_armures} - {bonus_bouclier} = {total}"
        if success:
            message += "\nSuccès! Vous prendrez moitié moins de dégâts."
        else:
            message += "\nÉchec! Vous prendrez les dégâts complets."

        await interaction.response.send_message(message)

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
    await bot.add_cog(CombatCommands(bot))