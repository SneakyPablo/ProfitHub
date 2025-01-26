import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
from bson import ObjectId

class TicketManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_ticket(self, interaction: discord.Interaction, product_id: str):
        category = interaction.guild.get_channel(self.bot.config.TICKET_CATEGORY_ID)
        product = await self.bot.db.get_product(ObjectId(product_id))
        seller = interaction.guild.get_member(int(product['seller_id']))
        
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True),
                seller: discord.PermissionOverwrite(read_messages=True)
            }
        )
        
        ticket_data = {
            'channel_id': str(channel.id),
            'product_id': ObjectId(product_id),
            'buyer_id': str(interaction.user.id),
            'seller_id': str(seller.id),
            'status': 'open'
        }
        
        ticket_id = await self.bot.db.create_ticket(ticket_data)
        
        embed = discord.Embed(
            title="New Ticket",
            description=f"Product: {product['name']}\nPrice: ${product['price']}",
            color=discord.Color.green()
        )
        
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"Ticket created! Please check {channel.mention}", 
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_ticket_inactive(self):
        while True:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.bot.config.AUTO_CLOSE_HOURS)
            async for ticket in self.bot.db.tickets.find({'status': 'open'}):
                channel = self.bot.get_channel(int(ticket['channel_id']))
                if not channel:
                    continue
                    
                last_message = await channel.history(limit=1).flatten()
                if not last_message:
                    continue
                    
                if last_message[0].created_at < cutoff_time:
                    await channel.send("This ticket has been inactive for too long and will be closed.")
                    await channel.delete()
                    await self.bot.db.update_ticket(
                        ticket['_id'],
                        {
                            'status': 'closed',
                            'closed_at': datetime.utcnow()
                        }
                    )
            
            await asyncio.sleep(3600)  # Check every hour

async def setup(bot):
    await bot.add_cog(TicketManager(bot)) 
