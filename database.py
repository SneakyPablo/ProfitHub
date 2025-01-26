from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os
from bson import ObjectId

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

    async def get_active_tickets(self):
        """Get all active tickets"""
        cursor = self.tickets.find({'status': 'open'})
        tickets = await cursor.to_list(length=None)
        return tickets

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

    # Cleanup method
    async def close(self):
        """Close the database connection"""
        self.client.close()
