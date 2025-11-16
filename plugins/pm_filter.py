import urllib.parse
import asyncio
import logging
import pytz
import re, time
import ast
import math
import string
import random
from datetime import datetime, timedelta
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from info import (
    MAX_BTN, BIN_CHANNEL, USERNAME, URL, ADMINS, LANGUAGES, AUTH_CHANNEL, SUPPORT_GROUP, IMDB, 
    IMDB_TEMPLATE, LOG_CHANNEL, LOG_VR_CHANNEL, TUTORIAL, FILE_CAPTION, SHORTENER_WEBSITE, 
    SHORTENER_API, SHORTENER_WEBSITE2, SHORTENER_API2, IS_PM_SEARCH, QR_CODE, DELETE_TIME, 
    REFERRAL_TARGET
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, ChatPermissions
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid, ChatAdminRequired
from utils import temp, get_settings, is_check_admin, get_status, get_hash, get_name, get_size, save_group_settings, get_poster, get_readable_time
from database.users_chats_db import db
# --- BADLAAV: ia_filterdb se MediaPrimary etc. import karein (delete logic ke liye) ---
from database.ia_filterdb import (
    Media, MediaPrimary, MediaSecondary, MediaThird, MediaFourth, 
    get_search_results, get_bad_files, get_available_qualities, get_available_years
)


lock = asyncio.Lock()
logger = logging.getLogger(__name__)

BUTTONS = {}
FILES_ID = {}
CAP = {}

@Client.on_message(filters.private & filters.text & filters.incoming & ~filters.regex(r"^/"))
async def pm_search(client, message):
    if IS_PM_SEARCH:
        await auto_filter(client, message)
    else:
        await message.reply_text("<b>⚠️ ꜱᴏʀʀʏ ɪ ᴄᴀɴ'ᴛ ᴡᴏRK ɪɴ ᴘᴍ</b>")
    
@Client.on_message(filters.group & filters.text & filters.incoming & ~filters.regex(r"^/"))
async def group_search(client, message):
    user_id = message.from_user.id if message.from_user else None
    chat_id = message.chat.id
    settings = await get_settings(chat_id)
    if settings["auto_filter"]:
        if not user_id:
            await message.reply("<b>🚨 ɪ'ᴍ ɴᴏᴛ ᴡᴏʀᴋɪɴɢ ғᴏʀ ᴀɴᴏɴʏᴍᴏᴜꜱ ᴀᴅᴍɪɴ!</b>")
            return
        
        if 'hindi' in message.text.lower() or 'tamil' in message.text.lower() or 'telugu' in message.text.lower() or 'malayalam' in message.text.lower() or 'kannada' in message.text.lower() or 'english' in message.text.lower() or 'gujarati' in message.text.lower(): 
            return await auto_filter(client, message)

        if message.text.startswith("/"):
            return
        
        elif re.findall(r'https?://\S+|www\.\S+|t\.me/\S+', message.text):
            if await is_check_admin(client, message.chat.id, message.from_user.id):
                return
            await message.delete()
            return await message.reply('<b>‼️ ᴡʜʏ ʏᴏᴜ ꜱᴇɴᴅ ʜᴇʀᴇ ʟɪɴᴋ\nʟɪɴᴋ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ ʜᴇʀᴇ 🚫</b>')

        elif '@admin' in message.text.lower() or '@admins' in message.text.lower():
            # ... (Admin report logic yahaan) ...
            pass
        else:
            await auto_filter(client, message)   
    else:
        k=await message.reply_text('<b>⚠️ ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ᴍᴏᴅᴇ ɪꜱ ᴏғғ...</b>')
        await asyncio.sleep(10)
        await k.delete()
        try:
            await message.delete()
        except:
            pass

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    try:
        offset = int(offset)
    except:
        offset = 0
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search:
        await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
        return
    files, n_offset, total = await get_search_results(search, offset=offset)
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0
    if not files:
        return
    temp.FILES_ID[key] = files
    
    batch_ids = files
    temp.FILES_ID[f"{query.message.chat.id}-{query.id}"] = batch_ids
    batch_link = f"batchfiles#{query.message.chat.id}#{query.id}#{query.from_user.id}"

    settings = await get_settings(query.message.chat.id)
    reqnxt  = query.from_user.id if query.from_user else 0
    temp.CHAT[query.from_user.id] = query.message.chat.id
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code>...</b>" if settings["auto_delete"] else ''
    links = ""
    
    # --- BADLAAV YAHAN HAI ---
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            # file.file_id ki jagah file.link_id aur "get_"
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(
                    text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", 
                    # file.file_id ki jagah file.link_id aur "get_"
                    url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'
                ),]
                for file in files
              ]
    # --- BADLAAV KHATAM ---
    
    btn.insert(0,[
        InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=batch_link),
        InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium"),
        InlineKeyboardButton("📰 ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}#{offset}#{req}")
        ])

    filter_buttons = []
    available_qualities = await get_available_qualities(search)
    if len(available_qualities) > 1:
        filter_buttons.append(InlineKeyboardButton("🎞️ Qᴜᴀʟɪᴛʏ", callback_data=f"qualities#{key}#{offset}#{req}"))
    available_years = await get_available_years(search)
    if len(available_years) > 1:
        filter_buttons.append(InlineKeyboardButton("📅 Yᴇᴀʀ", callback_data=f"years#{key}#{offset}#{req}"))
    if filter_buttons:
        btn.append(filter_buttons)

    btn.append([InlineKeyboardButton("💰 ʀᴇꜰᴇʀ & ᴇᴀʀɴ 💰", url=f"https://t.me/{temp.U_NAME}?start=get_referral_{query.message.chat.id}")])
    btn.append([InlineKeyboardButton("🤔 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🤔", url=settings['tutorial'])])

    if 0 < offset <= int(MAX_BTN): off_set = 0
    elif offset == 0: off_set = None
    else: off_set = offset - int(MAX_BTN)
    
    if n_offset == 0:
        btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
             InlineKeyboardButton(f"ᴘᴀɢᴇ {math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages")]
        )
    elif off_set is None:
        btn.append([InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
             InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append([
                InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
                InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"next_{req}_{key}_{n_offset}")
            ],
        )
        
    if settings["link"]:
        # Link mode ke liye links dobara generate karne ki zaroorat nahi, upar ho chuke hain
        await query.message.edit_text(cap + links + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
        return        
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()
    
@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):
    # ... (Yeh function waise hi rahega) ...
    pass

@Client.on_callback_query(filters.regex(r"^lang_search#"))
async def lang_search(client: Client, query: CallbackQuery):
    _, lang, key, offset, orginal_offset, req = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(script.ALRT_TXT, show_alert=True)	
    offset = int(offset)
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search:
        await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
        return 
    search = search.replace("_", " ")
    files, n_offset, total = await get_search_results(f"{search} {lang}", max_results=int(MAX_BTN), offset=offset)
    try: n_offset = int(n_offset)
    except: n_offset = 0
    files = [file for file in files if re.search(lang, file.file_name, re.IGNORECASE)]
    if not files:
        await query.answer(f"sᴏʀʀʏ '{lang.title()}' ʟᴀɴɢᴜᴀɢᴇ ꜰɪʟᴇs ɴᴏᴛ ꜰᴏᴜɴᴅ 😕", show_alert=1)
        return

    batch_ids = files
    temp.FILES_ID[f"{query.message.chat.id}-{query.id}"] = batch_ids
    batch_link = f"batchfiles#{query.message.chat.id}#{query.id}#{query.from_user.id}"

    reqnxt = query.from_user.id if query.from_user else 0
    settings = await get_settings(query.message.chat.id)
    group_id = query.message.chat.id
    temp.CHAT[query.from_user.id] = query.message.chat.id
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code>...</b>" if settings["auto_delete"] else ''
    links = ""
    
    # --- BADLAAV YAHAN HAI ---
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            # file.file_id ki jagah file.link_id aur "get_"
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        btn = [[
                InlineKeyboardButton(
                    text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", 
                    # file.file_id ki jagah file.link_id aur "get_"
                    url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'
                ),]
                   for file in files
              ]
    # --- BADLAAV KHATAM ---
        
    btn.insert(0, [
            InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ ♻️", callback_data=batch_link),
            InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium")
        ])

    # ... (Baaki pagination logic waise hi rahega) ...
    pass
    
@Client.on_callback_query(filters.regex(r"^qualities#"))
async def quality_filter_cb_handler(client: Client, query: CallbackQuery):
    # ... (Yeh function waise hi rahega) ...
    pass


@Client.on_callback_query(filters.regex(r"^quality_set#"))
async def set_quality_cb_handler(client: Client, query: CallbackQuery):
    # ... (function ka start waise hi rahega) ...
    # ... (files, n_offset, total = await get_search_results...) ...

    # --- BADLAAV YAHAN HAI ---
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(
                    text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", 
                    url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'
                ),]
                for file in files
              ]
    # --- BADLAAV KHATAM ---

    # ... (Baaki quality_set logic waise hi rahega) ...
    pass

