import asyncio
import urllib.parse
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from database import db_client
from logger_config import logger

async def scroll_page(page):
    """Performs infinite scroll to load more job listings."""
    for _ in range(10): # Scroll 10 times for more volume
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

async def scrape_linkedin(keywords, location, filter_easy_apply=False):
    jobs = []
    query = urllib.parse.quote(keywords)
    loc = urllib.parse.quote(location)
    
    # f_WT=2 is the filter for Remote
    url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={loc}&f_WT=2"
    if filter_easy_apply:
        url += "&f_AL=true"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Correct Stealth usage
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        logger.info(f"Scraping LinkedIn: {url}")
        try:
            await page.goto(url, timeout=60000)
            await scroll_page(page)
            
            job_cards = await page.query_selector_all(".job-search-card, .base-card")
            for card in job_cards[:50]: # Increased to 50
                link_el = await card.query_selector("a.base-card__full-link, a.job-search-card__link")
                link = await link_el.get_attribute("href") if link_el else None
                if not link: continue
                link = link.split('?')[0]
                
                if db_client.vacancy_exists(link):
                    logger.info(f"Skipping existing: {link}")
                    continue
                
                title_el = await card.query_selector(".base-search-card__title, .job-search-card__title")
                company_el = await card.query_selector(".base-search-card__subtitle, .job-search-card__subtitle")
                
                # Check for Easy Apply badge/text
                card_text = await card.inner_text()
                apply_type = "Easy Apply" if "Easy Apply" in card_text or "Solicitud sencilla" in card_text else "External"
                
                # Get more description by clicking or navigating (simulated here for brevity)
                jobs.append({
                    "title": (await title_el.inner_text()).strip() if title_el else "N/A",
                    "company": (await company_el.inner_text()).strip() if company_el else "N/A",
                    "link": link,
                    "source": "LinkedIn",
                    "apply_type": apply_type,
                    "status": "PENDING"
                })
        except Exception as e:
            logger.error(f"LinkedIn Scrape Error: {e}")
        finally:
            await browser.close()
    return jobs

async def scrape_indeed(keywords, location):
    jobs = []
    query = urllib.parse.quote(keywords)
    loc = urllib.parse.quote(location)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        # We'll try to get up to 50 jobs by paginating (Indeed has ~15 per page)
        for page_num in range(0, 4): # Pages 0, 10, 20, 30...
            if len(jobs) >= 50: break
            
            start = page_num * 10
            # Simplified URL: removed sc filter which sometimes triggers blocks
            url = f"https://www.indeed.com/jobs?q={query}&l={loc}&start={start}"
            
            page = await context.new_page()
            stealth_config = Stealth()
            await stealth_config.apply_stealth_async(page)
            
            logger.info(f"Scraping Indeed (Page {page_num + 1}): {url}")
            try:
                await page.goto(url, timeout=60000)
                
                # Check for bot detection titles
                page_title = await page.title()
                if "hCaptcha" in page_title or "Cloudflare" in page_title or "Verify you are human" in page_title:
                    logger.error(f"Indeed bot detection triggered on page {page_num}!")
                    await page.close()
                    break

                await page.wait_for_selector(".job_seen_beacon", timeout=30000) # Increased to 30s
                
                job_cards = await page.query_selector_all(".job_seen_beacon")
                for card in job_cards:
                    if len(jobs) >= 50: break
                    
                    title_el = await card.query_selector("h2.jobTitle a")
                    company_el = await card.query_selector("[data-testid='company-name']")
                    
                    link = await title_el.get_attribute("href") if title_el else None
                    if not link: continue
                    if not link.startswith("http"):
                        link = "https://www.indeed.com" + link
                    link = link.split('&')[0] # Clean URL
                    
                    if db_client.vacancy_exists(link):
                        logger.info(f"Skipping existing: {link}")
                        continue
                    
                    card_text = await card.inner_text()
                    apply_type = "Easy Apply" if "Easily apply" in card_text or "Postulación sencilla" in card_text else "External"
                    
                    jobs.append({
                        "title": (await title_el.inner_text()).strip() if title_el else "N/A",
                        "company": (await company_el.inner_text()).strip() if company_el else "N/A",
                        "link": link,
                        "source": "Indeed",
                        "apply_type": apply_type,
                        "status": "PENDING"
                    })
                await page.close()
                await asyncio.sleep(2) # Anti-bot delay
            except Exception as e:
                logger.error(f"Indeed Scrape Error on page {page_num}: {e}")
                await page.close()
                break # Stop if we hit an error (likely a bot wall)
        
        await browser.close()
    return jobs

async def run_pro_scraper(keywords, location, filter_easy_apply=False):
    li_jobs = await scrape_linkedin(keywords, location, filter_easy_apply)
    ind_jobs = await scrape_indeed(keywords, location)
    all_jobs = li_jobs + ind_jobs
    return all_jobs
