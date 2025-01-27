import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import io
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
            disabled=False
        )

    async def callback(self, interaction: discord.Interaction):
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
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(embed=embed, view=view)

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
        
        key = await interaction.client.db.get_available_key(
            ticket['product_id'], 
            ticket['license_type']
        )
        if not key:
            await interaction.response.send_message(
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
        await interaction.response.edit_message(view=self)
        
        # Start auto-close timer
        await asyncio.sleep(300)  # 5 minutes
        await interaction.channel.send("This ticket will be closed in 5 minutes.")
        await asyncio.sleep(300)
        
        # Save transcript before closing
        await self.save_transcript(interaction.channel, ticket['_id'])
        await interaction.channel.delete()

    async def save_transcript(self, channel, ticket_id):
        """Save final transcript before closing ticket"""
        messages = await channel.history(limit=None, oldest_first=True).flatten()
        transcript_data = {
            'ticket_id': ticket_id,
            'channel_id': str(channel.id),
            'messages': [
                {
                    'content': msg.content,
                    'author_id': str(msg.author.id),
                    'created_at': msg.created_at,
                    'attachments': [att.url for att in msg.attachments]
                }
                for msg in messages
            ],
            'closed_at': datetime.utcnow()
        }
        await channel.guild.get_channel(channel.guild.system_channel.id).send(
            f"Ticket {ticket_id} closed. Transcript saved."
        )
        class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tickets = set()

    def is_admin():
        async def predicate(interaction: discord.Interaction):
            return interaction.guild.get_role(interaction.client.config.ADMIN_ROLE_ID) in interaction.user.roles
        return app_commands.check(predicate)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Save messages sent in ticket channels"""
        if message.author.bot or not isinstance(message.channel, discord.TextChannel):
            return
            
        ticket = await self.bot.db.get_ticket_by_channel(str(message.channel.id))
        if not ticket:
            return
            
        message_data = {
            'ticket_id': ticket['_id'],
            'channel_id': str(message.channel.id),
            'author_id': str(message.author.id),
            'content': message.content,
            'created_at': message.created_at,
            'attachments': [att.url for att in message.attachments]
        }
        
        await self.bot.db.save_message(message_data)

    async def create_ticket(self, interaction: discord.Interaction, product_id: str, license_type: str = None):
        """Create a new ticket"""
        if interaction.user.id in self.active_tickets:
            await interaction.response.send_message(
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
            'status': 'open',
            'created_at': datetime.utcnow()
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
        
        payment_view = PaymentView()
        await channel.send(
            "Please select your payment method (you can only select once):", 
            view=payment_view
        )
        
        await interaction.response.send_message(
            f"Ticket created! Please check {channel.mention}", 
            ephemeral=True
        )

    @app_commands.command(name="close")
    async def close_ticket(self, interaction: discord.Interaction):
        """Close the current ticket"""
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
            
        # Check if user has permission to close ticket
        is_admin = interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles
        is_seller = str(interaction.user.id) == ticket['seller_id']
        is_buyer = str(interaction.user.id) == ticket['buyer_id']
        
        if not (is_admin or is_seller or is_buyer):
            await interaction.response.send_message(
                "You don't have permission to close this ticket!", 
                ephemeral=True
            )
            return
        
        await interaction.response.send_message("Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        
        # Save transcript before closing
        messages = await interaction.channel.history(limit=None, oldest_first=True).flatten()
        transcript_data = {
            'ticket_id': ticket['_id'],
            'channel_id': str(interaction.channel.id),
            'messages': [
                {
                    'content': msg.content,
                    'author_id': str(msg.author.id),
                    'created_at': msg.created_at,
                    'attachments': [att.url for att in msg.attachments]
                }
                for msg in messages
            ],
            'closed_at': datetime.utcnow(),
            'closed_by': str(interaction.user.id)
        }
        
        await self.bot.db.update_ticket(
            ticket['_id'],
            {
                'status': 'closed',
                'closed_at': datetime.utcnow(),
                'closed_by': str(interaction.user.id)
            }
        )
        
        # Remove from active tickets
        if int(ticket['buyer_id']) in self.active_tickets:
            self.active_tickets.remove(int(ticket['buyer_id']))
        
        await interaction.channel.delete()

    @app_commands.command(name="transcript")
    async def get_transcript(self, interaction: discord.Interaction):
        """Get chat transcript for current ticket"""
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
    @app_commands.command(name="adduser")
    @is_admin()
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        """Add a user to the current ticket (Admin only)"""
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
        
        await interaction.channel.set_permissions(user, 
            read_messages=True,
            send_messages=True
        )
        
        await interaction.response.send_message(
            f"Added {user.mention} to the ticket.",
            allowed_mentions=discord.AllowedMentions(users=True)
        )

    @app_commands.command(name="removeuser")
    @is_admin()
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        """Remove a user from the current ticket (Admin only)"""
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
        
        # Don't allow removing the buyer or seller
        if str(user.id) in [ticket['buyer_id'], ticket['seller_id']]:
            await interaction.response.send_message(
                "Cannot remove the buyer or seller from the ticket!", 
                ephemeral=True
            )
            return
        
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(f"Removed {user.mention} from the ticket.")

    @app_commands.command(name="forceclose")
    @is_admin()
    async def force_close(self, interaction: discord.Interaction):
        """Force close a ticket (Admin only)"""
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
        
        await interaction.response.send_message("⚠️ Force closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        
        # Save transcript before closing
        messages = await interaction.channel.history(limit=None, oldest_first=True).flatten()
        transcript_data = {
            'ticket_id': ticket['_id'],
            'channel_id': str(interaction.channel.id),
            'messages': [
                {
                    'content': msg.content,
                    'author_id': str(msg.author.id),
                    'created_at': msg.created_at,
                    'attachments': [att.url for att in msg.attachments]
                }
                for msg in messages
            ],
            'closed_at': datetime.utcnow(),
            'closed_by': str(interaction.user.id),
            'force_closed': True
        }
        
        await self.bot.db.update_ticket(
            ticket['_id'],
            {
                'status': 'force_closed',
                'closed_at': datetime.utcnow(),
                'closed_by': str(interaction.user.id),
                'force_closed': True
            }
        )
        
        # Remove from active tickets
        if int(ticket['buyer_id']) in self.active_tickets:
            self.active_tickets.remove(int(ticket['buyer_id']))
        
        # Notify users
        try:
            buyer = interaction.guild.get_member(int(ticket['buyer_id']))
            seller = interaction.guild.get_member(int(ticket['seller_id']))
            
            notify_embed = discord.Embed(
                title="Ticket Force Closed",
                description=f"Your ticket has been force closed by an administrator.",
                color=discord.Color.red()
            )
            
            if buyer:
                await buyer.send(embed=notify_embed)
            if seller:
                await seller.send(embed=notify_embed)
        except:
            pass
        
        await interaction.channel.delete()

    @app_commands.command(name="tickets")
    @is_admin()
    async def list_tickets(self, interaction: discord.Interaction):
        """List all active tickets (Admin only)"""
        active_tickets = await self.bot.db.get_active_tickets()
        
        if not active_tickets:
            await interaction.response.send_message(
                "No active tickets found.", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🎫 Active Tickets",
            color=discord.Color.blue()
        )
        
        for ticket in active_tickets:
            buyer = interaction.guild.get_member(int(ticket['buyer_id']))
            seller = interaction.guild.get_member(int(ticket['seller_id']))
            channel = interaction.guild.get_channel(int(ticket['channel_id']))
            
            if channel:
                embed.add_field(
                    name=f"Ticket {ticket['_id']}",
                    value=(
                        f"Channel: {channel.mention}\n"
                        f"Buyer: {buyer.mention if buyer else 'Unknown'}\n"
                        f"Seller: {seller.mention if seller else 'Unknown'}\n"
                        f"Created: {discord.utils.format_dt(ticket['created_at'])}"
                    ),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ticket_inactive(self):
        """Check for inactive tickets and auto-close them"""
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
                    await channel.send("⚠️ This ticket has been inactive for too long and will be closed.")
                    await asyncio.sleep(5)
                    
                    # Save transcript and close
                    messages = await channel.history(limit=None, oldest_first=True).flatten()
                    transcript_data = {
                        'ticket_id': ticket['_id'],
                        'channel_id': str(channel.id),
                        'messages': [
                            {
                                'content': msg.content,
                                'author_id': str(msg.author.id),
                                'created_at': msg.created_at,
                                'attachments': [att.url for att in msg.attachments]
                            }
                            for msg in messages
                        ],
                        'closed_at': datetime.utcnow(),
                        'auto_closed': True
                    }
                    
                    await self.bot.db.update_ticket(
                        ticket['_id'],
                        {
                            'status': 'closed',
                            'closed_at': datetime.utcnow(),
                            'auto_closed': True
                        }
                    )
                    
                    if int(ticket['buyer_id']) in self.active_tickets:
                        self.active_tickets.remove(int(ticket['buyer_id']))
                    
                    await channel.delete()
            
            await asyncio.sleep(3600)  # Check every hour

class PaymentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PaymentMethodSelect())

async def setup(bot):
    await bot.add_cog(TicketManager(bot))
