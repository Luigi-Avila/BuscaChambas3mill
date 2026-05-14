# Job Search Agent

An automated agent to search, evaluate, and track job vacancies using Gemini AI, Playwright, and Telegram.

## Features
- **Smart Scraping**: Multi-source scraping (LinkedIn, Indeed) with automatic detection of "Easy Apply" vs "External" applications.
- **AI Evaluation**: Advanced job matching using **Ollama (local)** with a 3-retry redundancy fallback to **Gemini (cloud)**.
- **Interactive Reports**: Daily Telegram reports with inline buttons to view vacancies or trigger automated applications.
- **Automated Applying**: Background process that fills job forms automatically using your CV and AI-mapped field detection.
- **Session Management**: Persistent browser sessions to maintain LinkedIn login and bypass 2FA after the first setup.
- **Database**: Persistence with Firestore/Firebase to track application status (`PENDING`, `APPLYING`, `APPLIED`, `FAILED`).

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

4. **LinkedIn Session Setup (Crucial)**:
   - Run the login helper to save your browser session:
     ```bash
     python3 login.py
     ```
   - Login manually in the window that opens, complete 2FA, and press ENTER in the terminal to save.

5. **Credentials**:
   - Place your `credentials.json` (Gmail API) and `serviceAccountKey.json` (Firebase) in the root directory.

6. **Run**:
   - Start the main agent with the scheduler:
     ```bash
     python main.py
     ```

## Telegram Commands
- `/status`: Show current agent health, host, and AI model.
- `/run [perfil]`: Manually trigger a scan and report for 'luis' or 'hector'.
- `/pending [perfil]`: Retrieve up to 10 high-match jobs that haven't been applied to yet.
- `/help`: Display all available commands.
- `/stop`: Remote shutdown of the agent.

## Security
Sensitive files like `.env`, `*.json` credentials, `.linkedin_session/`, and logs are excluded from version control via `.gitignore`.
