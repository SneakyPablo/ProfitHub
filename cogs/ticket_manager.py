class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tickets = set()

    def is_admin():
        async def predicate(interaction: discord.Interaction):
            return interaction.guild.get_role(interaction.client.config.ADMIN_ROLE_ID) in interaction.user.roles
        return app_commands.check(predicate)

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
