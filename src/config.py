import json
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Meta/WhatsApp configuration
APP_SECRET = os.getenv("APP_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_ID = os.getenv("PHONE_ID")
WEBHOOK_VERIFICATION_TOKEN = os.getenv("WEBHOOK_VERIFICATION_TOKEN")

# Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Google Cloud Platform / Conversational Agents configuration
GCP_SERVICE_ACCOUNT_JSON = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
CA_PROJECT_ID = os.getenv("CA_PROJECT_ID")
CA_AGENT_ID = os.getenv("CA_AGENT_ID")
CA_LOCATION = os.getenv("CA_LOCATION")


def get_gcp_credentials_dict() -> dict | None:
    """
    Parse and return GCP service account credentials as a dictionary.
    The GCP_SERVICE_ACCOUNT_JSON can be either:
    1. A JSON string
    2. A file path to a JSON file
    """
    if not GCP_SERVICE_ACCOUNT_JSON:
        return None

    # Try parsing as JSON string first
    try:
        return json.loads(GCP_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError:
        pass

    # Try treating as file path
    try:
        credentials_path = Path(GCP_SERVICE_ACCOUNT_JSON)
        if credentials_path.exists() and credentials_path.is_file():
            with open(credentials_path, "r") as f:
                return json.load(f)
    except Exception:
        pass

    return None
