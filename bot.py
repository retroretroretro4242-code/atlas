import os
import discord
from discord.ext import commands
import time
import datetime
from collections import defaultdict

TOKEN = os.getenv("TOKEN")

TICKET_CATEGORY_ID = 1474827965643886864
LOG_CHANNEL_ID = 1474827965643886864  # TEXT kanal olmalı

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

    # Yetkili mi kontrol et
    is_staff = any(role.id in YETKILI_ROLLER for role in message.author.roles)

    content = message.content.lower()

    # ================= KÜFÜR =================
    if not is_staff:
        if any(word in content for word in banned_words):
            await message.delete()
            await message.channel.send("Küfür yasak!", delete_after=3)
            warn_data[message.author.id] += 1
            return

    # ================= CAPS =================
    if not is_staff:
        if len(message.content) > 5:
            upper = sum(1 for c in message.content if c.isupper())
            if upper / len(message.content) * 100 > caps_limit:
                await message.delete()
                await message.channel.send("Caps yasak!", delete_after=3)
                return

    # ================= LINK =================
    if not is_staff:
        if "http://" in content or "https://" in content or "discord.gg" in content:
            await message.delete()
            await message.channel.send("Link paylaşmak yasak!", delete_after=3)
            return

    # ================= SPAM =================
    now = time.time()
    spam_cache[message.author.id].append(now)
    spam_cache[message.author.id] = [t for t in spam_cache[message.author.id] if now - t < 4]

    if not is_staff:
        if len(spam_cache[message.author.id]) > 6:
            await message.delete()
            return

    await bot.process_commands(message)

# ================= RAID =================
@bot.event
async def on_member_join(member):
    now = time.time()
    join_cache.append(now)
    recent = [t for t in join_cache if now - t < 10]

    if len(recent) > 8:
        await member.guild.edit(verification_level=discord.VerificationLevel.high)


# ================= SLASH =================
@bot.tree.command(name="mute", description="Kullanıcıyı susturur")
async def mute(interaction: discord.Interaction, member: discord.Member, süre: int):
    until = discord.utils.utcnow() + datetime.timedelta(minutes=süre)
    await member.timeout(until)
    await interaction.response.send_message(f"{member.mention} {süre} dakika susturuldu.")


@bot.tree.command(name="warn", description="Warn verir")
async def warn(interaction: discord.Interaction, member: discord.Member):
    warn_data[member.id] += 1
    await interaction.response.send_message(
        f"{member.mention} uyarıldı. Toplam: {warn_data[member.id]}"
    )


# ================= TICKET =================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Sipariş", description="Yeni sipariş vermek istiyorum", emoji="🛒"),
            discord.SelectOption(label="Destek", description="Bir sorunum var", emoji="🛠️"),
            discord.SelectOption(label="Proje İsteği", description="Özel proje talebi", emoji="⭐"),
            discord.SelectOption(label="Ücretsiz Proje", description="Ücretsiz proje bilgisi", emoji="🎁"),
            discord.SelectOption(label="Diğer", description="Diğer konular", emoji="❓"),
        ]

        super().__init__(
            placeholder="Bir kategori seç...",
            options=options,
            custom_id="ticket_select"
        )

    async def callback(self, interaction: discord.Interaction):

        if interaction.user.id in open_tickets:
            return await interaction.response.send_message(
                "Zaten açık ticketin var.",
                ephemeral=True
            )

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

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
            description=f"{interaction.user.mention} talebiniz oluşturuldu.\n\nYetkili ekip en kısa sürede ilgilenecektir.",
            color=0x2b2d31
        )

        embed.set_footer(text="Atlas Project Destek Sistemi")

        await channel.send(
            content=" ".join([f"<@&{r}>" for r in YETKILI_ROLLER]),
            embed=embed,
            view=TicketButtons()
        )

        await interaction.response.send_message(
            f"Ticket oluşturuldu: {channel.mention}",
            ephemeral=True
        )


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🔒 Ticket Kapat",
            style=discord.ButtonStyle.danger,
            custom_id="ticket_close"
        )

    async def callback(self, interaction: discord.Interaction):

        channel = interaction.channel

        transcript = []
        async for msg in channel.history(limit=None, oldest_first=True):
            transcript.append(f"{msg.author}: {msg.content}")

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


@bot.tree.command(name="ticketpanel", description="Atlas Project Ticket Paneli")
async def ticketpanel(interaction: discord.Interaction):

    embed = discord.Embed(
        title="📩 Atlas Project - Destek Merkezi",
        description=(
            "**Destek Merkezi Hakkında**\n"
            "Aşağıdaki kategorilerden uygun olanı seçerek hemen ticket oluşturabilirsiniz.\n\n"
            "⚠ Gereksiz ticket açmayınız."
        ),
        color=0x2b2d31
    )

    embed.add_field(
        name="Sunucu Bilgisi",
        value="Kuralları okumayı unutmayın.",
        inline=False
    )

    embed.set_footer(text="Atlas Project © 2026")

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


bot.run(TOKEN)
