import discord


def info_embed(description: str, title: str = "Theranor") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.blurple())


def success_embed(description: str, title: str = "Theranor") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.green())


def warning_embed(description: str, title: str = "Theranor") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.orange())


def error_embed(description: str, title: str = "Theranor") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.red())


def roll_embed(description: str, title: str = "Jet de dé") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.gold())


def coerce_content_to_embed(
    content: str | None,
    embed: discord.Embed | None,
    title: str = "Theranor",
) -> tuple[str | None, discord.Embed | None]:
    if embed is not None or content is None:
        return content, embed
    return None, info_embed(content, title=title)
