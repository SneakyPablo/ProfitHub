from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os

class Database:
    def __init__(self):
        # Get MongoDB URI from environment variable
        mongodb_uri = os.getenv('MONGODB_URI')
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable not set")
            
        self.client = AsyncIOMotorClient(mongodb_uri)
        self.db = self.client.marketplace
        
        # Collections
        self.products = self.db.products
        self.tickets = self.db.tickets
        self.reviews = self.db.reviews
        self.keys = self.db.keys

    async def create_product(self, data):
        data['created_at'] = datetime.utcnow()
        result = await self.products.insert_one(data)
        return result.inserted_id

    async def get_product(self, product_id):
        return await self.products.find_one({'_id': product_id})

    async def create_ticket(self, data):
        data['created_at'] = datetime.utcnow()
        result = await self.tickets.insert_one(data)
        return result.inserted_id

    async def update_ticket(self, ticket_id, update_data):
        await self.tickets.update_one(
            {'_id': ticket_id},
            {'$set': update_data}
        )

    async def create_review(self, data):
        data['created_at'] = datetime.utcnow()
        result = await self.reviews.insert_one(data)
        return result.inserted_id

    async def get_reviews(self, seller_id):
        cursor = self.reviews.find({'seller_id': seller_id})
        return await cursor.to_list(length=None)

    async def add_product_key(self, data):
        data['created_at'] = datetime.utcnow()
        data['is_used'] = False
        result = await self.keys.insert_one(data)
        return result.inserted_id
