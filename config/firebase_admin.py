import firebase_admin
from firebase_admin import credentials
import os
from dotenv import load_dotenv
from pathlib import Path
import json

# Load environment variables
load_dotenv()

def init_firebase():
    try:
        # Check if Firebase is already initialized
        try:
            firebase_admin.get_app()
            print("Firebase Admin SDK already initialized")
            return
        except ValueError:
            pass  # Not initialized yet, continue with initialization

        # Try to get credentials from JSON string first (Heroku)
        firebase_creds = os.getenv('FIREBASE_CREDENTIALS')
        if firebase_creds:
            cred_dict = json.loads(firebase_creds)
            cred = credentials.Certificate(cred_dict)
        else:
            # Fallback to file path (local development)
            creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
            if not creds_path:
                raise ValueError("Neither FIREBASE_CREDENTIALS nor FIREBASE_CREDENTIALS_PATH found")
            cred = credentials.Certificate(creds_path)

        default_app = firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully")
        return default_app
        
    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
        raise