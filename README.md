# TheranorV1.3 Discord Bot

Bot Discord pour la gestion de personnages, combats, familiers, inventaire et utilitaires de jeu de rôle.
Système de jeu: Theranor première version.

## Fonctionnalités

- Création et gestion de personnages (`/creer`, `/creer_personnage`, `/choisir_personnage`, `/info`, etc.)
- Système de combat (`/attaquer`, `/utiliser_magie`, `/damage`, `/heal`, `/armure`, etc.)
- Gestion des familiers (`/ajouter_familier`, `/attaquer_familier`, `/info_familier`, etc.)
- Gestion d'inventaire et monnaie (`/ajouter_objet`, `/donner_objet`, `/donner_argent`, etc.)
- Outils utilitaires (`/de`, `/rencontre`, `/fouille`, `/aide`, etc.)

## Stack Technique

- Python 3.11+ recommandé
- `discord.py` (slash commands / cogs)
- SQLite (stockage local)

## Installation

1. Cloner le dépôt:

```bash
git clone <URL_DU_REPO>
cd theranorV1.3
```

2. Créer et activer un environnement virtuel:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Installer les dépendances:

```bash
pip install -r requirements.txt
```

4. Configurer l'environnement:

```bash
cp .env.example .env
```

5. Éditer `.env` avec tes valeurs réelles.

## Configuration `.env`

Variables principales:

- `TOKEN` (obligatoire): token du bot Discord
- `GUILD_ID` (obligatoire): ID de la guilde de test/sync
- `PREFIX` (optionnel, défaut `!`)
- `DATABASE_PATH` (optionnel, défaut `players.db`)
- `ADMIN_IDS` (optionnel): liste d'IDs Discord séparés par des virgules
- `MESSAGE_CONTENT_INTENT` (optionnel, défaut `true`)

## Lancer le bot

```bash
python3 main.py
```

## Architecture

- `main.py`: bootstrap du bot + chargement des extensions
- `config.py`: chargement et validation de la configuration environnementale
- `database.py`: accès SQLite + bootstrap/migrations
- `commands/`: cogs Discord + logique métier extraite
  - `*_commands.py`: orchestration des interactions Discord
  - `*_logic.py`: logique métier pure/réutilisable
  - `player_views.py`: vues Discord UI (boutons/pagination)

## Notes

Ce projet est une base de bot Discord orientée JDR, en cours d'amélioration continue.
Les évolutions sont faites selon mes besoins de jeu et de maintenance.

## Licence

MIT
