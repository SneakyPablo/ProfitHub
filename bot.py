import discord
from discord.ext import commands
import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

class Config:
    def __init__(self):
        # Get configuration from Railway variables
        self.TOKEN = os.environ.get('DISCORD_TOKEN')
        self.PREFIX = os.environ.get('BOT_PREFIX', '!')
        self.TICKET_CATEGORY_ID = int(os.environ.get('TICKET_CATEGORY_ID', 0))
        self.ADMIN_ROLE_ID = int(os.environ.get('ADMIN_ROLE_ID', 0))
        self.SELLER_ROLE_ID = int(os.environ.get('SELLER_ROLE_ID', 0))
        self.AUTO_CLOSE_HOURS = int(os.environ.get('AUTO_CLOSE_HOURS', 48))
        self.PAYMENT_INFO = {
            'paypal': os.environ.get('PAYPAL_EMAIL', 'example@email.com'),
            'crypto': os.environ.get('CRYPTO_WALLET', 'YOUR_WALLET_ADDRESS'),
            'bank': os.environ.get('BANK_DETAILS', 'Bank: Example Bank\nIBAN: XX00 0000 0000 0000')
        }

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
        data['created_at'] = datetime.now(timezone.utc)
        result = await self.products.insert_one(data)
        return result.inserted_id

    async def get_product(self, product_id):
        """Get a product by ID"""
        return await self.products.find_one({'_id': ObjectId(product_id)})

    async def delete_product(self, product_id):
        """Delete a product"""
        await self.products.delete_one({'_id': ObjectId(product_id)})

    async def delete_product_keys(self, product_id):
        """Delete all keys for a product"""
        await self.keys.delete_many({'product_id': ObjectId(product_id)})

    async def get_product_by_name_and_seller(self, name: str, seller_id: str):
        """Get a product by name and seller ID"""
        return await self.products.find_one({
            'name': name,
            'seller_id': seller_id
        })

    async def get_all_products(self):
        """Get all products (admin only)"""
        cursor = self.products.find()
        return await cursor.to_list(length=None)

    async def get_seller_products(self, seller_id: str):
        """Get products for a specific seller"""
        cursor = self.products.find({'seller_id': seller_id})
        return await cursor.to_list(length=None)

    # Key Methods
    async def add_product_key(self, data):
        """Add a new product key"""
        data['created_at'] = datetime.now(timezone.utc)
        data['is_used'] = False
        result = await self.keys.insert_one(data)
        return result.inserted_id

    async def get_key(self, key_id):
        """Get a key by ID"""
        return await self.keys.find_one({'_id': ObjectId(key_id)})

    async def delete_key(self, key_id):
        """Delete a key"""
        await self.keys.delete_one({'_id': ObjectId(key_id)})

    async def get_available_key(self, product_id, license_type: str):
        """Get an unused key for a product and license type"""
        return await self.keys.find_one({
            'product_id': ObjectId(product_id),
            'license_type': license_type,
            'is_used': False
        })

    async def get_available_key_count(self, product_id, license_type: str = None):
        """Get count of available keys for a product"""
        query = {
            'product_id': ObjectId(product_id),
            'is_used': False
        }
        if license_type:
            query['license_type'] = license_type
        return await self.keys.count_documents(query)

    async def get_keys_by_type(self, product_id, license_type: str):
        """Get all keys of a specific type for a product"""
        cursor = self.keys.find({
            'product_id': ObjectId(product_id),
            'license_type': license_type
        })
        return await cursor.to_list(length=None)

    async def get_product_keys(self, product_id):
        """Get all keys for a product"""
        cursor = self.keys.find({'product_id': ObjectId(product_id)})
        return await cursor.to_list(length=None)

    async def mark_key_as_used(self, key_id, buyer_id: str):
        """Mark a key as used"""
        await self.keys.update_one(
            {'_id': ObjectId(key_id)},
            {
                '$set': {
                    'is_used': True,
                    'used_by': buyer_id,
                    'used_at': datetime.now(timezone.utc)
                }
            }
        )

    # Ticket Methods
    async def create_ticket(self, data):
        """Create a new ticket"""
        data['created_at'] = datetime.now(timezone.utc)
        result = await self.tickets.insert_one(data)
        return result.inserted_id

    async def get_ticket_by_channel(self, channel_id: str):
        """Get ticket by channel ID"""
        return await self.tickets.find_one({'channel_id': channel_id})

    async def update_ticket(self, ticket_id, update_data):
        """Update ticket status"""
        update_data['updated_at'] = datetime.now(timezone.utc)
        await self.tickets.update_one(
            {'_id': ObjectId(ticket_id)},
            {'$set': update_data}
        )

    async def get_user_active_tickets(self, user_id: str):
        """Get active tickets for a user"""
        cursor = self.tickets.find({
            'buyer_id': user_id,
            'status': 'open'
        })
        return await cursor.to_list(length=None)

    # Review Methods
    async def create_review(self, data):
        """Create a new review"""
        data['created_at'] = datetime.now(timezone.utc)
        result = await self.reviews.insert_one(data)
        return result.inserted_id

    async def get_reviews(self, seller_id: str):
        """Get all reviews for a seller"""
        cursor = self.reviews.find({'seller_id': seller_id}).sort('created_at', -1)
        return await cursor.to_list(length=None)

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
            intents=intents,
            description="Marketplace Bot with ticket system and product management"
        )
        
        self.db = Database()

    async def setup_hook(self):
        """Set up bot and load cogs"""
        print("Setting up bot...")
        
        # Load all cogs
        cogs = ['product_manager', 'ticket_manager', 'review_manager', 'help_manager']
        for cog in cogs:
            try:
                await self.load_extension(f'cogs.{cog}')
                print(f'Loaded cog: {cog}')
            except Exception as e:
                print(f'Failed to load cog {cog}: {e}')

    async def on_ready(self):
        """Called when bot is ready"""
        print(f'Logged in as {self.user.name}')
        print(f'Bot ID: {self.user.id}')
        print('------')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{self.config.PREFIX}help | Marketplace"
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
