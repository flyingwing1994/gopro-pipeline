import os
import json
import requests
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.appendonly',
    'https://www.googleapis.com/auth/photoslibrary.sharing'
]

# Zorg voor een absoluut pad naar de projectmap
BASE_DIR = Path(__file__).resolve().parent
ALBUMS_CACHE_FILE = BASE_DIR / "albums.json"

def get_credentials():
    creds = None
    token_path = BASE_DIR / 'token.json'
    cred_path = BASE_DIR / 'credentials.json'

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds

def load_cached_albums() -> dict:
    """Laadt lokaal bekende albums uit albums.json."""
    if ALBUMS_CACHE_FILE.exists():
        try:
            with open(ALBUMS_CACHE_FILE, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"[Waarschuwing] Kon albums.json niet laden: {e}")
            return {}
    return {}

def save_cached_album(title: str, album_id: str):
    """Slaat een album veilig op zonder bestaande entries te overschrijven."""
    albums = load_cached_albums()
    albums[title] = album_id
    with open(ALBUMS_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(albums, f, indent=2, ensure_ascii=False)

def list_app_albums(creds) -> dict:
    """Haalt albums op: start met lokale entries en voegt API-albums toe (zonder te wissen)."""
    albums = load_cached_albums()

    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }
    try:
        res = requests.get('https://photoslibrary.googleapis.com/v1/albums', headers=headers, params={'pageSize': 50})
        if res.status_code == 200:
            for alb in res.json().get('albums', []):
                titel = alb.get('title')
                alb_id = alb.get('id')
                if titel and alb_id:
                    albums[titel] = alb_id
            # Werk cache bij met behoud van eerdere handmatige entries
            with open(ALBUMS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(albums, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return albums

def get_or_create_album(creds, album_title: str) -> str:
    cached = load_cached_albums()
    if album_title in cached and cached[album_title] != "test_auto":
        return cached[album_title]

    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }
    payload = {'album': {'title': album_title}}
    res = requests.post('https://photoslibrary.googleapis.com/v1/albums', headers=headers, json=payload)
    if res.status_code == 200:
        album_id = res.json().get('id')
        save_cached_album(album_title, album_id)
        return album_id
    return None

def upload_video_file(creds, file_path: Path, album_id: str) -> bool:
    file_path = Path(file_path)
    if not file_path.exists():
        return False

    # Automatisch token vernieuwen als de batch langer dan 60 minuten draait
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"[OAuth] Kon token niet vernieuwen: {e}")

    file_size = file_path.stat().st_size
    upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'

    init_headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/octet-stream',
        'X-Goog-Upload-Content-Type': 'video/mp4',
        'X-Goog-Upload-Protocol': 'resumable',
        'X-Goog-Upload-Command': 'start',
        'X-Goog-Upload-Raw-Size': str(file_size)
    }

    init_res = requests.post(upload_url, headers=init_headers)
    if init_res.status_code != 200:
        return False

    upload_endpoint = init_res.headers.get('X-Goog-Upload-URL')

    upload_headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/octet-stream',
        'X-Goog-Upload-Command': 'upload, finalize',
        'X-Goog-Upload-Offset': '0'
    }

    with open(file_path, 'rb') as f:
        res = requests.post(upload_endpoint, headers=upload_headers, data=f)

    if res.status_code != 200:
        return False

    upload_token = res.text

    batch_url = 'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate'
    batch_headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }
    body = {
        'albumId': album_id,
        'newMediaItems': [{
            'description': f'Converted 1080p: {file_path.name}',
            'simpleMediaItem': {'uploadToken': upload_token}
        }]
    }

    batch_res = requests.post(batch_url, headers=batch_headers, json=body)
    return batch_res.status_code == 200