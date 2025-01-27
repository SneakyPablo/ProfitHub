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
        self.BUYER_ROLE_ID = int(os.environ.get('BUYER_ROLE_ID', 0))
        self.BOT_LOGS_CHANNEL_ID = int(os.environ.get('BOT_LOGS_CHANNEL_ID', 0))
        self.TRANSCRIPTS_CHANNEL_ID = int(os.environ.get('TRANSCRIPTS_CHANNEL_ID', 0))
        self.REVIEWS_CHANNEL_ID = int(os.environ.get('REVIEWS_CHANNEL_ID', 0))
        
        # Bot settings
        self.EMBED_COLOR = Color.blue()  # Default color for embeds
        self.AUTO_CLOSE_HOURS = int(os.environ.get('AUTO_CLOSE_HOURS', 48))  # Default 48 hours
        
        # Payment information
        self.PAYMENT_INFO = {
            'paypal': os.environ.get('PAYPAL_EMAIL', 'example@email.com'),
            'crypto': os.environ.get('CRYPTO_WALLET', 'YOUR_WALLET_ADDRESS'),
            'bank': os.environ.get('BANK_DETAILS', 'Bank: Example Bank\nIBAN: XX00 0000 0000 0000')
        }

        # Development settings
        self.DEV_MODE = os.environ.get('DEV_MODE', 'false').lower() == 'true'

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
        if not self.BUYER_ROLE_ID:
            raise ValueError("BUYER_ROLE_ID environment variable not set")
        if not self.BOT_LOGS_CHANNEL_ID:
            raise ValueError("BOT_LOGS_CHANNEL_ID environment variable not set")
        if not self.TRANSCRIPTS_CHANNEL_ID:
            raise ValueError("TRANSCRIPTS_CHANNEL_ID environment variable not set")
        if not self.REVIEWS_CHANNEL_ID:
            raise ValueError("REVIEWS_CHANNEL_ID environment variable not set") 
