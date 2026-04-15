import discord
from discord import Interaction

from commands.embed_utils import warning_embed
from commands.player_logic import build_base_info_embed


class InfoNavigationView(discord.ui.View):
    def __init__(self, user_id, player_data):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.player_data = player_data

    @discord.ui.button(label="📋 Stats", style=discord.ButtonStyle.success)
    async def stats_button(self, interaction: Interaction, button: discord.ui.Button):
        embed = build_base_info_embed(self.player_data)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🐾 Familiers", style=discord.ButtonStyle.primary)
    async def familiers_button(self, interaction: Interaction, button: discord.ui.Button):
        familiers = self.player_data["familiers"]
        description = "\n".join([f"- {f['nom']}" for f in familiers]) or "Aucun familier"
        embed = discord.Embed(title="Familiers", description=description, color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🧠 Skills", style=discord.ButtonStyle.primary)
    async def skills_button(self, interaction: Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Compétences", color=discord.Color.green())
        for stat, values in self.player_data["skills"].items():
            content = "\n".join([f"{name}: {val}" for name, val in values.items()])
            embed.add_field(name=stat.capitalize(), value=content or "Aucune", inline=True)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚔️ Équipement", style=discord.ButtonStyle.primary)
    async def equip_button(self, interaction: Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Équipement", color=discord.Color.green())
        armes = self.player_data["inventory"]["armes"]
        armures = self.player_data["inventory"]["armures"]
        armes_text = "\n".join([f"{a['nom']}: {a['description']} (+{a['bonus_value']} {a['bonus_type']})" for a in armes]) or "Aucune arme"
        armures_text = "\n".join([f"{a['nom']}: {a['description']} (+{a['bonus_value']} {a['bonus_type']})" for a in armures]) or "Aucune armure"
        embed.add_field(name="Armes", value=armes_text, inline=False)
        embed.add_field(name="Armures", value=armures_text, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🎒 Inventaire", style=discord.ButtonStyle.primary)
    async def inventaire_button(self, interaction: Interaction, button: discord.ui.Button):
        objets = self.player_data["inventory"]["autres_objets"]
        pages = [objets[i : i + 20] for i in range(0, len(objets), 20)] or [[]]
        embed = self._get_inventory_embed(pages, 0)
        await interaction.response.edit_message(embed=embed, view=InventoryView(self.user_id, self.player_data, pages, 0))

    def _get_inventory_embed(self, pages, page):
        embed = discord.Embed(title=f"Inventaire - Page {page + 1}/{len(pages)}", color=discord.Color.green())
        lines = [f"• {obj['nom']} : {obj['description']} (+{obj['bonus_value']} {obj['bonus_type']})" for obj in pages[page]]
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


class CreationOwnerView(discord.ui.View):
    def __init__(self, user_id, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = str(user_id)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                embed=warning_embed("Cette interaction ne vous est pas destinée.", title="Interaction"),
                ephemeral=True,
            )
            return False
        return True


class OpenModalView(CreationOwnerView):
    def __init__(self, user_id, modal_factory, button_label):
        super().__init__(user_id)
        self.modal_factory = modal_factory
        button = discord.ui.Button(label=button_label, style=discord.ButtonStyle.primary)
        button.callback = self._open_modal
        self.add_item(button)

    async def _open_modal(self, interaction: Interaction):
        await interaction.response.send_modal(self.modal_factory())


class _RaceSelect(discord.ui.Select):
    def __init__(self, cog, user_id, options):
        self.cog = cog
        self.user_id = str(user_id)
        select_options = [discord.SelectOption(label=option, value=option) for option in options]
        super().__init__(placeholder="Choisissez une race", min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: Interaction):
        await self.cog.handle_creation_race_selection(interaction, self.user_id, self.values[0])


class RaceSelectionView(CreationOwnerView):
    def __init__(self, cog, user_id, options):
        super().__init__(user_id)
        self.add_item(_RaceSelect(cog, user_id, options))


class _MagicSelect(discord.ui.Select):
    def __init__(self, cog, user_id, options, step):
        self.cog = cog
        self.user_id = str(user_id)
        self.step = step
        select_options = [discord.SelectOption(label=option, value=option) for option in options]
        placeholder = "Choisissez votre première magie" if step == 5 else "Choisissez votre deuxième magie"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: Interaction):
        await self.cog.handle_creation_magic_selection(interaction, self.user_id, self.values[0], self.step)


class MagicSelectionView(CreationOwnerView):
    def __init__(self, cog, user_id, options, step):
        super().__init__(user_id)
        self.add_item(_MagicSelect(cog, user_id, options, step))


class CharacterIdentityModal(discord.ui.Modal, title="Création de personnage"):
    name_input = discord.ui.TextInput(
        label="Nom du personnage",
        placeholder="Exemple: Tharion",
        min_length=2,
        max_length=32,
    )
    age_input = discord.ui.TextInput(
        label="Âge du personnage",
        placeholder="Exemple: 25",
        min_length=1,
        max_length=3,
    )

    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = str(user_id)

    async def on_submit(self, interaction: Interaction):
        await self.cog.handle_creation_identity_submit(
            interaction,
            self.user_id,
            self.name_input.value,
            self.age_input.value,
        )


class AttributeDistributionModal(discord.ui.Modal, title="Répartition des attributs"):
    def __init__(self, cog, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = str(user_id)
        self.attribute_inputs = {}
        fields = [("for", "Force (FOR)"), ("agi", "Agilité (AGI)"), ("cha", "Charisme (CHA)"), ("int", "Intelligence (INT)")]
        for key, label in fields:
            text_input = discord.ui.TextInput(
                label=label,
                placeholder="0",
                required=True,
                max_length=2,
            )
            self.attribute_inputs[key] = text_input
            self.add_item(text_input)

    async def on_submit(self, interaction: Interaction):
        values = {key: text_input.value for key, text_input in self.attribute_inputs.items()}
        await self.cog.handle_creation_attribute_submit(interaction, self.user_id, values)


class SkillAdjustButton(discord.ui.Button):
    def __init__(self, user_id, category, skill_name, delta, row, adjust_handler):
        self.user_id = str(user_id)
        self.category = category
        self.skill_name = skill_name
        self.delta = delta
        self.adjust_handler = adjust_handler
        symbol = "+" if delta > 0 else "-"
        label = f"{symbol} {skill_name.replace('_', ' ')[:70]}"
        style = discord.ButtonStyle.success if delta > 0 else discord.ButtonStyle.danger
        super().__init__(label=label, style=style, row=row)

    async def callback(self, interaction: Interaction):
        await self.adjust_handler(interaction, self.user_id, self.category, self.skill_name, self.delta)


class SkillCategoryView(CreationOwnerView):
    def __init__(self, cog, user_id, category, skills, adjust_handler, back_handler):
        super().__init__(user_id)
        self.cog = cog
        self.category = category
        self.adjust_handler = adjust_handler
        self.back_handler = back_handler

        for index, skill_name in enumerate(skills):
            row = index // 2
            plus_button = SkillAdjustButton(user_id, category, skill_name, 1, row, adjust_handler)
            minus_button = SkillAdjustButton(user_id, category, skill_name, -1, row, adjust_handler)
            self.add_item(plus_button)
            self.add_item(minus_button)

        back_button = discord.ui.Button(label="Retour", style=discord.ButtonStyle.secondary, row=4)
        back_button.callback = self._go_back
        self.add_item(back_button)

    async def _go_back(self, interaction: Interaction):
        await self.back_handler(interaction, self.user_id)


class SkillDistributionView(CreationOwnerView):
    def __init__(self, cog, user_id, open_category_handler, validate_handler):
        super().__init__(user_id)
        self.cog = cog
        self.open_category_handler = open_category_handler
        self.validate_handler = validate_handler

    @discord.ui.button(label="FORCE", style=discord.ButtonStyle.primary)
    async def force_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.open_category_handler(interaction, self.user_id, "force")

    @discord.ui.button(label="AGILITE", style=discord.ButtonStyle.primary)
    async def agilite_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.open_category_handler(interaction, self.user_id, "agilite")

    @discord.ui.button(label="CHARISME", style=discord.ButtonStyle.primary)
    async def charisme_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.open_category_handler(interaction, self.user_id, "charisme")

    @discord.ui.button(label="INTELLIGENCE", style=discord.ButtonStyle.primary)
    async def intelligence_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.open_category_handler(interaction, self.user_id, "intelligence")

    @discord.ui.button(label="Valider", style=discord.ButtonStyle.success, row=1)
    async def validate_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.validate_handler(interaction, self.user_id)


class LevelUpAttributeView(CreationOwnerView):
    def __init__(self, cog, user_id):
        super().__init__(user_id)
        self.cog = cog

    @discord.ui.button(label="FOR +1", style=discord.ButtonStyle.primary)
    async def for_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.handle_level_up_attribute_selection(interaction, self.user_id, "for")

    @discord.ui.button(label="AGI +1", style=discord.ButtonStyle.primary)
    async def agi_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.handle_level_up_attribute_selection(interaction, self.user_id, "agi")

    @discord.ui.button(label="CHA +1", style=discord.ButtonStyle.primary)
    async def cha_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.handle_level_up_attribute_selection(interaction, self.user_id, "cha")

    @discord.ui.button(label="INT +1", style=discord.ButtonStyle.primary)
    async def int_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.cog.handle_level_up_attribute_selection(interaction, self.user_id, "int")
