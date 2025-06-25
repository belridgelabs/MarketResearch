import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LinkedinProfileAgent:
    def __init__(self, profile_text_path: str, name: str = None, agency: str = None):
        self.profile_text_path = profile_text_path
        self.name = name
        self.agency = agency
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


    def process_profile(self) -> str:
        try:
            with open(self.profile_text_path, 'r', encoding='utf-8') as f:
                profile_content = f.read()
            
            # Create context-aware prompt
            context_info = ""
            if self.name and self.agency:
                context_info = f" for {self.name} from {self.agency}"
            elif self.name:
                context_info = f" for {self.name}"
            
            # prompt = f"""This is {self.name}'s LinkedIn Profile. We want to know hyper-specific, key knowledge that would help us design a sales approach.
            # This should be immersive. Not a summary, but a commentary. However, organize it in a way that serves as a primer into the person and how we can approach them. This should be relatively short.
            # ***Include a few key potential conversation starter questions based on {self.name}'s experience and interests.
            # What technologies can we talk about? What experiences? What should we know about {self.name} that will give us a competitive advantage in the marketplace? Be HYPER SPECIFIC when suggesting an approach and do not generalize.
            # \n\n{profile_content}"""
            
            prompt = f"""
            This is {self.name}'s LinkedIn profile. Your task is to generate a **sales strategy briefing**.

            Don't summarize — analyze. Treat this like a high-stakes pre-call readout. Highlight insights that will **shape how we approach {self.name}** as a potential buyer, champion, or stakeholder. Focus on **hyper-specific hooks** — experiences, technologies, roles, or phrases that signal pain points, interests, or strategic priorities.

            Output should be structured and actionable. Include:
            - A brief **persona snapshot** of {self.name} (tone, role, interests, background)
            - **Three conversation starters** tailored to their background
            - **Relevant technologies, methodologies, or tools** to bring up
            - **Strategic insight**: What gives us a unique edge in engaging this person?
            - **Two interesting pieces**: What would most people miss when looking into this person?

            Avoid generic fluff. Think like a seller trying to win a deal. 

            {profile_content}
            """

            response = self.client.chat.completions.create(
                model="gpt-4o", # You can choose a different model if preferred
                messages=[
                    {"role": "system", "content": "You are a strategic sales assistant that analyzes LinkedIn profiles to generate actionable, hyper-specific insights. Your output is in Markdown format, structured to help a founder or seller prepare for a high-impact, personalized conversation. Focus on extracting unique hooks, relevant technologies, and sharp conversation starters based on the person's background. Avoid generic summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500
            )
            llm_summary = response.choices[0].message.content
            
            return f"{llm_summary}\n"
        except FileNotFoundError:
            return f"### LinkedIn Profile Summary\n\nProfile file not found at {self.profile_text_path}\n"
        except Exception as e:
            return f"### LinkedIn Profile Summary\n\nError processing profile: {e}\n"

class LinkedinEndorsementAgent:
    def __init__(self, skills_file_paths: list, name: str = None, agency: str = None):
        self.skills_file_paths = skills_file_paths
        self.name = name
        self.agency = agency
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def process_endorsements(self) -> str:
        all_endorsements = []
        for file_path in self.skills_file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    all_endorsements.extend(f.readlines())
            except FileNotFoundError:
                all_endorsements.append(f"File not found: {file_path}\n")
            except Exception as e:
                all_endorsements.append(f"Error reading {file_path}: {e}\n")

        # Combine all endorsement text
        raw_endorsement_text = ''.join(all_endorsements)
        
        if not raw_endorsement_text.strip():
            return "### LinkedIn Endorsements\n\nNo endorsement data found or processed.\n"

        # Use LLM to extract and analyze endorsement data
        context_info = ""
        if self.name and self.agency:
            context_info = f" for {self.name} from {self.agency}"
        elif self.name:
            context_info = f" for {self.name}"
            
        extraction_prompt = f"""Please analyze the following LinkedIn endorsement text{context_info} and try to link {self.name} to his endorsers
                    The information should contain key names including the most common endorsers, their company names.
                    We're trying to find broad information about {self.name}'s connections.
                    INCLUDE 5 SPECIFIC NAMES of endorsers and Company
                    Raw endorsement text:
                    {raw_endorsement_text}

                    """
        
        extraction_response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing LinkedIn endorsement data. Share specific names, insights, and connections that might be useful to know before a sales call."},
                {"role": "user", "content": extraction_prompt}
            ],
            max_tokens=1500
        )
        
        structured_analysis = extraction_response.choices[0].message.content
        
        prompt = f"Based on the following structured endorsement analysis, create a concise summary highlighting the most important insights for a sales call:\n\n{structured_analysis}"

        response = self.client.chat.completions.create(
            model="gpt-4o", # You can choose a different model if preferred
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes LinkedIn endorsement data."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500
        )
        llm_summary = response.choices[0].message.content

        return f"{llm_summary}\n"