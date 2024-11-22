from fastapi import FastAPI, Depends, HTTPException, WebSocket 
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from firebase_admin import auth, credentials, initialize_app
import firebase_admin

import database 
import models
from typing import Optional
import httpx
from pydantic import BaseModel
from dotenv import load_dotenv
from jwt import PyJWKClient
import os
import uvicorn 
from chatbotlogic import ChatbotLogic, ChatbotManager 
from typing import Optional
from config.firebase_admin import init_firebase
import json
from datetime import datetime, timedelta


load_dotenv()

#cred = credentials.Certificate(os.getenv('FIREBASE_CREDENTIALS_PATH'))


app = FastAPI()
security = HTTPBearer()
init_firebase()


origins = [
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  
    allow_credentials=True,  
    allow_methods=["*"],  
    allow_headers=["*"],  
)



class UserCreate(BaseModel):
    email: str
    uid: str
    name: Optional[str] = None
    picture: Optional[str] = None

async def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        if token.startswith('Bearer '):
            token = token[7:]
        
        print(f"Attempting to verify token: {token[:10]}...")
        decoded_token = auth.verify_id_token(token)
        print(f"Token verified successfully for UID: {decoded_token['uid']}")
        return decoded_token
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )

@app.get("/api/auth/check")
async def check_auth(token_data: dict = Depends(verify_firebase_token)):
    try:
        return {"status": "authenticated", "uid": token_data["uid"]}
    except Exception as e:
        print(f"Auth check error: {str(e)}")
        raise

@app.post("/api/users")
async def create_user(
    user: UserCreate,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        if token_data["uid"] != user.uid:
            raise HTTPException(status_code=403, detail="Unauthorized: UID mismatch")
        
        # Check if user exists
        existing_user = db.query(models.User).filter(models.User.uid == user.uid).first()
        if existing_user:
            return existing_user
        
        # Create new user
        db_user = models.User(
            email=user.email,
            uid=user.uid,
            name=user.name,
            picture=user.picture
        )
        
        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except Exception as e:
            db.rollback()
            print(f"Database error: {e}")
            raise HTTPException(status_code=400, detail="Database error occurred")
            
    except Exception as e:
        print(f"Create user error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.on_event("startup")
async def startup_event():
    try:
        # This will raise ValueError if not initialized
        firebase_admin.get_app()
        print("Firebase Admin SDK is initialized")
    except ValueError:
        print("Firebase Admin SDK not initialized, initializing now...")
        init_firebase()

@app.get("/api/users/me")
async def read_user(
    db: Session = Depends(database.get_db),
    token_data: dict = Depends(verify_firebase_token)
):
    user = db.query(models.User).filter(models.User.uid == token_data["uid"]).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/api/auth/logout")
async def logout(token_data: dict = Depends(verify_firebase_token)):
    try:
        return {"status": "logged out"}
    except Exception as e:
        print(f"Logout error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class UserMessage(BaseModel):
    message: str 

class ChatResponse(BaseModel):
    response: str
    role: Optional[str] = None
    completed: Optional[bool] = None
    phase: Optional[int] = None
    schedule: Optional[dict] = None


def get_chatbot(db: Session = Depends(database.get_db)):
    return ChatbotLogic(db)

@app.post("/chat", response_model=ChatResponse)
async def handle_chat(
    user_message: UserMessage,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        user_id = token_data["uid"]
        # Get or create chatbot instance for this user
        chatbot = ChatbotManager.get_instance(user_id, db)
        
        result = await chatbot.process_message(message=user_message.message, user_id=user_id)
        
        # If chat is completed, clear the instance
        if result.get("completed"):
            ChatbotManager.clear_instance(user_id)
        
        return ChatResponse(
            response=result["response"],
            role=result.get("role"),
            completed=False if not result.get("completed") else result.get("completed"),
            phase=result.get("phase", 1)
        )
        
    except Exception as e:
        print(f"Chat error: {e}")
        # Clear instance on error to avoid stuck states
        ChatbotManager.clear_instance(user_id)
        raise HTTPException(status_code=500, detail=str(e))

# Update WebSocket endpoint as well
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    await websocket.accept()
    try:
        user_id = token_data["uid"]
        chatbot = ChatbotManager.get_instance(user_id, db)
        while True:
            data = await websocket.receive_text()
            result = await chatbot.process_message(message=data, user_id=user_id)
            if result.get("completed"):
                ChatbotManager.clear_instance(user_id)
            await websocket.send_json(result)
    except Exception as e:
        print(f"WebSocket error: {e}")
        ChatbotManager.clear_instance(token_data["uid"])
        await websocket.close()

@app.get("/api/schedule/{user_id}")
async def get_user_schedule(
    user_id: str,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        if token_data["uid"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this schedule")
            
        # Get the most recent persona from the new table
        persona = db.query(models.PersonaInputNew).filter(
            models.PersonaInputNew.user_id == user_id
        ).order_by(models.PersonaInputNew.created_at.desc()).first()
        
        if not persona:
            raise HTTPException(status_code=404, detail="No content schedule found")
            
        # Get all posts from the new posts table
        posts = db.query(models.PostNew).filter(
            models.PostNew.persona_id == persona.id
        ).order_by(models.PostNew.post_date.asc()).all()
        
        formatted_posts = {
            str(i): {
                "Post_content": post.post_content,
                "Post_date": post.post_date.strftime("%Y-%m-%d")
            }
            for i, post in enumerate(posts)
        }
        
        return {
            "persona_id": persona.id,
            "generated_posts": formatted_posts
        }
        
    except Exception as e:
        print(f"Error getting schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    