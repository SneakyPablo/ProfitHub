import discord
from discord.ext import commands
from discord import app_commands
from bson import ObjectId

class ProductManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        
        product_id = await self.bot.db.create_product(product_data)
        
        embed = discord.Embed(
            title=f"🌟 {name}",
            description=f"A premium product by {interaction.user.mention}",
            color=discord.Color.gold()
        )
        
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
        
        embed.set_footer(
            text=f"Product ID: {product_id} • Created: {discord.utils.format_dt(discord.utils.utcnow(), style='R')}"
        )
        
        view = ProductPanel(str(product_id))
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"Product panel created! Use `/addkey {product_id} <license_type> <key>` to add keys.", 
            ephemeral=True
        )

    @app_commands.command(name="products")
    async def list_products(self, interaction: discord.Interaction):
        """List all products you have access to view"""
        try:
            # Send initial response to prevent timeout
            await interaction.response.defer(ephemeral=True)
            
            is_seller = interaction.guild.get_role(self.bot.config.SELLER_ROLE_ID) in interaction.user.roles
            is_admin = interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles
            
            if not (is_seller or is_admin):
                await interaction.followup.send(
                    "You need to be a seller or admin to use this command!", 
                    ephemeral=True
                )
                return
            
            products = await self.bot.db.get_all_products() if is_admin else await self.bot.db.get_seller_products(str(interaction.user.id))
            
            if not products:
                await interaction.followup.send("No products found.", ephemeral=True)
                return
            
            embeds = []
            current_embed = discord.Embed(title="🏪 Product List", color=discord.Color.blue())
            field_count = 0
            
            for product in products:
                try:
                    seller = interaction.guild.get_member(int(product['seller_id']))
                    seller_name = seller.display_name if seller else "Unknown Seller"
                    
                    stock_info = ""
                    for license_type in ['daily', 'monthly', 'lifetime']:
                        keys = await self.bot.db.get_available_key_count(product['_id'], license_type)
                        emoji = "🟢" if keys > 0 else "🔴"
                        stock_info += f"{emoji} {license_type.title()}: {keys}\n"
                    
                    prices = product.get('prices', {})
                    price_text = "\n".join([
                        f"{type_.title()}: ${price:.2f}"
                        for type_, price in prices.items()
                    ])
                    
                    value = (
                        f"💰 Prices:\n{price_text}\n\n"
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
                await interaction.followup.send("No valid products found.", ephemeral=True)
                return
            
            await interaction.followup.send(embed=embeds[0], ephemeral=True)
            for embed in embeds[1:]:
                await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while listing products. Please try again later.", 
                ephemeral=True
            )
            print(f"Error in products command: {e}")

    @app_commands.command(name="keys")
    @is_seller()
    async def view_keys(self, interaction: discord.Interaction):
        """View all your product keys"""
        try:
            # Send initial response to prevent timeout
            await interaction.response.defer(ephemeral=True)
            
            products = await self.bot.db.get_seller_products(str(interaction.user.id))
            
            if not products:
                await interaction.followup.send(
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
                for license_type in ['daily', 'monthly', 'lifetime']:
                    keys = await self.bot.db.get_keys_by_type(product['_id'], license_type)
                    if not keys:
                        continue
                    
                    available_keys = [k for k in keys if not k.get('is_used', False)]
                    used_keys = [k for k in keys if k.get('is_used', False)]
                    
                    value = f"Available Keys: {len(available_keys)}/{len(keys)}\n\n"
                    
                    if available_keys:
                        value += "🟢 Available:\n"
                        for key in available_keys[:5]:
                            value += f"`{key['key']}`\n"
                        if len(available_keys) > 5:
                            value += f"...and {len(available_keys) - 5} more\n"
                    
                    if used_keys:
                        value += "\n🔴 Used:\n"
                        for key in used_keys[:3]:
                            buyer_id = key.get('used_by', 'Unknown')
                            buyer = interaction.guild.get_member(int(buyer_id)) if buyer_id != 'Unknown' else None
                            buyer_name = buyer.display_name if buyer else 'Unknown User'
                            value += f"`{key['key']}` - {buyer_name}\n"
                        if len(used_keys) > 3:
                            value += f"...and {len(used_keys) - 3} more\n"
                    
                    current_embed.add_field(
                        name=f"📦 {product['name']} ({license_type.title()})",
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

            if not embeds:
                await interaction.followup.send(
                    "No keys found for your products.", 
                    ephemeral=True
                )
                return

            await interaction.followup.send(embed=embeds[0], ephemeral=True)
            for embed in embeds[1:]:
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                "An error occurred while fetching keys. Please try again later.",
                ephemeral=True
            )
            print(f"Error in keys command: {e}")

    @app_commands.command(name="addkey")
    @is_seller()
    async def addkey(self, interaction: discord.Interaction, product_id: str, 
                     license_type: str, key: str):
        """Add a key to your product"""
        if license_type.lower() not in ['daily', 'monthly', 'lifetime']:
            await interaction.response.send_message(
                "Invalid license type! Use 'daily', 'monthly', or 'lifetime'", 
                ephemeral=True
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)
            product = await self.bot.db.get_product(ObjectId(product_id))
            if not product:
                await interaction.followup.send(
                    "Product not found! Make sure the ID is correct.", 
                    ephemeral=True
                )
                return
            
            if product['seller_id'] != str(interaction.user.id):
                await interaction.followup.send(
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
            
            # Update the product panel
            category = interaction.channel.category
            if category:
                for channel in category.channels:
                    try:
                        async for message in channel.history(limit=100):
                            if message.author == self.bot.user and len(message.embeds) > 0:
                                embed = message.embeds[0]
                                if str(product['_id']) in embed.footer.text:
                                    # Create updated stock status
                                    stock_status = ""
                                    for ltype in ['daily', 'monthly', 'lifetime']:
                                        keys = await self.bot.db.get_available_key_count(product['_id'], ltype)
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
                        print(f"Error updating product panel in {channel.name}: {e}")
                        continue

            await interaction.followup.send(
                f"Key added successfully to {product['name']} ({license_type})!", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"Error adding key: {str(e)}", 
                ephemeral=True
            )
            print(f"Error in addkey: {e}")

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

    @app_commands.command(name="deletepanel")
    @is_seller()
    async def deletepanel(self, interaction: discord.Interaction, product_id: str):
        """Delete a product panel"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            product = await self.bot.db.get_product(ObjectId(product_id))
            if not product:
                await interaction.followup.send(
                    "Product not found! Make sure the ID is correct.", 
                    ephemeral=True
                )
                return
            
            if product['seller_id'] != str(interaction.user.id):
                await interaction.followup.send(
                    "You don't own this product!", 
                    ephemeral=True
                )
                return

            found = False
            # Search in all channels in the category
            category = interaction.channel.category
            if category:
                for channel in category.channels:
                    try:
                        async for message in channel.history(limit=100):
                            if message.author == self.bot.user and len(message.embeds) > 0:
                                embed = message.embeds[0]
                                if str(product_id) in embed.footer.text:
                                    await message.delete()
                                    found = True
                                    break
                        if found:
                            break
                    except Exception as e:
                        print(f"Error searching in channel {channel.name}: {e}")
                        continue
            
            # Delete from database first
            await self.bot.db.delete_product(ObjectId(product_id))
            await self.bot.db.delete_product_keys(ObjectId(product_id))
            
            if found:
                await interaction.followup.send(
                    "Product panel and associated data deleted successfully!", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Product data deleted, but couldn't find the panel message. You may need to delete it manually.", 
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                f"Error deleting panel: {str(e)}", 
                ephemeral=True
            )
            print(f"Error in deletepanel: {e}")

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
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Check if specific license type has stock
            keys = await interaction.client.db.get_available_key_count(ObjectId(self.product_id), license_type)
            if keys == 0:
                await interaction.followup.send(
                    f"Sorry, this product is currently out of stock for {license_type} licenses!", 
                    ephemeral=True
                )
                return

            # Get the TicketManager cog
            ticket_manager = interaction.client.get_cog('TicketManager')
            if not ticket_manager:
                await interaction.followup.send(
                    "Error: Ticket system is currently unavailable. Please contact an administrator.", 
                    ephemeral=True
                )
                return

            # Create the ticket
            try:
                await ticket_manager.create_ticket(interaction, self.product_id, license_type)
            except Exception as e:
                print(f"Error creating ticket: {e}")
                await interaction.followup.send(
                    "An error occurred while creating your ticket. Please try again or contact an administrator.",
                    ephemeral=True
                )
            
        except Exception as e:
            print(f"Error in create_purchase_ticket: {e}")
            await interaction.followup.send(
                "An error occurred while processing your request. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProductManager(bot)) 
