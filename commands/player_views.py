import discord
from discord import Interaction

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
