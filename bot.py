import os
import discord
from discord.ext import commands
import time
import datetime
from collections import defaultdict
import threading
from flask import Flask

TOKEN = os.getenv("TOKEN")

TICKET_CATEGORY_ID = 1474827965643886864   # Ticket kategori ID
LOG_CHANNEL_ID = 1474827965643886864       # Transcript atılacak TEXT kanal ID

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


# ================= KEEP ALIVE =================
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

keep_alive()


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

    # Küfür
    if any(word in content.lower() for word in banned_words):
        await message.delete()
        await message.channel.send(f"{message.author.mention} küfür yasak!", delete_after=3)
        warn_data[message.author.id] += 1

    # Link engel
    if link_block and ("http://" in content or "https://" in content):
        if not any(role.id in YETKILI_ROLLER for role in message.author.roles):
            await message.delete()
            await message.channel.send(f"{message.author.mention} link paylaşamaz!", delete_after=3)

    # Caps engel
    if len(content) > 5:
        upper = sum(1 for c in content if c.isupper())
        if upper / len(content) * 100 > caps_limit:
            await message.delete()
            await message.channel.send("Caps lock yasak!", delete_after=3)

    # Spam engel
    now = time.time()
    spam_cache[message.author.id].append(now)
    spam_cache[message.author.id] = [t for t in spam_cache[message.author.id] if now - t < 4]

    if len(spam_cache[message.author.id]) > 6:
        await message.delete()

    await bot.process_commands(message)


# ================= RAID KORUMA =================
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
            title="🎫 Atlas Destek",
            description=f"Kategori: {selected}\nOluşturan: {interaction.user.mention}",
            color=0x5865F2
        )

        await channel.send(embed=embed, view=TicketButtons())

        await interaction.response.send_message(
            f"Ticket oluşturuldu: {channel.mention}",
            ephemeral=True
        )


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
                f"Transcript - {channel.name}",
                file=discord.File(file_name)
            )

        for user_id, ch_id in list(open_tickets.items()):
            if ch_id == channel.id:
                del open_tickets[user_id]

        await channel.delete()


class TicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseButton())


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


@bot.tree.command(name="ticketpanel", description="Destek paneli")
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 Atlas Destek Paneli",
        description="Kategori seçerek ticket oluştur.",
        color=0x5865F2
    )

    await interaction.response.send_message(embed=embed, view=TicketView())


bot.run(TOKEN)
