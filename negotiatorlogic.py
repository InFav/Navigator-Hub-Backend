import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
import json
from models import ChatState, ChatHistory, NegotiatorInput, NegotiatorPlan, NegotiatorState, NegotiatorHistory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('negotiator.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('NegotiatorChatbot')

load_dotenv()

class NegotiatorChatbot:
    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id
        logger.info(f"Initializing NegotiatorChatbot for user: {user_id}")
        
        # Initialize Gemini model
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            logger.error("No Google API key found")
            raise ValueError("No Google API key found")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        self.questions = [
            "What specific skills would you like to develop? Please list them in order of priority.",
            "How many hours per week can you dedicate to skill development and networking?",
            "What's your dream career position or role? Where do you see yourself ultimately?",
            "What are your current skills and expertise levels?",
            "How do you prefer to learn? (Video courses, reading, hands-on projects, mentorship)",
            "What types of resources do you prefer? (Online courses, books, workshops, mentorship)",
            "How do you feel about networking? Do you prefer one-on-one meetings or group events?",
        ]
        
        # Load state from database
        self.load_state()
    
    def load_state(self):
        try:
            logger.info(f"Loading state for user: {self.user_id}")
            negotiator_state = self.db.query(NegotiatorState).filter(
                NegotiatorState.user_id == self.user_id
            ).first()
            
            if negotiator_state:
                self.current_question_index = negotiator_state.current_question_index
                try:
                    self.user_profile = json.loads(negotiator_state.user_profile) if isinstance(negotiator_state.user_profile, str) else negotiator_state.user_profile or {}
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Error parsing user profile: {e}")
                    self.user_profile = {}
                self.completed = negotiator_state.completed
                logger.info(f"State loaded - Question index: {self.current_question_index}, Profile: {self.user_profile}")
            else:
                logger.info("No existing state found, initializing new state")
                self.current_question_index = 0
                self.user_profile = {}
                self.completed = False
                self.save_state()
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            self.current_question_index = 0
            self.user_profile = {}
            self.completed = False

    def validate_user_profile(self) -> bool:
        required_fields = [
            self.questions[0],  # Skills
            self.questions[1],  # Hours
            self.questions[2],  # Career Dream
            self.questions[3],  # Current Skills
            self.questions[4]   # Learning Style
        ]
        
        for field in required_fields:
            if not self.user_profile.get(field):
                logger.warning(f"Missing required field: {field}")
                return False
        return True

    def save_state(self):
        try:
            logger.info("Saving state to database")
            self.db.rollback()
            
            negotiator_state = self.db.query(NegotiatorState).filter(
                NegotiatorState.user_id == self.user_id
            ).first()
            
            if not negotiator_state:
                negotiator_state = NegotiatorState(
                    user_id=self.user_id,
                    current_question_index=self.current_question_index,
                    user_profile=json.dumps(self.user_profile),
                    completed=self.completed
                )
                self.db.add(negotiator_state)
            else:
                negotiator_state.current_question_index = self.current_question_index
                negotiator_state.user_profile = json.dumps(self.user_profile)
                negotiator_state.completed = self.completed
                negotiator_state.updated_at = datetime.now()
            
            self.db.commit()
            logger.info(f"State saved - Question index: {self.current_question_index}, Profile: {self.user_profile}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            self.db.rollback()

    def save_history(self, message: str, sender: str):
        try:
            logger.info(f"Saving message history - Sender: {sender}")
            self.db.rollback()
            history = NegotiatorHistory(
                user_id=self.user_id,
                message=message,
                sender=sender
            )
            self.db.add(history)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error saving history: {e}")
            self.db.rollback()

    async def generate_plans(self):
        try:
            logger.info("Generating achievement plans")
            base_hours = int(self.user_profile.get(self.questions[1], "5"))
            
            hours = {
                'achievable': base_hours,
                'negotiated': min(base_hours + 2, 40),
                'ambitious': min(base_hours + 5, 40)
            }

            plans = {}
            for plan_type, weekly_hours in hours.items():
                logger.info(f"Generating {plan_type} plan with {weekly_hours} hours")
                prompt = f"""
                Create a detailed learning and networking plan with the following requirements:
                
                User Profile:
                - Desired Skills: {self.user_profile.get(self.questions[0])}
                - Weekly Hours Available: {weekly_hours}
                - Career Dream: {self.user_profile.get(self.questions[2])}
                - Current Skills: {self.user_profile.get(self.questions[3])}
                - Learning Style: {self.user_profile.get(self.questions[4])}
                
                Plan Type: {plan_type.capitalize()}
                
                Return only a raw JSON object without any markdown formatting or JSON keyword. The response should strictly follow this format:
                {{
                    "courses": [
                        {{"name": "Course Name", "link": "Course URL", "duration": "Duration"}}
                    ],
                    "connections": [
                        {{"title": "Job Title", "company": "Company Name", "reason": "Reason for Connection"}}
                    ],
                    "events": [
                        {{"name": "Event Name", "type": "Event Type", "frequency": "Event Frequency"}}
                    ]
                }}
                """

                try:
                    response = self.model.generate_content(prompt).text
                    
                    # Clean up the response
                    response = response.strip()
                    # Remove all possible markdown and code block indicators
                    response = response.replace('```JSON', '')
                    response = response.replace('```json', '')
                    response = response.replace('```', '')
                    response = response.replace('JSON:', '')
                    response = response.replace('json:', '')
                    response = response.strip()
                    
                    logger.info(f"Raw response for {plan_type}: {response}")
                    
                    # Try to extract JSON if it's embedded in other text
                    try:
                        # Find the first { and last }
                        start_idx = response.find('{')
                        end_idx = response.rfind('}') + 1
                        if start_idx != -1 and end_idx != 0:
                            response = response[start_idx:end_idx]
                    except:
                        pass
                    
                    plan_data = json.loads(response)
                    
                    # Validate required keys
                    required_keys = ["courses", "connections", "events"]
                    if not all(key in plan_data for key in required_keys):
                        raise ValueError(f"Missing required keys in plan data. Required: {required_keys}")
                    
                    standardized_data = {
                        "courses": plan_data["courses"],
                        "connections": plan_data["connections"],
                        "events": plan_data["events"]
                    }

                    plans[plan_type] = standardized_data
                    logger.info(f"Successfully generated {plan_type} plan")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing error for {plan_type} plan: {e}")
                    logger.error(f"Raw response: {response}")
                    return None
                except Exception as e:
                    logger.error(f"Error generating {plan_type} plan: {e}")
                    return None

            return plans
        except Exception as e:
            logger.error(f"Error in generate_plans: {e}")
            return None
    async def save_plans(self, plans):
        try:
            logger.info("Saving plans to database")
            self.db.rollback()
            base_hours = int(self.user_profile.get(self.questions[1], "5"))
            
            hours = {
                'achievable': base_hours,
                'negotiated': min(base_hours + 2, 40),
                'ambitious': min(base_hours + 5, 40)
            }
            
            negotiator_input = NegotiatorInput(
                user_id=self.user_id,
                desired_skills=self.user_profile.get(self.questions[0], "").split(','),
                weekly_hours=base_hours,  # Using base hours for input record
                career_dream=self.user_profile.get(self.questions[2], ""),
                current_skills=self.user_profile.get(self.questions[3], "").split(','),
                learning_style=self.user_profile.get(self.questions[4], ""),
                preferred_resources=self.user_profile.get(self.questions[5], "").split(','),
                networking_preferences=self.user_profile.get(self.questions[6], "")
            )
            
            self.db.add(negotiator_input)
            self.db.commit()
            self.db.refresh(negotiator_input)

            for plan_type, plan_data in plans.items():
                negotiator_plan = NegotiatorPlan(
                    negotiator_id=negotiator_input.id,
                    plan_type=plan_type,
                    weekly_hours=hours[plan_type],  # Using the calculated hours based on plan type
                    courses=plan_data["courses"],
                    connections=plan_data["connections"],
                    events=plan_data["events"]
                )
                self.db.add(negotiator_plan)
            
            self.db.commit()
            logger.info(f"Plans saved successfully with input ID: {negotiator_input.id}")
            return negotiator_input.id
        except Exception as e:
            logger.error(f"Error saving plans: {e}")
            self.db.rollback()
            raise

    async def process_message(self, message: str) -> dict:
        try:
            logger.info(f"Processing message - Question index: {self.current_question_index}")
            
            # First validate the current state
            if self.current_question_index >= len(self.questions):
                self.current_question_index = 0
                self.user_profile = {}
                self.completed = False
                self.save_state()
            
            # Save user message
            self.save_history(message, 'user')
            
            # Check if chat is completed
            if self.completed:
                return {
                    "response": "Your achievement plan has already been created. Would you like to create a new one?",
                    "completed": True,
                    "plans": None
                }

            current_question = self.questions[self.current_question_index]
            
            # Handle the current answer
            if self.current_question_index == 1:
                try:
                    hours = int(message)
                    if hours <= 0:
                        logger.warning("Invalid hours input: <= 0")
                        return {
                            "response": "Please enter a number greater than 0 for hours per week.",
                            "completed": False
                        }
                    self.user_profile[current_question] = str(hours)
                except ValueError:
                    logger.warning(f"Invalid hours input: {message}")
                    return {
                        "response": "Please enter a valid number of hours per week (e.g., 5, 10, etc.)",
                        "completed": False
                    }
            else:
                self.user_profile[current_question] = message

            # Save state after processing answer
            self.save_state()
            
            # Move to next question
            self.current_question_index += 1
            
            # Save state after incrementing index
            self.save_state()
            
            # Check if we've reached the end
            if self.current_question_index >= len(self.questions):
                if not self.validate_user_profile():
                    logger.error("User profile validation failed")
                    return {
                        "response": "Some required information is missing. Let's start over.",
                        "completed": False
                    }
                
                # Generate and save plans
                plans = await self.generate_plans()
                if not plans:
                    logger.error("Failed to generate plans")
                    return {
                        "response": "I apologize, but I encountered an error generating your plans. Let's try again.",
                        "completed": False
                    }
                
                try:
                    plan_id = await self.save_plans(plans)
                    self.completed = True
                    self.save_state()
                    
                    final_response = """
                    Thank you for sharing your goals and preferences! I've created three personalized achievement plans for you:
                    1. Achievable Plan - Aligned with your current time commitment
                    2. Negotiated Plan - Slightly increased commitment for faster progress
                    3. Ambitious Plan - Accelerated path for maximum growth
                    
                    You can view these plans with detailed course recommendations, networking suggestions, and events in the Achievement Plan section.
                    """
                    
                    self.save_history(final_response, 'bot')
                    
                    return {
                        "response": final_response,
                        "completed": True,
                        "plans": {
                            "plan_id": plan_id,
                            "data": plans
                        }
                    }
                except Exception as e:
                    logger.error(f"Error saving plans: {e}")
                    return {
                        "response": "I apologize, but I encountered an error saving your plans. Let's try again.",
                        "completed": False
                    }
            
            # Get next question
            next_question = self.questions[self.current_question_index]
            self.save_history(next_question, 'bot')
            
            return {
                "response": next_question,
                "completed": False
            }
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "response": "I apologize, but I encountered an error. Could you please try again?",
                "completed": False
            }

    def reset_state(self):
        try:
            logger.info("Resetting state")
            self.current_question_index = 0
            self.user_profile = {}
            self.completed = False
            self.save_state()
            return {
                "response": self.questions[0],
                "completed": False
            }
        except Exception as e:
            logger.error(f"Error resetting state: {e}")
            return {
                "response": "An error occurred while resetting. Please try again.",
                "completed": False
            }