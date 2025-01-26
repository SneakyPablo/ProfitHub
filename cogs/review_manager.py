import discord
from discord.ext import commands
from discord import app_commands

class ReviewManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingRole):
            await interaction.response.send_message(
                f"You don't have permission to use this command.", 
                ephemeral=True
            )
        else:
            print(f'Error in {interaction.command.name}: {str(error)}')

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
            'comment': comment,
            'created_at': discord.utils.utcnow()
        }
        
        await self.bot.db.create_review(review_data)
        
        # Create an enhanced review embed
        embed = discord.Embed(
            title=f"⭐ New Review for {seller.display_name}",
            color=discord.Color.gold()
        )
        
        # Reviewer info
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        # Rating display
        stars = "⭐" * rating + "☆" * (5 - rating)
        embed.add_field(
            name="Rating",
            value=stars,
            inline=False
        )
        
        # Review comment
        embed.add_field(
            name="Comment",
            value=comment,
            inline=False
        )
        
        # Get seller's average rating
        all_reviews = await self.bot.db.get_reviews(str(seller.id))
        avg_rating = sum(r['rating'] for r in all_reviews) / len(all_reviews)
        total_reviews = len(all_reviews)
        
        embed.add_field(
            name="Seller Statistics",
            value=f"Average Rating: {avg_rating:.1f} ⭐\nTotal Reviews: {total_reviews}",
            inline=True
        )
        
        embed.set_footer(text=f"Review ID: {review_data['_id']} • {discord.utils.format_dt(discord.utils.utcnow())}")
        
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Review posted successfully!", ephemeral=True)

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
