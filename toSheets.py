import firebase_admin
from firebase_admin import credentials, auth
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def setup_firebase():
    """Initialize Firebase Admin SDK"""
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)

def get_firebase_users():
    """Retrieve all users from Firebase Authentication"""
    try:
        users = []
        page = auth.list_users()
        while page:
            for user in page.users:
                users.append(user.email)
            page = page.get_next_page()
        return users
    except Exception as e:
        print(f"Error fetching Firebase users: {e}")
        return []

def setup_sheets():
    """Initialize Google Sheets API"""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    sheets_cred_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
    if not sheets_cred_path:
        raise ValueError("Google Sheets credentials path not found in environment variables")
    
    creds = service_account.Credentials.from_service_account_file(
        sheets_cred_path,
        scopes=SCOPES
    )
    
    service = build('sheets', 'v4', credentials=creds)
    return service

def append_to_sheet(service, spreadsheet_id, users):
    """Append user emails to Google Sheet"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values = [[timestamp, email] for email in users]
        
        body = {
            'values': values
        }
        
        sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'Sheet1')
        range_name = f'{sheet_name}!A:B'
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        print(f"Appended {len(values)} rows.")
        return result
    except Exception as e:
        print(f"Error appending to sheet: {e}")
        return None

def main():
    spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
    if not spreadsheet_id:
        raise ValueError("Spreadsheet ID not found in environment variables")
    
    setup_firebase()
    sheets_service = setup_sheets()
    
    users = get_firebase_users()
    if not users:
        print("No users found or error occurred")
        return
    
    result = append_to_sheet(sheets_service, spreadsheet_id, users)
    if result:
        print("Successfully synced users to Google Sheet")

if __name__ == "__main__":
    main()