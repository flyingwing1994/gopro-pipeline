import json
from pathlib import Path
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/photoslibrary']


def get_authenticated_service(credentials_path: Path, token_path: Path):
    """Authenticates using local OAuth desktop client credentials and saves/refreshes token."""
    creds = None
    credentials_path = Path(credentials_path)
    token_path = Path(token_path)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Configuratiebestand ontbreekt: {credentials_path}. "
                    "Download je OAuth credentials via de Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())

    return creds


def get_or_create_album(creds, album_title: str) -> str:
    """Finds an existing album by name or creates a new one, returning its ID."""
    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }

    # Zoek in bestaande albums
    url = 'https://photoslibrary.googleapis.com/v1/albums'
    params = {'pageSize': 50}

    while url:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200:
            break
        data = res.json()
        albums = data.get('albums', [])
        for album in albums:
            if album.get('title') == album_title:
                return album.get('id')

        next_page = data.get('nextPageToken')
        if next_page:
            params['pageToken'] = next_page
        else:
            break

    # Maak nieuw album aan als het niet bestaat
    create_url = 'https://photoslibrary.googleapis.com/v1/albums'
    body = {'album': {'title': album_title}}
    res = requests.post(create_url, headers=headers, json=body)
    res.raise_for_status()
    return res.json().get('id')


def upload_video_file(creds, file_path: Path, album_id: str) -> bool:
    """
    Uploads a video to Google Photos using the robust Resumable Upload protocol.
    Works reliably with larger video deliveries.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"Bestand niet gevonden voor upload: {file_path}")
        return False

    file_size = file_path.stat().st_size
    upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'

    # Stap 1: Initialiseer resumable sessie
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
        print(f"Fout bij starten uploadsessie ({init_res.status_code}): {init_res.text}")
        return False

    upload_endpoint = init_res.headers.get('X-Goog-Upload-URL')
    if not upload_endpoint:
        print("Geen upload endpoint ontvangen van Google Photos.")
        return False

    # Stap 2: Stuur binaire data door
    upload_headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/octet-stream',
        'X-Goog-Upload-Command': 'upload, finalize',
        'X-Goog-Upload-Offset': '0'
    }

    with open(file_path, 'rb') as f:
        upload_res = requests.post(upload_endpoint, headers=upload_headers, data=f)

    if upload_res.status_code != 200:
        print(f"Fout tijdens het streamen van data ({upload_res.status_code}): {upload_res.text}")
        return False

    upload_token = upload_res.text

    # Stap 3: Registreer het media-item in het doelalbum
    batch_url = 'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate'
    batch_headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/json'
    }
    body = {
        'albumId': album_id,
        'newMediaItems': [{
            'description': f'GoPro 1080p Rec.709: {file_path.name}',
            'simpleMediaItem': {'uploadToken': upload_token}
        }]
    }

    batch_res = requests.post(batch_url, headers=batch_headers, json=body)
    if batch_res.status_code != 200:
        print(f"Fout bij toevoegen aan album ({batch_res.status_code}): {batch_res.text}")
        return False

    results = batch_res.json().get('newMediaItemResults', [])
    if results and results[0].get('status', {}).get('message') in [None, 'Success', 'OK']:
        return True
    
    print(f"Google Photos upload status: {results}")
    return False