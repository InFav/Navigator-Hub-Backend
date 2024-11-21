import firebase_admin
from firebase_admin import credentials
import os
from dotenv import load_dotenv
from pathlib import Path

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

        # Get the absolute path to the credentials file
        creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        if not creds_path:
            raise ValueError("FIREBASE_CREDENTIALS_PATH not found in environment variables")

        # Convert to absolute path if relative
        creds_path = Path(creds_path).resolve()

        if not creds_path.exists():
            raise FileNotFoundError(f"Firebase credentials file not found at {creds_path}")

        print(f"Initializing Firebase with credentials from: {creds_path}")
        
        # Initialize the app
        cred = credentials.Certificate(str(creds_path))
        default_app = firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully")
        return default_app
        
    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
        raise