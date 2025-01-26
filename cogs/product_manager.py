import discord
from discord.ext import commands
from discord import app_commands
from bson import ObjectId

class ProductManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingRole):
            await interaction.response.send_message(
                f"You need the Seller role to use this command.", 
                ephemeral=True
            )
        else:
            print(f'Error in {interaction.command.name}: {str(error)}')

    def is_seller():
        def predicate(interaction: discord.Interaction) -> bool:
            return interaction.guild.get_role(interaction.client.config.SELLER_ROLE_ID) in interaction.user.roles
        return app_commands.check(predicate)

    @app_commands.command(name="createpanel")
    @is_seller()
    async def createpanel(self, interaction: discord.Interaction, name: str, 
                         daily_price: float, monthly_price: float, lifetime_price: float,
                         description: str, category: str = None):
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
        
        # Check if there are any keys in stock
        keys = await self.bot.db.get_product_key_count(ObjectId(product_id))
        if keys == 0:
            await interaction.response.send_message(
                "You need to add keys before creating a panel! Use /addkey to add keys.", 
                ephemeral=True
            )
            return
        
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
        pricing_text = (
            f"💰 **License Prices**\n"
            f"Daily: ${daily_price:.2f}\n"
            f"Monthly: ${monthly_price:.2f}\n"
            f"Lifetime: ${lifetime_price:.2f}"
        )
        if category:
            embed.add_field(name="📁 Category", value=category, inline=True)
        
        embed.add_field(name="💳 Pricing", value=pricing_text, inline=False)
        
        # Stock counter
        keys_available = await self.bot.db.get_available_key_count(ObjectId(product_id))
        embed.add_field(
            name="📦 Stock",
            value=f"Keys Available: {keys_available}",
            inline=True
        )
        
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
        
        embed.set_footer(text=f"Product ID: {product_id} • Created at {discord.utils.format_dt(discord.utils.utcnow())}")
        
        view = ProductPanel(str(product_id))
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Product panel created!", ephemeral=True)

    @app_commands.command(name="addkey")
    @is_seller()
    async def addkey(self, interaction: discord.Interaction, product_id: str, key: str):
        try:
            product = await self.bot.db.get_product(ObjectId(product_id))
        except:
            await interaction.response.send_message("Invalid product ID!", ephemeral=True)
            return
            
        if not product:
            await interaction.response.send_message("Product not found!", ephemeral=True)
            return
            
        if product['seller_id'] != str(interaction.user.id):
            await interaction.response.send_message("You don't own this product!", ephemeral=True)
            return
            
        key_data = {
            'product_id': ObjectId(product_id),
            'key': key,
            'seller_id': str(interaction.user.id)
        }
        
        await self.bot.db.add_product_key(key_data)
        await interaction.response.send_message("Key added successfully!", ephemeral=True)

    @app_commands.command(name="products")
    async def list_products(self, interaction: discord.Interaction):
        """List all products you have access to view"""
        is_seller = interaction.guild.get_role(self.bot.config.SELLER_ROLE_ID) in interaction.user.roles
        is_admin = interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles
        
        if not (is_seller or is_admin):
            await interaction.response.send_message(
                "You need to be a seller or admin to use this command!", 
                ephemeral=True
            )
            return
        
        if is_admin:
            # Admin can see all products
            products = await self.bot.db.get_all_products()
        else:
            # Sellers can only see their products
            products = await self.bot.db.get_seller_products(str(interaction.user.id))
        
        if not products:
            await interaction.response.send_message(
                "No products found.", 
                ephemeral=True
            )
            return
        
        embeds = []
        current_embed = discord.Embed(
            title="🏪 Product List",
            color=discord.Color.blue()
        )
        field_count = 0
        
        for product in products:
            seller = interaction.guild.get_member(int(product['seller_id']))
            seller_name = seller.display_name if seller else "Unknown Seller"
            
            value = (
                f"💰 Price: ${product['price']:.2f}\n"
                f"📁 Category: {product.get('category', 'N/A')}\n"
                f"👤 Seller: {seller_name}\n"
                f"🆔 ID: `{product['_id']}`"
            )
            
            current_embed.add_field(
                name=f"📦 {product['name']}",
                value=value,
                inline=False
            )
            field_count += 1
            
            # Discord embeds can only have 25 fields
            if field_count == 25:
                embeds.append(current_embed)
                current_embed = discord.Embed(
                    title="🏪 Product List (Continued)",
                    color=discord.Color.blue()
                )
                field_count = 0
        
        if field_count > 0:
            embeds.append(current_embed)
        
        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        else:
            # Send first embed with the initial response
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
            # Send additional embeds as follow-up messages
            for embed in embeds[1:]:
                await interaction.followup.send(embed=embed, ephemeral=True)

class ProductPanel(discord.ui.View):
    def __init__(self, product_id: str):
        super().__init__(timeout=None)
        self.product_id = product_id

    async def check_stock(self, interaction: discord.Interaction):
        keys_available = await interaction.client.db.get_available_key_count(ObjectId(self.product_id))
        if keys_available == 0:
            await interaction.response.send_message(
                "Sorry, this product is currently out of stock!", 
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Buy Daily", style=discord.ButtonStyle.success)
    async def buy_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_stock(interaction):
            return
        await self.create_purchase_ticket(interaction, "daily")

    @discord.ui.button(label="Buy Monthly", style=discord.ButtonStyle.success)
    async def buy_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_stock(interaction):
            return
        await self.create_purchase_ticket(interaction, "monthly")

    @discord.ui.button(label="Buy Lifetime", style=discord.ButtonStyle.success)
    async def buy_lifetime(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_stock(interaction):
            return
        await self.create_purchase_ticket(interaction, "lifetime")

    @discord.ui.button(label="Request Info", style=discord.ButtonStyle.primary)
    async def request_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            product = await interaction.client.db.get_product(ObjectId(self.product_id))
            if product:
                embed = discord.Embed(
                    title=product['name'],
                    description=product['description'],
                    color=discord.Color.blue()
                )
                for license_type, price in product['prices'].items():
                    embed.add_field(name=f"{license_type.title()} Price", value=f"${price}")
                if product.get('category'):
                    embed.add_field(name="Category", value=product['category'])
                
                keys_available = await interaction.client.db.get_available_key_count(ObjectId(self.product_id))
                embed.add_field(name="Stock", value=f"{keys_available} keys available")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("Product not found!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("Error fetching product information.", ephemeral=True)

    async def create_purchase_ticket(self, interaction: discord.Interaction, license_type: str):
        ticket_manager = interaction.client.get_cog('TicketManager')
        if ticket_manager:
            await ticket_manager.create_ticket(interaction, self.product_id, license_type)
        else:
            await interaction.response.send_message(
                "Error: Ticket system is not available.", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProductManager(bot)) 
