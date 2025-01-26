import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
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
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        payment_info = {
            "paypal": "PayPal Email: example@email.com",
            "crypto": "Wallet Address: YOUR_WALLET_ADDRESS",
            "bank": "Bank Details: \nBank: Example Bank\nIBAN: XX00 0000 0000 0000"
        }
        
        embed = discord.Embed(
            title="💳 Payment Information",
            description=f"Please send payment using the following details:\n\n{payment_info[self.values[0]]}",
            color=discord.Color.green()
        )
        embed.set_footer(text="After sending payment, click 'Confirm Payment' below")
        
        view = ConfirmPaymentView()
        await interaction.response.send_message(embed=embed, view=view)

class ConfirmPaymentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.payment_confirmed = False

    @discord.ui.button(label="Confirm Payment", style=discord.ButtonStyle.success)
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.payment_confirmed:
            await interaction.response.send_message("Payment already confirmed!", ephemeral=True)
            return
            
        self.payment_confirmed = True
        button.disabled = True
        
        # Notify seller
        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        seller = interaction.guild.get_member(int(ticket['seller_id']))
        
        embed = discord.Embed(
            title="💰 Payment Confirmation",
            description="The buyer has confirmed their payment. Please verify and deliver the product.",
            color=discord.Color.gold()
        )
        
        view = SellerConfirmationView()
        await interaction.channel.send(f"{seller.mention}", embed=embed, view=view)
        await interaction.response.edit_message(view=self)

class SellerConfirmationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Payment & Deliver", style=discord.ButtonStyle.success)
    async def confirm_and_deliver(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        
        # Get an available key
        key = await interaction.client.db.get_available_key(ticket['product_id'])
        if not key:
            await interaction.response.send_message(
                "Error: No available keys for this product!", 
                ephemeral=True
            )
            return
        
        # Mark key as used
        await interaction.client.db.mark_key_as_used(key['_id'], ticket['buyer_id'])
        
        # Get buyer and send DM
        buyer = interaction.guild.get_member(int(ticket['buyer_id']))
        try:
            embed = discord.Embed(
                title="🔑 Your Product Key",
                description=f"Thank you for your purchase! Here's your product key:\n\n`{key['key']}`",
                color=discord.Color.green()
            )
            await buyer.send(embed=embed)
            
            # Send confirmation in ticket
            await interaction.channel.send("✅ Product key has been delivered to buyer's DM!")
        except discord.Forbidden:
            await interaction.channel.send(
                f"⚠️ Couldn't DM the buyer. Here's the key (visible only in ticket):\n`{key['key']}`"
            )
        
        # Disable the button
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Update product panel if it exists
        try:
            product = await interaction.client.db.get_product(ticket['product_id'])
            if product:
                # Find and update the product panel
                async for message in interaction.channel.guild.get_channel(ticket['channel_id']).history():
                    if message.author == interaction.client.user and len(message.embeds) > 0:
                        embed = message.embeds[0]
                        keys_available = await interaction.client.db.get_available_key_count(ticket['product_id'])
                        for field in embed.fields:
                            if field.name == "📦 Stock":
                                field.value = f"Keys Available: {keys_available}"
                                await message.edit(embed=embed)
                                break
        except Exception as e:
            print(f"Error updating product panel: {e}")
        
        # Start auto-close timer
        await asyncio.sleep(300)  # 5 minutes
        await interaction.channel.send("This ticket will be closed in 5 minutes.")
        await asyncio.sleep(300)
        await interaction.channel.delete()

class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tickets = set()  # Track active tickets per user

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingRole):
            await interaction.response.send_message(
                f"You don't have permission to use this command.", 
                ephemeral=True
            )
        else:
            print(f'Error in {interaction.command.name}: {str(error)}')

    async def create_ticket(self, interaction: discord.Interaction, product_id: str, license_type: str = None):
        """Create a new ticket"""
        # Check if user already has an active ticket
        if interaction.user.id in self.active_tickets:
            await interaction.response.send_message(
                "You already have an active ticket! Please complete or close it first.", 
                ephemeral=True
            )
            return
            
        # Create ticket channel and add to active tickets
        self.active_tickets.add(interaction.user.id)
        
        category = interaction.guild.get_channel(self.bot.config.TICKET_CATEGORY_ID)
        product = await self.bot.db.get_product(ObjectId(product_id))
        seller = interaction.guild.get_member(int(product['seller_id']))
        
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True),
                seller: discord.PermissionOverwrite(read_messages=True)
            }
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
        
        # Send initial ticket message
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
        await channel.send(embed=embed)
        
        # Send payment method selector
        payment_view = PaymentView()
        await channel.send(
            "Please select your payment method (you can only select once):", 
            view=payment_view
        )
        
        await interaction.response.send_message(
            f"Ticket created! Please check {channel.mention}", 
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_ticket_inactive(self):
        while True:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.bot.config.AUTO_CLOSE_HOURS)
            async for ticket in self.bot.db.tickets.find({'status': 'open'}):
                channel = self.bot.get_channel(int(ticket['channel_id']))
                if not channel:
                    continue
                    
                last_message = await channel.history(limit=1).flatten()
                if not last_message:
                    continue
                    
                if last_message[0].created_at < cutoff_time:
                    await channel.send("This ticket has been inactive for too long and will be closed.")
                    await channel.delete()
                    await self.bot.db.update_ticket(
                        ticket['_id'],
                        {
                            'status': 'closed',
                            'closed_at': datetime.utcnow()
                        }
                    )
            
            await asyncio.sleep(3600)  # Check every hour

class PaymentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PaymentMethodSelect())

async def setup(bot):
    await bot.add_cog(TicketManager(bot)) 
