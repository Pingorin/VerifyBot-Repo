import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError, OperationFailure
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import (
    DATABASE_URI, DATABASE_URI2, DATABASE_URI3, DATABASE_URI4, 
    DATABASE_NAME, COLLECTION_NAME, MAX_BTN, QUALITIES
)

logger = logging.getLogger(__name__)

# --- Sabhi 4 connections (jaise pehle the) ---
client_primary = AsyncIOMotorClient(DATABASE_URI)
mydb_primary = client_primary[DATABASE_NAME]
instance_primary = Instance.from_db(mydb_primary)

client_secondary = AsyncIOMotorClient(DATABASE_URI2)
mydb_secondary = client_secondary[DATABASE_NAME]
instance_secondary = Instance.from_db(mydb_secondary)

client_third = AsyncIOMotorClient(DATABASE_URI3)
mydb_third = client_third[DATABASE_NAME]
instance_third = Instance.from_db(mydb_third)

client_fourth = AsyncIOMotorClient(DATABASE_URI4)
mydb_fourth = client_fourth[DATABASE_NAME]
instance_fourth = Instance.from_db(mydb_fourth)


# --- NAYA CHHOTA COLLECTION (files_data) ---
# Yeh aapka permanent master list hai. Ise 'instance_primary' (main DB) par banayein.
@instance_primary.register
class FilesData(Document):
    file_id = fields.StrField(required=True, unique=True) # file_id (Bot 2 ka)
    file_ref = fields.StrField(allow_none=True)
    message_id = fields.IntField(required=True)
    channel_id = fields.IntField(required=True)
    file_size = fields.IntField(required=True)
    
    class Meta:
        collection_name = "files_data" # Collection ka naam
        indexes = [
            fields.IndexModel("file_id", unique=True),
            fields.IndexModel(["message_id", "channel_id"], unique=True)
        ]

# --- BADA COLLECTION (files_search) MEIN BADLAAV ---
# (MediaPrimary, MediaSecondary, MediaThird, MediaFourth)

@instance_primary.register
class MediaPrimary(Document):
    file_id = fields.StrField(attribute='_id') # Search ke liye temporary ID
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    caption = fields.StrField(allow_none=True)
    
    # --- YEH NAYI LINE ADD HUI ---
    link_id = fields.StrField(required=True) # Yeh 'files_data' ke file_id ko point karega

    class Meta:
        indexes = ('$file_name', )
        collection_name = f"{COLLECTION_NAME}_PRIMARY" 

@instance_secondary.register
class MediaSecondary(Document):
    file_id = fields.StrField(attribute='_id')
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    caption = fields.StrField(allow_none=True)
    link_id = fields.StrField(required=True) # <-- Yahaan bhi add karein
    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME

@instance_third.register
class MediaThird(Document):
    file_id = fields.StrField(attribute='_id')
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    caption = fields.StrField(allow_none=True)
    link_id = fields.StrField(required=True) # <-- Yahaan bhi add karein
    class Meta:
        indexes = ('$file_name', )
        collection_name = f"{COLLECTION_NAME}_THIRD" 

@instance_fourth.register
class MediaFourth(Document):
    file_id = fields.StrField(attribute='_id')
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    caption = fields.StrField(allow_none=True)
    link_id = fields.StrField(required=True) # <-- Yahaan bhi add karein
    class Meta:
        indexes = ('$file_name', )
        collection_name = f"{COLLECTION_NAME}_FOURTH" 

# --- Compatibility Fix (Yeh waise hi rahega) ---
Media = MediaSecondary
mydb = mydb_secondary 

# --- NAYA 2-STEP SAVE LOGIC ---

async def save_file_data(media):
    """Step 1: File ko master list (files_data) mein save karta hai."""
    file_id, file_ref = unpack_new_file_id(media.file_id)

    try:
        file_data = FilesData(
            file_id=file_id,
            file_ref=file_ref,
            message_id=media.message_id,
            channel_id=media.channel_id,
            file_size=media.file_size
        )
        await file_data.commit()
        logger.info(f"Master List mein save kiya: {media.file_name}")
        return file_data
    except DuplicateKeyError:
        logger.warning(f"{media.file_name} pehle se Master List mein hai.")
        return await FilesData.find_one({'file_id': file_id}) # Puraana data return karein
    except Exception as e:
        logger.error(f"FilesData save karte hue error: {e}")
        return None

