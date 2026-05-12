# Job Search Agent

An automated agent to search, evaluate, and track job vacancies using Gemini AI, Playwright, and Telegram.

## Features
- **Scraping**: Automated job scraping from various platforms.
- **Evaluation**: AI-powered job evaluation based on your profile.
- **Monitoring**: Gmail monitoring for job updates.
- **Notifications**: Telegram bot for reports and manual control.
- **Database**: Persistence with Firestore/Firebase.

## Setup

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd job_search_agent
   ```

2. **Install dependencies**:
   - Python: `pip install -r requirements.txt`
   - Node (for Playwright): `npm install && npx playwright install`

3. **Environment Variables**:
   - Copy `.env.example` to `.env`.
   - Fill in your API keys and configuration.
   ```bash
   cp .env.example .env
   ```

4. **Credentials**:
   - Place your `credentials.json` (Gmail API) and `serviceAccountKey.json` (Firebase) in the root directory. These are ignored by git for security.

5. **Run**:
   ```bash
   python main.py
   ```

## Security
Sensitive files like `.env`, `*.json` credentials, and `context/` are excluded from version control via `.gitignore`.
