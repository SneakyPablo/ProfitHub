import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
from bson import ObjectId
import io

class PaymentMethodSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PaymentDropdown())

class PaymentDropdown(discord.ui.Select):
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
        
        payment_info = interaction.client.config.PAYMENT_INFO.get(self.values[0], "Payment information not available")
        
        embed = discord.Embed(
            title="💳 Payment Information",
            description=f"Please send payment using the following details:\n\n{payment_info}",
            color=discord.Color.green()
        )
        embed.set_footer(text="After sending payment, click 'Confirm Payment' below")
        
        view = ConfirmPaymentView()
        await interaction.followup.send(embed=embed, view=view)
        self.disabled = True
        await interaction.message.edit(view=self.view)

class ConfirmPaymentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Payment", style=discord.ButtonStyle.success, custom_id="confirm_payment")
    async def confirm_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        seller = interaction.guild.get_member(int(ticket['seller_id']))
        
        embed = discord.Embed(
            title="💰 Payment Confirmation",
            description="The buyer has confirmed their payment. Please verify and deliver the product.",
            color=discord.Color.gold()
        )
        
        view = SellerConfirmationView()
        await interaction.channel.send(f"{seller.mention}", embed=embed, view=view)
        button.disabled = True
        await interaction.message.edit(view=self)

class SellerConfirmationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Payment & Deliver", style=discord.ButtonStyle.success, custom_id="seller_confirm")
    async def confirm_and_deliver(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        ticket = await interaction.client.db.get_ticket_by_channel(str(interaction.channel.id))
        if str(interaction.user.id) != ticket['seller_id']:
            await interaction.followup.send("Only the seller can confirm the payment!", ephemeral=True)
            return
            
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

        # Mark key as used and update stock
        await interaction.client.db.mark_key_as_used(key['_id'], ticket['buyer_id'])
        
        # Update product panel stock count
        try:
            for channel in interaction.guild.channels:
                async for message in channel.history(limit=100):
                    if (message.author == interaction.client.user and 
                        len(message.embeds) > 0 and 
                        str(ticket['product_id']) in message.embeds[0].footer.text):
                        embed = message.embeds[0]
                        
                        # Update stock status
                        stock_status = ""
                        for ltype in ['daily', 'monthly', 'lifetime']:
                            keys = await interaction.client.db.get_available_key_count(
                                ticket['product_id'], 
                                ltype
                            )
                            emoji = "🟢" if keys > 0 else "🔴"
                            stock_status += f"{emoji} {ltype.title()}: {keys}\n"
                        
                        # Update the stock field
                        for i, field in enumerate(embed.fields):
                            if field.name == "📦 Stock Status":
                                embed.set_field_at(
                                    i,
                                    name="📦 Stock Status",
                                    value=stock_status,
                                    inline=True
                                )
                                await message.edit(embed=embed)
                                break
        except Exception as e:
            print(f"Error updating stock display: {e}")

        # Add buyer role and deliver key
        buyer = interaction.guild.get_member(int(ticket['buyer_id']))
        buyer_role = interaction.guild.get_role(interaction.client.config.BUYER_ROLE_ID)
        
        if buyer_role:
            try:
                await buyer.add_roles(buyer_role)
            except Exception as e:
                print(f"Error adding buyer role: {e}")

        # Send key to buyer
        try:
            key_embed = discord.Embed(
                title="🔑 Your Product Key",
                description=f"Thank you for your purchase! Here's your product key:\n\n`{key['key']}`",
                color=discord.Color.green()
            )
            await buyer.send(embed=key_embed)
            await interaction.channel.send("✅ Product key has been delivered to buyer's DM!")
        except discord.Forbidden:
            await interaction.channel.send(
                f"⚠️ Couldn't DM the buyer. Here's the key (visible only in ticket):\n`{key['key']}`"
            )

        # Send vouch reminder
        info_embed = discord.Embed(
            title="⭐ Important Information",
            description=(
                f"{buyer.mention}, please note:\n\n"
                "1️⃣ You have 24 hours to vouch using the `/vouch` command\n"
                "2️⃣ If you don't vouch, your buyer role will be removed\n"
                "3️⃣ This ticket will automatically close in 15 minutes\n\n"
                "Need help? Contact the seller before the ticket closes!"
            ),
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=info_embed)
        
        button.disabled = True
        await interaction.message.edit(view=self)

        # Start auto-close timer
        await asyncio.sleep(900)  # 15 minutes
        await interaction.channel.send("⏰ This ticket will close in 60 seconds...")
        await asyncio.sleep(60)
        
        # Save transcript and close ticket
        ticket_manager = interaction.client.get_cog('TicketManager')
        if ticket_manager:
            await ticket_manager.save_transcript(
                interaction.channel,
                ticket,
                "Auto-closed after delivery"
            )
        
        await interaction.channel.delete()

class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tickets = set()

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
    @app_commands.checks.has_role("Admin")
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
