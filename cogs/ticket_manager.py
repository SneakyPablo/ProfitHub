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
            category = interaction.guild.get_channel(interaction.client.config.TICKET_CATEGORY_ID)
            for channel in category.guild.channels:
                async for message in channel.history(limit=100):
                    if (message.author == interaction.client.user and 
                        len(message.embeds) > 0 and 
                        str(ticket['product_id']) in message.embeds[0].footer.text):
                        embed = message.embeds[0]
                        
                        # Get current stock counts
                        stock_status = ""
                        for ltype in ['daily', 'monthly', 'lifetime']:
                            keys = await interaction.client.db.get_available_key_count(
                                ticket['product_id'], 
                                ltype
                            )
                            emoji = "🟢" if keys > 0 else "🔴"
                            stock_status += f"{emoji} {ltype.title()}: {keys}\n"
                        
                        # Update the stock status field
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
            print(f"Error updating product panel: {e}")
            await interaction.channel.send("⚠️ Failed to update stock display. Please notify an administrator.")
        
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
        
        # Send vouch reminder and closure notice
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
        await interaction.channel.send("⏰ This ticket will close in 15 minutes...")
        await asyncio.sleep(900)  # 15 minutes
        
        close_embed = discord.Embed(
            title="🔒 Ticket Closing",
            description="This ticket will be closed in 60 seconds. Save any important information!",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=close_embed)
        
        await asyncio.sleep(60)
        await interaction.channel.delete()
