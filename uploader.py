import os
import requests
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.appendonly',
    'https://www.googleapis.com/auth/photoslibrary.sharing'
]

def get_credentials():
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
    return creds

def get_or_create_album(creds, album_title: str) -> str:
    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }
    
    # Maak nieuw album aan (of gebruik bestaande)
    payload = {'album': {'title': album_title}}
    res = requests.post('https://photoslibrary.googleapis.com/v1/albums', headers=headers, json=payload)
    if res.status_code == 200:
        return res.json().get('id')
    return None

def upload_video_file(creds, file_path: Path, album_id: str) -> bool:
    file_path = Path(file_path)
    if not file_path.exists():
        return False

    upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'
    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/octet-stream',
        'X-Goog-Upload-Content-Type': 'video/mp4',
        'X-Goog-Upload-Protocol': 'raw'
    }

    # 1. Byte stream uploaden
    with open(file_path, 'rb') as f:
        res = requests.post(upload_url, headers=headers, data=f)

    if res.status_code != 200:
        return False

    upload_token = res.text

    # 2. Media-item toevoegen aan het album
    batch_url = 'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate'
    batch_headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }
    body = {
        'albumId': album_id,
        'newMediaItems': [{
            'description': f'Uploaded by GoPro Pipeline: {file_path.name}',
            'simpleMediaItem': {'uploadToken': upload_token}
        }]
    }

    batch_res = requests.post(batch_url, headers=batch_headers, json=body)
    return batch_res.status_code == 200