async def save_file(media, db_choice='secondary'):
    """Step 2: File ko search index (MediaPrimary etc.) mein save karta hai."""
    
    # Step 1: Pehle file ko master list mein save karo
    file_data = await save_file_data(media)
    if not file_data:
        return 'err'
    
    link_id = file_data.file_id # Master list ka ID
    search_id = base64.urlsafe_b64encode(media.file_unique_id.encode()).decode() # Search ke liye unique ID

    # Step 2: Ab file ko search index (db_choice) mein save karo
    if db_choice == 'primary': MediaClass = MediaPrimary
    elif db_choice == 'third': MediaClass = MediaThird
    elif db_choice == 'fourth': MediaClass = MediaFourth
    else: MediaClass = MediaSecondary
        
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
    
    try:
        file_search = MediaClass(
            file_id=f"{search_id}_{db_choice}", # Search index ke liye unique ID
            file_name=file_name,
            file_size=media.file_size,
            caption=media.caption.html if media.caption else None,
            link_id=link_id  # <-- Master list ka link_id yahaan save karein
        )
        await file_search.commit()
    except DuplicateKeyError:      
        logger.warning(f'{file_name} pehle se {db_choice} Search Index mein hai') 
        return 'dup'
    except Exception as e:
        logger.error(f"Search Index save karte hue error: {e}")
        return 'err'
    
    logger.info(f"'{db_choice}' Search Index mein save kiya: {file_name}")
    return 'suc'

# --- NAYA GET_FILE LOGIC ---

async def get_file_data_by_link_id(link_id: str):
    """
    Bot 2 iska istemaal karega file ka (message_id, chat_id) dhoondhne ke liye
    """
    try:
        # Hum 'file_id' ko hi 'link_id' ki tarah use kar rahe hain
        return await FilesData.find_one({'file_id': link_id})
    except Exception as e:
        logger.error(f"get_file_data_by_link_id error: {e}")
        return None

# --- Baaki functions (get_search_results, get_bad_files, etc.) waise hi rahenge ---
# (get_file_details ki ab zaroorat nahi padegi, lekin use rakhe rehne se koi nuksaan nahi hai)

async def get_search_results(query, max_results=MAX_BTN, offset=0, lang=None, quality=None, year=None):
    # ... (Yeh function poora waise hi rahega, yeh files_search collection se search karega) ...
    query = query.strip()
    if not query: raw_pattern = '.'
    elif ' ' not in query: raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else: raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]') 
    
    try: simple_regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except: simple_regex = query
    file_name_regex = simple_regex
    
    if quality and year: file_name_regex = re.compile(f"(?=.*{raw_pattern})(?=.*{re.escape(quality)})(?=.*{re.escape(year)})", flags=re.IGNORECASE)
    elif quality: file_name_regex = re.compile(f"(?=.*{raw_pattern})(?=.*{re.escape(quality)})", flags=re.IGNORECASE)
    elif year: file_name_regex = re.compile(f"(?=.*{raw_pattern})(?=.*{re.escape(year)})", flags=re.IGNORECASE)

    filter = {'$or': [{'file_name': file_name_regex}, {'caption': simple_regex}]}
    
    files_primary = files_secondary = files_third = files_fourth = []
    try: files_primary = await MediaPrimary.find(filter).sort('$natural', -1).to_list(length=None)
    except Exception as e: logger.error(f"Primary DB search error: {e}")
    try: files_secondary = await MediaSecondary.find(filter).sort('$natural', -1).to_list(length=None)
    except Exception as e: logger.error(f"Secondary DB search error: {e}")
    try: files_third = await MediaThird.find(filter).sort('$natural', -1).to_list(length=None)
    except Exception as e: logger.error(f"Third DB search error: {e}")
    try: files_fourth = await MediaFourth.find(filter).sort('$natural', -1).to_list(length=None)
    except Exception as e: logger.error(f"Fourth DB search error: {e}")

    all_files = files_primary + files_secondary + files_third + files_fourth
    
    if all_files:
        unique_files = {file.link_id: file for file in all_files} # link_id se duplicate hatayein
        all_files = list(unique_files.values())

    total_results = len(all_files)
    files_to_send = all_files[offset : offset + max_results]
    next_offset = offset + len(files_to_send)
    if next_offset >= total_results: next_offset = ''
        
    return files_to_send, next_offset, total_results

async def get_file_details(query):
    # YEH FUNCTION AB BOT 2 USE NAHI KAREGA, LEKIN DELETE KARNE KI BHI ZAROORAT NAHI
    filter = {'file_id': query}
    for MediaClass in [MediaSecondary, MediaPrimary, MediaThird, MediaFourth]:
        try:
            filedetails = await MediaClass.find(filter).to_list(length=1)
            if filedetails: return filedetails
        except Exception as e:
            logger.error(f"get_file_details error in {MediaClass.__name__}: {e}")
    return [] 

# ... (get_available_qualities, get_available_years, get_bad_files, unpack_new_file_id waise hi rahenge) ...