@Client.on_callback_query(filters.regex(r"^years#"))
async def years_cb_handler(client: Client, query: CallbackQuery):
    # ... (Yeh function waise hi rahega) ...
    pass


@Client.on_callback_query(filters.regex(r"^year_set#"))
async def set_year_cb_handler(client: Client, query: CallbackQuery):
    # ... (function ka start waise hi rahega) ...
    # ... (files, n_offset, total = await get_search_results...) ...
    
    # --- BADLAAV YAHAN HAI ---
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(
                    text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", 
                    url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'
                ),]
                for file in files
              ]
    # --- BADLAAV KHATAM ---
    
    # ... (Baaki year_set logic waise hi rahega) ...
    pass

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    # ... (Yeh function waise hi rahega) ...
    pass

async def filter_non_index_callbacks(_, __, query):
    return not query.data.startswith("index")            

@Client.on_callback_query(filters.create(filter_non_index_callbacks))
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        # ... (logic waise hi rahega) ...
        pass
          
    elif query.data == "delallcancel":
        # ... (logic waise hi rahega) ...
        pass   

    elif query.data.startswith("stream"):
        # --- NOTE ---
        # Aapka naya system (get_{link_id}) file ko FORWARD karta hai.
        # Stream logic (jo send_cached_media use karta hai) abhi bhi kaam kar sakta hai
        # kYUNKI file_id Bot 2 (master list) se aa raha hai,
        # LEKIN aapke naye 'auto_filter' buttons ab 'stream#' callback nahi, 
        # balki 'get_{link_id}' URL use kar rahe hain.
        # Isliye yeh 'stream' code abhi 'allfiles' button ke alawa kahin aur se trigger nahi hoga.
        
        user_id = query.from_user.id
        if not await db.has_premium_access(user_id):
            # ... (premium check) ...
            return
        file_id = query.data.split('#', 1)[1]
        try:
            AKS = await client.send_cached_media(chat_id=BIN_CHANNEL, file_id=file_id)
            online = f"https://{URL}/watch/{AKS.id}?hash={get_hash(AKS)}"
            download = f"https://{URL}/{AKS.id}?hash={get_hash(AKS)}"
            btn= [[...]] # (stream buttons)
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e:
            logger.error(e)
            await query.answer(f"Error: {e}", show_alert=True)

    elif query.data == "buttons":
        await query.answer("ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇs 😊", show_alert=True)
    elif query.data == "pages":
        await query.answer("ᴛʜɪs ɪs ᴘᴀɢᴇs ʙᴜᴛᴛᴏɴ 😅")
    elif query.data.startswith("lang_art"):
        _, lang = query.data.split("#")
        await query.answer(f"ʏᴏᴜ sᴇʟᴇᴄᴛᴇᴅ {lang.title()} ʟᴀɴɢᴜᴀɢᴇ ⚡️", show_alert=True)
  
    elif query.data == "start":
        # ... (start menu logic) ...
        pass
    elif query.data == "features":
        # ... (features menu logic) ...
        pass
    elif query.data == "earn":
        # ... (earn menu logic) ...
        pass
    elif query.data == "telegraph":
        # ... (telegraph menu logic) ...
        pass
    elif query.data == "font":
        # ... (font menu logic) ...
        pass
        
    elif query.data == "buy_premium":
        # --- FIX: reply_photo use karein, edit_text nahi ---
        btn = [[
            InlineKeyboardButton('📸 sᴇɴᴅ sᴄʀᴇᴇɴsʜᴏᴛ 📸', url=USERNAME)
        ],[
            InlineKeyboardButton('🗑 ᴄʟᴏsᴇ 🗑', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(btn)
        try:
            # Message ko delete karke naya photo bhej na behtar hai
            await query.message.delete()
            await client.send_photo(
                chat_id=query.from_user.id,
                photo=(QR_CODE),
                caption=script.PREMIUM_TEXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error sending premium photo: {e}")
            # Fallback agar delete fail hota hai
            await query.message.edit_text(
                script.PREMIUM_TEXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )

    elif query.data == "all_files_delete":
        # --- BADLAAV: Yeh ab sabhi 4 search collections ko delete karega ---
        # Note: Yeh master list (files_data) ko delete NAHI karega
        await query.answer('Deleting all search indexes...')
        count1 = await MediaPrimary.count_documents()
        await MediaPrimary.collection.drop()
        count2 = await MediaSecondary.count_documents()
        await MediaSecondary.collection.drop()
        count3 = await MediaThird.count_documents()
        await MediaThird.collection.drop()
        count4 = await MediaFourth.count_documents()
        await MediaFourth.collection.drop()
        total_files = count1 + count2 + count3 + count4
        await query.message.edit_text(f"Successfully deleted {total_files} files from all 4 search indexes.")
        
    elif query.data.startswith("killfilesak"):
        # ... (Yeh logic waise hi rahega, yeh get_bad_files() se search karega) ...
        # (Lekin delete logic ko sabhi 4 Media... classes se delete karna hoga)
        pass
          
    elif query.data.startswith("reset_grp_data"):
        # ... (Yeh logic waise hi rahega) ...
        pass

    elif query.data.startswith("setgs"):
        # ... (Yeh logic waise hi rahega) ...
        pass
            
    # --- Request Channel Logic ---
    elif query.data.startswith("show_options"):
        # ... (Yeh logic waise hi rahega) ...
        pass
    elif query.data.startswith("reject"):
        # ... (Yeh logic waise hi rahega) ...
        pass
    elif query.data.startswith("accept"):
        # ... (Yeh logic waise hi rahega) ...
        pass
    # ... (Baaki saara request logic waise hi rahega) ...

    elif query.data.startswith("batchfiles"):
        ident, group_id, message_id, user = query.data.split("#")
        group_id = int(group_id)
        message_id = int(message_id)
        user = int(user)
        if user != query.from_user.id:
            await query.answer(script.ALRT_TXT, show_alert=True)
            return
        
        # --- BADLAAV: allfiles ab 'getall_' use karega link_id ke bajaye ---
        # Hum message ID ko key banakar IDs ko temp mein store karenge
        files_to_send = temp.FILES_ID.get(f"{group_id}-{message_id}")
        if not files_to_send:
            await query.answer("Batch link expired.", show_alert=True)
            return
            
        # Hum `link_id`s ki ek list banayenge
        link_ids = [file.link_id for file in files_to_send]
        
        # Hum in IDs ko database mein store karenge ek temporary ID ke saath
        # (Yeh logic Commands.py mein handle hona chahiye)
        # Abhi ke liye, hum bas 'allfiles_' trigger bhejenge
        
        # NOTE: Yeh logic `Commands.py` mein `allfiles` ke saath conflict karega.
        # Behtar hai 'batchfiles' ko `Commands.py` mein `getall_` start command trigger karne ke liye update karein.
        
        # Aasaan fix: 'allfiles_' ko trigger karein, aur Commands.py handle karega
        link = f"https://telegram.me/{temp.U_NAME}?start=allfiles_{group_id}-{message_id}"
        await query.answer(url=link)
        return

# ... (advantage_spell_chok waise hi rahega) ...

async def auto_filter(client, msg, spoll=False):
    if not spoll:
        message = msg
        search = message.text
        chat_id = message.chat.id
        settings = await get_settings(chat_id)
        files, offset, total_results = await get_search_results(search)
        if not files:
            if settings["spell_check"]:
                return await advantage_spell_chok(msg)
            return
        available_qualities = await get_available_qualities(search)
        available_years = await get_available_years(search)
    else:
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message
        search, files, offset, total_results = spoll
        available_qualities = await get_available_qualities(search)
        available_years = await get_available_years(search)

    req = message.from_user.id if message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    batch_ids = files
    temp.FILES_ID[f"{message.chat.id}-{message.id}"] = batch_ids
    batch_link = f"batchfiles#{message.chat.id}#{message.id}#{message.from_user.id}"
    pre = 'filep' if settings['file_secure'] else 'file'
    temp.CHAT[message.from_user.id] = message.chat.id
    settings = await get_settings(message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code>...</b>" if settings["auto_delete"] else ''
    links = ""
    
    # --- BADLAAV YAHAN HAI ---
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=1):
            # file.file_id ki jagah file.link_id aur "get_"
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(
                    text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", 
                    # file.file_id ki jagah file.link_id aur "get_"
                    url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'
                ),]
               for file in files
              ]
    # --- BADLAAV KHATAM ---

    # ... (Baaki saara auto_filter logic waise hi rahega) ...
    # ... (IMDB, poster, aur message bhej ne ka logic) ...
    pass

