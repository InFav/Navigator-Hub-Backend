import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

class ChatbotLogic:
    def __init__(self, questions):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("No Google API key found")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        self.questions = questions
        self.current_question_index = 0
        self.user_profile = {}
        self.conversation_history = []
        self.role_assigned = False

    def process_message(self, message: str) -> dict:
        self.conversation_history.append({
            'role': 'user',
            'parts': [message]
        })

        if self.current_question_index < len(self.questions):
            current_question = self.questions[self.current_question_index]
            
            if message.strip():
                self.user_profile[current_question] = message
                self.current_question_index += 1

            try:
                prompt = (
                    f"You are a professional career advisor having a conversation. "
                    f"Previous question was: {current_question}. "
                    f"User response: {message}. "
                    f"Provide a thoughtful, encouraging response and naturally lead into "
                    f"the next question if there is one. Keep the response conversational and friendly."
                )
                
                response = self.model.generate_content(prompt).text

                # Get next question if available
                next_question = self.get_next_question()
                if next_question:
                    response = f"{response}\n\n{next_question}"

                return {
                    "response": response,
                    "role": None
                }

            except Exception as e:
                print(f"Error generating response: {e}")
                fallback_response = f"Thank you for sharing. {self.get_next_question() or 'Let me analyze your profile.'}"
                return {
                    "response": fallback_response,
                    "role": None
                }

        else:
            # Interview is complete, generate summary and determine role
            try:
                summary_prompt = (
                    "Analyze this professional profile and provide a detailed summary:\n" + 
                    "\n".join([f"{q}: {ans}" for q, ans in self.user_profile.items()])
                )
                
                profile_summary = self.model.generate_content(summary_prompt).text
                role = self.determine_role(profile_summary)
                
                role_response_prompt = f"""
                The user has been identified as a {role}. 
                Generate an encouraging message that:
                1. Thanks them for sharing their journey
                2. Briefly mentions why they'd make a great {role}
                3. Explains the next steps in the matching process
                Do not mention the profile summary or analysis process.
                Keep the response under 150 words.
                """
                
                final_response = self.model.generate_content(role_response_prompt).text
                
                return {
                    "response": final_response,
                    "role": role
                }

            except Exception as e:
                print(f"Error in final response: {e}")
                return {
                    "response": "Thank you for sharing your professional journey. I'll help connect you with the right opportunity.",
                    "role": "mentee"
                }

    def determine_role(self, profile_summary: str) -> str:
        try:
            role_prompt = """
            Based on this professional profile summary, determine if this person should be a MENTOR or MENTEE.
            Consider:
            - Years of experience
            - Leadership positions
            - Expertise level
            - Career stage
            - Teaching/mentoring experience

            Profile Summary:
            {profile_summary}

            Respond with only one word: either 'mentor' or 'mentee'
            """.format(profile_summary=profile_summary)
            
            role_response = self.model.generate_content(role_prompt).text.strip().lower()
            return role_response if role_response in ['mentor', 'mentee'] else 'mentee'
        except Exception as e:
            print(f"Error determining role: {e}")
            return 'mentee'

    def get_next_question(self):
        return (
            self.questions[self.current_question_index]
            if self.current_question_index < len(self.questions)
            else None
        )