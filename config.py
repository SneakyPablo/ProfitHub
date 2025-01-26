import os
from discord import Color

class Config:
    def __init__(self):
        # Get configuration from Railway variables
        self.TOKEN = os.environ.get('DISCORD_TOKEN')
        self.PREFIX = os.environ.get('BOT_PREFIX', '!')  # Default prefix is '!' if not set
        
        # Convert string IDs to integers
        self.TICKET_CATEGORY_ID = int(os.environ.get('TICKET_CATEGORY_ID', 0))
        self.ADMIN_ROLE_ID = int(os.environ.get('ADMIN_ROLE_ID', 0))
        self.SELLER_ROLE_ID = int(os.environ.get('SELLER_ROLE_ID', 0))
        
        # Bot settings
        self.EMBED_COLOR = Color.blue()  # Default color for embeds
        self.AUTO_CLOSE_HOURS = int(os.environ.get('AUTO_CLOSE_HOURS', 48))  # Default 48 hours

    def validate(self):
        """Validate required configuration"""
        if not self.TOKEN:
            raise ValueError("DISCORD_TOKEN environment variable not set")
        if not self.TICKET_CATEGORY_ID:
            raise ValueError("TICKET_CATEGORY_ID environment variable not set")
        if not self.ADMIN_ROLE_ID:
            raise ValueError("ADMIN_ROLE_ID environment variable not set")
        if not self.SELLER_ROLE_ID:
            raise ValueError("SELLER_ROLE_ID environment variable not set")
