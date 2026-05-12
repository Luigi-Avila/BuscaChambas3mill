import os
import google.generativeai as genai
from dotenv import load_dotenv
import json

load_dotenv()

LUIS_PROFILE = """
Luis Angel Avila Flores - Senior Android Engineer
- 7 years of hands-on Android development (6 years Kotlin, 1 year Java).
- Expert in: Jetpack Compose, MVVM, MVI, Clean Architecture, Hilt, Dagger, Coroutines.
- Experience at major companies like Walmart (current) and Wells Fargo.
- Background in high-scale apps (70M+ customers), banking, retail, and security (NFC/QR).
- Skilled in UI migration (XML to Compose), performance optimization (KSP), and CI/CD.
- Educational Background: Bachelor's in Computer Systems Engineering.
"""

def evaluate_vacancy_pro(job_data: dict):
    """
    Advanced evaluation using Gemini 1.5 Pro (or latest available).
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found.")
    
    genai.configure(api_key=api_key)
    # Using gemini-flash-latest as it was confirmed working and stable in 2026
    model = genai.GenerativeModel('gemini-flash-latest')
    
    description = job_data.get('description', 'No description available.')
    title = job_data.get('title', 'N/A')
    
    prompt = f"""
    You are an expert technical recruiter matching jobs for Luis, a Senior Android Engineer.
    
    Luis's Profile:
    {LUIS_PROFILE}
    
    Job to evaluate:
    Title: {title}
    Description: {description}
    
    Instructions:
    1. Analyze if this job is a match (match_score 0-10).
    2. Identify why it might not be a perfect match (reason_no_match).
    3. Estimate salary if mentioned (salary).
    4. Create a 'study_plan' with:
       - 'links': Real Android documentation or high-quality tutorial links for missing skills.
       - 'exercises': Practical coding exercises to prepare for the interview.
    
    Respond STRICTLY in JSON format:
    {{
        "match_score": integer,
        "worth_applying": boolean,
        "reason_no_match": "string",
        "salary": "string or 'Not specified'",
        "study_plan": {{
            "links": ["url1", "url2"],
            "exercises": ["exercise1", "exercise2"]
        }}
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(content)
        return analysis
    except Exception as e:
        print(f"Brain Pro Error: {e}")
        return {
            "match_score": 0,
            "worth_applying": False,
            "reason_no_match": f"Error: {str(e)}",
            "salary": "N/A",
            "study_plan": {"links": [], "exercises": []}
        }
