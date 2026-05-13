import os
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from database import db_client
import asyncio
from logger_config import logger

load_dotenv()

class CareerBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        # Support multiple IDs: LUIST_ID and HECTOR_ID
        self.luis_chat_id = os.getenv("TELEGRAM_CHAT_ID") # Primary/Luis
        self.hector_chat_id = "2111751929" # Specific ID for Hector
        self.url = f"https://api.telegram.org/bot{self.token}/"

    def send_report(self, vacancies):
        """Sends reports to the appropriate user based on the profile."""
        use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
        model_name = os.getenv("OLLAMA_MODEL", "qwen3:14b") if use_ollama else "Gemini Flash"
        
        # Group vacancies by profile to send separate reports
        luis_jobs = [v for v in vacancies if v['evaluation'].get('profile', 'luis').lower() == "luis"]
        hector_jobs = [v for v in vacancies if v['evaluation'].get('profile', '').lower() == "hector"]

        if luis_jobs:
            self._send_profile_report(luis_jobs, self.luis_chat_id, "Luis", model_name)
        
        if hector_jobs:
            self._send_profile_report(hector_jobs, self.hector_chat_id, "Hector", model_name)

    def _send_profile_report(self, vacancies, chat_id, name, model_name):
        header = f"<b>🌅 Reporte Diario de Carrera - {name}</b>\n"
        header += f"🤖 Inteligencia: {model_name}\n\n"
        
        current_message = header
        for v in vacancies:
            status = "✅" if v['evaluation']['worth_applying'] else "❌"
            resp_time = v['evaluation'].get('response_time', 'N/A')
            
            job_entry = f"{status} <b>{v['title']}</b> ({v['company']})\n"
            job_entry += f"Score: {v['evaluation']['match_score']}/10 | ⏱ {resp_time}s\n"
            
            # Show OE only for Hector
            if v['evaluation'].get('profile', 'luis').lower() == "hector":
                oe = v['evaluation'].get('oe_analysis', 'N/A')
                job_entry += f"💡 OE: {oe}\n"
            
            # Reason for match/no match
            reason = v['evaluation'].get('reason_no_match', 'N/A')
            job_entry += f"📝 <b>Motivo:</b> {reason}\n"

            # Study Plan / Skills
            study_plan = v['evaluation'].get('study_plan', {})
            links = study_plan.get('links', [])
            exercises = study_plan.get('exercises', [])
            
            if links or exercises:
                job_entry += "📚 <b>Para estudiar:</b>\n"
                if links:
                    job_entry += "  🔗 " + ", ".join([f"<a href='{l}'>Link</a>" for l in links]) + "\n"
                if exercises:
                    job_entry += "  ✍️ " + "; ".join(exercises[:2]) + "\n" # Show first 2 exercises

            job_entry += f"🔗 <a href='{v['link']}'>Ver Vacante</a>\n\n"
            
            # Telegram has a 4096 character limit per message
            if len(current_message) + len(job_entry) > 4000:
                self._send_msg(current_message, chat_id)
                current_message = job_entry
            else:
                current_message += job_entry
        
        if current_message:
            self._send_msg(current_message, chat_id)

    def _send_msg(self, text, chat_id=None):
        target_id = chat_id or self.luis_chat_id
        payload = {
            "chat_id": target_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            response = requests.post(self.url + "sendMessage", json=payload)
            if not response.ok:
                logger.error(f"Telegram API Error for {target_id}: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Failed to send message to {target_id}: {e}")

    def notify_error(self, context, error):
        """Notifies the user about an error via Telegram."""
        message = f"⚠️ <b>Error en el Agente</b>\n\n<b>Contexto:</b> {context}\n<b>Error:</b> <code>{str(error)}</code>"
        self._send_msg(message)

    async def listen_for_commands(self):
        """Polls for new messages/commands from Telegram."""
        offset = 0
        logger.info("Bot command listener active. Use /status in Telegram.")
        while True:
            try:
                response = requests.get(self.url + f"getUpdates?offset={offset}&timeout=10")
                updates = response.json().get('result', [])
                for update in updates:
                    offset = update['update_id'] + 1
                    message = update.get('message', {})
                    text = message.get('text', '')
                    chat_id = str(message.get('chat', {}).get('id', ''))
                    
                    # Verify if the user is authorized
                    if chat_id not in [self.luis_chat_id, self.hector_chat_id]:
                        continue

                    if text.startswith("/status"):
                        from datetime import datetime
                        now = datetime.now().strftime("%H:%M:%S")
                        use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
                        model_info = f"Ollama ({os.getenv('OLLAMA_MODEL', 'qwen3:14b')})" if use_ollama else "Gemini Flash"
                        profile = "Luis" if chat_id == self.luis_chat_id else "Hector"
                        
                        self._send_msg(
                            f"🤖 <b>Status: ACTIVO ({profile})</b>\n"
                            f"🧠 Modelo: {model_info}\n"
                            f"⏰ Hora actual: {now}\n"
                            f"📅 Próximo escaneo: 02:00 AM\n"
                            f"📊 Reporte diario: 08:30 AM",
                            chat_id
                        )
                    
                    elif text.startswith("/run"):
                        # If Hector sends /run, default to his profile
                        default_profile = "luis" if chat_id == self.luis_chat_id else "hector"
                        parts = text.split()
                        profile = parts[1].lower() if len(parts) > 1 else default_profile
                        
                        if profile not in ["luis", "hector"]:
                            self._send_msg("⚠️ Perfil no válido. Usa <code>/run luis</code> o <code>/run hector</code>.", chat_id)
                            continue
                            
                        self._send_msg(f"🚀 Iniciando búsqueda manual para <b>{profile.capitalize()}</b>...", chat_id)
                        asyncio.create_task(do_manual_run(profile))
                        
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Bot Listener Error: {e}")
                await asyncio.sleep(5)

async def do_manual_run(profile):
    await do_scrape(profile)
    await do_report()

async def do_scrape(profile="luis"):
    """Triggered to scrape and analyze jobs for a specific profile."""
    from scraper import run_pro_scraper
    from brain import evaluate_vacancy_pro
    bot = CareerBot()
    
    # Define keywords based on profile
    keywords = "Android Developer" if profile == "luis" else "Scrum Master"
    
    try:
        logger.info(f"--- Starting Scrape for {profile} ({keywords}) ---")
        new_jobs = await run_pro_scraper(keywords, "California")
        
        evaluated_count = 0
        for job in new_jobs:
            logger.info(f"Analyzing for {profile}: {job['title']}...")
            analysis = evaluate_vacancy_pro(job, profile_name=profile)
            job['evaluation'] = analysis
            db_client.save_vacancy(job)
            evaluated_count += 1
            await asyncio.sleep(2) # Quota safety
        
        logger.info(f"Scrape completed for {profile}. {evaluated_count} jobs analyzed.")
    except Exception as e:
        logger.error(f"Error during scrape ({profile}): {e}")
        bot.notify_error(f"Escaneo ({profile})", e)

async def do_report():
    """Triggered at 8:30 AM to send the Telegram report."""
    bot = CareerBot()
    try:
        logger.info("--- Starting Scheduled Report (8:30 AM) ---")
        # Get jobs from the last 10 hours (covers since 2 AM scrape)
        recent_jobs = db_client.get_recent_vacancies(hours=10)
        
        if recent_jobs:
            bot.send_report(recent_jobs)
            logger.info(f"Report sent with {len(recent_jobs)} jobs.")
        else:
            bot._send_msg("📭 No se encontraron nuevas vacantes en el escaneo de hoy.")
            logger.info("No new jobs to report.")
    except Exception as e:
        logger.error(f"Error during report generation: {e}")
        bot.notify_error("Generación de Reporte (8:30 AM)", e)

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="America/Los_Angeles")
    
    # Default scheduled scrape for Luis
    scheduler.add_job(do_scrape, 'cron', hour=2, args=["luis"], misfire_grace_time=21600)
    
    # Report at 8:30 AM
    scheduler.add_job(do_report, 'cron', hour=8, minute=30, misfire_grace_time=10800)
    
    scheduler.start()
    logger.info("Scheduler active: Scrape at 2:00 AM (Luis), Report at 8:30 AM (PST).")
