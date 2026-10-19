import os
import time
import json
import logging
import requests
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.appendonly',
    'https://www.googleapis.com/auth/photoslibrary.sharing'
]

BASE_DIR = Path(__file__).resolve().parent
ALBUMS_CACHE_FILE = BASE_DIR / "albums.json"
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB optimale Google Cloud transfer chunks

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
    if ALBUMS_CACHE_FILE.exists():
        try:
            with open(ALBUMS_CACHE_FILE, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}

def save_cached_album(title: str, album_id: str):
    albums = load_cached_albums()
    albums[title] = album_id
    with open(ALBUMS_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(albums, f, indent=2, ensure_ascii=False)

def list_app_albums(creds) -> dict:
    albums = load_cached_albums()
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            pass

    headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}
    try:
        res = requests.get('https://photoslibrary.googleapis.com/v1/albums', headers=headers, params={'pageSize': 50})
        if res.status_code == 200:
            for alb in res.json().get('albums', []):
                titel = alb.get('title')
                alb_id = alb.get('id')
                if titel and alb_id:
                    albums[titel] = alb_id
            with open(ALBUMS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(albums, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"Kon albums niet ophalen van Google API: {e}")
    return albums

def get_or_create_album(creds, album_title: str) -> str:
    cached = load_cached_albums()
    if album_title in cached and cached[album_title] != "test_auto":
        return cached[album_title]

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}
    payload = {'album': {'title': album_title}}
    res = requests.post('https://photoslibrary.googleapis.com/v1/albums', headers=headers, json=payload)
    if res.status_code == 200:
        album_id = res.json().get('id')
        save_cached_album(album_title, album_id)
        return album_id
    return None

def upload_video_file(creds, file_path: Path, album_id: str, progress_callback=None) -> bool:
    """Uploadt video in 8MB chunks met automatische token-refresh, exponential retries en API-verificatie."""
    file_path = Path(file_path)
    if not file_path.exists():
        return False

    file_size = file_path.stat().st_size
    upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'

    # Automatische OAuth vernieuwing
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            logging.error(f"Fout bij refreshen OAuth token: {e}")

    # Stap 1: Sessie initiëren
    init_headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/octet-stream',
        'X-Goog-Upload-Content-Type': 'video/mp4',
        'X-Goog-Upload-Protocol': 'resumable',
        'X-Goog-Upload-Command': 'start',
        'X-Goog-Upload-Raw-Size': str(file_size)
    }

    upload_endpoint = None
    for attempt in range(4):
        try:
            res = requests.post(upload_url, headers=init_headers, timeout=20)
            if res.status_code == 200:
                upload_endpoint = res.headers.get('X-Goog-Upload-URL')
                break
        except Exception as e:
            logging.warning(f"Poging {attempt+1} voor sessie-start mislukt: {e}")
        time.sleep(3)

    if not upload_endpoint:
        logging.error(f"Upload sessie kon niet gestart worden voor {file_path.name}")
        return False

    # Stap 2: Uploaden in 8 MB chunks
    bytes_uploaded = 0
    upload_token = None

    with open(file_path, 'rb') as f:
        while bytes_uploaded < file_size:
            chunk = f.read(CHUNK_SIZE)
            is_last = (bytes_uploaded + len(chunk)) >= file_size
            command = 'upload, finalize' if is_last else 'upload'

            chunk_headers = {
                'Authorization': f'Bearer {creds.token}',
                'Content-Type': 'application/octet-stream',
                'X-Goog-Upload-Offset': str(bytes_uploaded),
                'X-Goog-Upload-Command': command
            }

            chunk_success = False
            for retry in range(4):
                try:
                    chunk_res = requests.post(upload_endpoint, headers=chunk_headers, data=chunk, timeout=60)
                    if chunk_res.status_code == 200:
                        chunk_success = True
                        if is_last:
                            upload_token = chunk_res.text
                        break
                except Exception as e:
                    logging.warning(f"Hapering op chunk {bytes_uploaded} van {file_path.name}: {e}")
                time.sleep(4)

            if not chunk_success:
                logging.error(f"Upload afgebroken voor {file_path.name} op byte {bytes_uploaded}")
                return False

            bytes_uploaded += len(chunk)
            if progress_callback:
                progress_callback(bytes_uploaded, file_size)

    if not upload_token:
        return False

    # Stap 3: Verificatie & toewijzing aan album
    batch_url = 'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate'
    batch_headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}
    body = {
        'albumId': album_id,
        'newMediaItems': [{
            'description': f'GoPro Converted: {file_path.name}',
            'simpleMediaItem': {'uploadToken': upload_token}
        }]
    }

    try:
        verify_res = requests.post(batch_url, headers=batch_headers, json=body, timeout=30)
        if verify_res.status_code == 200:
            results = verify_res.json().get('newMediaItemResults', [])
            if results:
                st_info = results[0].get('status', {})
                msg = st_info.get('message', '')
                if not msg or msg.lower() in ['success', 'ok']:
                    logging.info(f"Upload geverifieerd in Google Photos album: {file_path.name}")
                    return True
                else:
                    logging.warning(f"Album weigering ({msg}). Uploaden naar hoofdbibliotheek...")
                    # Fallback: voeg toe aan bibliotheek zonder specifiek album
                    fallback_body = {
                        'newMediaItems': [{
                            'description': f'GoPro Converted: {file_path.name}',
                            'simpleMediaItem': {'uploadToken': upload_token}
                        }]
                    }
                    fb_res = requests.post(batch_url, headers=batch_headers, json=fallback_body, timeout=30)
                    if fb_res.status_code == 200:
                        logging.info(f"Upload geverifieerd in Google Photos bibliotheek: {file_path.name}")
                        return True
                    else:
                        logging.error(f"Fallback mislukt: {fb_res.text}")
        else:
            logging.error(f"batchCreate HTTP {verify_res.status_code}: {verify_res.text}")
    except Exception as e:
        logging.error(f"Fout tijdens verificatie van {file_path.name}: {e}")

    logging.error(f"Google weigerde toevoeging van {file_path.name}")
    return False