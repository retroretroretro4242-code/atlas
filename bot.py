
import os
import discord
from discord.ext import commands
from discord import app_commands
import time
from collections import defaultdict

TOKEN = os.getenv("TOKEN")
TICKET_CATEGORY_ID = 123456789012345678  # değiştir

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

spam_cache = defaultdict(list)
warn_data = defaultdict(int)
join_cache = []

banned_words = ["küfür1", "küfür2"]
link_block = True
caps_limit = 70  # %70 büyük harf

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} aktif!")

# ------------------- AUTOMOD -------------------
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
        await message.delete()
        await message.channel.send("Link paylaşmak yasak!", delete_after=3)

    # Caps engel
    if len(content) > 5:
        upper = sum(1 for c in content if c.isupper())
        if upper / len(content) * 100 > caps_limit:
            await message.delete()
            await message.channel.send("Caps lock yasak!", delete_after=3)

    # Spam
    now = time.time()
    spam_cache[message.author.id].append(now)
    spam_cache[message.author.id] = [t for t in spam_cache[message.author.id] if now - t < 4]
    if len(spam_cache[message.author.id]) > 6:
        await message.delete()

    await bot.process_commands(message)

# ------------------- RAID KORUMA -------------------
@bot.event
async def on_member_join(member):
    now = time.time()
    join_cache.append(now)
    recent = [t for t in join_cache if now - t < 10]

    if len(recent) > 8:
        await member.guild.edit(verification_level=discord.VerificationLevel.high)
        print("Raid koruma aktif!")

# ------------------- SLASH MODERATION -------------------
@bot.tree.command(name="mute", description="Kullanıcıyı susturur")
async def mute(interaction: discord.Interaction, member: discord.Member, süre: int):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("Yetkin yok!", ephemeral=True)

    await member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=süre))
    await interaction.response.send_message(f"{member} {süre} dakika susturuldu.")

@bot.tree.command(name="warn", description="Kullanıcıya uyarı verir")
async def warn(interaction: discord.Interaction, member: discord.Member):
    warn_data[member.id] += 1
    await interaction.response.send_message(f"{member} uyarıldı. Toplam warn: {warn_data[member.id]}")

@bot.tree.command(name="kick", description="Kullanıcıyı atar")
async def kick(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("Yetki yok!", ephemeral=True)

    await member.kick()
    await interaction.response.send_message(f"{member} atıldı.")

@bot.tree.command(name="ban", description="Kullanıcıyı banlar")
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("Yetki yok!", ephemeral=True)

    await member.ban()
    await interaction.response.send_message(f"{member} banlandı.")

# ------------------- TICKET SİSTEMİ -------------------
class TicketModal(discord.ui.Modal, title="Destek Talebi"):
    reason = discord.ui.TextInput(label="Sorunun nedir?", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(title="Yeni Ticket", description=self.reason.value, color=discord.Color.green())
        embed.set_footer(text=f"Oluşturan: {interaction.user}")

        await channel.send(embed=embed)
        await interaction.response.send_message(f"Ticket açıldı: {channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    @discord.ui.button(label="🎫 Ticket Aç", style=discord.ButtonStyle.green)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="ticketpanel", description="Ticket paneli oluşturur")
async def ticketpanel(interaction: discord.Interaction):
    view = TicketView(timeout=None)
    await interaction.response.send_message("Destek almak için butona bas:", view=view)

bot.run(TOKEN)
