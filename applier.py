import asyncio
import json
from playwright.async_api import async_playwright
from database import db_client
from brain import evaluate_with_ollama, evaluate_with_gemini
import google.generativeai as genai
import os
from shared_state import shared_state
from logger_config import logger
import requests

async def fill_form(url, user_cv, chat_id=None):
    """
    Automates form filling using an AI Advisor loop.
    The agent analyzes the page state and decides the next action.
    """
    async with async_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), ".linkedin_session")
        logger.info(f"Starting AI-Driven application for {url}")
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, 
            slow_mo=1000 
        )
        
        # Increase default timeouts to 60s
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        
        # Track the active page (can change if new tabs open)
        state_container = {"active_page": context.pages[0] if context.pages else await context.new_page()}
        
        try:
            logger.info(f"Navigating to: {url}")
            await state_container["active_page"].goto(url, timeout=90000) 
            await state_container["active_page"].wait_for_load_state("networkidle")
            await asyncio.sleep(5) 

            # AI Advisor Loop
            max_steps = 25 # Increased for complex forms
            for step in range(1, max_steps + 1):
                page = state_container["active_page"]
                logger.info(f"--- AI Advisor Step {step}/{max_steps} ---")
                
                # Ensure the page is ready before capturing state
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(3) 
                
                # 1. Capture Page State
                state = await capture_page_state(page)
                
                # 2. Ask AI for Next Action
                action = await get_ai_decision(state, user_cv)
                logger.info(f"AI Decision: {action['type'].upper()} -> {action.get('reason', '')}")
                
                # 3. Execute Action
                if action['type'] == 'click':
                    await execute_click(state_container, action['selector'], context)
                elif action['type'] == 'fill':
                    await execute_fill(page, action['fields'], chat_id, user_cv)
                elif action['type'] == 'wait':
                    await asyncio.sleep(5)
                elif action['type'] == 'done':
                    logger.info("AI marked the process as COMPLETED.")
                    break
                elif action['type'] == 'fail':
                    logger.error(f"AI marked the process as FAILED: {action.get('reason')}")
                    break
                
                await asyncio.sleep(2) 

        except Exception as e:
            logger.error(f"Critical error in AI Applier: {e}")
            raise e
        finally:
            logger.info("Closing AI Applier context.")
            await context.close()

async def capture_page_state(page):
    """Extracts a text-based summary of relevant interactive elements, prioritizing actions."""
    elements = await page.evaluate('''() => {
        const getSelector = (el) => {
            if (el.id) return `#${el.id}`;
            // Prioritize specific LinkedIn classes
            if (el.classList.contains('jobs-apply-button')) return '.jobs-apply-button';
            if (el.classList.contains('jobs-s-apply')) return '.jobs-s-apply button';
            
            if (el.className && typeof el.className === 'string') {
                const classes = el.className.split(' ').filter(c => c.length > 0).slice(0, 2);
                if (classes.length > 0) return `.${classes.join('.')}`;
            }
            return el.tagName.toLowerCase();
        };

        const items = [];
        // 1. Prioritize Buttons and 'Apply' links
        const actions = document.querySelectorAll('button, a.jobs-apply-button, .jobs-s-apply button, [role="button"]');
        actions.forEach(el => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                const text = el.innerText.trim();
                // Flag primary action buttons
                const isApply = /apply|aplicar|postularse|sencilla/i.test(text);
                const isNext = /next|continuar|sig|siguiente|save/i.test(text);
                
                items.push({
                    type: 'button',
                    text: text.substring(0, 50),
                    selector: getSelector(el),
                    is_priority: isApply || isNext || el.classList.contains('artdeco-button--primary')
                });
            }
        });

        // 2. Form Inputs
        document.querySelectorAll('input, textarea, select').forEach(el => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                items.push({
                    type: 'input',
                    label: (el.labels && el.labels[0]?.innerText) || el.placeholder || el.name || el.id || 'unlabeled',
                    selector: getSelector(el),
                    current_value: el.value
                });
            }
        });
        return items;
    }''')
    
    title = await page.title()
    elements.sort(key=lambda x: x.get('is_priority', False), reverse=True)
    return {"title": title, "elements": elements[:50]} 

