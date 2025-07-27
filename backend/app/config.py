import os
import json

def get_google_oauth_config():
    """Load Google OAuth config from JSON file"""
    config_path = os.path.join(os.path.dirname(__file__), "env/google_oauth_client.json")
    with open(config_path) as f:
        secrets = json.load(f)
    
    return {
        "client_id": secrets["web"]["client_id"],
        "client_secret": secrets["web"]["client_secret"]
    }

# You can add other config here later
SECRET = "SECRET"  # TODO: Move to environment variable