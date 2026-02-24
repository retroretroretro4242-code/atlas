import os
import discord
from discord.ext import commands
from discord import app_commands
import time
import datetime
from collections import defaultdict

TOKEN = os.getenv("TOKEN")

TICKET_CATEGORY_ID = 1474827965643886864  # Ticketların açılacağı kategori
LOG_CATEGORY_ID = 1474827965643886864     # Log kategorisi (istersen ayrı yap)

YETKILI_ROLLER = [
    1474831393644220599,
    1384294618195169311,
    1474830960393453619,
    1474831019017371678,
    1474831132062122005,
    1474831344273068063
]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

spam_cache = defaultdict(list)
warn_data = defaultdict(int)
join_cache = []
open_tickets = {}

banned_words = ["küfür1", "küfür2"]
link_block = True
caps_limit = 70


# ================= READY =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(TicketView())
    print(f"{bot.user} aktif!")


# ================= AUTOMOD =================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content

    if any(word in content.lower() for word in banned_words):
        await message.delete()
        await message.channel.send(f"{message.author.mention} küfür yasak!", delete_after=3)
        warn_data[message.author.id] += 1

    if link_block and ("http://" in content or "https://" in content):
        if not any(role.id in YETKILI_ROLLER for role in message.author.roles):
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} link paylaşamaz! (Sadece yetkililer)",
                delete_after=3
            )

    if len(content) > 5:
        upper = sum(1 for c in content if c.isupper())
        if upper / len(content) * 100 > caps_limit:
            await message.delete()
            await message.channel.send("Caps lock yasak!", delete_after=3)

    now = time.time()
    spam_cache[message.author.id].append(now)
    spam_cache[message.author.id] = [t for t in spam_cache[message.author.id] if now - t < 4]

    if len(spam_cache[message.author.id]) > 6:
        await message.delete()

    await bot.process_commands(message)


# ================= RAID =================
@bot.event
async def on_member_join(member):
    now = time.time()
    join_cache.append(now)
    recent = [t for t in join_cache if now - t < 10]

    if len(recent) > 8:
        await member.guild.edit(verification_level=discord.VerificationLevel.high)
        print("Raid koruma aktif!")


# ================= MODERATION =================
@bot.tree.command(name="mute", description="Kullanıcıyı susturur")
async def mute(interaction: discord.Interaction, member: discord.Member, süre: int):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("Yetkin yok!", ephemeral=True)

    until = discord.utils.utcnow() + datetime.timedelta(minutes=süre)
    await member.timeout(until)
    await interaction.response.send_message(f"{member.mention} {süre} dakika susturuldu.")


@bot.tree.command(name="warn", description="Kullanıcıya uyarı verir")
async def warn(interaction: discord.Interaction, member: discord.Member):
    warn_data[member.id] += 1
    await interaction.response.send_message(
        f"{member.mention} uyarıldı. Toplam warn: {warn_data[member.id]}"
    )


@bot.tree.command(name="kick", description="Kullanıcıyı atar")
async def kick(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("Yetki yok!", ephemeral=True)

    await member.kick()
    await interaction.response.send_message(f"{member.mention} atıldı.")


@bot.tree.command(name="ban", description="Kullanıcıyı banlar")
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("Yetki yok!", ephemeral=True)

    await member.ban()
    await interaction.response.send_message(f"{member.mention} banlandı.")


# ================= TICKET SELECT =================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Sunucu", emoji="🖥️"),
            discord.SelectOption(label="Pack", emoji="📦"),
            discord.SelectOption(label="Plugin Pack", emoji="⚙️"),
            discord.SelectOption(label="Discord Bot", emoji="🤖"),
        ]

        super().__init__(
            placeholder="Destek kategorisi seç...",
            options=options,
            custom_id="ticket_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id in open_tickets:
            return await interaction.response.send_message(
                "Zaten açık bir ticketin var.",
                ephemeral=True
            )

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        selected = self.values[0]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        for role_id in YETKILI_ROLLER:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        open_tickets[interaction.user.id] = channel.id

        embed = discord.Embed(
            title="🎫 Atlas Project Destek",
            description=(
                f"**Kategori:** {selected}\n"
                f"**Oluşturan:** {interaction.user.mention}\n\n"
                "Lütfen sorununuzu detaylı şekilde yazınız."
            ),
            color=0x5865F2
        )

        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"Ticket oluşturuldu: {channel.mention}",
            ephemeral=True
        )

        # LOG
        log_embed = discord.Embed(
            title="📁 Yeni Ticket",
            description=f"{interaction.user} | {selected}\n{channel.mention}",
            color=discord.Color.green()
        )

        log_category = guild.get_channel(LOG_CATEGORY_ID)
        if log_category and isinstance(log_category, discord.CategoryChannel):
            if log_category.text_channels:
                await log_category.text_channels[0].send(embed=log_embed)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


@bot.tree.command(name="ticketpanel", description="Atlas Destek Paneli")
async def ticketpanel(interaction: discord.Interaction):

    embed = discord.Embed(
        title="🚀 Atlas Project Destek Paneli",
        description=(
            "Destek almak için aşağıdan kategori seç.\n\n"
            "🖥️ Sunucu\n"
            "📦 Pack\n"
            "⚙️ Plugin Pack\n"
            "🤖 Discord Bot"
        ),
        color=0x5865F2
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


# ================= START =================
bot.run(TOKEN)
