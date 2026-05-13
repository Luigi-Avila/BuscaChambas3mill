import logging
import os
from google.cloud import logging as cloud_logging
from google.oauth2 import service_account

# Define log file path
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")

def setup_logger():
    """Configures the global logger to write to console, a file, and Google Cloud Logging."""
    logger = logging.getLogger("CareerAgent")
    logger.setLevel(logging.INFO)

    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 1. File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)

    # 2. Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # 3. Google Cloud Logging Handler
    try:
        cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        if cred_path and os.path.exists(cred_path):
            credentials = service_account.Credentials.from_service_account_file(cred_path)
            client = cloud_logging.Client(credentials=credentials)
            # This handler will ship logs to Google Cloud
            cloud_handler = cloud_logging.handlers.CloudLoggingHandler(client, name="career-agent-logs")
            cloud_handler.setLevel(logging.INFO)
            logger.addHandler(cloud_handler)
            print("Google Cloud Logging enabled.")
    except Exception as e:
        print(f"Warning: Could not initialize Google Cloud Logging: {e}")

    # Add other handlers to logger
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        logger.addHandler(file_handler)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, cloud_logging.handlers.CloudLoggingHandler) for h in logger.handlers):
        logger.addHandler(console_handler)

    return logger

# Initialize the logger
logger = setup_logger()
