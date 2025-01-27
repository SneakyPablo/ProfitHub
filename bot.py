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
            description="Marketplace Bot"
        )
        
        self.db = Database()
        self.logger = Logger(self)

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
        
        try:
            print("Syncing commands...")
            await self.tree.sync()
            print("Commands synced successfully!")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

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
