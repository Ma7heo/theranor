ENCOUNTER_BIOMES = ["plaine", "forêt", "océan", "désert", "montagne"]
FOUILLE_BIOMES = ["plaine", "forêt", "caverne", "désert", "montagne", "rivière", "colline", "marais", "volcan"]
LOOT_LEVELS = ["T1", "T2", "T3", "T4", "T5"]

ENCOUNTER_POOLS_BY_BIOME = {
    "océan": (
        ["animal"],
        ["monster"],
        ["Jeune Kraken", "Serpent des Mers", "Requin-Sorcier", "Golem d'Algue", "Dragonnet de Mer", "Méduse Abyssale", "Léviathan", "Kraken"],
    ),
    "désert": (
        ["animal"],
        ["Serpent des Sables", "Scorpions Géants", "Hommes-Lézards", "Araignées du Désert", "Chacals Sauvages", "Momies", "Elementaires de Terre", "Elementaires d'Air", "Vautours Géants", "Scarabs Mangeurs de Chair"],
        ["Sultan des Sables", "Scorpion Antique", "Ver des Dunes", "Pharaon Maudit", "Drake des Sables", "Sphinx"],
    ),
    "montagne": (
        ["animal"],
        ["monster"],
        ["Ours", "Loup", "Rapace", "Félin", "Bandit", "Monstre légendaire"],
    ),
}

DEFAULT_ENCOUNTER_POOLS = (
    ["Ours", "Meute de Loups", "Félins", "Rapace"],
    ["orc", "gobelin", "gnoll", "morts-vivants", "élémentaire", "lizardman"],
    ["Ours", "Loups", "Élémentaire", "Rapace", "Armée Morts-Vivants", "Armée Orc", "Félin", "Monstre Légendaire", "Armée Lizardman", "Bandit Légendaire"],
)

FOUILLE_TABLES = {
    "forêt": {
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
        "Écaille de caméléon": range(100, 101),
    },
    "rivière": {
        "Eau pure": range(1, 56),
        "Écorce d'orme": range(56, 68),
        "Algue marine": range(68, 76),
        "Écaille de poisson": range(76, 84),
        "Feuille de lotus de feu": range(84, 92),
        "Goutte d'eau bénite": range(92, 100),
        "Algue centenaire": range(100, 101),
    },
    "plaine": {
        "Feuille de menthe": range(1, 48),
        "Baies guérisseuses": range(48, 63),
        "Fleur de bouclier": range(63, 78),
        "Plume d'oiseau rapide": range(78, 85),
        "Fleur de fumée": range(85, 92),
        "Herbe rapide": range(92, 95),
        "Sabot de centaure": range(95, 98),
        "Plume d'anti-magie": range(98, 99),
        "Herbe mémorielle": range(99, 100),
        "Pétales de rose": range(100, 101),
    },
    "caverne": {
        "Toile d'araignée": range(1, 26),
        "Pierre d'annulation": range(26, 51),
        "Champignon toxique": range(51, 76),
        "Essence de cristal": range(76, 86),
        "Crystal de glace": range(86, 91),
        "Champignon luminescent": range(91, 96),
        "Crystal de minotaure": range(96, 99),
        "Crystal d'ombre": range(99, 100),
        "Cristal de clairvoyance": range(100, 101),
    },
    "colline": {
        "Poudre d'étoile": range(1, 81),
        "Poudre de lune": range(81, 93),
        "Essence de lune": range(93, 100),
        "Poudre de météorite": range(100, 101),
    },
    "montagne": {
        "Brume mystique": range(1, 30),
        "Larmes de yéti": range(30, 59),
        "Dent de serpent": range(59, 74),
        "Souffle du vent du nord": range(74, 89),
        "Pierre de force": range(89, 94),
        "Vent de zéphyr": range(94, 99),
        "Plume de phénix": range(99, 100),
        "Plume de griffon royal": range(100, 101),
    },
    "marais": {
        "Résine de gobelin": range(1, 71),
        "Venin de serpent": range(71, 97),
        "Serpent agile": range(97, 100),
        "Pétale de lotus": range(100, 101),
    },
    "désert": {
        "Poudre d'ombre": range(1, 75),
        "Ambre parfumé": range(75, 85),
        "Poussière de Clairail": range(85, 95),
        "Fleur d'ombre": range(95, 100),
        "Larme de licorne": range(100, 101),
    },
    "volcan": {
        "Goutte de lave": range(1, 41),
        "Essence de feu": range(41, 81),
        "Peau de salamandre": range(81, 101),
    },
}

