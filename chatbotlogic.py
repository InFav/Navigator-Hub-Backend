import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime, timedelta
import json
from models import ChatState, ChatHistory

load_dotenv()

class ChatbotManager:
    _instances = {}
    
    @classmethod
    def get_instance(cls, user_id: str, db) -> 'ChatbotLogic':
        # Create new instance every time but load state from database
        return ChatbotLogic(db, user_id)



class ChatbotLogic:
    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id
        
        # Load or initialize state
        chat_state = self.load_chat_state()
        if chat_state:
            self.current_phase = chat_state.current_phase
            self.current_question_index = chat_state.current_question_index
            self.user_profile = chat_state.user_profile or {}
            self.completed = chat_state.completed
        else:
            self.current_phase = 1
            self.current_question_index = 0
            self.user_profile = {}
            self.completed = False
            self.save_chat_state()  # Save initial state
        
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("No Google API key found")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        self.phase1_questions = [
            "Could you tell me about your current professional role?",
            "What are your key career achievements?",
            "What are your short-term and long-term career goals?",
            "What skills are you looking to develop?",
            "Are you interested in changing industries or roles?",
            "What motivates you professionally?"
        ]
        
        self.phase2_questions = [
            "What best describes your professional role? (Startup Founder/Early Career Professional/Mid Level Professional/Senior or Executive)",
            "Where do you currently work?",
            "What is your main goal for building influence? (Personal Branding/Product Promotions/Specific Topic Expertise)",
            "Tell me about your career journey.",
            "What size of companies are you targeting? (10-50/50-100/100-500/500-1000/1000+)",
            "Which industries are you focusing on?",
            "Who is your target audience? (Engineers/Researchers/Product Managers/Marketers/Designers)",
            "Could you share some of your favorite LinkedIn posts that reflect your writing style?",
            "What posts or content have performed best with your audience?",
            "How many posts would you like to create? (Choose between 5-10)",
            "What's the purpose of these posts? (Building up to News/Provide Information/Foster Audience Relationships/Promote Something/Expand your Network)",
            "What's your preferred timeline for these posts? (1-4 weeks)"
        ]

    def load_chat_state(self):
        return (self.db.query(ChatState)
                .filter(ChatState.user_id == self.user_id)
                .first())

    def save_chat_state(self):
        chat_state = self.load_chat_state()
        
        if not chat_state:
            chat_state = ChatState(
                user_id=self.user_id,
                current_phase=self.current_phase,
                current_question_index=self.current_question_index,
                user_profile=self.user_profile,
                completed=self.completed
            )
            self.db.add(chat_state)
        else:
            chat_state.current_phase = self.current_phase
            chat_state.current_question_index = self.current_question_index
            chat_state.user_profile = self.user_profile
            chat_state.completed = self.completed
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Error saving chat state: {e}")
            raise

    def save_chat_history(self, user_id: str, message: str, sender: str):
        chat_history = ChatHistory(
            user_id=user_id,
            message=message,
            sender=sender
        )
        self.db.add(chat_history)
        self.db.commit()

    async def process_message(self, message: str, user_id: str) -> dict:
        try:
            # Save user message
            self.save_chat_history(user_id, message, 'user')
            
            if self.current_phase == 1:
                result = await self.process_phase1_message(message, user_id)
            else:
                result = await self.process_phase2_message(message, user_id)
            
            # Save bot response
            if result.get("response"):
                self.save_chat_history(user_id, result["response"], 'bot')
            
            # Update state
            if result.get("completed"):
                self.completed = True
            self.save_chat_state()
            
            return result
            
        except Exception as e:
            print(f"Error processing message: {e}")
            raise

    def determine_role(self, profile_summary: str) -> str:
        try:
            role_prompt = """
            Based on this professional profile summary, determine if this person should be a MENTOR or MENTEE.
            Key indicators for MENTOR:
            - 5+ years of experience
            - Leadership or management experience
            - History of mentoring others
            - Strong expertise in specific areas
            - Achievement-focused responses
            
            Key indicators for MENTEE:
            - Less than 5 years experience
            - Seeking guidance or development
            - Focus on learning and growth
            - Minimal leadership experience
            - Challenge-focused responses

            Profile Summary:
            {profile_summary}

            Respond with only one word: either 'mentor' or 'mentee'
            """.format(profile_summary=profile_summary)
            
            role_response = self.model.generate_content(role_prompt).text.strip().lower()
            return role_response if role_response in ['mentor', 'mentee'] else 'mentee'
        except Exception as e:
            print(f"Error determining role: {e}")
            return 'mentee'

    async def process_phase1_message(self, message: str, user_id: str) -> dict:
        try:
            # Store the answer to the current question
            current_question = self.phase1_questions[self.current_question_index]
            self.user_profile[current_question] = message
            
            # Check if we have completed all phase 1 questions
            if self.current_question_index >= len(self.phase1_questions) - 1:
                # Generate profile summary and determine role
                summary_prompt = (
                    "Create a professional profile summary focused on experience level, "
                    "leadership history, and mentoring potential from these responses:\n" + 
                    "\n".join([f"{q}: {ans}" for q, ans in self.user_profile.items()])
                )
                
                profile_summary = self.model.generate_content(summary_prompt).text
                role = self.determine_role(profile_summary)
                
                transition_response = f"Thank you for sharing your professional journey. Based on your responses, you would be an excellent {role}. Let's create a content strategy that leverages your {role} position."
                first_content_question = self.phase2_questions[0]
                response = f"{transition_response}\n\n{first_content_question}"
                
                # Transition to phase 2
                self.current_phase = 2
                self.current_question_index = 0
                
                return {
                    "response": response,
                    "completed": False,
                    "phase": 1,
                    "role": role
                }
            else:
                # Move to next question
                self.current_question_index += 1
                next_question = self.phase1_questions[self.current_question_index]
                response = f"Thank you for sharing that.\n\n{next_question}"
                
                return {
                    "response": response,
                    "completed": False,
                    "phase": 1
                }
                
        except Exception as e:
            print(f"Error in phase 1: {e}")
            return {
                "response": "I understand. Let's continue with our discussion.",
                "completed": False,
                "phase": 1
            }

    async def process_phase2_message(self, message: str, user_id: str) -> dict:
        current_question = self.phase2_questions[self.current_question_index]
        
        if message.strip():
            self.user_profile[current_question] = message
            self.current_question_index += 1

        try:
            if self.current_question_index < len(self.phase2_questions):
                # Still have more questions to ask
                next_question = self.phase2_questions[self.current_question_index]
                response = f"Thank you for sharing that.\n\n{next_question}"
                
                return {
                    "response": response,
                    "completed": False,
                    "phase": 2
                }
            else:
                # All questions completed, generate content schedule
                try:
                    content_schedule = await self.generate_content_schedule(user_id)
                    final_response = "Great! I've created your content schedule based on our discussion. Redirecting you to your content calendar..."
                    
                    return {
                        "response": final_response,
                        "completed": True,
                        "phase": 2,
                        "schedule": content_schedule
                    }
                except Exception as e:
                    print(f"Error generating content schedule: {e}")
                    raise
        except Exception as e:
            print(f"Error in phase 2: {e}")
            return {
                "response": "Thank you for sharing. Let's continue discussing your content strategy.",
                "completed": False,
                "phase": 2
            }

    def save_persona_input(self, user_id: str):
        from models import PersonaInputNew
        from datetime import datetime
        
        try:
            # Rollback any existing transaction
            self.db.rollback()
            
            persona_data = PersonaInputNew(
                user_id=user_id,
                profession=self.user_profile.get(self.phase2_questions[0], ''),
                current_work=self.user_profile.get(self.phase2_questions[1], ''),
                goal=self.user_profile.get(self.phase2_questions[2], ''),
                journey=self.user_profile.get(self.phase2_questions[3], ''),
                company_size=self.user_profile.get(self.phase2_questions[4], ''),
                industry_target=self.user_profile.get(self.phase2_questions[5], ''),
                target_type=self.user_profile.get(self.phase2_questions[6], ''),
                favorite_posts=self.user_profile.get(self.phase2_questions[7], ''),
                best_posts=self.user_profile.get(self.phase2_questions[8], ''),
                posts_to_create=int(self.user_profile.get(self.phase2_questions[9], 5)),
                post_purpose=self.user_profile.get(self.phase2_questions[10], ''),
                timeline=self.user_profile.get(self.phase2_questions[11], '')
            )
            
            self.db.add(persona_data)
            self.db.commit()
            self.db.refresh(persona_data)
            return persona_data.id
            
        except Exception as e:
            self.db.rollback()
            print(f"Error saving persona input: {e}")
            raise
    async def generate_content_schedule(self, user_id: str):
        try:
            # Save persona first
            persona_id = self.save_persona_input(user_id)
            
            # Generate posts based on the persona
            num_posts = int(self.user_profile.get(self.phase2_questions[9], 5))
            timeline_weeks = int(self.user_profile.get(self.phase2_questions[11], '2').split()[0])
            
            # Generate content using AI
            prompt = f"""
            Create {num_posts} LinkedIn posts for a {self.user_profile.get(self.phase2_questions[0], '')} who works at {self.user_profile.get(self.phase2_questions[1], '')}.
            Their goal is {self.user_profile.get(self.phase2_questions[2], '')}.
            Target audience: {self.user_profile.get(self.phase2_questions[6], '')}.
            Industry focus: {self.user_profile.get(self.phase2_questions[5], '')}.
            Purpose: {self.user_profile.get(self.phase2_questions[10], '')}.
            Make posts professional and engaging for LinkedIn audience.
            Each post should be complete and self-contained.
            Include relevant hashtags at the end of each post.
            """
            
            response = self.model.generate_content(prompt).text
            posts = self.parse_generated_posts(response, num_posts, timeline_weeks)
            
            # Save posts to database
            self.save_posts(persona_id, posts)
            
            return {
                "persona_id": persona_id,
                "generated_posts": posts
            }
            
        except Exception as e:
            print(f"Error generating content schedule: {e}")
            raise

    def parse_generated_posts(self, ai_response: str, num_posts: int, timeline_weeks: int) -> dict:
        from datetime import datetime, timedelta
        
        # Split the AI response into individual posts
        post_contents = ai_response.split('\n\n')[:num_posts]
        
        # Calculate post dates spread across the timeline
        days_between_posts = (timeline_weeks * 7) // num_posts
        start_date = datetime.now()
        
        posts = {}
        for i, content in enumerate(post_contents):
            post_date = start_date + timedelta(days=i * days_between_posts)
            posts[str(i)] = {
                "Post_content": content.strip(),
                "Post_date": post_date.strftime("%Y-%m-%d")
            }
        
        return posts

    def save_posts(self, persona_id: int, posts: dict):
        from models import PostNew
        from datetime import datetime
        
        try:
            self.db.rollback()  # Rollback any existing transaction
            
            for post_data in posts.values():
                post = PostNew(
                    persona_id=persona_id,
                    post_content=post_data['Post_content'],
                    post_date=datetime.strptime(post_data['Post_date'], '%Y-%m-%d')
                )
                self.db.add(post)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            print(f"Error saving posts: {e}")
            raise