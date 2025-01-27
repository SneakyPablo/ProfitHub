    @app_commands.command(name="createpanel")
    @app_commands.describe(
        name="Product name",
        daily_price="Price for daily license",
        monthly_price="Price for monthly license",
        lifetime_price="Price for lifetime license",
        feature1="Main product feature",
        feature2="Additional feature (optional)",
        feature3="Additional feature (optional)",
        feature4="Additional feature (optional)",
        feature5="Additional feature (optional)",
        category="Product category (optional)"
    )
    @is_seller()
    async def createpanel(
        self, 
        interaction: discord.Interaction, 
        name: str,
        daily_price: float,
        monthly_price: float,
        lifetime_price: float,
        feature1: str,
        feature2: str = None,
        feature3: str = None,
        feature4: str = None,
        feature5: str = None,
        category: str = None
    ):
        """Create a new product panel"""
        # Collect all provided features
        features = [feature1]
        if feature2: features.append(feature2)
        if feature3: features.append(feature3)
        if feature4: features.append(feature4)
        if feature5: features.append(feature5)
        
        # Create description from features
        description = "\n".join(features)
        
        product_data = {
            'name': name,
            'description': description,
            'prices': {
                'daily': daily_price,
                'monthly': monthly_price,
                'lifetime': lifetime_price
            },
            'seller_id': str(interaction.user.id),
            'category': category
        }
        
        product_id = await self.bot.db.create_product(product_data)
        
        # Format features for display
        features_text = ""
        for i, feature in enumerate(features, 1):
            features_text += f"✨ Feature {i}: {feature}\n"
        
        embed = discord.Embed(
            title=f"🌟 {name}",
            description=f"A premium product by {interaction.user.mention}",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="📋 Product Features",
            value=(
                "```\n"
                f"{features_text}"
                "```"
            ),
            inline=False
        )
        
        # Rest of the code remains the same...
