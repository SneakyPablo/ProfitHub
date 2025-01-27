import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId

class PaymentMethodSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="PayPal",
                description="Pay with PayPal",
                emoji="💰",
                value="paypal"
            ),
            discord.SelectOption(
                label="Crypto",
                description="Pay with Cryptocurrency",
                emoji="💎",
                value="crypto"
            ),
            discord.SelectOption(
                label="Bank Transfer",
                description="Pay with Bank Transfer",
                emoji="🏦",
                value="bank"
            )
        ]
        super().__init__(
            placeholder="Select payment method...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="payment_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.disabled = True
        self.view.children[0].disabled = True
        
        payment_info = interaction.client.config.PAYMENT_INFO.get(self.values[0], "Payment information not available")
        
        embed = discord.Embed(
            title="💳 Payment Information",
            description=f"Please send payment using the following details:\n\n{payment_info}",
            color=discord.Color.green()
        )
        embed.set_footer(text="After sending payment, click 'Confirm Payment' below")
        
        view = ConfirmPaymentView()
        await interaction.followup.send(embed=embed, view=view)
        await interaction.message.edit(view=self.view)

class ConfirmPaymentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.payment_confirmed = False

    @discord.ui.button(label="Confirm Payment", style=discord.ButtonStyle.success, custom_id="confirm_payment")
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.payment_confirmed:
            await interaction.response.send_message("Payment already confirmed!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        self.payment_confirmed = True
        button.disabled = True
        
        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        seller = interaction.guild.get_member(int(ticket['seller_id']))
        
        embed = discord.Embed(
            title="💰 Payment Confirmation",
            description="The buyer has confirmed their payment. Please verify and deliver the product.",
            color=discord.Color.gold()
        )
        
        view = SellerConfirmationView()
        await interaction.channel.send(f"{seller.mention}", embed=embed, view=view)
        await interaction.message.edit(view=self)

class SellerConfirmationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Payment & Deliver", style=discord.ButtonStyle.success, custom_id="seller_confirm")
    async def confirm_and_deliver(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        
        key = await interaction.client.db.get_available_key(
            ticket['product_id'], 
            ticket['license_type']
        )
        if not key:
            await interaction.followup.send(
                "Error: No available keys for this product type!", 
                ephemeral=True
            )
            return
        
        await interaction.client.db.mark_key_as_used(key['_id'], ticket['buyer_id'])
        
        buyer = interaction.guild.get_member(int(ticket['buyer_id']))
        try:
            embed = discord.Embed(
                title="🔑 Your Product Key",
                description=f"Thank you for your purchase! Here's your product key:\n\n`{key['key']}`",
                color=discord.Color.green()
            )
            await buyer.send(embed=embed)
            await interaction.channel.send("✅ Product key has been delivered to buyer's DM!")
        except discord.Forbidden:
            await interaction.channel.send(
                f"⚠️ Couldn't DM the buyer. Here's the key (visible only in ticket):\n`{key['key']}`"
            )
        
        button.disabled = True
        await interaction.message.edit(view=self)
        
        # Start auto-close timer
        await asyncio.sleep(300)  # 5 minutes
        await interaction.channel.send("This ticket will be closed in 5 minutes.")
        await asyncio.sleep(300)
        
        await interaction.channel.delete()

class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tickets = set()

    def is_admin():
        async def predicate(interaction: discord.Interaction):
            return interaction.guild.get_role(interaction.client.config.ADMIN_ROLE_ID) in interaction.user.roles
        return app_commands.check(predicate)

    async def create_ticket(self, interaction: discord.Interaction, product_id: str, license_type: str = None):
        """Create a new ticket"""
        if interaction.user.id in self.active_tickets:
            await interaction.followup.send(
                "You already have an active ticket! Please complete or close it first.", 
                ephemeral=True
            )
            return
            
        self.active_tickets.add(interaction.user.id)
        
        category = interaction.guild.get_channel(self.bot.config.TICKET_CATEGORY_ID)
        product = await self.bot.db.get_product(ObjectId(product_id))
        seller = interaction.guild.get_member(int(product['seller_id']))
        
        # Create ticket channel with permissions
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            seller: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID): discord.PermissionOverwrite(
                read_messages=True, 
                send_messages=True,
                manage_channels=True
            )
        }
        
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        
        price = product['prices'].get(license_type, 0) if license_type else 0
        
        ticket_data = {
            'channel_id': str(channel.id),
            'product_id': ObjectId(product_id),
            'buyer_id': str(interaction.user.id),
            'seller_id': str(seller.id),
            'license_type': license_type,
            'price': price,
            'status': 'open'
        }
        
        ticket_id = await self.bot.db.create_ticket(ticket_data)
        
        embed = discord.Embed(
            title="🛍️ New Purchase Ticket",
            description=(
                f"**Product:** {product['name']}\n"
                f"**Type:** {license_type.title() if license_type else 'N/A'} License\n"
                f"**Price:** ${price:.2f}"
            ),
            color=discord.Color.green()
        )
        embed.add_field(name="👤 Buyer", value=interaction.user.mention)
        embed.add_field(name="💼 Seller", value=seller.mention)
        embed.add_field(name="🎫 Ticket ID", value=str(ticket_id), inline=False)
        
        await channel.send(embed=embed)
        
        view = discord.ui.View()
        view.add_item(PaymentMethodSelect())
        await channel.send(
            "Please select your payment method:", 
            view=view
        )
        
        await interaction.followup.send(
            f"Ticket created! Please check {channel.mention}", 
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(TicketManager(bot)) 
