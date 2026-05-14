import asyncio
from playwright.async_api import async_playwright
from database import db_client
import google.generativeai as genai
import os

async def fill_form(url, user_cv):
    """
    Automates form filling using a persistent LinkedIn session.
    """
    async with async_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), ".linkedin_session")
        
        # Use persistent context to reuse the session from login.py
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Keeping it visible so user can supervise
            slow_mo=500
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url)
        
        # 1. Identify fields
        inputs = await page.query_selector_all("input, textarea, select")
        for field in inputs:
            label = await page.evaluate("(el) => el.labels[0]?.innerText || el.placeholder || el.name", field)
            
            # 2. Check FAQ first
            stored_answer = db_client.get_faq(label)
            if stored_answer:
                await field.fill(stored_answer)
                continue
            
            # 3. Ask Gemini to map from CV
            answer = await ask_gemini_to_map(label, user_cv)
            if answer and answer != "UNKNOWN":
                await field.fill(answer)
            else:
                # 4. Trigger Telegram Q&A (Simulated here)
                print(f"Field '{label}' unknown. Waiting for user input via Telegram...")
                # In actual implementation, this would pause and wait for a bot event
        
        print("Form filled as much as possible. Review and submit.")
        await asyncio.sleep(10) # Give user time to see
        await context.close()

async def ask_gemini_to_map(field_label, cv_text):
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = f"Based on this CV: {cv_text}\nWhat is the value for the field labeled '{field_label}'? If not found, respond strictly with 'UNKNOWN'."
    response = await model.generate_content_async(prompt)
    return response.text.strip()
