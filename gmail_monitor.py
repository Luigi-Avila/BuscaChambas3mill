import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from database import db_client

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def monitor_emails():
    """Checks Gmail for status updates from recruitment domains."""
    try:
        service = get_gmail_service()
        # Search for common recruitment platforms
        query = "from:(greenhouse.io OR lever.co OR workday.com)"
        results = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
        messages = results.get('messages', [])

        for msg in messages:
            txt = service.users().messages().get(userId='me', id=msg['id']).execute()
            snippet = txt.get('snippet', '').lower()
            subject = ""
            for header in txt['payload']['headers']:
                if header['name'] == 'Subject':
                    subject = header['value'].lower()
            
            # Logic to determine status
            new_status = None
            if "interview" in subject or "schedule" in snippet:
                new_status = "INTERVIEW"
            elif "thank you for your interest" in snippet or "not moving forward" in snippet:
                new_status = "REJECTED"
            
            if new_status:
                print(f"Detected status change: {new_status} from email: {subject}")
                # In a real scenario, we'd match the company name to a Firestore doc
                # This is a simplified placeholder for the mapping logic
    except Exception as e:
        print(f"Gmail Monitor Error: {e}")

if __name__ == "__main__":
    monitor_emails()
