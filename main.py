from fastapi import FastAPI, Depends, HTTPException, WebSocket 
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from firebase_admin import auth, credentials, initialize_app
import firebase_admin
from sqlalchemy import text
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
from typing import List
from config.firebase_admin import init_firebase
import json
from datetime import datetime, timedelta
import google.generativeai as genai
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import BaseModel, EmailStr
from datetime import datetime
from models import Feedback
from models import ChatState, ChatHistory, NegotiatorInput, NegotiatorPlan
from negotiatorlogic import NegotiatorChatbot

load_dotenv()

#cred = credentials.Certificate(os.getenv('FIREBASE_CREDENTIALS_PATH'))


app = FastAPI()
security = HTTPBearer()
init_firebase()


origins = [
    "http://localhost:5173",
    "https://navigatorhub.netlify.app",
    "http://navigatorhub.netlify.app",
    "https://navhub-backend-3bcc3222593e.herokuapp.com",
    "https://navhub.ai",
    "http://navhub.ai"
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

class FeedbackCreate(BaseModel):
    rating: int
    type: str
    feedback: str
    userEmail: Optional[str]
    timestamp: str

class ChatHistoryResponse(BaseModel):
    messages: List[dict]

class RegeneratePostRequest(BaseModel):
    customPrompt: Optional[str] = None

# Email configuration
mail_config = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_FROM"),
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

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
        print(f"Processing chat for user: {user_id}")
        print(f"Message received: {user_message.message}")
        
        # Get chatbot instance
        try:
            chatbot = ChatbotManager.get_instance(user_id, db)
            print(f"Chatbot instance created. Phase: {chatbot.current_phase}")
            print(f"Current user_profile: {chatbot.user_profile}")
        except Exception as e:
            print(f"Error creating chatbot instance: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error initializing chat: {str(e)}"
            )
        
        # Process message
        try:
            result = await chatbot.process_message(message=user_message.message, user_id=user_id)
            print(f"Message processed. Result: {result}")
            return ChatResponse(
                response=result["response"],
                role=result.get("role"),
                completed=result.get("completed", False),
                phase=result.get("phase", 1),
                schedule=result.get("schedule")
            )
        except Exception as chat_error:
            print(f"Error processing chat message: {str(chat_error)}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Chat processing error: {str(chat_error)}"
            )
        
    except Exception as e:
        print(f"Chat endpoint error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Server error: {str(e)}"
        )

@app.get("/test-db")
async def test_db(db: Session = Depends(database.get_db)):
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {"status": "Database connected", "test_query": result}
    except Exception as e:
        print(f"Database error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


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

@app.post("/api/posts/{persona_id}/{post_index}/regenerate")
async def regenerate_post(
    persona_id: int,
    post_index: int,
    request: RegeneratePostRequest,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        persona = db.query(models.PersonaInputNew).filter(
            models.PersonaInputNew.id == persona_id
        ).first()
        
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        
        posts = db.query(models.PostNew).filter(
            models.PostNew.persona_id == persona_id
        ).order_by(models.PostNew.post_date.asc()).all()
        
        if not posts or post_index >= len(posts):
            raise HTTPException(status_code=404, detail="Post not found")
            
        post = posts[post_index]
            
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("No Google API key found")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        # Base prompt
        prompt = f"""
        Generate a new LinkedIn post for a {persona.profession} who works at {persona.current_work}.
        Their goal is {persona.goal}.
        Target audience: {persona.target_type}
        Industry focus: {persona.industry_target}
        Purpose: {persona.post_purpose}
        """

        # Add custom prompt if provided
        if request.customPrompt:
            prompt += f"\nAdditional requirements: {request.customPrompt}\n"

        prompt += """
        Requirements:
        1. Length: 200-400 characters
        2. Include engaging content
        3. Add 2-3 relevant hashtags at the end
        4. Make it professional and unique
        5. Keep consistent tone with target audience
        
        [POST START]
        Generate post here...
        [POST END]
        """
        
        response = model.generate_content(prompt).text
        
        if '[POST START]' in response and '[POST END]' in response:
            new_content = response.split('[POST START]')[1].split('[POST END]')[0].strip()
        else:
            new_content = response.strip()
        
        post.post_content = new_content
        post.regenerate_clicks = (post.regenerate_clicks or 0) + 1
        db.commit()
        
        updated_posts = db.query(models.PostNew).filter(
            models.PostNew.persona_id == persona_id
        ).order_by(models.PostNew.post_date.asc()).all()
        
        formatted_posts = {
            str(i): {
                "Post_content": p.post_content,
                "Post_date": p.post_date.strftime("%Y-%m-%d")
            }
            for i, p in enumerate(updated_posts)
        }
        
        return {
            "persona_id": persona_id,
            "generated_posts": formatted_posts
        }
        
    except Exception as e:
        print(f"Error regenerating post: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

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
@app.post("/api/feedback")
async def create_feedback(feedback: FeedbackCreate, db: Session = Depends(database.get_db)):
    try:
        # Save to database
        db_feedback = Feedback(
            rating=feedback.rating,
            type=feedback.type,
            feedback=feedback.feedback,
            user_email=feedback.userEmail,
            timestamp=datetime.fromisoformat(feedback.timestamp)
        )
        db.add(db_feedback)
        db.commit()

        # Create email content
        email_body = f"""
        New Feedback Received
        
        From: {feedback.userEmail or 'Anonymous'}
        Rating: {feedback.rating}/5
        Type: {feedback.type}
        
        Feedback Message:
        {feedback.feedback}
        
        Time: {feedback.timestamp}
        """

        admin_message = MessageSchema(
            subject=f"Navigator Hub Feedback: {feedback.type.title()}",
            recipients=["hello@navhub.ai", "users.navhub@gmail.com"],
            body=email_body,
            subtype="plain"
        )

        fastmail = FastMail(mail_config)
        await fastmail.send_message(admin_message)

        if feedback.userEmail:
            user_message = MessageSchema(
                subject="Thank you for your feedback - Navigator Hub",
                recipients=[feedback.userEmail],
                body=f"""
                Thank you for your feedback!
                
                We've received your {feedback.type} and will review it carefully.
                
                Your feedback:
                {feedback.feedback}
                
                Best regards,
                Navigator Hub Team
                """,
                subtype="plain"
            )
            await fastmail.send_message(user_message)

        return {"status": "success"}
    except Exception as e:
        print(f"Error processing feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history/{user_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    user_id: str,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        if token_data["uid"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view this chat history"
            )
        
        chat_state = db.query(ChatState).filter(
            ChatState.user_id == user_id
        ).first()
        
        history = db.query(ChatHistory).filter(
            ChatHistory.user_id == user_id
        ).order_by(ChatHistory.created_at.asc()).all()
        
        messages = [
            {
                "text": msg.message,
                "sender": msg.sender,
                "timestamp": msg.created_at.isoformat()
            }
            for msg in history
        ]
        
        return ChatHistoryResponse(
            messages=messages
        )
        
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/api/chat/state/{user_id}")
async def get_chat_state(
    user_id: str,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        if token_data["uid"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view this chat state"
            )
        
        chat_state = db.query(ChatState).filter(
            ChatState.user_id == user_id
        ).first()
        
        if not chat_state:
            return {
                "current_phase": 1,
                "current_question_index": 0,
                "completed": False,
                "user_profile": {}
            }
            
        return {
            "current_phase": chat_state.current_phase,
            "current_question_index": chat_state.current_question_index,
            "completed": chat_state.completed,
            "user_profile": chat_state.user_profile
        }
        
    except Exception as e:
        print(f"Error fetching chat state: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
@app.post("/negotiator/chat", response_model=ChatResponse)
async def handle_negotiator_chat(
    user_message: UserMessage,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        user_id = token_data["uid"]
        chatbot = NegotiatorChatbot(db, user_id)
        
        try:
            result = await chatbot.process_message(message=user_message.message)
            return ChatResponse(
                response=result["response"],
                completed=result.get("completed", False),
                plans=result.get("plans")
            )
        except Exception as e:
            db.rollback()  
            print(f"Error processing message: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error processing message"
            )
            
    except Exception as e:
        db.rollback()  
        print(f"Negotiator chat error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Server error: {str(e)}"
        )
    finally:
        try:
            db.close()  
        except:
            pass

@app.get("/negotiator/plans/{user_id}")
async def get_user_plans(
    user_id: str,
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(database.get_db)
):
    try:
        if token_data["uid"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view these plans")
            
        negotiator_input = db.query(NegotiatorInput).filter(
            NegotiatorInput.user_id == user_id
        ).order_by(NegotiatorInput.created_at.desc()).first()
        
        if not negotiator_input:
            raise HTTPException(status_code=404, detail="No plans found")
            
        plans = db.query(NegotiatorPlan).filter(
            NegotiatorPlan.negotiator_id == negotiator_input.id
        ).all()
        
        response_data = {
            "plan_id": negotiator_input.id,
            "data": {
                plan.plan_type: {
                    "weekly_hours": plan.weekly_hours,
                    "courses": plan.courses,
                    "connections": plan.connections,
                    "events": plan.events
                }
                for plan in plans
            }
        }
        
        # Debug logging
        print("Response data:", response_data)
        
        return response_data
        
    except Exception as e:
        print(f"Error getting plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    