import discord
from discord.ext import commands
import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from database import Database
from utils.logger import Logger
from discord import app_commands

class MarketplaceBot(commands.Bot):
    def __init__(self):
        self.config = Config()
        self.config.validate()
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=self.config.PREFIX,
            intents=intents,
            description="Marketplace Bot",
            application_id=1328451665602543768
        )
        
        self.db = Database()
        self.logger = Logger(self)
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self):
        """Set up bot and load cogs"""
        print("Setting up bot...")
        
        # Load cogs in specific order
        cogs = [
            'cogs.ticket_manager',
            'cogs.review_manager',
            'cogs.product_manager'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f'Loaded cog: {cog}')
            except Exception as e:
                print(f'Failed to load cog {cog}: {e}')
                import traceback
                traceback.print_exc()

    async def on_ready(self):
        """Called when bot is ready"""
        print(f'Logged in as {self.user.name}')
        print(f'Bot ID: {self.user.id}')
        print('------')

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle slash command errors"""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )
        else:
            print(f'Error in command {interaction.command}: {error}')
            traceback.print_exc()
            await interaction.response.send_message(
                "An error occurred while executing this command.",
                ephemeral=True
            )

    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command!")
        elif isinstance(error, commands.MissingRole):
            await ctx.send(f"You need the required role to use this command!")
        else:
            print(f'Error in command {ctx.command}: {error}')

    async def close(self):
        """Cleanup when bot shuts down"""
        print("Bot is shutting down...")
        await self.db.close()
        await super().close()

def run_bot():
    """Initialize and run the bot"""
    try:
        bot = MarketplaceBot()
        print("Starting bot...")
        bot.run(bot.config.TOKEN)
    except Exception as e:
        print(f"Failed to start bot: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    run_bot()
