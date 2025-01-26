import discord
from discord.ext import commands
import asyncio
from config import Config
from database import Database
import os

class MarketplaceBot(commands.Bot):
    def __init__(self):
        self.config = Config()
        # Validate config before starting the bot
        self.config.validate()
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=self.config.PREFIX,
            intents=intents
        )
        
        self.db = Database()

    async def setup_hook(self):
        # Load all cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded cog: {filename[:-3]}')

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

def run_bot():
    bot = MarketplaceBot()
    bot.run(bot.config.TOKEN)

if __name__ == "__main__":
    run_bot()
