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
            title=name,
            description=description,
            color=discord.Color.blue()
        )
        embed.add_field(name="Price", value=f"${price}")
        if category:
            embed.add_field(name="Category", value=category)
        embed.set_footer(text=f"Product ID: {product_id}")
        
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

class ProductPanel(discord.ui.View):
    def __init__(self, product_id: str):
        super().__init__(timeout=None)
        self.product_id = product_id

    @discord.ui.button(label="Buy Now", style=discord.ButtonStyle.success)
    async def buy_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get the ticket manager cog
        ticket_manager = interaction.client.get_cog('TicketManager')
        if ticket_manager:
            await ticket_manager.create_ticket(interaction, self.product_id)
        else:
            await interaction.response.send_message(
                "Error: Ticket system is not available.", 
                ephemeral=True
            )

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
                embed.add_field(name="Price", value=f"${product['price']}")
                if product.get('category'):
                    embed.add_field(name="Category", value=product['category'])
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Product not found!", 
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                "Error fetching product information.", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProductManager(bot)) 
