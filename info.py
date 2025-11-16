import re
import os
from os import environ
from pyrogram import enums
from Script import script
import asyncio
import json
from collections import defaultdict
from pyrogram import Client

id_pattern = re.compile(r'^-?\d+$')
def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# --- Main Bot Variables ---
API_ID = int(environ.get('API_ID', '123456'))
API_HASH = environ.get('API_HASH', 'abcdef...')
BOT_TOKEN = environ.get('BOT_TOKEN', '123:ABC...')

# --- Admin and Log Channels ---
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '7245547751').split()]
USERNAME = environ.get('USERNAME', 'https://t.me/ramSitaam') # Admin/Owner username
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '-100...')) # Bot logs
LOG_VR_CHANNEL = int(environ.get('LOG_VR_CHANNEL', '-100...')) # Verification logs
LOG_API_CHANNEL = int(environ.get('LOG_API_CHANNEL', '-100...')) # Shortener API change logs
SUPPORT_GROUP = int(environ.get('SUPPORT_GROUP', '-100...')) # Support group ID
REQUEST_CHANNEL = int(environ.get('REQUEST_CHANNEL', '-100...')) # Request channel ID

# --- Databases (All 4) ---
DATABASE_URI = environ.get('DATABASE_URI', "")
DATABASE_URI2 = environ.get('DATABASE_URI2', "")
DATABASE_URI3 = environ.get('DATABASE_URI3', "")
DATABASE_URI4 = environ.get('DATABASE_URI4', "")
DATABASE_NAME = environ.get('DATABASE_NAME', "Cluster0")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Files')

# --- File Indexing and Streaming ---
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', '-100...').split()]
BIN_CHANNEL = int(environ.get('BIN_CHANNEL', '-100...')) # For streaming links
URL = environ.get('URL', 'my-bot.onrender.com') # Your bot's public URL

# --- 3-Step Verification System ---
IS_VERIFY = is_enabled(environ.get('IS_VERIFY', 'True'), True)
TUTORIAL = environ.get("TUTORIAL", "https://t.me/how_to_dwnload_mov")
VERIFY_IMG = environ.get("VERIFY_IMG", "https://graph.org/file/1669ab9af68eaa62c3ca4.jpg")

# Shortener 1 (V1)
SHORTENER_WEBSITE = environ.get("SHORTENER_WEBSITE", "")
SHORTENER_API = environ.get("SHORTENER_API", "")

# Shortener 2 (V2)
SHORTENER_WEBSITE2 = environ.get("SHORTENER_WEBSITE2", "")
SHORTENER_API2 = environ.get("SHORTENER_API2", "")

# --- FIX: Shortener 3 (V3) ---
# These are now read from environment variables instead of being empty
SHORTENER_WEBSITE3 = environ.get("SHORTENER_WEBSITE3", "")
SHORTENER_API3 = environ.get("SHORTENER_API3", "")

# Verification Timings
TWO_VERIFY_GAP = int(environ.get('TWO_VERIFY_GAP', "300")) # 5 min gap V1 -> V2
THIRD_VERIFY_GAP = int(environ.get('THIRD_VERIFY_GAP', '300')) # 5 min gap V2 -> V3
DEFAULT_VERIFY_DURATION = int(environ.get('DEFAULT_VERIFY_DURATION', '86400')) # 24 hours access after V3

# --- Force Subscribe (FSub) Channels (All 4) ---
# FSub 1 (Request)
auth_channel = environ.get('AUTH_CHANNEL', '-100...')
AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else None

# FSub 2 (Request)
auth_channel_2 = environ.get('AUTH_CHANNEL_2', '-100...')
AUTH_CHANNEL_2 = int(auth_channel_2) if auth_channel_2 and id_pattern.search(auth_channel_2) else None

# FSub 3 (Normal Join)
auth_channel_3 = environ.get('AUTH_CHANNEL_3', '-100...') 
AUTH_CHANNEL_3 = int(auth_channel_3) if auth_channel_3 and id_pattern.search(auth_channel_3) else auth_channel_3

# FSub 4 (Request - Post-Verification)
AUTH_CHANNEL_4 = environ.get('AUTH_CHANNEL_4', '-100...')
AUTH_CHANNEL_4 = int(AUTH_CHANNEL_4) if AUTH_CHANNEL_4 and id_pattern.search(AUTH_CHANNEL_4) else None
AUTH_CHANNEL_4_TEXT = environ.get('AUTH_CHANNEL_4_TEXT', '✅ Join Backup & Get File')

# --- Bot Settings ---
IS_PM_SEARCH = is_enabled(environ.get('IS_PM_SEARCH', 'True'), True) # Bot 2 should work in PM
AUTO_FILTER = is_enabled(environ.get('AUTO_FILTER', 'True'), True)
PORT = int(os.environ.get('PORT', '8080'))
MAX_BTN = int(environ.get('MAX_BTN', '8'))
AUTO_DELETE = is_enabled(environ.get('AUTO_DELETE', 'True'), True)
DELETE_TIME = int(environ.get('DELETE_TIME', 1200))
IMDB = is_enabled(environ.get('IMDB', 'True'), True)
FILE_CAPTION = environ.get('FILE_CAPTION', f'{script.FILE_CAPTION}')
IMDB_TEMPLATE = environ.get('IMDB_TEMPLATE', f'{script.IMDB_TEMPLATE_TXT}')
LONG_IMDB_DESCRIPTION = is_enabled(environ.get('LONG_IMDB_DESCRIPTION', 'False'), False)
PROTECT_CONTENT = is_enabled(environ.get('PROTECT_CONTENT', 'True'), True) # Bot 2 should protect files
SPELL_CHECK = is_enabled(environ.get('SPELL_CHECK', 'True'), True)
LINK_MODE = is_enabled(environ.get('LINK_MODE', 'False'), False) # Bot 2 should use Button mode

# --- Premium & Referral System ---
QR_CODE = environ.get('QR_CODE', 'https://i.ibb.co/ycnxb1CB/x.jpg')
REFERRAL_TARGET = int(environ.get('REFERRAL_TARGET', '10')) # Referrals needed
PREMIUM_MONTH_DURATION = int(environ.get('PREMIUM_MONTH_DURATION', '30')) # Days of premium

# --- Filter Settings ---
LANGUAGES = ["hindi", "english", "telugu", "tamil", "kannada", "malayalam"]
QUALITIES = ["4K", "2160p", "1080p", "720p", "480p", "360p"]
