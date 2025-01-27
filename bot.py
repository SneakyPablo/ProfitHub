import discord
from discord.ext import commands
import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config
from database import Database
from utils.logger import Logger

class MarketplaceBot(commands.Bot):
    def __init__(self):
        self.config = Config()
        self.config.validate()
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=self.config.PREFIX,
            intents=intents,
            description="Marketplace Bot with ticket system and product management"
        )
        
        self.db = Database()
        self.logger = Logger(self)

    async def setup_hook(self):
        """Set up bot and load cogs"""
        print("Setting up bot...")
        
        # Load cogs in specific order
        cogs = [
            'ticket_manager',  # Load this first
            'review_manager',  # Then load review manager
            'product_manager'  # Load product manager last
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(f'cogs.{cog}')
                print(f'Loaded cog: {cog}')
            except Exception as e:
                print(f'Failed to load cog {cog}: {e}')
                # Print more detailed error information
                import traceback
                traceback.print_exc()

    async def on_ready(self):
        """Called when bot is ready"""
        print(f'Logged in as {self.user.name}')
        print(f'Bot ID: {self.user.id}')
        print('------')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{self.config.PREFIX}help | Profit Hub"
            ),
            status=discord.Status.online
        )
        
        # Sync commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

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

if __name__ == "__main__":
    run_bot() 
