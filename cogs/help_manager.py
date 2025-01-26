import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

class HelpManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help")
    async def help(self, interaction: discord.Interaction, command: Optional[str] = None):
        """Shows help about bot commands"""
        
        if command:
            await self.show_command_help(interaction, command)
            return
            
        embed = discord.Embed(
            title="🤖 Marketplace Bot Help",
            description="Welcome to the marketplace! Here are all available commands:",
            color=discord.Color.blue()
        )
        
        # Check user roles
        is_seller = interaction.guild.get_role(self.bot.config.SELLER_ROLE_ID) in interaction.user.roles
        is_admin = interaction.guild.get_role(self.bot.config.ADMIN_ROLE_ID) in interaction.user.roles
        
        # Basic Commands (Available to everyone)
        basic_commands = (
            "🛍️ **Basic Commands**\n"
            "`/help` - Shows this help message\n"
            "`/vouch <seller> <rating> <comment>` - Leave a review for a seller\n"
            "`/vouches <seller>` - View seller's reviews\n"
        )
        embed.add_field(name="Basic Commands", value=basic_commands, inline=False)
        
        # Seller Commands
        if is_seller or is_admin:
            seller_commands = (
                "💼 **Seller Commands**\n"
                "`/createpanel <name> <price> <description> [category]` - Create a product panel\n"
                "`/addkey <product_id> <key>` - Add a product key\n"
            )
            embed.add_field(name="Seller Commands", value=seller_commands, inline=False)
        
        # Admin Commands
        if is_admin:
            admin_commands = (
                "⚡ **Admin Commands**\n"
                "All seller commands plus:\n"
                "• Manage roles\n"
                "• Handle disputes\n"
                "• View logs\n"
            )
            embed.add_field(name="Admin Commands", value=admin_commands, inline=False)
        
        # Usage Tips
        tips = (
            "💡 **Tips**\n"
            "• Use `/help <command>` for detailed information about a specific command\n"
            "• Product panels have buttons for buying and requesting information\n"
            "• Tickets auto-close after inactivity\n"
        )
        embed.add_field(name="Tips", value=tips, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def show_command_help(self, interaction: discord.Interaction, command_name: str):
        """Shows detailed help for a specific command"""
        
        command_help = {
            "createpanel": {
                "description": "Creates a new product panel",
                "usage": "/createpanel <name> <price> <description> [category]",
                "example": "/createpanel name:\"Premium Software\" price:29.99 description:\"Amazing features!\" category:\"Software\"",
                "notes": "• Description can include multiple lines for features\n• Category is optional",
                "permission": "Seller role required"
            },
            "addkey": {
                "description": "Adds a product key to your product",
                "usage": "/addkey <product_id> <key>",
                "example": "/addkey product_id:12345 key:\"XXXX-YYYY-ZZZZ\"",
                "notes": "• Only the product owner can add keys\n• Keys are automatically marked as unused",
                "permission": "Seller role required"
            },
            "vouch": {
                "description": "Leave a review for a seller",
                "usage": "/vouch <seller> <rating> <comment>",
                "example": "/vouch @Seller 5 \"Great service!\"",
                "notes": "• Rating must be between 1-5\n• Reviews are public",
                "permission": "No special permission required"
            },
            "vouches": {
                "description": "View reviews for a seller",
                "usage": "/vouches <seller>",
                "example": "/vouches @Seller",
                "notes": "• Shows the 5 most recent reviews\n• Displays average rating",
                "permission": "No special permission required"
            }
        }
        
        if command_name not in command_help:
            await interaction.response.send_message(
                f"Command `{command_name}` not found. Use `/help` to see all commands.", 
                ephemeral=True
            )
            return
            
        help_data = command_help[command_name]
        embed = discord.Embed(
            title=f"Command Help: /{command_name}",
            description=help_data["description"],
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Usage", value=f"```{help_data['usage']}```", inline=False)
        embed.add_field(name="Example", value=f"```{help_data['example']}```", inline=False)
        embed.add_field(name="Notes", value=help_data["notes"], inline=False)
        embed.add_field(name="Permission", value=help_data["permission"], inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpManager(bot)) 
