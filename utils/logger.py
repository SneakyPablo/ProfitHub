import discord
from datetime import datetime

class Logger:
    def __init__(self, bot):
        self.bot = bot

    async def log(self, title, description, color=discord.Color.blue(), fields=None):
        """Send a log message to the bot logs channel"""
        logs_channel = self.bot.get_channel(self.bot.config.BOT_LOGS_CHANNEL_ID)
        if logs_channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.utcnow()
            )
            
            if fields:
                for name, value, inline in fields:
                    embed.add_field(name=name, value=value, inline=inline)
                    
            await logs_channel.send(embed=embed) 
