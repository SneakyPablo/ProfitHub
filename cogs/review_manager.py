import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from bson import ObjectId
from cogs.product_manager import MARKETPLACE_NAME, MARKETPLACE_ICON

class ReviewManager(commands.GroupCog, name="review"):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="vouch")
    async def vouch(self, interaction: discord.Interaction):
        """Vouch for a purchase"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if in ticket channel
        ticket = await self.bot.db.get_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.followup.send(
                "This command can only be used in ticket channels!", 
                ephemeral=True
            )
            return
        
        # Check if user is the buyer
        if str(interaction.user.id) != ticket['buyer_id']:
            await interaction.followup.send(
                "Only the buyer can vouch for this purchase!", 
                ephemeral=True
            )
            return
        
        # Check if already vouched
        if ticket.get('vouched', False):
            await interaction.followup.send(
                "You have already vouched for this purchase!", 
                ephemeral=True
            )
            return
        
        # Update ticket with vouch
        await self.bot.db.update_ticket(ticket['_id'], {'vouched': True})
        
        # Get product and seller info
        product = await self.bot.db.get_product(ticket['product_id'])
        seller = interaction.guild.get_member(int(ticket['seller_id']))
        
        # Create review embed
        review_embed = discord.Embed(
            title="⭐ New Verified Purchase Review",
            description=f"A new purchase has been vouched for!",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        review_embed.add_field(
            name="Product",
            value=product['name'],
            inline=True
        )
        review_embed.add_field(
            name="License Type",
            value=ticket['license_type'].title(),
            inline=True
        )
        review_embed.add_field(
            name="Seller",
            value=seller.mention,
            inline=True
        )
        review_embed.add_field(
            name="Buyer",
            value=interaction.user.mention,
            inline=True
        )
        
        # Get seller's total vouches
        seller_vouches = await self.bot.db.get_seller_vouches(str(seller.id))
        review_embed.add_field(
            name="Total Seller Vouches",
            value=str(len(seller_vouches)),
            inline=True
        )
        
        review_embed.set_footer(
            text=f"{MARKETPLACE_NAME} • Trusted Reviews",
            icon_url=MARKETPLACE_ICON
        )
        
        # Send to reviews channel
        reviews_channel = self.bot.get_channel(self.bot.config.REVIEWS_CHANNEL_ID)
        if reviews_channel:
            await reviews_channel.send(embed=review_embed)
        
        # Log the vouch
        await self.bot.logger.log(
            "⭐ New Vouch",
            f"A purchase has been vouched for",
            discord.Color.gold(),
            fields=[
                ("Product", product['name'], True),
                ("Buyer", interaction.user.mention, True),
                ("Seller", seller.mention, True),
                ("License", ticket['license_type'].title(), True)
            ]
        )
        
        # Send confirmation
        await interaction.followup.send(
            "Thank you for vouching! Your buyer role will be kept.", 
            ephemeral=True
        )
        await interaction.channel.send(
            f"✅ {interaction.user.mention} has vouched for their purchase!"
        )

    @app_commands.command(name="vouches")
    async def list_vouches(self, interaction: discord.Interaction, seller: discord.Member = None):
        """View vouches for a seller"""
        await interaction.response.defer(ephemeral=True)
        
        target_seller = seller or interaction.user
        vouched_tickets = await self.bot.db.get_seller_vouches(str(target_seller.id))
        
        if not vouched_tickets:
            await interaction.followup.send(
                f"No vouches found for {target_seller.mention}",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"⭐ Vouches for {target_seller.display_name}",
            description=f"Total Vouches: {len(vouched_tickets)}",
            color=discord.Color.gold()
        )
        
        for ticket in vouched_tickets[:10]:  # Show last 10 vouches
            product = await self.bot.db.get_product(ticket['product_id'])
            buyer = interaction.guild.get_member(int(ticket['buyer_id']))
            
            embed.add_field(
                name=f"Purchase: {product['name']}",
                value=(
                    f"Buyer: {buyer.mention if buyer else 'Unknown'}\n"
                    f"Type: {ticket.get('license_type', 'N/A')}\n"
                    f"Date: {discord.utils.format_dt(ticket['created_at'], style='R')}"
                ),
                inline=False
            )
        
        if len(vouched_tickets) > 10:
            embed.set_footer(text=f"Showing 10 most recent vouches out of {len(vouched_tickets)}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ReviewManager(bot)) 
