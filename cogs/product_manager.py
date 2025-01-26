# In the createpanel command, update the embed creation:
    @app_commands.command(name="createpanel")
    @is_seller()
    async def createpanel(self, interaction: discord.Interaction, name: str, price: float, 
                         description: str, category: str = None):
        product_data = {
            'name': name,
            'description': description,
            'price': price,
            'seller_id': str(interaction.user.id),
            'category': category
        }
        
        product_id = await self.bot.db.create_product(product_data)
        
        embed = discord.Embed(
            title=f"🌟 {name}",
            color=discord.Color.gold()
        )
        
        # Features section with emojis
        features = description.split('\n')
        features_text = ""
        for feature in features:
            features_text += f"• {feature.strip()}\n"
            
        embed.add_field(
            name="✨ Features",
            value=features_text or "No features listed",
            inline=False
        )
        
        # Pricing section
        pricing_text = f"💰 **Monthly License** : ${price:.2f}\n"
        if category:
            embed.add_field(name="📁 Category", value=category, inline=True)
        
        embed.add_field(name="💳 Pricing", value=pricing_text, inline=False)
        
        # Security and Support
        embed.add_field(
            name="🛡️ Security",
            value="• Instant Delivery\n• 24/7 Support\n• Anti-Leak Protection",
            inline=True
        )
        
        # Seller info
        seller = interaction.guild.get_member(int(product_data['seller_id']))
        embed.add_field(
            name="👤 Seller Information",
            value=f"Seller: {seller.mention}\nID: {product_id}",
            inline=True
        )
        
        # Footer
        embed.set_footer(text=f"Product ID: {product_id} • Created at {discord.utils.format_dt(discord.utils.utcnow())}")
        
        view = ProductPanel(str(product_id))
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Product panel created!", ephemeral=True)
