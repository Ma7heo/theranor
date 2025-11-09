import discord
from discord import app_commands
import random
from discord.ext import commands
from utils import parse_dice_expression, roll_d100, roll_d20, roll_d12, roll_dice
from database import load_player


class UtilityCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def setup(self):
        self.bot.tree.add_command(self.loot_command)
        self.bot.tree.add_command(self.aide_command)
        self.bot.tree.add_command(self.rencontre)

    @app_commands.command(name="de", description="Lance un dé avec l'expression spécifiée.")
    async def de(self, interaction: discord.Interaction, expression: str):
        try:
            total, details = parse_dice_expression(expression)
            await interaction.response.send_message(f"Résultat de {expression}: {total} ({' + '.join(details)})")
        except ValueError:
            await interaction.response.send_message("Expression invalide. Utilisez le format : 2d6+8d4+1d20+4")

    # Fonction d'autocomplétion pour le biome
    async def biome_autocomplete(self, interaction: discord.Interaction, current: str):
        biomes = ["plaine", "forêt", "océan", "désert", "montagne"]
        return [
            app_commands.Choice(name=biome, value=biome)
            for biome in biomes if current.lower() in biome.lower()
        ]
    async def biome_autocomplete_2(self, interaction: discord.Interaction, current: str):
        biomes = ["plaine", "forêt", "caverne", "désert", "montagne", "rivière", "colline", "marais", "volcan"]
        return [
            app_commands.Choice(name=biome, value=biome)
            for biome in biomes if current.lower() in biome.lower()
        ]

    @app_commands.command(name="rencontre", description="Génère une rencontre aléatoire.")
    @app_commands.autocomplete(biome=biome_autocomplete)
    async def rencontre(self, interaction: discord.Interaction, biome: str = "plaine"):
        encounter_table = {
            "boss": range(1, 3),
            "monstre": range(3, 16),
            "animaux": range(16, 24),
            "bandits": range(24, 34),
            "rien": range(34, 61),
            "bourse": range(61, 71),
            "objet": range(71, 76),
            "marchand": range(76, 86),
            "PNJ": range(86, 96),
            "event": range(96, 101)
        }
        
        if biome == "océan":
            bosses = ["Jeune Kraken", "Serpent des Mers", "Requin-Sorcier", "Golem d'Algue", "Dragonnet de Mer", "Méduse Abyssale", "Léviathan", "Kraken"]
            animals=['animal']
            monsters=['monster']
        elif biome == "désert":
            animals=['animal']
            bosses = ["Sultan des Sables", "Scorpion Antique", "Ver des Dunes", "Pharaon Maudit", "Drake des Sables", "Sphinx"]
            monsters = ["Serpent des Sables", "Scorpions Géants", "Hommes-Lézards", "Araignées du Désert", "Chacals Sauvages", "Momies", "Elementaires de Terre", "Elementaires d'Air", "Vautours Géants", "Scarabs Mangeurs de Chair"]
        elif biome == "montagne":
            bosses = ["Ours", "Loup", "Rapace", "Félin", "Bandit", "Monstre légendaire"]
            animals=['animal']
            monsters=['monster']
        else:
            animals = ["Ours", "Meute de Loups", "Félins", "Rapace"]
            monsters = ["orc", "gobelin", "gnoll", "morts-vivants", "élémentaire", "lizardman"]
            bosses = ["Ours", "Loups", "Élémentaire", "Rapace", "Armée Morts-Vivants", "Armée Orc", "Félin", "Monstre Légendaire", "Armée Lizardman", "Bandit Légendaire"]


        roll = roll_d100()
        encounter_type = None

        for key, value in encounter_table.items():
            if roll in value:
                encounter_type = key
                break

        if encounter_type == "boss":
            encounter = random.choice(bosses)
            await interaction.response.send_message(f"Rencontre avec un BOSS : {encounter}")
        elif encounter_type == "monstre":
            encounter = random.choice(monsters)
            await interaction.response.send_message(f"Rencontre avec un MONSTRE : {encounter}")
        elif encounter_type == "animaux":
            encounter = random.choice(animals)
            await interaction.response.send_message(f"Rencontre avec un ANIMAL SAUVAGE : {encounter}")
        elif encounter_type == "bandits":
            await interaction.response.send_message("Rencontre avec des BANDITS.")
        elif encounter_type == "rien":
            await interaction.response.send_message("Aucune rencontre.")
        elif encounter_type == "bourse":
            await interaction.response.send_message("Vous trouvez une bourse.")
        elif encounter_type == "objet":
            await interaction.response.send_message("Vous trouvez un objet.")
        elif encounter_type == "marchand":
            await interaction.response.send_message("Vous rencontrez un marchand.")
        elif encounter_type == "PNJ":
            await interaction.response.send_message("Vous rencontrez un PNJ.")
        elif encounter_type == "event":
            await interaction.response.send_message("Un événement se produit.")
        else:
            await interaction.response.send_message("Erreur de rencontre.")


    @app_commands.command(name="fouille", description="Génère une fouille aléatoire.")
    @app_commands.autocomplete(biome=biome_autocomplete_2)
    async def fouille(self, interaction: discord.Interaction, biome: str = "plaine"):
        
        if biome == "forêt":
            objet_table = {
                "Herbe médicinale": range(1, 37),
                "Racine d'arbre ancien": range(37, 48),
                "Résine explosive": range(48, 59),
                "Écorce de chêne": range(59, 67),
                "Aconit": range(67, 75),
                "Écorce de Mandragore": range(75, 80),
                "Sève d'arbre": range(80, 85),
                "Belladone": range(85, 90),
                "Œil de hibou": range(90, 93),
                "Larmes de Dryade": range(93, 95),
                "Griffe de bête sauvage": range(95, 97),
                "Racine de sagesse": range(97, 98),
                "Poussière de fée": range(98, 99),
                "Sève de l'arbre de vie": range(99, 100),
                "Écaille de caméléon": range(100, 101)
            }
        elif biome == "rivière":
            objet_table = {
                "Eau pure": range(1, 56),
                "Écorce d'orme": range(56, 68),
                "Algue marine": range(68, 76),
                "Écaille de poisson": range(76, 84),
                "Feuille de lotus de feu": range(84, 92),
                "Goutte d'eau bénite": range(92, 100),
                "Algue centenaire": range(100, 101)
            }
        elif biome == "plaine":
            objet_table = {
                "Feuille de menthe": range(1, 48),
                "Baies guérisseuses": range(48, 63),
                "Fleur de bouclier": range(63, 78),
                "Plume d'oiseau rapide": range(78, 85),
                "Fleur de fumée": range(85, 92),
                "Herbe rapide": range(92, 95),
                "Sabot de centaure": range(95, 98),
                "Plume d'anti-magie": range(98, 99),
                "Herbe mémorielle": range(99, 100),
                "Pétales de rose": range(100, 101)
            }
        elif biome == "caverne":
            objet_table = {
                "Toile d'araignée": range(1, 26),
                "Pierre d'annulation": range(26, 51),
                "Champignon toxique": range(51, 76),
                "Essence de cristal": range(76, 86),
                "Crystal de glace": range(86, 91),
                "Champignon luminescent": range(91, 96),
                "Crystal de minotaure": range(96, 99),
                "Crystal d'ombre": range(99, 100),
                "Cristal de clairvoyance": range(100, 101)
            }
        elif biome == "colline":
            objet_table = {
                "Poudre d'étoile": range(1, 81),
                "Poudre de lune": range(81, 93),
                "Essence de lune": range(93, 100),
                "Poudre de météorite": range(100, 101)
            }
        elif biome == "montagne":
            objet_table = {
                "Brume mystique": range(1, 30),
                "Larmes de yéti": range(30, 59),
                "Dent de serpent": range(59, 74),
                "Souffle du vent du nord": range(74, 89),
                "Pierre de force": range(89, 94),
                "Vent de zéphyr": range(94, 99),
                "Plume de phénix": range(99, 100),
                "Plume de griffon royal": range(100, 101)
            }
        elif biome == "marais":
            objet_table = {
                "Résine de gobelin": range(1, 71),
                "Venin de serpent": range(71, 97),
                "Serpent agile": range(97, 100),
                "Pétale de lotus": range(100, 101)
            }
        elif biome == "désert":
            objet_table = {
                "Poudre d'ombre": range(1, 75),
                "Ambre parfumé": range(75, 85),
                "Poussière de Clairail": range(85, 95),
                "Fleur d'ombre": range(95, 100),
                "Larme de licorne": range(100, 101)
            }
        elif biome == "volcan":
            objet_table = {
                "Goutte de lave": range(1, 41),
                "Essence de feu": range(41, 81),
                "Peau de salamandre": range(81, 101)
            }
        else:
            await interaction.response.send_message("biome inconnu")

        roll = roll_d100()
        objet = None

        for key, value in objet_table.items():
            if roll in value:
                objet = key
                break
        await interaction.response.send_message(f"Objet: {objet}")
    

    @app_commands.command(name="blessure", description="Génère une blessure aléatoire.")
    async def blessure(self, interaction: discord.Interaction):
        blessure_table = {
            "torse": range(1, 25),
            "visage": range(25, 49),
            "bras": range(49, 73),
            "jambe": range(73, 97),
            "borgne": range(97, 101)
        }

        roll = roll_d100()
        bless = None

        for key, value in blessure_table.items():
            if roll in value:
                bless = key
                break

        if bless=="torse":
            await interaction.response.send_message("Blessure au torse: desavantage aux jets concernant la FOR et l'AGI")
        elif bless=="visage":
            await interaction.response.send_message("Blessure au visage visage: desavantage aux jets concernant le CHA et l'INT")
        elif bless=="bras":
            await interaction.response.send_message("Blessure au bras: vous ne pouvez plus entreprendre d'action necessitant l'usage de vos deux bras")
        elif bless=="jambe":
            await interaction.response.send_message("Blessure à la jambe: votre mobilité est réduite de 50%")
        elif bless=="borgne":
            await interaction.response.send_message("Borgne: Désavantage à tous vos jets ciblant quelqu'un ou quelque chose, ainsi qu'à vos jets d'observation et d'esquive")
        else:
            await interaction.response.send_message("Erreur de blessure.")

    @app_commands.command(name="init", description="Effectue un jet d'initiative.")
    async def init(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        player_data = load_player(user_id)

        if not player_data:
            await interaction.response.send_message("Joueur non trouvé.")
            return

        agi = player_data['attributes'].get('agi', 0)
        initiative = roll_d20() + agi
        await interaction.response.send_message(f"Initiative de {player_data['name']}: 1d20 + {agi} = {initiative}")

    def get_loot_choices(self):
        return ["T1", "T2", "T3", "T4", "T5"]
    
    async def loot_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=choice, value=choice) for choice in self.get_loot_choices() if current.lower() in choice.lower()]
        return choices

    @app_commands.command(name="loot", description="Génère un loot en fonction du niveau spécifié")
    @app_commands.autocomplete(niveau=loot_autocomplete)
    async def loot(self, interaction: discord.Interaction, niveau: str):
        loot_tables = {
            "T1": {
                "rien": range(1, 21),
                "faible somme": range(21, 61),
                "somme raisonnable": range(61, 81),
                "objet peu commun": range(81, 101)
            },
            "T2": {
                "faible somme": range(1, 16),
                "somme raisonnable": range(16, 46),
                "objet peu commun": range(46, 66),
                "objet rare": range(66, 86),
                "somme importante": range(86, 99),
                "objet epique": range(99, 101)
            },
            "T3": {
                "somme raisonnable": range(1, 26),
                "objet rare": range(26, 56),
                "somme importante": range(56, 76),
                "objet epique": range(76, 88),
                "somme consequente": range(88, 99),
                "objet legendaire": range(99, 101)
            },
            "T4": {
                "objet rare": range(1, 11),
                "somme importante": range(11, 26),
                "objet epique": range(26, 56),
                "somme consequente": range(56, 81),
                "objet legendaire": range(81, 91),
                "somme incommensurable": range(91, 101)
            },
            "T5": {
                "objet epique": range(1, 11),
                "somme consequente": range(11, 26),
                "objet legendaire": range(26, 56),
                "somme incommensurable": range(56, 86),
                "somme astronomique": range(86, 96),
                "objet mythique": range(96, 101)
            }
        }

        argent_table = {
            "faible somme": (1, 50, "pc"),
            "somme raisonnable": (50, 300, "pc"),
            "somme importante": (3, 10, "pa"),
            "somme consequente": (10, 100, "pa"),
            "somme incommensurable": (1, 10, "po"),
            "somme astronomique": (10, 100, "po")
        }

        objet_table = {
            "alchimie": range(1, 3),
            "arme": range(3, 6),
            "armure": range(6, 9),
            "objet magique": range(9, 12),
            "surprise": range(12, 13)
        }

        def generer_loot(niveau):
            table = loot_tables.get(niveau)
            if not table:
                return "Niveau de loot invalide."

            roll = roll_d100()
            loot_type = next((key for key, value in table.items() if roll in value), "rien")
            if "somme" in loot_type:
                min_val, max_val, unit = argent_table[loot_type]
                amount = roll_dice(1, max_val - min_val + 1) + min_val - 1
                return f"Loot {niveau}: {loot_type.capitalize()} - {amount}{unit}"
            elif "objet" in loot_type:
                objet_roll = roll_d12()
                objet = next((key for key, value in objet_table.items() if objet_roll in value), "rien")
                return f"Loot {niveau}: {loot_type.capitalize()} - {objet.capitalize()}"
            else:
                return f"Loot {niveau}: {loot_type.capitalize()}"

        resultat = generer_loot(niveau)
        await interaction.response.send_message(resultat)

    async def aide_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = [app_commands.Choice(name=cmd, value=cmd) for cmd in self.get_command_choices() if current.lower() in cmd.lower()]
        return choices
    
    def get_command_choices(self):
        return [
            "creer", "supprimer", "modifier_joueur", "monter_niveau", "info",
            "donner_argent", "retirer_argent", "ajouter_argent", "ajouter_objet",
            "donner_objet", "retirer_objet", "l", "utiliser_magie", "attaquer",
            "repos_long", "init", "armure", "de", "ajouter_familier", "familier",
            "init_familier", "armure_familier", "info_familier", "r", "loot",
            "damage", "heal", "submana", "addmana"
        ]
    

    
    @app_commands.command(name="aide", description="Affiche l'aide pour une commande spécifique")
    @app_commands.autocomplete(command_name=aide_autocomplete)
    async def aide(self, interaction: discord.Interaction, command_name: str):
        commands_info = {
            "creer": {
                "description": "Crée un nouveau personnage.",
                "usage": "!creer"
            },
            "supprimer": {
                "description": "Supprime un personnage.",
                "usage": "!supprimer [joueur_id]"
            },
            "modifier_joueur": {
                "description": "Modifie un champ spécifique d'un joueur.",
                "usage": "!modifier_joueur <joueur> <champ> <valeur>"
            },
            "monter_niveau": {
                "description": "Augmente le niveau d'un joueur et distribue des points d'attributs et de compétences.",
                "usage": "!monter_niveau <joueur>"
            },
            "info": {
                "description": "Affiche les informations du joueur.",
                "usage": "!info [joueur]"
            },
            "donner_argent": {
                "description": "Donne une certaine quantité d'argent à un autre joueur.",
                "usage": "!donner_argent <destinataire> <montant> <type_piece>"
            },
            "retirer_argent": {
                "description": "Retire une certaine quantité d'argent d'un joueur.",
                "usage": "!retirer_argent <montant> <type_piece> <joueur>(optional)"
            },
            "ajouter_argent": {
                "description": "Ajoute une certaine quantité d'argent à un joueur.",
                "usage": "!ajouter_argent <joueur> <montant> <type_piece>"
            },
            "ajouter_objet": {
                "description": "Ajoute un objet à l'inventaire d'un joueur.",
                "usage": "!ajouter_objet <destinataire> <categorie> <nom> <description> [<bonus_type> <bonus_value>] [<degats>]"
            },
            "donner_objet": {
                "description": "Donne un objet d'un joueur à un autre.",
                "usage": "!donner_objet <destinataire> <categorie> <nom>"
            },
            "retirer_objet": {
                "description": "Retire un objet de l'inventaire d'un joueur.",
                "usage": "!retirer_objet <nom> <categorie> <joueur>(optional)"
            },
            "l": {
                "description": "Effectue un jet de compétence ou d'attribut.",
                "usage": "!lancer_de <skill_name>"
            },
            "utiliser_magie": {
                "description": "Utilise une magie du joueur.",
                "usage": "!utiliser_magie <magie_type> <niveau>"
            },
            "attaquer": {
                "description": "Effectue une attaque avec une arme ou avec 'pugilat'.",
                "usage": "!attaquer <weapon_name>"
            },
            "repos_long": {
                "description": "Effectue un repos long et restaure les PV et PM de tous les joueurs.",
                "usage": "!repos_long"
            },
            "init": {
                "description": "Effectue un jet d'initiative pour le joueur.",
                "usage": "!init"
            },
            "armure": {
                "description": "Effectue un jet d'armure pour réduire les dégâts.",
                "usage": "!armure"
            },
            "de": {
                "description": "Lance un jet de dés avec l'expression spécifiée.",
                "usage": "!de <expression>"
            },
            "ajouter_familier": {
                "description": "Ajoute un familier à un joueur.",
                "usage": "!ajouter_familier <joueur> <nom> <niveau> <for> <agi> <cha> <int_> <pv_max> <mana_max> <compétences...>"
            },
            "familier": {
                "description": "Utilise une action avec un familier.",
                "usage": "!familier <nom_familier> <action>"
            },
            "init_familier": {
                "description": "Effectue un jet d'initiative pour le familier.",
                "usage": "!init_familier <nom_familier>"
            },
            "armure_familier": {
                "description": "Effectue un jet d'armure pour réduire les dégâts du familier.",
                "usage": "!armure_familier <nom_familier>"
            },
            "info_familier": {
                "description": "Affiche les informations du familier.",
                "usage": "!info_familier <nom_familier>"
            },
            "r": {
                "description": "Génère une rencontre aléatoire.",
                "usage": "!r"
            },
            "loot": {
                "description": "Génère un loot en fonction du niveau spécifié.",
                "usage": "!loot <niveau>"
            },
            "damage":{
                "description":"Inflige des dégâts à un joueur",
                "usage": "!damage <joueur> <dés de dégâts> <true>(s'il armure)"
            },
            "heal": {
                "description": "Soigne le joueur.",
                "usage": "!heal <dé de soin> <joueur>(optional)"
            },
            "submana": {
                "description": "Retire du mana au joueur.",
                "usage": "!submana <dé de mana> <joueur>(optional)"
            },
            "addmana": {
                "description": "Ajoute du mana au joueur.",
                "usage": "!addmana <dé de mana> <joueur>(optional)"
            }

        }

        if command_name:
            command_name = command_name.lower()
            if command_name in commands_info:
                command_info = commands_info[command_name]
                await interaction.response.send_message(f"**{command_name}**\nDescription: {command_info['description']}\nUsage: {command_info['usage']}")
            else:
                await interaction.response.send_message(f"La commande '{command_name}' n'existe pas.")
        else:
            help_message = "**Liste des commandes :**\n"
            for cmd, info in commands_info.items():
                help_message += f"**{cmd}** - {info['description']}\nUsage: {info['usage']}\n\n"

            if len(help_message) > 2000:
                chunks = [help_message[i:i + 2000] for i in range(0, len(help_message), 2000)]
                for chunk in chunks:
                    await interaction.response.send_message(chunk)
            else:
                await interaction.response.send_message(help_message)

    

async def setup(bot):
    await bot.add_cog(UtilityCommands(bot))
