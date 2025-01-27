from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
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
        """Get all products"""
        cursor = self.products.find()
        return await cursor.to_list(length=None)

    async def get_seller_products(self, seller_id: str):
        """Get products for a specific seller"""
        cursor = self.products.find({'seller_id': seller_id})
        return await cursor.to_list(length=None)

    # Key Methods
    async def add_product_key(self, data):
        """Add a new product key"""
        data['created_at'] = datetime.utcnow()
        result = await self.keys.insert_one(data)
        return result.inserted_id

    async def get_available_key(self, product_id, license_type: str):
        """Get an available key for a product"""
        return await self.keys.find_one({
            'product_id': ObjectId(product_id),
            'license_type': license_type,
            'is_used': False
        })

    async def get_available_key_count(self, product_id, license_type: str = None):
        """Get count of available keys"""
        query = {
            'product_id': ObjectId(product_id),
            'is_used': False
        }
        if license_type:
            query['license_type'] = license_type
        return await self.keys.count_documents(query)

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

    # Ticket Methods
    async def create_ticket(self, data):
        """Create a new ticket"""
        data['created_at'] = datetime.utcnow()
        data['status'] = 'open'
        result = await self.tickets.insert_one(data)
        return result.inserted_id

    async def get_ticket_by_channel(self, channel_id: str):
        """Get ticket by channel ID"""
        return await self.tickets.find_one({'channel_id': channel_id})

    async def update_ticket(self, ticket_id, update_data):
        """Update ticket"""
        update_data['updated_at'] = datetime.utcnow()
        await self.tickets.update_one(
            {'_id': ObjectId(ticket_id)},
            {'$set': update_data}
        )

    async def get_seller_vouches(self, seller_id: str):
        """Get all vouched tickets for a seller"""
        cursor = self.tickets.find({
            'seller_id': seller_id,
            'vouched': True
        }).sort('created_at', -1)
        return await cursor.to_list(length=None)

    # Cleanup Methods
    async def delete_product(self, product_id):
        """Delete a product and its keys"""
        await self.products.delete_one({'_id': ObjectId(product_id)})
        await self.keys.delete_many({'product_id': ObjectId(product_id)})

    async def close(self):
        """Close database connection"""
        self.client.close()

    async def get_keys_by_type(self, product_id, license_type: str):
        """Get all keys of a specific type for a product"""
        cursor = self.keys.find({
            'product_id': ObjectId(product_id),
            'license_type': license_type
        })
        return await cursor.to_list(length=None)

    async def delete_key(self, key_id):
        """Delete a key"""
        await self.keys.delete_one({'_id': ObjectId(key_id)})

    async def get_user_active_tickets(self, user_id: str):
        """Get active tickets for a user"""
        cursor = self.tickets.find({
            'buyer_id': user_id,
            'status': 'open'
        })
        return await cursor.to_list(length=None)

    async def get_active_tickets(self):
        """Get all active tickets"""
        cursor = self.tickets.find({'status': 'open'})
        return await cursor.to_list(length=None)

    async def save_message(self, data):
        """Save a chat message"""
        data['created_at'] = datetime.utcnow()
        result = await self.messages.insert_one(data)
        return result.inserted_id

    async def get_ticket_messages(self, ticket_id):
        """Get all messages for a ticket"""
        cursor = self.messages.find({'ticket_id': ticket_id}).sort('created_at', 1)
        return await cursor.to_list(length=None)

    async def get_ticket_stats(self):
        """Get ticket statistics"""
        total = await self.tickets.count_documents({})
        open_tickets = await self.tickets.count_documents({'status': 'open'})
        closed_today = await self.tickets.count_documents({
            'status': 'closed',
            'closed_at': {'$gte': datetime.utcnow() - timedelta(days=1)}
        })
        vouched = await self.tickets.count_documents({'vouched': True})
        
        return {
            'total': total,
            'open': open_tickets,
            'closed_today': closed_today,
            'vouched': vouched
        }

    async def get_user_tickets(self, user_id: str):
        """Get all tickets for a user"""
        cursor = self.tickets.find({
            '$or': [
                {'buyer_id': user_id},
                {'seller_id': user_id}
            ]
        }).sort('created_at', -1)
        return await cursor.to_list(length=None) 
