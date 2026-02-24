import os
import discord
from discord.ext import commands
import time
import datetime
from collections import defaultdict

TOKEN = os.getenv("TOKEN")

TICKET_CATEGORY_ID = 1474827965643886864
LOG_CHANNEL_ID = 1474827965643886864  # Transcript atılacak kanal ID (TEXT KANAL OLMALI)

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
    bot.add_view(TicketButtons())
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
                f"{message.author.mention} link paylaşamaz!",
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
            custom_id="ticket_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id in open_tickets:
            return await interaction.response.send_message(
                "Zaten açık ticketin var.",
                ephemeral=True
            )

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        selected = self.values[0]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        for role_id in YETKILI_ROLLER:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

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
                "Sorununuzu detaylı yazınız."
            ),
            color=0x5865F2
        )

        await channel.send(embed=embed, view=TicketButtons())

        await interaction.response.send_message(
            f"Ticket oluşturuldu: {channel.mention}",
            ephemeral=True
        )


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ================= CLOSE BUTTON =================
class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🔒 Ticket Kapat",
            style=discord.ButtonStyle.danger,
            custom_id="ticket_close_button"
        )

    async def callback(self, interaction: discord.Interaction):
        if not any(role.id in YETKILI_ROLLER for role in interaction.user.roles):
            return await interaction.response.send_message("Yetkin yok.", ephemeral=True)

        channel = interaction.channel

        # Transcript oluştur
        transcript = []
        async for msg in channel.history(limit=None, oldest_first=True):
            transcript.append(
                f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author}: {msg.content}"
            )

        file_name = f"transcript-{channel.id}.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write("\n".join(transcript))

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"📁 Transcript - {channel.name}",
                file=discord.File(file_name)
            )

        # open_tickets temizle
        for user_id, ch_id in list(open_tickets.items()):
            if ch_id == channel.id:
                del open_tickets[user_id]

        await channel.delete()


class TicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseButton())


@bot.tree.command(name="ticketpanel", description="Atlas Destek Paneli")
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 Atlas Destek Paneli",
        description=(
            "Aşağıdan kategori seçerek ticket oluştur.\n\n"
            "🖥️ Sunucu\n"
            "📦 Pack\n"
            "⚙️ Plugin Pack\n"
            "🤖 Discord Bot"
        ),
        color=0x5865F2
    )

    await interaction.response.send_message(embed=embed, view=TicketView())


# ================= START =================
bot.run(TOKEN)