LOOT_TABLES = {
    "T1": {
        "rien": range(1, 21),
        "faible somme": range(21, 61),
        "somme raisonnable": range(61, 81),
        "objet peu commun": range(81, 101),
    },
    "T2": {
        "faible somme": range(1, 16),
        "somme raisonnable": range(16, 46),
        "objet peu commun": range(46, 66),
        "objet rare": range(66, 86),
        "somme importante": range(86, 99),
        "objet epique": range(99, 101),
    },
    "T3": {
        "somme raisonnable": range(1, 26),
        "objet rare": range(26, 56),
        "somme importante": range(56, 76),
        "objet epique": range(76, 88),
        "somme consequente": range(88, 99),
        "objet legendaire": range(99, 101),
    },
    "T4": {
        "objet rare": range(1, 11),
        "somme importante": range(11, 26),
        "objet epique": range(26, 56),
        "somme consequente": range(56, 81),
        "objet legendaire": range(81, 91),
        "somme incommensurable": range(91, 101),
    },
    "T5": {
        "objet epique": range(1, 11),
        "somme consequente": range(11, 26),
        "objet legendaire": range(26, 56),
        "somme incommensurable": range(56, 86),
        "somme astronomique": range(86, 96),
        "objet mythique": range(96, 101),
    },
}

LOOT_ARGENT_TABLE = {
    "faible somme": (1, 50, "pc"),
    "somme raisonnable": (50, 300, "pc"),
    "somme importante": (3, 10, "pa"),
    "somme consequente": (10, 100, "pa"),
    "somme incommensurable": (1, 10, "po"),
    "somme astronomique": (10, 100, "po"),
}

LOOT_OBJET_TABLE = {
    "alchimie": range(1, 3),
    "arme": range(3, 6),
    "armure": range(6, 9),
    "objet magique": range(9, 12),
    "surprise": range(12, 13),
}

