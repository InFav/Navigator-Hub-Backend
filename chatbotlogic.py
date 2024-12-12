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
        return ChatbotLogic(db, user_id)



class ChatbotLogic:
    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id
        try:
            chat_state = self.load_chat_state()
            if chat_state:
                print(f"Loading existing chat state for user {user_id}")

                self.current_phase = chat_state.current_phase
                self.current_question_index = chat_state.current_question_index
                self.user_profile = chat_state.user_profile or {}
                self.completed = chat_state.completed
            else:
                print(f"Initializing new chat state for user {user_id}")

                self.current_phase = 1
                self.current_question_index = 0
                self.user_profile = {}
                self.completed = False
                self.save_chat_state()  
            
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("No Google API key found")
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            
            self.phase1_questions = [
                {
                    "number": 1,
                    "total": 5,
                    "question": "Can you tell me your name.",
                    "emoji": "👋"
                },
                {
                    "number": 2,
                    "total": 5,
                    "question": "How many years of professional experience do you have?",
                    "emoji": "⏳"
                },
                {
                    "number": 3,
                    "total": 5,
                    "question": "What are the highlights of your career journey so far? What are the achievements you are most proud of? For example: tell me about an award you won or a project you were recognised for.",
                    "emoji": "🏆"
                },
                {
                    "number": 4,
                    "total": 5,
                    "question": "What are your short and long term goals? Where do you see yourself in 5 years? What is your ideal role?",
                    "emoji": "🎯"
                },
                {
                    "number": 5,
                    "total": 5,
                    "question": "What motivates you to progress professionally? Tell me what makes you excited when you get up in the morning or the key factor behind your hard work. An Example: My team's goal is to build a legacy.",
                    "emoji": "✨"
                }
            ]
            
            self.phase2_questions = [
            {
                "number": 1,
                "total": 10,
                "question": "What best describes your professional role? (Student/Startup Founder/Early Career Professional/Mid Level Professional/Senior or Executive)",
                "emoji": "💼"
            },
            {
                "number": 2,
                "total": 10,
                "question": "Where do you currently work/study? Please mention your current role, the previous kind of projects you have done or the path you took to be where you are right now. The more information the better!",
                "emoji": "🏢"
            },
            {
                "number": 3,
                "total": 10,
                "question": "What is your main goal for building influence? (Personal Branding/Product Promotions/Specific Topic Expertise)",
                "emoji": "🎯"
            },
            {
                "number": 4,
                "total": 10,
                "question": "We are going to get deeper into the Strategy of targeting the type of audience you want to capture. That is, what size of companies would you prefer most of the audience come from, who get impacted by your content (10-50/50-100/100-500/500-1000/1000+)",
                "emoji": "🎯"
            },
            {
                "number": 5,
                "total": 10,
                "question": "What is your focus industry for building influence, that is, what industry would you like most if your audience members to come from?",
                "emoji": "🏭"
            },
            {
                "number": 6,
                "total": 10,
                "question": "Could you share some of your favorite LinkedIn posts or ANY writing samples that reflect your writing style the most? Please copy and paste the post text, no links please– I get confused with links.",
                "emoji": "✍️"
            },
            {
                "number": 7,
                "total": 10,
                "question": "What posts or content have performed best with your audience? This could be something you wrote or read that seem to have gotten a lot of traction with the audience members you'd like to influence. Please copy and paste the post text, no links– I get confused with links.",
                "emoji": "📈"
            },
            {
                "number": 8,
                "total": 10,
                "question": "How many posts would you like to create for your first LinkedIn post series by Aru from NavHub? (Choose between 5-10)",
                "emoji": "🔢"
            },
            {
                "number": 9,
                "total": 10,
                "question": "What's the purpose of this specific first LinkedIn post series we will be launching today? (Examples: Building up to a News, Provide Information, Foster Audience Relationships, Promote Something, Expand your Network)",
                "emoji": "🎯"
            },
            {
                "number": 10,
                "total": 10,
                "question": "What's your preferred timeline for these posts, aka, how long would you like this inaugural series for building your strategic influence, to last? (1-4 weeks)",
                "emoji": "📅"
            }
        ]
        except Exception as e:
            print(f"Error initializing ChatbotLogic: {e}")
            raise

    def load_chat_state(self):
        try:
            chat_state = (self.db.query(ChatState)
                        .filter(ChatState.user_id == self.user_id)
                        .first())
            
            if chat_state and chat_state.user_profile:
                try:
                    if isinstance(chat_state.user_profile, str):
                        chat_state.user_profile = json.loads(chat_state.user_profile)
                    elif isinstance(chat_state.user_profile, dict):
                        pass
                    else:
                        print(f"Unexpected user_profile type: {type(chat_state.user_profile)}")
                        chat_state.user_profile = {}
                except Exception as e:
                    print(f"Error parsing user_profile: {e}")
                    chat_state.user_profile = {}
                    
            return chat_state
        except Exception as e:
            print(f"Error in load_chat_state: {e}")
            return None

    def save_chat_state(self):
        try:
            chat_state = self.load_chat_state()
            user_profile_json = json.dumps(self.user_profile) if self.user_profile else '{}'
            
            if not chat_state:
                chat_state = ChatState(
                    user_id=self.user_id,
                    current_phase=self.current_phase,
                    current_question_index=self.current_question_index,
                    user_profile=user_profile_json,
                    completed=self.completed
                )
                self.db.add(chat_state)
            else:
                chat_state.current_phase = self.current_phase
                chat_state.current_question_index = self.current_question_index
                chat_state.user_profile = user_profile_json
                chat_state.completed = self.completed
                chat_state.updated_at = datetime.now()
            
            try:
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                print(f"Error saving chat state: {e}")
                raise
        except Exception as e:
            print(f"Error in save_chat_state: {e}")
            self.db.rollback()
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
            self.save_chat_history(user_id, message, 'user')
            
            if self.completed:
                return {
                    "response": "Your content strategy has already been created. Would you like to create a new one?",
                    "completed": True,
                    "phase": self.current_phase,
                    "schedule": None
                }
            
            result = await (self.process_phase1_message(message, user_id) 
                        if self.current_phase == 1 
                        else self.process_phase2_message(message, user_id))
            
            if result is None:
                result = {
                    "response": "I apologize, but I encountered an unexpected error. Please try again.",
                    "completed": False,
                    "phase": self.current_phase
                }
                
            self.save_chat_history(user_id, result["response"], 'bot')
            
            if result.get("next_message"):
                self.save_chat_history(user_id, result["next_message"], 'bot')
            
            if result.get("completed"):
                self.completed = True
                
            self.save_chat_state()
            return result
                
        except Exception as e:
            print(f"Error processing message: {e}")
            return {
                "response": "I apologize, but I encountered an unexpected error. Please try again.",
                "completed": False,
                "phase": self.current_phase
            }
        
    def determine_role(self, profile_summary: str) -> str:
        try:
            years_question = "How many years of professional experience do you have?"
            years_response = self.user_profile.get(years_question, "0")
            
            try:
                years = float(''.join(c for c in years_response.split()[0] if c.isdigit() or c == '.'))
            except:
                years = 0
                print(f"Could not parse years from response: {years_response}")
            
            role_prompt = f"""
            Based on this professional's profile, determine if they should be a MENTOR or MENTEE.
            They have {years} years of experience.

            Rules:
            - If less than 5 years experience = MENTEE
            - If 5 or more years experience = MENTOR

            Additional factors to consider only if years are borderline (4-6 years):
            - Leadership or management experience
            - History of mentoring others
            - Strong expertise in specific areas
            - Achievement-focused responses

            Profile Summary:
            {profile_summary}
            Years of Experience: {years}

            Respond with only one word: either 'mentor' or 'mentee'
            """
            
            role_response = self.model.generate_content(role_prompt).text.strip().lower()
            determined_role = role_response if role_response in ['mentor', 'mentee'] else 'mentee'
            
            print(f"Role determination: Years: {years}, Role: {determined_role}")
            return determined_role
            
        except Exception as e:
            print(f"Error determining role: {e}")
            return 'mentee'

    async def process_phase1_message(self, message: str, user_id: str) -> dict:
        try:
            print(f"Phase 1 - Current index: {self.current_question_index}")  # Debug log
            current_question = self.phase1_questions[self.current_question_index]
            question_key = current_question["question"]
            self.user_profile[question_key] = message
            
            self.current_question_index += 1
            print(f"Phase 1 - Incremented index: {self.current_question_index}")  # Debug log
            
            if self.current_question_index >= len(self.phase1_questions):
                print("Phase 1 complete - Transitioning to Phase 2")  # Debug log
                summary_pairs = []
                for q in self.phase1_questions:
                    question = q["question"]
                    answer = self.user_profile.get(question, "")
                    summary_pairs.append(f"{question}: {answer}")
                    
                summary_prompt = (
                    "Create a professional profile summary focused on experience level, "
                    "leadership history, and mentoring potential from these responses:\n" + 
                    "\n".join(summary_pairs)
                )
                
                profile_summary = self.model.generate_content(summary_prompt).text
                role = self.determine_role(profile_summary)
                
                # Reset for phase 2
                self.current_phase = 2
                self.current_question_index = 0
                
                # Prepare first question of phase 2
                first_question = self.phase2_questions[0]
                formatted_question = json.dumps({
                    "number": first_question["number"],
                    "total": len(self.phase2_questions),
                    "text": first_question["question"],
                    "emoji": first_question["emoji"]
                })
                
                # Save state before returning
                self.save_chat_state()
                
                return {
                    "response": (
                        "Thank you for sharing your professional journey. Your growth so far sounds inspiring! "
                        f"You seem to be in an ideal position to be a great {role}. "
                        "I have a few more questions to know more about your style, so that we can build your content with authenticity."
                    ),
                    "next_message": formatted_question,
                    "completed": False,
                    "phase": 2,
                    "role": role,
                    "formatted": True
                }
            else:
                next_question = self.phase1_questions[self.current_question_index]
                formatted_question = json.dumps({
                    "number": next_question["number"],
                    "total": len(self.phase1_questions),
                    "text": next_question["question"],
                    "emoji": next_question["emoji"]
                })
                
                return {
                    "response": formatted_question,
                    "completed": False,
                    "phase": 1,
                    "formatted": True
                }
                        
        except Exception as e:
            print(f"Error in phase 1: {e}")
            return {
                "response": "I apologize, but I encountered an error. Let's continue with our discussion.",
                "completed": False,
                "phase": 1
            }

    async def process_phase2_message(self, message: str, user_id: str) -> dict:
        try:
            print(f"Phase 2 - Current index: {self.current_question_index}")  # Debug log
            
            # Validate current index
            if self.current_question_index >= len(self.phase2_questions):
                print("Phase 2 complete - Generating content")  # Debug log
                try:
                    content_schedule = await self.generate_content_schedule(user_id)
                    if content_schedule:
                        return {
                            "response": "Thank you for sharing all that information! I've created your content schedule based on our discussion.",
                            "completed": True,
                            "phase": 2,
                            "schedule": content_schedule
                        }
                    else:
                        return {
                            "response": "I apologize, but I encountered an issue creating your content schedule. Please try again.",
                            "completed": False,
                            "phase": 2
                        }
                except Exception as e:
                    print(f"Error generating content schedule: {e}")
                    return {
                        "response": "I apologize, but I encountered an error creating your schedule. Please try again.",
                        "completed": False,
                        "phase": 2
                    }

            # Process current question
            current_question = self.phase2_questions[self.current_question_index]
            
            if message.strip():
                self.user_profile[current_question["question"]] = message
                print(f"Phase 2 - Saved answer for question {self.current_question_index}")  # Debug log
                self.current_question_index += 1
                print(f"Phase 2 - Incremented to question index {self.current_question_index}")  # Debug log
                
                # Save state after increment
                self.save_chat_state()

            # Check if we should move to content generation
            if self.current_question_index >= len(self.phase2_questions):
                print("Phase 2 - Moving to content generation")  # Debug log
                try:
                    content_schedule = await self.generate_content_schedule(user_id)
                    if content_schedule:
                        return {
                            "response": "Thank you for sharing all that information! I've created your content schedule based on our discussion.",
                            "completed": True,
                            "phase": 2,
                            "schedule": content_schedule
                        }
                except Exception as e:
                    print(f"Error generating content schedule: {e}")
                    return {
                        "response": "I apologize, but I encountered an error creating your schedule. Please try again.",
                        "completed": False,
                        "phase": 2
                    }
            
            # Get next question
            next_question = self.phase2_questions[self.current_question_index]
            formatted_question = {
                "number": next_question["number"],
                "total": len(self.phase2_questions),
                "text": next_question["question"],
                "emoji": next_question["emoji"]
            }
            
            return {
                "response": json.dumps(formatted_question),
                "completed": False,
                "phase": 2,
                "formatted": True
            }
                
        except Exception as e:
            print(f"Error in phase 2: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")  # Add detailed error logging
            return {
                "response": "I apologize, but I encountered an unexpected error. Please try again.",
                "completed": False,
                "phase": 2
            }
    
    def save_persona_input(self, user_id: str):
        from models import PersonaInputNew
        
        try:
            self.db.rollback()
            
            profession_q = self.phase2_questions[0]["question"]
            current_work_q = self.phase2_questions[1]["question"]
            goal_q = self.phase2_questions[2]["question"]
            audience_q = self.phase2_questions[3]["question"]
            industry_q = self.phase2_questions[4]["question"]
            favorite_posts_q = self.phase2_questions[5]["question"]
            best_posts_q = self.phase2_questions[6]["question"]
            posts_count_q = self.phase2_questions[7]["question"]
            purpose_q = self.phase2_questions[8]["question"]
            timeline_q = self.phase2_questions[9]["question"]
            
            try:
                posts_to_create = int(self.user_profile.get(posts_count_q, '5'))
                timeline = self.user_profile.get(timeline_q, '2 weeks')
            except (ValueError, IndexError):
                posts_to_create = 5
                timeline = '2 weeks'
            
            persona_data = PersonaInputNew(
                user_id=user_id,
                profession=self.user_profile.get(profession_q, ''),
                current_work=self.user_profile.get(current_work_q, ''),
                goal=self.user_profile.get(goal_q, ''),
                journey=self.user_profile.get(audience_q, ''),
                company_size=self.user_profile.get(audience_q, ''),
                industry_target=self.user_profile.get(industry_q, ''),
                target_type=self.user_profile.get(audience_q, ''),
                favorite_posts=self.user_profile.get(favorite_posts_q, ''),
                best_posts=self.user_profile.get(best_posts_q, ''),
                posts_to_create=posts_to_create,
                post_purpose=self.user_profile.get(purpose_q, ''),
                timeline=timeline
            )
            
            self.db.add(persona_data)
            self.db.commit()
            self.db.refresh(persona_data)
            return persona_data.id
            
        except Exception as e:
            self.db.rollback()
            print(f"Error saving persona input: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise
        
    async def generate_content_schedule(self, user_id: str):
        try:
            persona_id = self.save_persona_input(user_id)
            posts_to_create = int(self.user_profile.get(self.phase2_questions[7]["question"], 5))  
            timeline_weeks = int(self.user_profile.get(self.phase2_questions[9]["question"], '2').split()[0])  # Changed index to 9
            
            print(f"Generating {posts_to_create} posts over {timeline_weeks} weeks")
            
            prompt = f"""
            Generate {posts_to_create} LinkedIn posts for a professional content calendar. Each post must follow this exact format:

            [POST START]
            Main content here...
            Hashtags here...
            [POST END]

            Professional Profile:
            - Role: {self.user_profile.get(self.phase2_questions[0]["question"], '')}
            - Company: {self.user_profile.get(self.phase2_questions[1]["question"], '')}
            - Goal: {self.user_profile.get(self.phase2_questions[2]["question"], '')}
            - Target Audience: {self.user_profile.get(self.phase2_questions[6]["question"], '')}
            - Industry: {self.user_profile.get(self.phase2_questions[4]["question"], '')}
            - Purpose: {self.user_profile.get(self.phase2_questions[8]["question"], '')}

            Requirements for each post:
            1. Length: 200-400 characters per post
            2. Include engaging content relevant to the profile
            3. Add 2-3 relevant hashtags at the end
            4. Make each post unique and different
            5. Must use the [POST START] and [POST END] delimiters
            6. Generate exactly {posts_to_create} posts

            Begin generating posts:
            """
            
            response = self.model.generate_content(prompt).text
            print(f"AI Response length: {len(response)}")
            posts = self.parse_generated_posts(response, posts_to_create, timeline_weeks)
            
            valid_posts = {
                str(i): post for i, post in posts.items()
                if len(post["Post_content"].strip()) > 50
            }
            
            if len(valid_posts) < posts_to_create:
                remaining_posts = posts_to_create - len(valid_posts)
                additional_prompt = f"""
                Generate {remaining_posts} more LinkedIn posts following the same format:
                [POST START]
                Content here...
                Hashtags here...
                [POST END]
                """
                additional_response = self.model.generate_content(additional_prompt).text
                additional_posts = self.parse_generated_posts(additional_response, remaining_posts, timeline_weeks)
                
                start_index = len(valid_posts)
                for i, post in additional_posts.items():
                    if len(post["Post_content"].strip()) > 50:
                        valid_posts[str(start_index)] = post
                        start_index += 1
            
            self.save_posts(persona_id, valid_posts)
            
            return {
                "persona_id": persona_id,
                "generated_posts": valid_posts
            }
            
        except Exception as e:
            print(f"Error generating content schedule: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")  # Add detailed error logging
            raise

    def parse_generated_posts(self, ai_response: str, num_posts: int, timeline_weeks: int) -> dict:
        from datetime import datetime, timedelta
        
        # Parse posts using delimiters
        raw_posts = []
        post_parts = ai_response.split('[POST START]')
        
        for part in post_parts[1:]:  # Skip first empty part
            if '[POST END]' in part:
                content = part.split('[POST END]')[0].strip()
                if content:
                    raw_posts.append(content)
                
        # If no valid posts found, try alternative parsing
        if not raw_posts:
            raw_posts = [post.strip() for post in ai_response.split('\n\n') if post.strip()]
        
        # Validate and clean posts
        valid_posts = []
        for post in raw_posts:
            cleaned_post = post.strip()
            if len(cleaned_post) > 50:  # Minimum content length
                valid_posts.append(cleaned_post)
        
        # Calculate dates
        days_between_posts = max(1, (timeline_weeks * 7) // num_posts)
        start_date = datetime.now()
        
        posts = {}
        for i, content in enumerate(valid_posts[:num_posts]):
            post_date = start_date + timedelta(days=i * days_between_posts)
            posts[str(i)] = {
                "Post_content": content,
                "Post_date": post_date.strftime("%Y-%m-%d")
            }        
        return posts

    def save_posts(self, persona_id: int, posts: dict):
        from models import PostNew
        from datetime import datetime
        
        try:
            self.db.rollback()  
            
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