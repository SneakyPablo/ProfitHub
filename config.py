import os
from discord import Color

class Config:
    def __init__(self):
        # Get configuration from environment variables
        self.TOKEN = os.environ.get('DISCORD_TOKEN')
        self.PREFIX = os.environ.get('BOT_PREFIX', '!')
        
        # Convert string IDs to integers
        self.TICKET_CATEGORY_ID = int(os.environ.get('TICKET_CATEGORY_ID', 0))
        self.ADMIN_ROLE_ID = int(os.environ.get('ADMIN_ROLE_ID', 0))
        self.SELLER_ROLE_ID = int(os.environ.get('SELLER_ROLE_ID', 0))
        self.BUYER_ROLE_ID = int(os.environ.get('BUYER_ROLE_ID', 0))
        self.BOT_LOGS_CHANNEL_ID = int(os.environ.get('BOT_LOGS_CHANNEL_ID', 0))
        self.TRANSCRIPTS_CHANNEL_ID = int(os.environ.get('TRANSCRIPTS_CHANNEL_ID', 0))
        self.REVIEWS_CHANNEL_ID = int(os.environ.get('REVIEWS_CHANNEL_ID', 0))
        
        # Bot settings
        self.EMBED_COLOR = Color.blue()
        self.AUTO_CLOSE_HOURS = int(os.environ.get('AUTO_CLOSE_HOURS', 48))
        
        # Payment information
        self.PAYMENT_INFO = {
            'paypal': os.environ.get('PAYPAL_EMAIL', ''),
            'crypto': os.environ.get('CRYPTO_WALLET', ''),
            'bank': os.environ.get('BANK_DETAILS', '')
        }

    def validate(self):
        """Validate required configuration"""
        required_vars = {
            'DISCORD_TOKEN': self.TOKEN,
            'TICKET_CATEGORY_ID': self.TICKET_CATEGORY_ID,
            'ADMIN_ROLE_ID': self.ADMIN_ROLE_ID,
            'SELLER_ROLE_ID': self.SELLER_ROLE_ID,
            'BUYER_ROLE_ID': self.BUYER_ROLE_ID,
            'BOT_LOGS_CHANNEL_ID': self.BOT_LOGS_CHANNEL_ID,
            'TRANSCRIPTS_CHANNEL_ID': self.TRANSCRIPTS_CHANNEL_ID,
            'REVIEWS_CHANNEL_ID': self.REVIEWS_CHANNEL_ID
        }
        
        for var_name, value in required_vars.items():
            if not value:
                raise ValueError(f"{var_name} environment variable not set")
