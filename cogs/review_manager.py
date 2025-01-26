import discord
from discord.ext import commands
from discord import app_commands

class ReviewManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vouch")
    async def vouch(self, interaction: discord.Interaction, seller: discord.Member, 
                   rating: int, comment: str):
        if rating < 1 or rating > 5:
            await interaction.response.send_message(
                "Rating must be between 1 and 5!", 
                ephemeral=True
            )
            return
        
        review_data = {
            'seller_id': str(seller.id),
            'reviewer_id': str(interaction.user.id),
            'rating': rating,
            'comment': comment
        }
        
        await self.bot.db.create_review(review_data)
        
        stars = "⭐" * rating
        await interaction.response.send_message(
            f"Review submitted for {seller.mention}!\nRating: {stars}\nComment: {comment}"
        )

    @app_commands.command(name="vouches")
    async def vouches(self, interaction: discord.Interaction, seller: discord.Member):
        reviews = await self.bot.db.get_reviews(str(seller.id))
        
        if not reviews:
            await interaction.response.send_message(
                f"{seller.display_name} has no reviews yet.",
                ephemeral=True
            )
            return
            
        embed = discord.Embed(
            title=f"Reviews for {seller.display_name}",
            color=discord.Color.blue()
        )
        
        avg_rating = sum(r['rating'] for r in reviews) / len(reviews)
        embed.add_field(
            name="Average Rating",
            value=f"{'⭐' * round(avg_rating)} ({avg_rating:.1f})"
        )
        
        for review in reviews[:5]:  # Show 5 most recent reviews
            reviewer = interaction.guild.get_member(int(review['reviewer_id']))
            embed.add_field(
                name=f"{'⭐' * review['rating']} from {reviewer.display_name}",
                value=review['comment'],
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ReviewManager(bot)) 
