from pyrogram import Client, filters, enums
from info import CHANNELS
from database.ia_filterdb import save_file

media_filter = filters.document | filters.video

@Client.on_message(filters.chat(CHANNELS) & media_filter)
async def media(bot, message):
    media = getattr(message, message.media.value, None)
    
    # Check karein ki media 'None' nahi hai
    if media and media.mime_type in ['video/mp4', 'video/x-matroska']:
        media.file_type = message.media.value
        media.caption = message.caption
        
        # --- YEH HAI FIX ---
        # File save karne se pehle uska address (ID) batayein
        media.message_id = message.id
        media.channel_id = message.chat.id
        # --- FIX KHATAM ---

        # 'secondary' (default) DB mein save karega
        await save_file(media, 'secondary') 
