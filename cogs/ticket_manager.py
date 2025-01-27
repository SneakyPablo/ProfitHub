import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
import io

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

class TicketControlsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        if not any([
            interaction.guild.get_role(interaction.client.config.ADMIN_ROLE_ID) in interaction.user.roles,
            interaction.guild.get_role(interaction.client.config.SELLER_ROLE_ID) in interaction.user.roles,
            str(interaction.user.id) == ticket['buyer_id']
        ]):
            await interaction.followup.send("You don't have permission to close this ticket!", ephemeral=True)
            return

        await interaction.channel.send("🔒 Closing ticket in 5 seconds...")
        
        # Save transcript before closing
        ticket_manager = interaction.client.get_cog('TicketManager')
        if ticket_manager:
            await ticket_manager.save_transcript(
                interaction.channel,
                ticket,
                f"{interaction.user.name}#{interaction.user.discriminator}"
            )
        
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        if not interaction.guild.get_role(interaction.client.config.ADMIN_ROLE_ID) in interaction.user.roles:
            await interaction.followup.send("Only administrators can claim tickets!", ephemeral=True)
            return

        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        await interaction.client.db.update_ticket(ticket['_id'], {'claimed_by': str(interaction.user.id)})
        
        embed = discord.Embed(
            title="👤 Ticket Claimed",
            description=f"This ticket has been claimed by {interaction.user.mention}",
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=embed)
        button.disabled = True
        await interaction.message.edit(view=self)

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
        
        # Create ticket channel with permissions - only allow panel creator to view
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
        
        # Only allow the panel creator (seller) to view the ticket
        if str(interaction.user.id) != product['seller_id']:
            overwrites[interaction.user] = discord.PermissionOverwrite(read_messages=False)
        
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        
        # Log ticket creation
        await self.bot.logger.log(
            "🎫 Ticket Created",
            f"New ticket created for {product['name']}",
            discord.Color.green(),
            fields=[
                ("Product", product['name'], True),
                ("License", license_type, True),
                ("Buyer", f"<@{interaction.user.id}>", True),
                ("Seller", f"<@{product['seller_id']}>", True),
                ("Channel", channel.mention, False)
            ]
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

        # Add ticket controls after creating the ticket
        controls_embed = discord.Embed(
            title="🛠️ Ticket Controls",
            description="Use these buttons to manage the ticket:",
            color=discord.Color.blurple()
        )
        await channel.send(embed=controls_embed, view=TicketControlsView())

    @app_commands.command(name="ticket")
    @app_commands.describe(
        action="The action to perform",
        user="The user to add/remove (for add/remove actions)",
        reason="Reason for the action (optional)"
    )
    @app_commands.choices(action=[
        discord.app_commands.Choice(name="close", value="close"),
        discord.app_commands.Choice(name="add", value="add"),
        discord.app_commands.Choice(name="remove", value="remove"),
        discord.app_commands.Choice(name="rename", value="rename"),
        discord.app_commands.Choice(name="claim", value="claim")
    ])
    async def ticket_command(self, interaction: discord.Interaction, 
                           action: str, user: Optional[discord.Member] = None,
                           reason: Optional[str] = None):
        """Manage tickets"""
        await interaction.response.defer(ephemeral=True)
        
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.followup.send("This command can only be used in ticket channels!", ephemeral=True)
            return

        if action == "close":
            await interaction.channel.send("🔒 Closing ticket in 5 seconds...")
            await asyncio.sleep(5)
            await interaction.channel.delete()
            
        elif action == "add":
            if not user:
                await interaction.followup.send("Please specify a user to add!", ephemeral=True)
                return
                
            await interaction.channel.set_permissions(user, 
                read_messages=True,
                send_messages=True
            )
            await interaction.channel.send(f"✅ Added {user.mention} to the ticket")
            
        elif action == "remove":
            if not user:
                await interaction.followup.send("Please specify a user to remove!", ephemeral=True)
                return
                
            if str(user.id) in [ticket['buyer_id'], ticket['seller_id']]:
                await interaction.followup.send("Cannot remove the buyer or seller!", ephemeral=True)
                return
                
            await interaction.channel.set_permissions(user, overwrite=None)
            await interaction.channel.send(f"❌ Removed {user.mention} from the ticket")
            
        elif action == "rename":
            if not reason:
                await interaction.followup.send("Please provide a new name!", ephemeral=True)
                return
                
            await interaction.channel.edit(name=f"ticket-{reason}")
            await interaction.channel.send(f"✏️ Ticket renamed to: ticket-{reason}")
            
        elif action == "claim":
            if not interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles:
                await interaction.followup.send("Only administrators can claim tickets!", ephemeral=True)
                return
                
            await self.bot.db.update_ticket(ticket['_id'], {'claimed_by': str(interaction.user.id)})
            embed = discord.Embed(
                title="👤 Ticket Claimed",
                description=f"This ticket has been claimed by {interaction.user.mention}",
                color=discord.Color.blue()
            )
            await interaction.channel.send(embed=embed)

    @app_commands.command(name="tickets")
    @is_admin()
    async def list_tickets(self, interaction: discord.Interaction):
        """List all active tickets"""
        await interaction.response.defer(ephemeral=True)
        
        active_tickets = await self.bot.db.get_active_tickets()
        if not active_tickets:
            await interaction.followup.send("No active tickets found.", ephemeral=True)
            return
            
        embeds = []
        current_embed = discord.Embed(title="🎫 Active Tickets", color=discord.Color.blue())
        
        for ticket in active_tickets:
            buyer = interaction.guild.get_member(int(ticket['buyer_id']))
            seller = interaction.guild.get_member(int(ticket['seller_id']))
            channel = interaction.guild.get_channel(int(ticket['channel_id']))
            
            if channel:
                field_value = (
                    f"Channel: {channel.mention}\n"
                    f"Buyer: {buyer.mention if buyer else 'Unknown'}\n"
                    f"Seller: {seller.mention if seller else 'Unknown'}\n"
                    f"Type: {ticket.get('license_type', 'N/A')}\n"
                    f"Status: {'Vouched' if ticket.get('vouched') else 'Not Vouched'}\n"
                    f"Created: {discord.utils.format_dt(ticket['created_at'])}"
                )
                
                if len(current_embed.fields) >= 25:
                    embeds.append(current_embed)
                    current_embed = discord.Embed(title="🎫 Active Tickets (Continued)", color=discord.Color.blue())
                
                current_embed.add_field(
                    name=f"Ticket {ticket['_id']}",
                    value=field_value,
                    inline=False
                )
        
        embeds.append(current_embed)
        
        await interaction.followup.send(embed=embeds[0], ephemeral=True)
        for embed in embeds[1:]:
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def save_transcript(self, channel, ticket_data, reason="Ticket Closed"):
        """Save ticket transcript"""
        try:
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                if message.content:
                    messages.append(f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author.name}#{message.author.discriminator}: {message.content}")
                for attachment in message.attachments:
                    messages.append(f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author.name}#{message.author.discriminator}: [Attachment] {attachment.url}")

            transcript_text = "\n".join(messages)
            transcript_file = discord.File(
                io.StringIO(transcript_text),
                filename=f"transcript-{channel.name}.txt"
            )

            # Send to transcripts channel
            transcripts_channel = self.bot.get_channel(self.bot.config.TRANSCRIPTS_CHANNEL_ID)
            if transcripts_channel:
                embed = discord.Embed(
                    title=f"📝 Ticket Transcript - {channel.name}",
                    description=f"Ticket closed by {reason}",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(
                    name="Ticket Information",
                    value=(
                        f"**Buyer:** <@{ticket_data['buyer_id']}>\n"
                        f"**Seller:** <@{ticket_data['seller_id']}>\n"
                        f"**License Type:** {ticket_data.get('license_type', 'N/A')}\n"
                        f"**Status:** {'Vouched' if ticket_data.get('vouched') else 'Not Vouched'}\n"
                        f"**Created:** {discord.utils.format_dt(ticket_data['created_at'])}\n"
                        f"**Closed:** {discord.utils.format_dt(datetime.utcnow())}"
                    ),
                    inline=False
                )
                await transcripts_channel.send(embed=embed, file=transcript_file)

        except Exception as e:
            print(f"Error saving transcript: {e}")

    @app_commands.command(name="transcript")
    async def get_transcript(self, interaction: discord.Interaction):
        """Get the transcript of the current ticket"""
        await interaction.response.defer(ephemeral=True)
        
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.followup.send(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return

        if not any([
            interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles,
            str(interaction.user.id) == ticket['buyer_id'],
            str(interaction.user.id) == ticket['seller_id']
        ]):
            await interaction.followup.send(
                "You don't have permission to get the transcript!", 
                ephemeral=True
            )
            return

        await self.save_transcript(
            interaction.channel,
            ticket,
            f"Requested by {interaction.user.name}#{interaction.user.discriminator}"
        )
        
        await interaction.followup.send(
            "Transcript has been saved and sent to the transcripts channel!", 
            ephemeral=True
        )

    async def log_ticket_event(self, channel, title, description, color=discord.Color.blue()):
        """Log ticket events to the logs channel"""
        logs_channel = self.bot.get_channel(self.bot.config.TICKET_LOGS_CHANNEL_ID)
        if logs_channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.utcnow()
            )
            await logs_channel.send(embed=embed)

    @app_commands.command(name="close")
    async def close_ticket(self, interaction: discord.Interaction):
        """Close the current ticket"""
        await interaction.response.defer(ephemeral=True)
        
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.followup.send(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
            
        # Check permissions
        if not any([
            interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles,
            str(interaction.user.id) == ticket['buyer_id'],
            str(interaction.user.id) == ticket['seller_id']
        ]):
            await interaction.followup.send(
                "You don't have permission to close this ticket!", 
                ephemeral=True
            )
            return

        await interaction.channel.send("🔒 Closing ticket in 5 seconds...")
        
        # Save transcript
        await self.save_transcript(
            interaction.channel,
            ticket,
            f"Closed by {interaction.user.name}#{interaction.user.discriminator}"
        )
        
        # Log ticket closure
        await self.bot.logger.log(
            "🔒 Ticket Closed",
            f"Ticket closed by {interaction.user.mention}",
            discord.Color.red(),
            fields=[
                ("Ticket", interaction.channel.name, True),
                ("Buyer", f"<@{ticket['buyer_id']}>", True),
                ("Seller", f"<@{ticket['seller_id']}>", True)
            ]
        )
        
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @app_commands.command(name="add")
    @is_admin()
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        """Add a user to the ticket (Admin only)"""
        await interaction.response.defer(ephemeral=True)
        
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.followup.send(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
            
        await interaction.channel.set_permissions(user,
            read_messages=True,
            send_messages=True
        )
        
        await interaction.channel.send(f"✅ Added {user.mention} to the ticket")
        await interaction.followup.send(
            f"Successfully added {user.mention} to the ticket", 
            ephemeral=True
        )

        # Log user addition
        await self.bot.logger.log(
            "👥 User Added to Ticket",
            f"{user.mention} was added to a ticket by {interaction.user.mention}",
            discord.Color.blue(),
            fields=[
                ("Ticket", interaction.channel.name, True),
                ("Added By", interaction.user.mention, True)
            ]
        )

async def setup(bot):
    await bot.add_cog(TicketManager(bot)) 
