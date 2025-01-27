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
        self.messages = self.db.messages

    # Add this new method
    async def get_available_key_count(self, product_id, license_type: str = None):
        """Get count of available keys for a product and license type"""
        query = {
            'product_id': ObjectId(product_id),
            'is_used': False
        }
        if license_type:
            query['license_type'] = license_type
        return await self.keys.count_documents(query)

    # Existing methods...
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
        return await cursor.to_list(length=None)

    async def get_seller_products(self, seller_id: str):
        """Get products for a specific seller"""
        cursor = self.products.find({'seller_id': seller_id})
        return await cursor.to_list(length=None)

    async def add_product_key(self, data):
        """Add a new product key"""
        data['created_at'] = datetime.utcnow()
        data['is_used'] = False
        result = await self.keys.insert_one(data)
        return result.inserted_id

    async def get_available_key(self, product_id, license_type: str):
        """Get an unused key for a product and license type"""
        return await self.keys.find_one({
            'product_id': ObjectId(product_id),
            'license_type': license_type,
            'is_used': False
        })

    async def get_keys_by_type(self, product_id, license_type: str):
        """Get all keys of a specific type for a product"""
        cursor = self.keys.find({
            'product_id': ObjectId(product_id),
            'license_type': license_type
        })
        return await cursor.to_list(length=None)

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

    async def delete_product(self, product_id):
        """Delete a product"""
        await self.products.delete_one({'_id': ObjectId(product_id)})

    async def delete_product_keys(self, product_id):
        """Delete all keys for a product"""
        await self.keys.delete_many({'product_id': ObjectId(product_id)})

    async def get_key(self, key_id):
        """Get a key by ID"""
        return await self.keys.find_one({'_id': ObjectId(key_id)})

    async def delete_key(self, key_id):
        """Delete a key"""
        await self.keys.delete_one({'_id': ObjectId(key_id)})

    async def close(self):
        """Close the database connection"""
        self.client.close() 