COMMANDS_INFO = {
    "creer": {
        "description": "Crée un utilisateur joueur.",
        "usage": "/creer",
    },
    "creer_personnage": {
        "description": "Lance le parcours de création d'un personnage.",
        "usage": "/creer_personnage",
    },
    "supprimer_personnage": {
        "description": "Supprime un personnage par son nom.",
        "usage": "/supprimer_personnage nom_personnage:<nom>",
    },
    "supprimer": {
        "description": "Supprime un utilisateur et tous ses personnages.",
        "usage": "/supprimer",
    },
    "liste_personnages": {
        "description": "Affiche la liste de vos personnages.",
        "usage": "/liste_personnages",
    },
    "choisir_personnage": {
        "description": "Définit le personnage actif.",
        "usage": "/choisir_personnage nom_personnage:<nom>",
    },
    "modifier_joueur": {
        "description": "Modifie un champ d'un joueur.",
        "usage": "/modifier_joueur champ:<champ> valeur:<valeur> [joueur] [familier:<...>]",
    },
    "monter_niveau": {
        "description": "Augmente le niveau du personnage actif.",
        "usage": "/monter_niveau [familier:<...>]",
    },
    "info": {
        "description": "Affiche la fiche du personnage actif (ou d'un joueur).",
        "usage": "/info [joueur] [familier:<...>]",
    },
    "donner_argent": {
        "description": "Transfère de l'argent à un autre joueur.",
        "usage": "/donner_argent destinataire:<membre> montant:<n> type_piece:<pc|pa|po> [familier_source:<...>] [familier_destinataire:<...>]",
    },
    "retirer_argent": {
        "description": "Retire de l'argent d'un inventaire.",
        "usage": "/retirer_argent montant:<n> type_piece:<pc|pa|po> [joueur] [familier:<...>]",
    },
    "ajouter_argent": {
        "description": "Ajoute de l'argent à un joueur.",
        "usage": "/ajouter_argent joueur:<membre> montant:<n> type_piece:<pc|pa|po> [familier:<...>]",
    },
    "ajouter_objet": {
        "description": "Ajoute un objet à l'inventaire d'un joueur.",
        "usage": "/ajouter_objet destinataire:<membre> entite:<personnage|familier> categorie:<...> nom:<...> [description] [bonus_type] [bonus_value] [degats]",
    },
    "donner_objet": {
        "description": "Donne un objet d'un joueur à un autre.",
        "usage": "/donner_objet entite_source:<personnage|familier> destinataire:<membre> entite_destinataire:<personnage|familier> categorie:<...> nom:<...>",
    },
    "retirer_objet": {
        "description": "Retire un objet de l'inventaire.",
        "usage": "/retirer_objet entite:<personnage|familier> nom:<...> [categorie] [joueur]",
    },
    "modifier_objet": {
        "description": "Modifie la description d'un objet.",
        "usage": "/modifier_objet entite:<personnage|familier> nom_objet:<...> nouvelle_description:<...>",
    },
    "ajouter_familier": {
        "description": "Crée un familier via un flow interactif (embed + pop-up + boutons).",
        "usage": "/ajouter_familier [personnage:<nom_personnage>]",
    },
    "associer_familier": {
        "description": "Associe un familier non associé à un personnage.",
        "usage": "/associer_familier nom_familier:<...> personnage:<nom_personnage>",
    },
    "attaquer": {
        "description": "Effectue une attaque avec une arme ou pugilat.",
        "usage": "/attaquer entite:<personnage|familier> weapon_name:<...> [effets...]",
    },
    "l": {
        "description": "Effectue un jet de compétence ou d'attribut.",
        "usage": "/l entite:<personnage|familier> skill_name:<...>",
    },
    "utiliser_magie": {
        "description": "Lance une magie avec effets optionnels.",
        "usage": "/utiliser_magie entite:<personnage|familier> magie_type:<magie1|magie2> [effets...]",
    },
    "damage": {
        "description": "Inflige des dégâts à un joueur.",
        "usage": "/damage joueur:<membre> expression:<dés> [familier:<...>] [armure]",
    },
    "heal": {
        "description": "Soigne un joueur.",
        "usage": "/heal expression:<dés> [joueur] [familier:<...>]",
    },
    "submana": {
        "description": "Retire du mana à un joueur.",
        "usage": "/submana expression:<dés> [joueur] [familier:<...>]",
    },
    "addmana": {
        "description": "Ajoute du mana à un joueur.",
        "usage": "/addmana expression:<dés> [joueur] [familier:<...>]",
    },
    "armure": {
        "description": "Effectue un jet d'armure.",
        "usage": "/armure entite:<personnage|familier>",
    },
    "repos_long": {
        "description": "Restaure PV/Mana d'un joueur ou de tous les joueurs.",
        "usage": "/repos_long [joueur]",
    },
    "update_db": {
        "description": "Exécute la mise à niveau de la base de données.",
        "usage": "/update_db",
    },
    "de": {
        "description": "Lance une expression de dés.",
        "usage": "/de expression:<dés>",
    },
    "rencontre": {
        "description": "Génère une rencontre aléatoire.",
        "usage": "/rencontre [biome]",
    },
    "fouille": {
        "description": "Génère un résultat de fouille aléatoire.",
        "usage": "/fouille [biome]",
    },
    "blessure": {
        "description": "Génère une blessure aléatoire.",
        "usage": "/blessure",
    },
    "init": {
        "description": "Effectue un jet d'initiative.",
        "usage": "/init entite:<personnage|familier>",
    },
    "loot": {
        "description": "Génère un loot selon le palier choisi.",
        "usage": "/loot niveau:<T1|T2|T3|T4|T5>",
    },
    "aide": {
        "description": "Affiche l'aide d'une commande.",
        "usage": "/aide command_name:<commande>",
    },
}
