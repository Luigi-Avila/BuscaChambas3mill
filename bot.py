import os
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from database import db_client
import asyncio

load_dotenv()

class CareerBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.url = f"https://api.telegram.org/bot{self.token}/"

    def send_report(self, vacancies):
        """Sends the daily 8:30 AM report."""
        message = "<b>🌅 Reporte Diario de Carrera</b>\n\n"
        for v in vacancies:
            status = "✅" if v['evaluation']['worth_applying'] else "❌"
            message += f"{status} <b>{v['title']}</b> ({v['company']})\n"
            message += f"Score: {v['evaluation']['match_score']}/10 | {v['evaluation']['salary']}\n"
            message += f"🔗 <a href='{v['link']}'>Ver Vacante</a>\n\n"
        
        self._send_msg(message)

    def _send_msg(self, text):
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            requests.post(self.url + "sendMessage", json=payload)
        except Exception as e:
            print(f"Failed to send message: {e}")

    def notify_error(self, context, error):
        """Notifies the user about an error via Telegram."""
        message = f"⚠️ <b>Error en el Agente</b>\n\n<b>Contexto:</b> {context}\n<b>Error:</b> <code>{str(error)}</code>"
        self._send_msg(message)

    async def listen_for_commands(self):
        """Polls for new messages/commands from Telegram."""
        offset = 0
        print("Bot command listener active. Use /status in Telegram.")
        while True:
            try:
                response = requests.get(self.url + f"getUpdates?offset={offset}&timeout=10")
                updates = response.json().get('result', [])
                for update in updates:
                    offset = update['update_id'] + 1
                    message = update.get('message', {})
                    text = message.get('text', '')
                    
                    if text == "/status":
                        from datetime import datetime
                        now = datetime.now().strftime("%H:%M:%S")
                        self._send_msg(f"🤖 <b>Status: ACTIVO</b>\n⏰ Hora actual: {now}\n📅 Próximo escaneo: 02:00 AM\n📊 Reporte diario: 08:30 AM")
                    
                    elif text == "/run":
                        self._send_msg("🚀 Iniciando búsqueda manual ahora mismo... Esto puede tardar unos minutos.")
                        # Run scrape and then report
                        async def manual_run():
                            await do_scrape()
                            await do_report()
                        asyncio.create_task(manual_run())
                        
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Bot Listener Error: {e}")
                await asyncio.sleep(5)

async def do_scrape():
    """Triggered at 2 AM to scrape and analyze jobs."""
    from scraper import run_pro_scraper
    from brain import evaluate_vacancy_pro
    bot = CareerBot()
    
    try:
        print("--- Starting Scheduled Scrape (2 AM) ---")
        new_jobs = await run_pro_scraper("Android Developer", "California")
        
        evaluated_count = 0
        for job in new_jobs:
            print(f"Analyzing: {job['title']}...")
            analysis = evaluate_vacancy_pro(job)
            job['evaluation'] = analysis
            db_client.save_vacancy(job)
            evaluated_count += 1
            await asyncio.sleep(2) # Quota safety
        
        print(f"Scrape completed. {evaluated_count} jobs analyzed and saved.")
    except Exception as e:
        bot.notify_error("Escaneo (2 AM)", e)

async def do_report():
    """Triggered at 8:30 AM to send the Telegram report."""
    bot = CareerBot()
    try:
        print("--- Starting Scheduled Report (8:30 AM) ---")
        # Get jobs from the last 10 hours (covers since 2 AM scrape)
        recent_jobs = db_client.get_recent_vacancies(hours=10)
        
        if recent_jobs:
            bot.send_report(recent_jobs)
            print(f"Report sent with {len(recent_jobs)} jobs.")
        else:
            bot._send_msg("📭 No se encontraron nuevas vacantes en el escaneo de hoy.")
            print("No new jobs to report.")
    except Exception as e:
        bot.notify_error("Generación de Reporte (8:30 AM)", e)

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone="America/Los_Angeles")
    
    # Scraper at 2 AM - 6h grace time in case computer is asleep
    scheduler.add_job(do_scrape, 'cron', hour=2, misfire_grace_time=21600)
    
    # Report at 8:30 AM - 3h grace time
    scheduler.add_job(do_report, 'cron', hour=8, minute=30, misfire_grace_time=10800)
    
    scheduler.start()
    print("Scheduler active: Scrape at 2:00 AM, Report at 8:30 AM (PST).")
