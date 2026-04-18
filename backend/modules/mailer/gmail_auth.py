import os
import json
from google.oauth2.credentials import Credentials

# Allow insecure transport for local testing (localhost)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_PATH = os.path.join("data", "credentials.json")
TOKEN_PATH = os.path.join("data", "gmail_token.json")

def get_gmail_service():
    from googleapiclient.discovery import build
    creds = get_credentials()
    if creds and creds.valid:
        return build('gmail', 'v1', credentials=creds)
    return None

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            pass

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save the refreshed credentials
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        except Exception:
            # Refresh failed, user needs to re-auth
            creds = None

    return creds

def generate_auth_url():
    """Generates the authorization URL and state to initiate OAuth flow."""
    if not os.path.exists(CREDENTIALS_PATH):
        return None, "credentials.json not found in data/ directory. Please download it from Google Cloud Console."
        
    flow = Flow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    flow.redirect_uri = "http://localhost:8000/api/gmail/oauth2callback"
    
    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline', include_granted_scopes='true')
    
    # Store the verifier so we can recover it in the callback
    with open(os.path.join("data", "auth_state.json"), 'w') as f:
        json.dump({"code_verifier": flow.code_verifier, "state": state}, f)
        
    return auth_url, state

def handle_callback(code: str, state: str, original_url: str):
    """Exchanges auth code for credentials."""
    # Load the verifier
    state_path = os.path.join("data", "auth_state.json")
    if not os.path.exists(state_path):
        return False
        
    with open(state_path, 'r') as f:
        saved_state = json.load(f)
    
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH, 
        SCOPES, 
        state=state,
        code_verifier=saved_state["code_verifier"]
    )
    flow.redirect_uri = "http://localhost:8000/api/gmail/oauth2callback"
    
    flow.fetch_token(authorization_response=original_url)
    
    creds = flow.credentials
    with open(TOKEN_PATH, 'w') as token:
        token.write(creds.to_json())
        
    # Cleanup state file
    if os.path.exists(state_path):
        os.remove(state_path)
        
    return True

def get_auth_status():
    creds = get_credentials()
    return {
        "is_authenticated": creds is not None and creds.valid,
        "credentials_missing": not os.path.exists(CREDENTIALS_PATH)
    }
