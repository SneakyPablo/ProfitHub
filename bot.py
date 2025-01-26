import discord
from discord.ext import commands
import asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient  # Add this import
from bson import ObjectId  # Add this import too

class Config:
    def __init__(self):
        # Get configuration from Railway variables
        self.TOKEN = os.environ.get('DISCORD_TOKEN')
        self.PREFIX = os.environ.get('BOT_PREFIX', '!')
        self.TICKET_CATEGORY_ID = int(os.environ.get('TICKET_CATEGORY_ID', 0))
        self.ADMIN_ROLE_ID = int(os.environ.get('ADMIN_ROLE_ID', 0))
        self.SELLER_ROLE_ID = int(os.environ.get('SELLER_ROLE_ID', 0))
        self.AUTO_CLOSE_HOURS = int(os.environ.get('AUTO_CLOSE_HOURS', 48))

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

class Database:
    def __init__(self):
        # Get MongoDB URI from Railway variables
        mongodb_uri = os.environ.get('MONGODB_URL')
        if not mongodb_uri:
            raise ValueError("MONGODB_URL environment variable not set")
            
        self.client = AsyncIOMotorClient(mongodb_uri)
        self.db = self.client.marketplace
        
        # Collections
        self.products = self.db.products
        self.tickets = self.db.tickets
        self.reviews = self.db.reviews
        self.keys = self.db.keys

    # Product Methods
    async def create_product(self, data):
        """Create a new product"""
        data['created_at'] = datetime.utcnow()
        result = await self.products.insert_one(data)
        return result.inserted_id

    async def get_product(self, product_id):
        """Get a product by ID"""
        return await self.products.find_one({'_id': ObjectId(product_id)})

    async def get_all_products(self):
        """Get all products (admin only)"""
        cursor = self.products.find()
        products = await cursor.to_list(length=None)
        return products

    async def get_seller_products(self, seller_id: str):
        """Get products for a specific seller"""
        cursor = self.products.find({'seller_id': seller_id})
        products = await cursor.to_list(length=None)
        return products

    # Ticket Methods
    async def create_ticket(self, data):
        """Create a new ticket"""
        data['created_at'] = datetime.utcnow()
        result = await self.tickets.insert_one(data)
        return result.inserted_id

    async def get_ticket_by_channel(self, channel_id: str):
        """Get ticket by channel ID"""
        return await self.tickets.find_one({'channel_id': channel_id})

    async def update_ticket(self, ticket_id, update_data):
        """Update ticket status"""
        await self.tickets.update_one(
            {'_id': ObjectId(ticket_id)},
            {'$set': update_data}
        )

    # Review Methods
    async def create_review(self, data):
        """Create a new review"""
        data['created_at'] = datetime.utcnow()
        result = await self.reviews.insert_one(data)
        return result.inserted_id

    async def get_reviews(self, seller_id: str):
        """Get all reviews for a seller"""
        cursor = self.reviews.find({'seller_id': seller_id}).sort('created_at', -1)
        reviews = await cursor.to_list(length=None)
        return reviews

    # Key Methods
    async def add_product_key(self, data):
        """Add a new product key"""
        data['created_at'] = datetime.utcnow()
        data['is_used'] = False
        result = await self.keys.insert_one(data)
        return result.inserted_id

    async def get_available_key(self, product_id):
        """Get an unused key for a product"""
        return await self.keys.find_one({
            'product_id': ObjectId(product_id),
            'is_used': False
        })

    async def mark_key_as_used(self, key_id, buyer_id: str):
        """Mark a key as used"""
        await self.keys.update_one(
            {'_id': ObjectId(key_id)},
            {
                '$set': {
                    'is_used': True,
                    'used_by': buyer_id,
                    'used_at': datetime.utcnow()
                }
            }
        )

    async def close(self):
        """Close the database connection"""
        await self.client.close()

class MarketplaceBot(commands.Bot):
    def __init__(self):
        self.config = Config()
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
        """Set up bot and load cogs"""
        # Load all cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'Loaded cog: {filename[:-3]}')
                except Exception as e:
                    print(f'Failed to load cog {filename}: {e}')

    async def on_ready(self):
        """Called when bot is ready"""
        print(f'Logged in as {self.user.name}')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{self.config.PREFIX}help | Marketplace"
            )
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
        else:
            print(f'Error in command {ctx.command}: {error}')

    async def close(self):
        """Cleanup when bot shuts down"""
        await self.db.close()
        await super().close()

def run_bot():
    """Initialize and run the bot"""
    try:
        bot = MarketplaceBot()
        bot.run(bot.config.TOKEN)
    except Exception as e:
        print(f"Failed to start bot: {e}")

if __name__ == "__main__":
    run_bot()
