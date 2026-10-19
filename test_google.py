import os
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Toegestane scopes voor ongeverifieerde apps
SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.appendonly',
    'https://www.googleapis.com/auth/photoslibrary.sharing'
]

def test_connection():
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[OAuth] Token vernieuwen...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("❌ FOUT: credentials.json ontbreekt!")
                return
            
            print("[OAuth] Start lokale authenticatieserver...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
            print("✅ Token succesvol opgeslagen in token.json")

    print("\n[API] Testen van albumbeheer via Google Photos API...")
    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }

    # Maak een specifiek app-album aan (of controleer of dat mag)
    album_title = "GoPro Pipeline Test"
    payload = {'album': {'title': album_title}}
    
    response = requests.post(
        'https://photoslibrary.googleapis.com/v1/albums',
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        album_data = response.json()
        print("✅ Verbinding en rechten succesvol! (Statuscode 200)")
        print(f"✅ Album aangemaakt/bevestigd: '{album_data.get('title')}'")
        print(f"   Album ID: {album_data.get('id')}")
        print(f"   URL: {album_data.get('productUrl')}")
    else:
        print(f"❌ API Fout: Statuscode {response.status_code}")
        print(response.text)

if __name__ == '__main__':
    test_connection()