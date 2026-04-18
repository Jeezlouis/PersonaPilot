import os
import sys
# Add current directory to path
sys.path.append(os.getcwd())

from backend.modules.mailer.gmail_auth import generate_auth_url, get_auth_status

def test_creds():
    print("Testing credentials.json structure...")
    status = get_auth_status()
    print(f"Current Status: {status}")
    
    if status['credentials_missing']:
        print("FAILED: credentials.json is still missing in data/ folder.")
        return

    print("Attempting to generate Auth URL to verify file validity...")
    try:
        url, state = generate_auth_url()
        if url:
            print("SUCCESS: Credentials are valid!")
            print(f"URL generated successfully (starts with): {url[:50]}...")
        else:
            print(f"FAILED: {state}")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    test_creds()
