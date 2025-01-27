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
        
        # Mark key as used
        await interaction.client.db.mark_key_as_used(key['_id'], ticket['buyer_id'])
        
        # Update product panel stock count
        try:
            category = interaction.channel.category
            if category:
                for channel in category.channels:
                    async for message in channel.history(limit=100):
                        if message.author == interaction.client.user and len(message.embeds) > 0:
                            embed = message.embeds[0]
                            if str(ticket['product_id']) in embed.footer.text:
                                # Update stock status
                                stock_status = ""
                                for ltype in ['daily', 'monthly', 'lifetime']:
                                    keys = await interaction.client.db.get_available_key_count(ticket['product_id'], ltype)
                                    emoji = "🟢" if keys > 0 else "🔴"
                                    stock_status += f"{emoji} {ltype.title()}: {keys}\n"
                                
                                # Update the stock status field
                                for i, field in enumerate(embed.fields):
                                    if field.name == "📦 Stock Status":
                                        embed.set_field_at(
                                            i,
                                            name="📦 Stock Status",
                                            value=f"```\n{stock_status}```",
                                            inline=True
                                        )
                                        await message.edit(embed=embed)
                                        break
        except Exception as e:
            print(f"Error updating product panel: {e}")
        
        buyer = interaction.guild.get_member(int(ticket['buyer_id']))
        
        # Add buyer role
        buyer_role = interaction.guild.get_role(interaction.client.config.BUYER_ROLE_ID)
        if buyer_role:
            try:
                await buyer.add_roles(buyer_role)
            except Exception as e:
                print(f"Error adding buyer role: {e}")
        
        # Send key to buyer
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
        
        # Send vouch reminder
        vouch_embed = discord.Embed(
            title="⭐ Vouch Reminder",
            description=(
                f"{buyer.mention}, please don't forget to vouch for your purchase!\n\n"
                "You have 24 hours to vouch using the `/vouch` command.\n"
                "If you don't vouch within 24 hours, your buyer role will be removed."
            ),
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=vouch_embed)
        
        button.disabled = True
        await interaction.message.edit(view=self)
        
        # Schedule buyer role removal if no vouch
        await asyncio.sleep(86400)  # 24 hours
        ticket_data = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket_data.get('vouched', False):
            try:
                await buyer.remove_roles(buyer_role)
                await interaction.channel.send(
                    f"⚠️ {buyer.mention}'s buyer role has been removed due to not vouching within 24 hours."
                )
            except Exception as e:
                print(f"Error removing buyer role: {e}")
        
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

    @app_commands.command(name="vouch")
    async def vouch(self, interaction: discord.Interaction):
        """Vouch for a purchase"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if in ticket channel
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.followup.send(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
        
        # Check if user is the buyer
        if str(interaction.user.id) != ticket['buyer_id']:
            await interaction.followup.send(
                "Only the buyer can vouch for this purchase!", 
                ephemeral=True
            )
            return
        
        # Check if already vouched
        if ticket.get('vouched', False):
            await interaction.followup.send(
                "You have already vouched for this purchase!", 
                ephemeral=True
            )
            return
        
        # Update ticket with vouch
        await self.bot.db.update_ticket(ticket['_id'], {'vouched': True})
        
        # Send confirmation
        await interaction.followup.send(
            "Thank you for vouching! Your buyer role will be kept.", 
            ephemeral=True
        )
        await interaction.channel.send(
            f"✅ {interaction.user.mention} has vouched for their purchase!"
        )

async def setup(bot):
    await bot.add_cog(TicketManager(bot)) 
