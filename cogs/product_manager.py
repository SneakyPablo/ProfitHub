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
        """Create a new product panel"""
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
        
        # Create the product first
        product_id = await self.bot.db.create_product(product_data)
        
        embed = discord.Embed(
            title=f"🌟 {name}",
            description=f"A premium product by {interaction.user.mention}",
            color=discord.Color.gold()
        )
        
        # Features section with emojis
        features = description.split('\n')
        features_text = ""
        for feature in features:
            if feature.strip():
                features_text += f"✅ {feature.strip()}\n"
        
        embed.add_field(
            name="📋 Features",
            value=features_text or "No features listed",
            inline=False
        )
        
        # Pricing section with better formatting
        embed.add_field(
            name="💰 License Pricing",
            value=(
                "```\n"
                f"Daily License    │ ${daily_price:.2f}\n"
                f"Monthly License  │ ${monthly_price:.2f}\n"
                f"Lifetime License │ ${lifetime_price:.2f}\n"
                "```"
            ),
            inline=False
        )
        
        if category:
            embed.add_field(
                name="📁 Category",
                value=f"`{category}`",
                inline=True
            )
        
        # Stock counter with emojis
        stock_status = ""
        for license_type in ['daily', 'monthly', 'lifetime']:
            keys = await self.bot.db.get_available_key_count(product_id, license_type)
            emoji = "🟢" if keys > 0 else "🔴"
            stock_status += f"{emoji} {license_type.title()}: {keys}\n"

        embed.add_field(
            name="📦 Stock Status",
            value=f"```\n{stock_status}```",
            inline=True
        )
        
        # Security and Support in a code block
        embed.add_field(
            name="🛡️ Security & Support",
            value=(
                "```\n"
                "✓ Instant Delivery\n"
                "✓ 24/7 Support\n"
                "✓ Anti-Leak Protection\n"
                "✓ Automatic Updates\n"
                "```"
            ),
            inline=False
        )
        
        # Footer with IDs
        embed.set_footer(
            text=f"Product ID: {product_id} • Created: {discord.utils.format_dt(discord.utils.utcnow(), style='R')}"
        )
        
        view = ProductPanel(str(product_id))
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"Product panel created! Use `/addkey {product_id} <license_type> <key>` to add keys.", 
            ephemeral=True
        )

    @app_commands.command(name="keys")
    @is_seller()
    async def view_keys(self, interaction: discord.Interaction):
        """View all your product keys"""
        # Get all products for this seller
        products = await self.bot.db.get_seller_products(str(interaction.user.id))
        
        if not products:
            await interaction.response.send_message(
                "You don't have any products!", 
                ephemeral=True
            )
            return

        embeds = []
        current_embed = discord.Embed(
            title="🔑 Your Product Keys",
            color=discord.Color.blue()
        )
        field_count = 0

        for product in products:
            # Get keys for each license type
            daily_keys = await self.bot.db.get_keys_by_type(product['_id'], 'daily')
            monthly_keys = await self.bot.db.get_keys_by_type(product['_id'], 'monthly')
            lifetime_keys = await self.bot.db.get_keys_by_type(product['_id'], 'lifetime')
            
            value = (
                f"**Daily Keys:** {len([k for k in daily_keys if not k['is_used']])}/{len(daily_keys)}\n"
                f"**Monthly Keys:** {len([k for k in monthly_keys if not k['is_used']])}/{len(monthly_keys)}\n"
                f"**Lifetime Keys:** {len([k for k in lifetime_keys if not k['is_used']])}/{len(lifetime_keys)}\n"
                f"Product ID: `{product['_id']}`"
            )
            
            current_embed.add_field(
                name=f"📦 {product['name']}",
                value=value,
                inline=False
            )
            field_count += 1
            
            if field_count == 25:
                embeds.append(current_embed)
                current_embed = discord.Embed(
                    title="🔑 Your Product Keys (Continued)",
                    color=discord.Color.blue()
                )
                field_count = 0
        
        if field_count > 0:
            embeds.append(current_embed)
        
        if len(embeds) == 1:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        else:
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
            for embed in embeds[1:]:
                await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="addkey")
    @is_seller()
    async def addkey(self, interaction: discord.Interaction, product_id: str, 
                     license_type: str, key: str):
        """Add a key to your product"""
        # Validate license type
        if license_type.lower() not in ['daily', 'monthly', 'lifetime']:
            await interaction.response.send_message(
                "Invalid license type! Use 'daily', 'monthly', or 'lifetime'", 
                ephemeral=True
            )
            return

        try:
            # Get product and verify ownership
            product = await self.bot.db.get_product(ObjectId(product_id))
            if not product:
                await interaction.response.send_message(
                    "Product not found! Make sure the ID is correct.", 
                    ephemeral=True
                )
                return
            
            if product['seller_id'] != str(interaction.user.id):
                await interaction.response.send_message(
                    "You don't own this product!", 
                    ephemeral=True
                )
                return

            key_data = {
                'product_id': product['_id'],
                'key': key,
                'seller_id': str(interaction.user.id),
                'license_type': license_type.lower(),
                'is_used': False
            }
            
            await self.bot.db.add_product_key(key_data)
            
            # Update product panel if it exists
            try:
                async for message in interaction.channel.history():
                    if message.author == self.bot.user and len(message.embeds) > 0:
                        embed = message.embeds[0]
                        if str(product['_id']) in embed.footer.text:
                            keys_available = await self.bot.db.get_available_key_count(product['_id'])
                            for field in embed.fields:
                                if field.name == "📦 Stock":
                                    field.value = f"Keys Available: {keys_available}"
                                    await message.edit(embed=embed)
                                    break
            except Exception as e:
                print(f"Error updating product panel: {e}")

            await interaction.response.send_message(
                f"Key added successfully to {product['name']} ({license_type})!", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Error adding key: Invalid product ID format", 
                ephemeral=True
            )

    @app_commands.command(name="deletekey")
    @is_seller()
    async def deletekey(self, interaction: discord.Interaction, key_id: str):
        """Delete a key from your product"""
        key = await self.bot.db.get_key(ObjectId(key_id))
        
        if not key:
            await interaction.response.send_message("Key not found!", ephemeral=True)
            return
        
        if key['seller_id'] != str(interaction.user.id):
            await interaction.response.send_message(
                "You don't own this key!", 
                ephemeral=True
            )
            return
        
        await self.bot.db.delete_key(ObjectId(key_id))
        await interaction.response.send_message("Key deleted successfully!", ephemeral=True)

    @app_commands.command(name="viewproductkeys")
    @is_seller()
    async def view_product_keys(self, interaction: discord.Interaction, product_name: str):
        """View all keys for a specific product"""
        product = await self.bot.db.get_product_by_name_and_seller(
            product_name, 
            str(interaction.user.id)
        )
        
        if not product:
            await interaction.response.send_message(
                f"Product '{product_name}' not found!", 
                ephemeral=True
            )
            return

        keys = await self.bot.db.get_product_keys(product['_id'])
        
        if not keys:
            await interaction.response.send_message(
                "No keys found for this product!", 
                ephemeral=True
            )
            return

        embeds = []
        current_embed = discord.Embed(
            title=f"🔑 Keys for {product_name}",
            color=discord.Color.blue()
        )
        
        # Group keys by license type
        daily_keys = [k for k in keys if k['license_type'] == 'daily']
        monthly_keys = [k for k in keys if k['license_type'] == 'monthly']
        lifetime_keys = [k for k in keys if k['license_type'] == 'lifetime']
        
        for license_type, type_keys in [
            ("Daily", daily_keys),
            ("Monthly", monthly_keys),
            ("Lifetime", lifetime_keys)
        ]:
            if type_keys:
                value = ""
                for key in type_keys:
                    status = "🔴 Used" if key['is_used'] else "🟢 Available"
                    value += f"ID: `{key['_id']}`\nKey: `{key['key']}`\nStatus: {status}\n\n"
                
                if len(value) > 1024:
                    # Split into multiple fields if too long
                    chunks = [value[i:i + 1000] for i in range(0, len(value), 1000)]
                    for i, chunk in enumerate(chunks):
                        current_embed.add_field(
                            name=f"{license_type} Keys (Part {i+1})",
                            value=chunk,
                            inline=False
                        )
                else:
                    current_embed.add_field(
                        name=f"{license_type} Keys",
                        value=value,
                        inline=False
                    )

        await interaction.response.send_message(embed=current_embed, ephemeral=True)

    @app_commands.command(name="products")
    async def list_products(self, interaction: discord.Interaction):
        """List all products you have access to view"""
        try:
            is_seller = interaction.guild.get_role(self.bot.config.SELLER_ROLE_ID) in interaction.user.roles
            is_admin = interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles
            
            if not (is_seller or is_admin):
                await interaction.response.send_message(
                    "You need to be a seller or admin to use this command!", 
                    ephemeral=True
                )
                return
            
            products = await self.bot.db.get_all_products() if is_admin else await self.bot.db.get_seller_products(str(interaction.user.id))
            
            if not products:
                await interaction.response.send_message("No products found.", ephemeral=True)
                return
            
            embeds = []
            current_embed = discord.Embed(title="🏪 Product List", color=discord.Color.blue())
            field_count = 0
            
            for product in products:
                try:
                    seller = interaction.guild.get_member(int(product['seller_id']))
                    seller_name = seller.display_name if seller else "Unknown Seller"
                    
                    # Handle both old and new price formats
                    prices = ""
                    if 'prices' in product:
                        prices = "\n".join([
                            f"{type_.title()}: ${price:.2f}"
                            for type_, price in product['prices'].items()
                        ])
                    elif 'price' in product:
                        prices = f"${product['price']:.2f}"
                    else:
                        prices = "Price not set"
                    
                    # Get stock info
                    stock_info = ""
                    for license_type in ['daily', 'monthly', 'lifetime']:
                        try:
                            keys = await self.bot.db.get_available_key_count(product['_id'], license_type)
                            emoji = "🟢" if keys > 0 else "🔴"
                            stock_info += f"{emoji} {license_type.title()}: {keys}\n"
                        except Exception:
                            continue
                    
                    value = (
                        f"💰 Prices:\n{prices}\n\n"
                        f"📦 Stock:\n{stock_info}\n"
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
                    
                    if field_count == 25:
                        embeds.append(current_embed)
                        current_embed = discord.Embed(
                            title="🏪 Product List (Continued)",
                            color=discord.Color.blue()
                        )
                        field_count = 0
                    
                except Exception as e:
                    print(f"Error processing product {product.get('_id')}: {e}")
                    continue
            
            if field_count > 0:
                embeds.append(current_embed)
            
            if not embeds:
                await interaction.response.send_message("No valid products found.", ephemeral=True)
                return
            
            await interaction.response.send_message(embed=embeds[0], ephemeral=True)
            for embed in embeds[1:]:
                await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred while listing products. Please try again later.", 
                ephemeral=True
            )
            print(f"Error in products command: {e}")

    @app_commands.command(name="deletepanel")
    @is_seller()
    async def deletepanel(self, interaction: discord.Interaction, product_id: str):
        """Delete a product panel"""
        try:
            # Get product and verify ownership
            product = await self.bot.db.get_product(ObjectId(product_id))
            if not product:
                await interaction.response.send_message(
                    "Product not found! Make sure the ID is correct.", 
                    ephemeral=True
                )
                return
            
            if product['seller_id'] != str(interaction.user.id):
                await interaction.response.send_message(
                    "You don't own this product!", 
                    ephemeral=True
                )
                return

            # Find and delete the panel message
            found = False
            async for message in interaction.channel.history(limit=100):
                if message.author == self.bot.user and len(message.embeds) > 0:
                    embed = message.embeds[0]
                    if str(product_id) in embed.footer.text:
                        await message.delete()
                        found = True
                        break
            
            # Delete product and associated keys from database
            await self.bot.db.delete_product(ObjectId(product_id))
            await self.bot.db.delete_product_keys(ObjectId(product_id))
            
            if found:
                await interaction.response.send_message(
                    "Product panel and associated data deleted successfully!", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Product data deleted, but couldn't find the panel message.", 
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"Error deleting panel: Invalid product ID format", 
                ephemeral=True
            )

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
