import asyncio
from scraper import run_pro_scraper
from brain import evaluate_vacancy_pro
from database import db_client
from bot import CareerBot, start_scheduler
from gmail_monitor import monitor_emails
from dotenv import load_dotenv
from logger_config import logger

async def run_now():
    """Manual run for immediate results."""
    load_dotenv()
    bot = CareerBot()
    
    logger.info("--- Executing Manual Run (Career Agent Pro v2.0) ---")
    
    # 1. Scraping
    new_jobs = await run_pro_scraper("Android Developer", "California")
    
    # 2. Evaluation & Persistence
    evaluated_jobs = []
    for job in new_jobs:
        logger.info(f"Analyzing: {job['title']}...")
        analysis = evaluate_vacancy_pro(job)
        job['evaluation'] = analysis
        
        # Save to Firestore
        db_client.save_vacancy(job)
        evaluated_jobs.append(job)
        await asyncio.sleep(2) # Quota safety
    
    # 3. Report
    if evaluated_jobs:
        bot.send_report(evaluated_jobs)
    
    # 4. Gmail Check
    monitor_emails()

async def main():
    logger.info("Initializing CareerBot...")
    bot = CareerBot()
    
    # Start scheduler
    logger.info("Starting Scheduler (2 AM Scrape, 8:30 AM Report)...")
    start_scheduler()
    
    # Start Telegram listener
    logger.info("Starting Telegram Listener... Use /status or /run in Telegram.")
    await bot.listen_for_commands()

if __name__ == "__main__":
    asyncio.run(main())
