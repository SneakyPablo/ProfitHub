import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === CHANNEL IDs ===
SELL_CHANNEL = 1396740394620030986
BUY_CHANNEL = 1396740410436489266
PRICE_UPDATES = 1396741041075392552
REVIEWS_CHANNEL = 1396740686333874227
REPORT_CHANNEL = 1396740712304869386
SCAMMER_LIST = 1396740728163405884

# === ROLE IDs ===
VERIFIED_SELLER = 1397205991031836843
VERIFIED_BUYER = 1397206088520175768
MIDDLEMAN_ROLE = 1397206192412950680
MUTED_ROLE = 1397206241117474828

# === BASIC COMMANDS ===
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def sell(ctx, amount: str, price: str, server: str):
    embed = discord.Embed(title="🛒 New Silk for Sale!", color=discord.Color.green())
    embed.add_field(name="Amount", value=amount, inline=True)
    embed.add_field(name="Price", value=price, inline=True)
    embed.add_field(name="Server", value=server, inline=True)
    embed.set_footer(text=f"Seller: {ctx.author}")
    channel = bot.get_channel(SELL_CHANNEL)
    await channel.send(embed=embed)
    await ctx.send("✅ Posted in #sell-silk")

@bot.command()
async def buy(ctx, amount: str, price: str, server: str):
    embed = discord.Embed(title="📢 Buying Silk!", color=discord.Color.blue())
    embed.add_field(name="Amount", value=amount, inline=True)
    embed.add_field(name="Price", value=price, inline=True)
    embed.add_field(name="Server", value=server, inline=True)
    embed.set_footer(text=f"Buyer: {ctx.author}")
    channel = bot.get_channel(BUY_CHANNEL)
    await channel.send(embed=embed)
    await ctx.send("✅ Posted in #buy-silk")

@bot.command()
async def updateprice(ctx, *, price_info: str):
    if ctx.author.guild_permissions.administrator:
        embed = discord.Embed(title="📈 New Price Update", description=price_info, color=discord.Color.orange())
        embed.set_footer(text=f"Updated by {ctx.author}")
        await bot.get_channel(PRICE_UPDATES).send(embed=embed)
        await ctx.send("✅ Price updated.")
    else:
        await ctx.send("❌ You don't have permission to do this.")

@bot.command()
async def vouch(ctx, member: discord.Member, *, review: str):
    embed = discord.Embed(title="✅ New Vouch", color=discord.Color.gold())
    embed.add_field(name="User", value=member.mention, inline=False)
    embed.add_field(name="Review", value=review, inline=False)
    embed.set_footer(text=f"From: {ctx.author}")
    await bot.get_channel(REVIEWS_CHANNEL).send(embed=embed)
    await ctx.send("✅ Vouch submitted.")

@bot.command()
async def report(ctx, member: discord.Member, *, reason: str):
    embed = discord.Embed(title="🚨 Scammer Reported", color=discord.Color.red())
    embed.add_field(name="User", value=member.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Reported by: {ctx.author}")
    await bot.get_channel(REPORT_CHANNEL).send(embed=embed)
    await bot.get_channel(SCAMMER_LIST).send(f"{member.mention} - {reason}")
    await ctx.send("⚠️ Scammer report submitted.")

# === TICKET SYSTEM ===
@bot.command()
async def ticket(ctx):
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
    }
    ticket_channel = await ctx.guild.create_text_channel(name=f"ticket-{ctx.author.name}", overwrites=overwrites)

    confirm_buyer = Button(label="Confirm Buyer", style=discord.ButtonStyle.green)
    confirm_payment = Button(label="Confirm Payment", style=discord.ButtonStyle.blurple)
    close_ticket = Button(label="Close Ticket", style=discord.ButtonStyle.red)

    async def confirm_buyer_callback(interaction):
        await ticket_channel.send("✅ Buyer Confirmed!")
        await interaction.response.defer()

    async def confirm_payment_callback(interaction):
        await ticket_channel.send("💰 Payment Confirmed!")
        await interaction.response.defer()

    async def close_ticket_callback(interaction):
        await ticket_channel.send("❌ Closing ticket...")
        await ticket_channel.delete()
        await interaction.response.defer()

    confirm_buyer.callback = confirm_buyer_callback
    confirm_payment.callback = confirm_payment_callback
    close_ticket.callback = close_ticket_callback

    view = View()
    view.add_item(confirm_buyer)
    view.add_item(confirm_payment)
    view.add_item(close_ticket)

    await ticket_channel.send(f"Welcome {ctx.author.mention}! Use the buttons below to manage your trade.", view=view)
    await ctx.send("🎟️ Ticket created!")

# === Replace with your token below ===
TOKEN = "MTMyODQ1MTY2NTYwMjU0Mzc2OA.GdEGri.dSRzoG3WXcWBjh8DspqL_xToJkUrivgRNS5rJQ"
bot.run(TOKEN)
