from config import BLAGUE_PRIVEE_CHANNEL_ID, BLAGUE_PRIVEE_MJ_ID


async def blague_privee(interaction):
    if BLAGUE_PRIVEE_CHANNEL_ID is None or BLAGUE_PRIVEE_MJ_ID is None:
        return
    channel = interaction.client.get_channel(BLAGUE_PRIVEE_CHANNEL_ID)
    if channel is None:
        return
    await channel.send(
        f"<@{BLAGUE_PRIVEE_MJ_ID}> bah nan ça existe pas perception, c'est observation CONNARD !"
    )