async def get_ai_decision(state, user_cv):
    """Calls AI to decide the next step. Strongly prioritizes 'Apply' action."""
    
    prompt = f"""
    You are an Automated Job Applier Advisor.
    Goal: Navigate to the application form and fill it.
    
    CURRENT SITUATION:
    Page Title: {state['title']}
    Elements Found: {state['elements']}
    
    CRITICAL INSTRUCTIONS:
    1. NAVIGATION FIRST: If you see an 'Apply', 'Easy Apply', or 'Solicitud Sencilla' button, you MUST CLICK IT FIRST. 
       Do NOT try to fill any form fields if a main Apply button is visible on the page.
    2. MODALS/STEPS: If you are already in a form, fill the fields. If you see 'Next', 'Continue', or 'Review', click them after filling.
    3. FINISHING: If you see 'Submit' or 'Apply' (inside a modal), click it to finish.
    4. DATA: Use the User CV Context for info. If info is missing, use 'ASK_USER'.
    
    User CV Context: {user_cv}
    
    Respond ONLY in JSON format:
    {{
        "type": "click" | "fill" | "wait" | "done" | "fail",
        "selector": "exact_selector_from_elements_list",
        "fields": {{"selector": "value"}},
        "reason": "short explanation"
    }}
    """
    
    content = None
    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    if use_ollama:
        logger.info("Decision Phase: Consulting Ollama...")
        content = await asyncio.to_thread(evaluate_with_ollama, prompt)
    
    if not content:
        logger.info("Decision Phase: Consulting Gemini...")
        content = await asyncio.to_thread(evaluate_with_gemini, prompt)
        
    if not content:
        return {"type": "wait", "reason": "AI did not respond."}

    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return json.loads(content)
    except Exception as e:
        logger.error(f"AI Decision Error: {e}")
        return {"type": "wait", "reason": "Format error in AI response."}

async def execute_click(state_container, selector, context):
    page = state_container["active_page"]
    try:
        logger.info(f"ACTION: Clicking {selector}")
        await page.hover(selector)
        
        async with context.expect_page(timeout=10000) as new_page_info:
            await page.click(selector, timeout=10000)
            
        new_page = await new_page_info.value
        logger.info("SUCCESS: New tab detected. Switching control.")
        await new_page.wait_for_load_state()
        state_container["active_page"] = new_page
    except Exception as e:
        logger.info(f"Click executed on same page/modal.")
        await page.wait_for_load_state("networkidle")

async def execute_fill(page, fields, chat_id, user_cv):
    for selector, value in fields.items():
        try:
            if value == "ASK_USER" and chat_id:
                label = await page.evaluate("(sel) => { \
                    const el = document.querySelector(sel); \
                    return el?.labels[0]?.innerText || el?.placeholder || el?.name || 'unknown field'; \
                }", selector)
                
                logger.info(f"Field '{label}' requires user input. Pausing...")
                send_telegram_question(chat_id, label)
                user_answer = await shared_state.ask_user(chat_id, label)
                if user_answer:
                    await page.fill(selector, user_answer)
                    db_client.save_faq(label, user_answer)
            else:
                logger.info(f"Filling {selector}")
                await page.fill(selector, value)
        except Exception as e:
            logger.warning(f"Failed to fill {selector}: {e}")

def send_telegram_question(chat_id, label):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    text = f"❓ <b>Pregunta desconocida en el formulario:</b>\n\n<code>{label}</code>\n\nResponde a este mensaje con la información necesaria para continuar."
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending question to Telegram: {e}")

async def ask_gemini_to_map(field_label, cv_text):
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = f"Based on this CV: {cv_text}\nWhat is the value for the field labeled '{field_label}'? If not found, respond strictly with 'UNKNOWN'."
    response = await model.generate_content_async(prompt)
    return response.text.strip()
