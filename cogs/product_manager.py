import discord
from discord.ext import commands
from discord import app_commands
from bson import ObjectId
from datetime import datetime
import traceback

# Add these constants at the top of the file, after the imports
MARKETPLACE_ICON = "https://i.imgur.com/WZZPViy.png"  # Replace with your icon URL
MARKETPLACE_BANNER = "https://i.imgur.com/WZZPViy.png"  # Replace with your banner URL
MARKETPLACE_NAME = "Profit Hub Marketplace"  # Your marketplace name

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

        # Rest of the delivery logic...

class ProductPanel(discord.ui.View):
    def __init__(self, product_id: str):
        super().__init__(timeout=None)
        self.product_id = product_id

    @discord.ui.button(label="Buy Daily", style=discord.ButtonStyle.success)
    async def buy_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_purchase_ticket(interaction, "daily")

    @discord.ui.button(label="Buy Monthly", style=discord.ButtonStyle.success)
    async def buy_monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_purchase_ticket(interaction, "monthly")

    @discord.ui.button(label="Buy Lifetime", style=discord.ButtonStyle.success)
    async def buy_lifetime(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_purchase_ticket(interaction, "lifetime")

    @discord.ui.button(label="Request Info", style=discord.ButtonStyle.primary)
    async def request_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        product = await interaction.client.db.get_product(ObjectId(self.product_id))
        
        if not product:
            await interaction.followup.send("Product not found!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title=f"ℹ️ {product['name']} Information",
            description=product['description'],
            color=discord.Color.blue()
        )
        
        # Add pricing information
        pricing = ""
        for license_type, price in product['prices'].items():
            pricing += f"{license_type.title()}: ${price:.2f}\n"
        embed.add_field(name="💰 Pricing", value=pricing, inline=False)
        
        # Add stock information
        stock_info = ""
        for license_type in ['daily', 'monthly', 'lifetime']:
            keys = await interaction.client.db.get_available_key_count(self.product_id, license_type)
            emoji = "🟢" if keys > 0 else "🔴"
            stock_info += f"{emoji} {license_type.title()}: {keys} available\n"
        embed.add_field(name="📦 Stock Status", value=stock_info, inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def create_purchase_ticket(self, interaction: discord.Interaction, license_type: str):
        await interaction.response.defer(ephemeral=True)
        
        # Check stock
        keys = await interaction.client.db.get_available_key_count(self.product_id, license_type)
        if keys == 0:
            await interaction.followup.send(
                f"Sorry, {license_type} licenses are currently out of stock!", 
                ephemeral=True
            )
            return

        try:
            # Get product info
            product = await interaction.client.db.get_product(ObjectId(self.product_id))
            if not product:
                await interaction.followup.send("Product not found!", ephemeral=True)
                return

            # Create ticket channel
            category = interaction.guild.get_channel(interaction.client.config.TICKET_CATEGORY_ID)
            if not category:
                await interaction.followup.send(
                    "Ticket category not found. Please contact an administrator.", 
                    ephemeral=True
                )
                return

            # Create ticket channel
            channel_name = f"ticket-{interaction.user.name}-{product['name'][:10]}"
            ticket_channel = await category.create_text_channel(
                name=channel_name,
                topic=f"Ticket for {product['name']} - {license_type} license"
            )

            # Set permissions
            await ticket_channel.set_permissions(interaction.guild.default_role, read_messages=False)
            await ticket_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
            seller = interaction.guild.get_member(int(product['seller_id']))
            if seller:
                await ticket_channel.set_permissions(seller, read_messages=True, send_messages=True)

            # Create ticket in database
            ticket_data = {
                'channel_id': str(ticket_channel.id),
                'buyer_id': str(interaction.user.id),
                'seller_id': product['seller_id'],
                'product_id': ObjectId(self.product_id),
                'license_type': license_type
            }
            await interaction.client.db.create_ticket(ticket_data)

            # Send initial message
            embed = discord.Embed(
                title="🎫 New Purchase Ticket",
                description=(
                    f"Welcome {interaction.user.mention}!\n\n"
                    f"Product: **{product['name']}**\n"
                    f"License: **{license_type.title()}**\n"
                    f"Price: **${product['prices'][license_type]}**\n\n"
                    "Please select your payment method below."
                ),
                color=discord.Color.blue()
            )

            view = PaymentMethodSelect()
            await ticket_channel.send(
                f"{interaction.user.mention} {seller.mention}",
                embed=embed,
                view=view
            )

            await interaction.followup.send(
                f"Ticket created! Please check {ticket_channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            print(f"Error creating ticket: {e}")
            await interaction.followup.send(
                "An error occurred while creating your ticket. Please try again or contact an administrator.",
                ephemeral=True
            )

class ProductManager(commands.GroupCog, name="product"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    def is_seller():
        async def predicate(interaction: discord.Interaction):
            return interaction.guild.get_role(interaction.client.config.SELLER_ROLE_ID) in interaction.user.roles
        return app_commands.check(predicate)

    @app_commands.command(name="create")
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
    async def create_panel(
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
        try:
            await interaction.response.defer()
            
            # Collect features
            features = [feature1]
            if feature2: features.append(feature2)
            if feature3: features.append(feature3)
            if feature4: features.append(feature4)
            if feature5: features.append(feature5)
            
            # Create product data
            product_data = {
                'name': name,
                'description': "\n".join(features),
                'prices': {
                    'daily': daily_price,
                    'monthly': monthly_price,
                    'lifetime': lifetime_price
                },
                'seller_id': str(interaction.user.id),
                'category': category
            }
            
            # Create product in database
            product_id = await self.bot.db.create_product(product_data)
            
            # Create panel embed
            embed = discord.Embed(
                title=f"🌟 {name}",
                description=(
                    f"A premium product by {interaction.user.mention}\n"
                    f"*Powered by {MARKETPLACE_NAME}*\n"
                    "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
                ),
                color=0xf1c40f
            )

            # Add watermark as thumbnail
            embed.set_thumbnail(url=MARKETPLACE_ICON)

            # Add watermark text at the top
            embed.add_field(
                name="",
                value=f"*Powered by {MARKETPLACE_NAME}*\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
                inline=False
            )

            # Features section
            features_text = ""
            feature_emojis = ["⚡", "🎮", "🔧", "🎯", "💫"]
            for emoji, feature in zip(feature_emojis, features):
                features_text += f"{emoji} {feature}\n"

            embed.add_field(
                name="📋 Product Features",
                value=(
                    "```ansi\n"
                    f"{features_text}"
                    "```"
                ),
                inline=False
            )

            # Pricing section with dark background
            embed.add_field(
                name="💰 License Pricing",
                value=(
                    "```\n"
                    f"Daily License    | ${daily_price:.2f}\n"
                    f"Monthly License  | ${monthly_price:.2f}\n"
                    f"Lifetime License | ${lifetime_price:.2f}\n"
                    "```"
                ),
                inline=False
            )

            # Stock status section
            stock_status = ""
            for license_type in ['daily', 'monthly', 'lifetime']:
                keys = await self.bot.db.get_available_key_count(product_id, license_type)
                emoji = "🔴" if keys == 0 else "🟢"
                stock_status += f"{emoji} {license_type.title()}: {keys}\n"
            embed.add_field(
                name="📦 Stock Status",
                value=f"```\n{stock_status}```",
                inline=False
            )

            # Security & Support section
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

            # Add bottom watermark with product ID
            embed.set_footer(
                text=f"Product ID: {product_id} • {MARKETPLACE_NAME}",
                icon_url=MARKETPLACE_ICON
            )

            # Create and send panel
            view = ProductPanel(str(product_id))
            await interaction.channel.send(embed=embed, view=view)
            
            await interaction.followup.send(
                f"Product panel created! Use `/product add {product_id} <license_type> <key>` to add keys.", 
                ephemeral=True
            )
            
            # Log panel creation
            await self.bot.logger.log(
                "🏪 Panel Created",
                f"New product panel created by {interaction.user.mention}",
                discord.Color.green(),
                fields=[
                    ("Product", name, True),
                    ("Category", category or "N/A", True),
                    ("Creator", interaction.user.mention, True),
                    ("Daily Price", f"${daily_price}", True),
                    ("Monthly Price", f"${monthly_price}", True),
                    ("Lifetime Price", f"${lifetime_price}", True)
                ]
            )
            
        except Exception as e:
            print(f"Error creating panel: {e}")
            await interaction.followup.send(
                "An error occurred while creating the panel. Please try again.", 
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

    @app_commands.command(name="add")
    @app_commands.describe(
        product_id="Product ID",
        license_type="License type (daily/monthly/lifetime)",
        key="Product key"
    )
    @is_seller()
    async def add_key(self, interaction: discord.Interaction, product_id: str, license_type: str, key: str):
        """Add a key to your product"""
        await interaction.response.defer(ephemeral=True)
        
        if license_type.lower() not in ['daily', 'monthly', 'lifetime']:
            await interaction.followup.send(
                "Invalid license type! Use 'daily', 'monthly', or 'lifetime'", 
                ephemeral=True
            )
            return

        try:
            product = await self.bot.db.get_product(ObjectId(product_id))
            if not product:
                await interaction.followup.send("Product not found!", ephemeral=True)
                return
            
            if product['seller_id'] != str(interaction.user.id):
                await interaction.followup.send("You don't own this product!", ephemeral=True)
                return

            key_data = {
                'product_id': ObjectId(product_id),  # Make sure it's ObjectId
                'key': key,
                'license_type': license_type.lower(),
                'seller_id': str(interaction.user.id),
                'is_used': False
            }
            
            await self.bot.db.add_product_key(key_data)
            
            # Update panel stock display
            try:
                for channel in interaction.guild.text_channels:  # Only search text channels
                    async for message in channel.history(limit=100):
                        if (message.author == self.bot.user and 
                            len(message.embeds) > 0):
                            embed = message.embeds[0]
                            
                            # Check if this is the right product panel
                            footer_text = embed.footer.text if embed.footer else ""
                            if f"Product ID: {product_id}" in footer_text:
                                # Update stock status
                                stock_status = ""
                                for ltype in ['daily', 'monthly', 'lifetime']:
                                    keys = await self.bot.db.get_available_key_count(product_id, ltype)
                                    emoji = "🔴" if keys == 0 else "🟢"
                                    stock_status += f"{emoji} {ltype.title()}: {keys}\n"
                                
                                # Find and update the stock status field
                                for i, field in enumerate(embed.fields):
                                    if field.name == "📦 Stock Status":
                                        embed.set_field_at(
                                            i,
                                            name="📦 Stock Status",
                                            value=f"```\n{stock_status}```",
                                            inline=False
                                        )
                                        await message.edit(embed=embed)
                                        break
                                break  # Stop searching after finding the panel
            except Exception as e:
                print(f"Error updating panel: {e}")

            await interaction.followup.send(
                f"Key added successfully to {product['name']} ({license_type})!", 
                ephemeral=True
            )
            
            # Log key addition
            await self.bot.logger.log(
                "🔑 Key Added",
                f"New key added to {product['name']}",
                discord.Color.blue(),
                fields=[
                    ("Product", product['name'], True),
                    ("License Type", license_type, True),
                    ("Added By", interaction.user.mention, True)
                ]
            )
            
        except Exception as e:
            await interaction.followup.send(f"Error adding key: {str(e)}", ephemeral=True)

    @app_commands.command(name="list")
    @is_seller()
    async def list_keys(self, interaction: discord.Interaction):
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

    @app_commands.command(name="delete")
    @is_seller()
    async def delete_key(self, interaction: discord.Interaction, key_id: str):
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

    @app_commands.command(name="remove")
    @is_seller()
    async def remove_panel(self, interaction: discord.Interaction, product_id: str):
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

async def setup(bot):
    await bot.add_cog(ProductManager(bot)) 
