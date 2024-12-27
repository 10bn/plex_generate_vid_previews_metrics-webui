# src/config/settings.py

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

class Settings:
    # Plex Configuration
    PLEX_URL = os.getenv('PLEX_URL', '')
    PLEX_TOKEN = os.getenv('PLEX_TOKEN', '')
    PLEX_BIF_FRAME_INTERVAL = int(os.getenv('PLEX_BIF_FRAME_INTERVAL', 5))
    THUMBNAIL_QUALITY = int(os.getenv('THUMBNAIL_QUALITY', 4))
    PLEX_LOCAL_MEDIA_PATH = os.getenv('PLEX_LOCAL_MEDIA_PATH', '/path_to/plex/Library/Application Support/Plex Media Server/Media')
    TMP_FOLDER = os.getenv('TMP_FOLDER', '/dev/shm/plex_generate_previews')
    PLEX_TIMEOUT = int(os.getenv('PLEX_TIMEOUT', 60))
    PLEX_LOCAL_VIDEOS_PATH_MAPPING = os.getenv('PLEX_LOCAL_VIDEOS_PATH_MAPPING', '')
    PLEX_VIDEOS_PATH_MAPPING = os.getenv('PLEX_VIDEOS_PATH_MAPPING', '')
    GPU_THREADS = int(os.getenv('GPU_THREADS', 4))
    CPU_THREADS = int(os.getenv('CPU_THREADS', 4))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

settings = Settings()
