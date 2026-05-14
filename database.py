import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.db = self._initialize_firebase()

    def _initialize_firebase(self):
        """Initializes Firebase Admin SDK."""
        cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        if not cred_path or not os.path.exists(cred_path):
            print(f"Warning: Firebase credentials not found at {cred_path}. Firestore will not be available.")
            return None
        
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        
        return firestore.client()

    def vacancy_exists(self, url):
        """Checks if a vacancy with the given URL already exists in Firestore."""
        if not self.db: return False
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = self.db.collection('vacantes').where(filter=FieldFilter('link', '==', url)).stream()
        return any(docs)

    def save_vacancy(self, vacancy_data):
        """Saves or updates a vacancy in the 'vacantes' collection with a timestamp."""
        if not self.db: return
        import hashlib
        from datetime import datetime
        
        doc_id = hashlib.md5(vacancy_data['link'].encode()).hexdigest()
        
        # Ensure we have a timestamp
        if 'scraped_at' not in vacancy_data:
            vacancy_data['scraped_at'] = datetime.utcnow()
            
        self.db.collection('vacantes').document(doc_id).set(vacancy_data)

    def get_recent_vacancies(self, hours=24):
        """Retrieves vacancies scraped within the last X hours."""
        if not self.db: return []
        from datetime import datetime, timedelta
        from google.cloud.firestore_v1.base_query import FieldFilter
        
        since = datetime.utcnow() - timedelta(hours=hours)
        docs = self.db.collection('vacantes').where(filter=FieldFilter('scraped_at', '>', since)).stream()
        
        return [doc.to_dict() for doc in docs]

    def get_vacancy_by_id(self, doc_id):
        """Retrieves a specific vacancy by its document ID."""
        if not self.db: return None
        doc = self.db.collection('vacantes').document(doc_id).get()
        return doc.to_dict() if doc.exists else None

    def get_pending_high_match_vacancies(self, profile="luis", limit=5):
        """Retrieves vacancies that are worth applying but are still in PENDING status for a profile."""
        if not self.db: return []
        from google.cloud.firestore_v1.base_query import FieldFilter
        
        docs = self.db.collection('vacantes')\
            .where(filter=FieldFilter('evaluation.profile', '==', profile))\
            .where(filter=FieldFilter('evaluation.worth_applying', '==', True))\
            .where(filter=FieldFilter('status', '==', 'PENDING'))\
            .limit(limit).stream()
        
        return [doc.to_dict() for doc in docs]

    def update_vacancy_status(self, doc_id, status):
        """Updates the status of a specific vacancy."""
        if not self.db: return
        self.db.collection('vacantes').document(doc_id).update({'status': status})

    def get_faq(self, question):
        """Retrieves an answer from the 'faq' sub-collection if it exists."""
        if not self.db: return None
        doc = self.db.collection('user_context').document('faq_base').collection('questions').document(question).get()
        return doc.to_dict().get('answer') if doc.exists else None

    def save_faq(self, question, answer):
        """Saves a new question-answer pair to the 'faq' base."""
        if not self.db: return
        self.db.collection('user_context').document('faq_base').collection('questions').document(question).set({
            'answer': answer
        })

db_client = Database()
