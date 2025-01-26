import discord
from discord.ext import commands
from discord import app_commands
from bson import ObjectId

class ProductManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createpanel")
    @app_commands.checks.has_role("Seller")
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
    @app_commands.checks.has_role("Seller")
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

async def setup(bot):
    await bot.add_cog(ProductManager(bot)) 
