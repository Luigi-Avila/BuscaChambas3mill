import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import requests
import time
from logger_config import logger

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

HECTOR_PROFILE = """
Hector Alonzo Romero - Technical Leader & Scrum Master
- 11 years of experience in IT, specializing in banking and large-scale mobile applications.
- Certifications: SMAC (Scrum Master Accredited), SPOAC (Scrum Product Owner Accredited), STMAC (Scrum Team Member Accredited).
- Education: MS in IT Project Management (in progress), MBA (in progress), Computer Systems Engineering (IPN).
- Experience: Mobile Systems Analyst (Scrum Master) at Walmart (1 year), Technical Leader at US Bank (7 years), Digital Channels Team Leader at Gentera.
- Work Authorization: Green Card holder (No visa sponsorship required). CANNOT apply to jobs requiring US Citizenship.
- Current Compensation: 150k USD/year. Looking for competitive salaries (>150k).
- Preferred Work Mode: 100% REMOTE ONLY.
- Strategy: Suitable for Overemployment (OE) - looking for roles with clear objectives and manageable meeting schedules.
- Application Preference: Prefers 'Easy Apply' or streamlined processes.
- Languages: Fluent in English and Spanish.
"""

def evaluate_with_ollama(prompt: str):
    """
    Calls local Ollama API with retry logic.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Ollama attempt {attempt}/{max_retries} for model {model}...")
            response = requests.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json"
                },
                timeout=None # Wait indefinitely for the local LLM
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "").strip()
        except requests.exceptions.Timeout:
            logger.warning(f"Ollama Timeout (Attempt {attempt}/{max_retries}).")
        except Exception as e:
            logger.error(f"Ollama Error (Attempt {attempt}/{max_retries}): {e}")
        
        if attempt < max_retries:
            time.sleep(2) # Short wait before retry
            
    logger.error("All Ollama attempts failed. Falling back to Gemini.")
    return None

def evaluate_with_gemini(prompt: str):
    """
    Calls Gemini API.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return None

def evaluate_vacancy_pro(job_data: dict, profile_name: str = "luis"):
    """
    Advanced evaluation using either Ollama or Gemini for a SPECIFIC profile.
    """
    start_time = time.time()
    description = job_data.get('description', 'No description available.')
    title = job_data.get('title', 'N/A')
    
    # Select the profile based on the argument
    if profile_name.lower() == "hector":
        selected_profile = HECTOR_PROFILE
        target_name = "Hector (Scrum Master/Lead)"
        constraints_prompt = """
        EXTRA CONSTRAINTS for Hector:
        1. MUST BE 100% REMOTE. If it is hybrid or on-site, match_score = 0 and worth_applying = false.
        2. NO CITIZENSHIP REQUIRED. If the job explicitly requires 'US Citizenship' (due to security clearance), match_score = 0. Green Card is fine.
        3. SALARY COMPETITIVE. He makes 150k. If the estimated salary is < 150k, mark as low match.
        4. OE SUITABILITY: Analyze if the role seems high-pressure or meeting-heavy vs objective-based.
        """
    else:
        selected_profile = LUIS_PROFILE
        target_name = "Luis (Android Engineer)"
        constraints_prompt = ""

    # Add profile-specific instructions for the LLM
    if profile_name.lower() == "hector":
        extra_instructions = "3. OE SUITABILITY: Analyze if the role seems high-pressure or meeting-heavy vs objective-based."
        oe_schema = '"oe_analysis": "brief analysis of suitability for overemployment",'
    else:
        extra_instructions = ""
        oe_schema = ""

    job_to_eval = f"""
    Title: {title}
    Source: {job_data.get('source', 'N/A')}
    Application Type: {job_data.get('apply_type', 'N/A')}
    Description: {description}
    """

    prompt = f"""
    You are an expert technical recruiter matching jobs for {target_name}.
    
    Candidate Profile:
    {selected_profile}
    
    {constraints_prompt}
    
    Job to evaluate:
    {job_to_eval}
    
    Instructions:
    1. Analyze if this job matches {profile_name.capitalize()} (match_score 0-10) based on all constraints.
    2. Identify why it might not be a perfect match (reason_no_match).
    {extra_instructions}
    4. Create a 'study_plan' with:
       - 'links': Real Android documentation or high-quality tutorial links for missing skills.
       - 'exercises': Practical coding exercises to prepare for the interview.
    5. Respond STRICTLY in JSON format.
    
    JSON Schema:
    {{
        "match_score": integer,
        "worth_applying": boolean,
        "reason_no_match": "string explaining why or highlighting gaps",
        "salary": "string or 'Not specified'",
        {oe_schema}
        "study_plan": {{
            "links": ["url1", "url2"],
            "exercises": ["exercise1", "exercise2"]
        }}
    }}
    """
    
    content = None
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    if use_ollama:
        logger.info(f"Using Ollama ({os.getenv('OLLAMA_MODEL', 'qwen3:14b')}) for {profile_name}...")
        content = evaluate_with_ollama(prompt)
    
    if not content:
        logger.info(f"Using Gemini for {profile_name}...")
        content = evaluate_with_gemini(prompt)
        
    if not content:
        return {
            "match_score": 0,
            "worth_applying": False,
            "reason_no_match": "Error: No response from LLM",
            "salary": "N/A",
            "study_plan": {"links": [], "exercises": []},
            "response_time": round(time.time() - start_time, 2),
            "profile": profile_name
        }

    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(content)
        analysis["response_time"] = round(time.time() - start_time, 2)
        analysis["profile"] = profile_name
        return analysis
    except Exception as e:
        logger.error(f"Parse Error: {e}\nContent: {content}")
        return {
            "match_score": 0,
            "worth_applying": False,
            "reason_no_match": f"Parse Error: {str(e)}",
            "salary": "N/A",
            "study_plan": {"links": [], "exercises": []},
            "response_time": round(time.time() - start_time, 2),
            "profile": profile_name
        }
