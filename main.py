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
from chatbotlogic import ChatbotLogic 
from typing import Optional
from config.firebase_admin import init_firebase


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
    next_question: Optional[str] = None

Questions = [
    "Could you tell me about your current professional role?",
    "What industries have you worked in?",
    "What are your key career achievements?",
    "What are your short-term and long-term career goals?",
    "What skills are you looking to develop?",
    "Are you interested in changing industries or roles?",
    "What motivates you professionally?"
]

chatbot_logic = ChatbotLogic(Questions)
@app.post("/chat", response_model=ChatResponse)
async def handle_chat(user_message: UserMessage):
    result = chatbot_logic.process_message(user_message.message)
    
    return ChatResponse(
        response=result["response"],
        role=result["role"]
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            result = chatbot_logic.process_message(data)
            await websocket.send_json(result)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    