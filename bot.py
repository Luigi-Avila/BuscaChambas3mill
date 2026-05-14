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

        # Fetch pending high-match jobs that weren't in this specific scan
        luis_pending = db_client.get_pending_high_match_vacancies(profile="luis", limit=5)
        hector_pending = db_client.get_pending_high_match_vacancies(profile="hector", limit=5)

        if luis_jobs or luis_pending:
            self._send_profile_report(luis_jobs, self.luis_chat_id, "Luis", model_name, pending_vacancies=luis_pending)
        
        if hector_jobs or hector_pending:
            self._send_profile_report(hector_jobs, self.hector_chat_id, "Hector", model_name, pending_vacancies=hector_pending)

    def _send_profile_report(self, vacancies, chat_id, name, model_name, pending_vacancies=None):
        header = f"<b>🌅 Reporte Diario de Carrera - {name}</b>\n"
        header += f"🤖 Inteligencia: {model_name}\n\n"
        self._send_msg(header, chat_id)
        
        # Split between high match and low match
        worth_applying_jobs = [v for v in vacancies if v['evaluation']['worth_applying']]
        other_jobs = [v for v in vacancies if not v['evaluation']['worth_applying']]

        # 1. Send High-Match Jobs with Buttons
        if worth_applying_jobs:
            self._send_msg("<b>🔥 Nuevas vacantes con Alto Match:</b>", chat_id)
            for v in worth_applying_jobs:
                self._send_job_with_buttons(v, chat_id)

        # 2. Send Pending High-Match Jobs (from previous scans)
        if pending_vacancies:
            # Filter out jobs that are already in the "worth_applying_jobs" list to avoid duplicates
            current_links = {v['link'] for v in worth_applying_jobs}
            real_pending = [v for v in pending_vacancies if v['link'] not in current_links]
            
            if real_pending:
                self._send_msg("<b>⏳ Recordatorio: Vacantes pendientes de aplicar:</b>", chat_id)
                for v in real_pending:
                    self._send_job_with_buttons(v, chat_id)

        # 3. Send Summary for Low-Match Jobs
        if other_jobs:
            summary_header = "<b>❌ Otras vacantes analizadas (Bajo Match):</b>\n\n"
            current_message = summary_header
            for v in other_jobs:
                job_line = f"• {v['title']} ({v['company']}) - Score: {v['evaluation']['match_score']}/10\n"
                if len(current_message) + len(job_line) > 4000:
                    self._send_msg(current_message, chat_id)
                    current_message = job_line
                else:
                    current_message += job_line
            
            if current_message:
                self._send_msg(current_message, chat_id)

    def _send_job_with_buttons(self, v, chat_id):
        """Helper to send a single job entry with its action buttons."""
        resp_time = v['evaluation'].get('response_time', 'N/A')
        source = v.get('source', 'LinkedIn')
        apply_type = v.get('apply_type', 'External')
        apply_emoji = "⚡️" if apply_type == "Easy Apply" else "📝"
        
        job_entry = f"✅ <b>{v['title']}</b>\n"
        job_entry += f"🏢 {v['company']}\n"
        job_entry += f"📍 {source} | {apply_emoji} {apply_type}\n"
        job_entry += f"Score: {v['evaluation']['match_score']}/10 | ⏱ {resp_time}s\n"
        
        if v['evaluation'].get('profile', 'luis').lower() == "hector":
            oe = v['evaluation'].get('oe_analysis', 'N/A')
            job_entry += f"💡 OE: {oe}\n"
        
        reason = v['evaluation'].get('reason_no_match', 'N/A')
        job_entry += f"📝 <b>Motivo:</b> {reason}\n"

        study_plan = v['evaluation'].get('study_plan', {})
        links = study_plan.get('links', [])
        exercises = study_plan.get('exercises', [])
        
        if links or exercises:
            job_entry += "📚 <b>Para estudiar:</b>\n"
            if links:
                job_entry += "  🔗 " + ", ".join([f"<a href='{l}'>Link</a>" for l in links]) + "\n"
            if exercises:
                job_entry += "  ✍️ " + "; ".join(exercises[:2]) + "\n"

        # Buttons for the link and automatic apply
        buttons = [
            {"text": f"🚀 Ver en {source}", "url": v['link']}
        ]
        
        if apply_type == "Easy Apply":
            import hashlib
            job_id = hashlib.md5(v['link'].encode()).hexdigest()
            buttons.append({"text": "⚡️ Aplicar Autom.", "callback_data": f"apply_{job_id}"})

        reply_markup = {
            "inline_keyboard": [buttons]
        }
        self._send_msg(job_entry, chat_id, reply_markup=reply_markup)

    def _send_msg(self, text, chat_id=None, reply_markup=None):
        target_id = chat_id or self.luis_chat_id
        payload = {
            "chat_id": target_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
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
        # Initial call to skip pending updates from before the bot started
        offset = 0
        try:
            response = requests.get(self.url + "getUpdates?offset=-1&timeout=0")
            updates = response.json().get('result', [])
            if updates:
                offset = updates[-1]['update_id'] + 1
                logger.info("Skipped old Telegram messages.")
        except Exception as e:
            logger.error(f"Error skipping updates: {e}")

        logger.info("Bot command listener active. Use /status in Telegram.")
        while True:
            try:
                response = requests.get(self.url + f"getUpdates?offset={offset}&timeout=10")
                updates = response.json().get('result', [])
                for update in updates:
                    offset = update['update_id'] + 1
                    
                    # Handle Callback Queries (Button Clicks)
                    if 'callback_query' in update:
                        cb = update['callback_query']
                        data = cb.get('data', '')
                        chat_id = str(cb.get('message', {}).get('chat', {}).get('id', ''))
                        cb_id = cb.get('id')
                        
                        if data.startswith("apply_"):
                            job_doc_id = data.replace("apply_", "")
                            # Acknowledge the callback immediately
                            requests.post(self.url + "answerCallbackQuery", json={"callback_query_id": cb_id, "text": "Iniciando aplicación automática..."})
                            
                            # Retrieve job details from DB
                            job = db_client.get_vacancy_by_id(job_doc_id)
                            if job:
                                self._send_msg(f"🤖 Iniciando aplicación para: <b>{job['title']}</b> en {job['company']}...", chat_id)
                                # Trigger background application task
                                asyncio.create_task(run_auto_apply(job, job_doc_id, chat_id))
                            else:
                                self._send_msg("⚠️ No se encontró la información de la vacante para aplicar.", chat_id)
                        continue

                    message = update.get('message', {})
                    text = message.get('text', '')
                    chat_id = str(message.get('chat', {}).get('id', ''))
                    
                    # Verify if the user is authorized
                    if chat_id not in [self.luis_chat_id, self.hector_chat_id]:
                        continue

                    if text.startswith("/status"):
                        from datetime import datetime
                        import socket
                        now = datetime.now().strftime("%H:%M:%S")
                        use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
                        model_info = f"Ollama ({os.getenv('OLLAMA_MODEL', 'qwen3:14b')})" if use_ollama else "Gemini Flash"
                        profile = "Luis" if chat_id == self.luis_chat_id else "Hector"
                        hostname = socket.gethostname()
                        pid = os.getpid()
                        
                        self._send_msg(
                            f"🤖 <b>Status: ACTIVO ({profile})</b>\n"
                            f"💻 Host: <code>{hostname}</code> (PID: {pid})\n"
                            f"🧠 Modelo: {model_info}\n"
                            f"⏰ Hora actual: {now}\n"
                            f"📅 Próximo escaneo: 02:00 AM\n"
                            f"📊 Reporte diario: 08:30 AM",
                            chat_id
                        )
                    
                    elif text.startswith("/help"):
                        help_text = (
                            "📖 <b>Guía de Comandos del Agente</b>\n\n"
                            "ℹ️ /status - Muestra el estado actual, el host y el modelo de IA.\n"
                            "🚀 /run [perfil] - Ejecuta una búsqueda manual. Ejemplo: <code>/run luis</code> o <code>/run hector</code>.\n"
                            "⏳ /pending [perfil] - Muestra vacantes de alto match pendientes de aplicar.\n"
                            "🛑 /stop - Apaga el agente en la máquina que responde.\n"
                            "❓ /help - Muestra esta lista de comandos."
                        )
                        self._send_msg(help_text, chat_id)
                    
                    elif text.startswith("/pending"):
                        default_profile = "luis" if chat_id == self.luis_chat_id else "hector"
                        parts = text.split()
                        profile = parts[1].lower() if len(parts) > 1 else default_profile
                        
                        if profile not in ["luis", "hector"]:
                            self._send_msg("⚠️ Perfil no válido. Usa <code>/pending luis</code> o <code>/pending hector</code>.", chat_id)
                            continue

                        self._send_msg(f"⏳ Buscando vacantes pendientes para <b>{profile.capitalize()}</b>...", chat_id)
                        pending = db_client.get_pending_high_match_vacancies(profile=profile, limit=10)
                        
                        if pending:
                            for v in pending:
                                self._send_job_with_buttons(v, chat_id)
                        else:
                            self._send_msg(f"✅ No tienes vacantes pendientes de alto match para el perfil <b>{profile.capitalize()}</b>.", chat_id)
                    
                    elif text.startswith("/stop"):
                        import socket
                        hostname = socket.gethostname()
                        self._send_msg(f"🛑 <b>Apagando agente</b> en <code>{hostname}</code> por comando remoto...", chat_id)
                        logger.warning(f"Remote shutdown triggered via Telegram from chat_id: {chat_id}")
                        await asyncio.sleep(1) # Give time to send message
                        os._exit(0) # Immediate exit
                    
                    elif text.startswith("/run"):
                        # If Hector sends /run, default to his profile
                        default_profile = "luis" if chat_id == self.luis_chat_id else "hector"
                        parts = text.split()
                        profile = parts[1].lower() if len(parts) > 1 else default_profile
                        
                        if profile not in ["luis", "hector"]:
                            self._send_msg("⚠️ Perfil no válido. Usa <code>/run luis</code> o <code>/run hector</code>.", chat_id)
                            continue
                            
                        self._send_msg(f"🚀 Iniciando búsqueda manual para <b>{profile.capitalize()}</b>...", chat_id)
                        asyncio.create_task(do_manual_run(profile, initiator_id=chat_id))
                        
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Bot Listener Error: {e}")
                await asyncio.sleep(5)

async def do_manual_run(profile, initiator_id=None):
    await do_scrape(profile)
    await do_report(initiator_id=initiator_id)

async def do_scrape(profile="luis"):
    """Triggered to scrape and analyze jobs for a specific profile."""
    from scraper import run_pro_scraper
    from brain import evaluate_vacancy_pro
    bot = CareerBot()
    
    # Define keywords based on profile
    keywords = "Android Developer" if profile == "luis" else "Scrum Master"
    filter_easy = (profile == "hector")
    
    try:
        logger.info(f"--- Starting Scrape for {profile} ({keywords}) ---")
        new_jobs = await run_pro_scraper(keywords, "California", filter_easy_apply=filter_easy)
        
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

async def do_report(initiator_id=None):
    """Triggered at 8:30 AM to send the Telegram report."""
    bot = CareerBot()
    try:
        logger.info("--- Starting Scheduled Report ---")
        # Get jobs from the last 10 hours
        recent_jobs = db_client.get_recent_vacancies(hours=10)
        
        # Always call send_report to include pending applications
        bot.send_report(recent_jobs)
        
        if recent_jobs:
            logger.info(f"Report sent with {len(recent_jobs)} new jobs.")
            if initiator_id:
                bot._send_msg("✅ El reporte ha sido generado y enviado correctamente.", initiator_id)
        else:
            logger.info("No new jobs in recent scan, but report sent with potential pending jobs.")
    except Exception as e:
        logger.error(f"Error during report generation: {e}")
        bot.notify_error("Generación de Reporte", e)

async def run_auto_apply(job, job_doc_id, chat_id):
    """Helper to run the application process in the background."""
    from applier import fill_form
    bot = CareerBot()
    
    # Update status to APPLYING
    db_client.update_vacancy_status(job_doc_id, "APPLYING")
    
    # Simple CV context (Ideally this comes from a file or DB)
    user_cv = "Luis Angel Avila Flores - Senior Android Engineer with 7 years of experience."
    if "hector" in job.get('evaluation', {}).get('profile', ''):
        user_cv = "Hector Alonzo Romero - Technical Leader & Scrum Master with 11 years of experience."
        
    try:
        # For now, it just triggers the form filler
        # This will open a browser on the server (headless=False for debug or headless=True for prod)
        await fill_form(job['link'], user_cv)
        
        # Update status to APPLIED
        db_client.update_vacancy_status(job_doc_id, "APPLIED")
        bot._send_msg(f"✅ Proceso de aplicación completado (Manual review recommended) para <b>{job['title']}</b>.", chat_id)
    except Exception as e:
        logger.error(f"Auto-Apply Error: {e}")
        # Update status to FAILED
        db_client.update_vacancy_status(job_doc_id, f"FAILED: {str(e)[:50]}")
        bot._send_msg(f"❌ Error en la aplicación automática: {str(e)}", chat_id)

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="America/Los_Angeles")
    
    # Default scheduled scrape for Luis
    scheduler.add_job(do_scrape, 'cron', hour=2, args=["luis"], misfire_grace_time=21600)
    
    # Report at 8:30 AM
    scheduler.add_job(do_report, 'cron', hour=8, minute=30, misfire_grace_time=10800)
    
    scheduler.start()
    logger.info("Scheduler active: Scrape at 2:00 AM (Luis), Report at 8:30 AM (PST).")
