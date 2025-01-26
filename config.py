import json
from pathlib import Path

class Config:
    def __init__(self):
        self.load_config()

    def load_config(self):
        config_path = Path('config.json')
        if not config_path.exists():
            self.create_default_config()
        
        with open('config.json', 'r') as f:
            config = json.load(f)
            
        self.TOKEN = config['token']
        self.PREFIX = config['prefix']
        self.TICKET_CATEGORY_ID = config['ticket_category_id']
        self.ADMIN_ROLE_ID = config['admin_role_id']
        self.SELLER_ROLE_ID = config['seller_role_id']
        self.EMBED_COLOR = int(config['embed_color'], 16)
        self.AUTO_CLOSE_HOURS = config['auto_close_hours']
        
    def create_default_config(self):
        default_config = {
            "token": "YOUR_BOT_TOKEN",
            "prefix": "!",
            "ticket_category_id": 0,
            "admin_role_id": 0,
            "seller_role_id": 0,
            "embed_color": "0x3498db",
            "auto_close_hours": 48
        }
        
        with open('config.json', 'w') as f:
            json.dump(default_config, f, indent=4)
