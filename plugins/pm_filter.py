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
from database.ia_filterdb import Media, get_search_results, get_bad_files, get_file_details, get_available_qualities, get_available_years

lock = asyncio.Lock()
logger = logging.getLogger(__name__)

BUTTONS = {}
FILES_ID = {}
CAP = {}

@Client.on_message(filters.private & filters.text & filters.incoming & ~filters.regex(r"^/"))
async def pm_search(client, message):
    if IS_PM_SEARCH:
        # Language check (optional, but good to have)
        if 'hindi' in message.text.lower() or 'tamil' in message.text.lower() or 'telugu' in message.text.lower() or 'malayalam' in message.text.lower() or 'kannada' in message.text.lower() or 'english' in message.text.lower() or 'gujarati' in message.text.lower(): 
            return await auto_filter(client, message)
        await auto_filter(client, message)
    else:
        await message.reply_text("<b>⚠️ ꜱᴏʀʀʏ ɪ ᴄᴀɴ'ᴛ ᴡᴏʀᴋ ɪɴ ᴘᴍ</b>")
    
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
            # ... (Admin report logic) ...
            pass # Aapka admin report logic yahaan
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
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code> ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs</b>" if settings["auto_delete"] else ''
    links = ""
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
        btn = [[InlineKeyboardButton(text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'),]
                for file in files
              ]
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
        btn.append([
            InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
            InlineKeyboardButton(f"ᴘᴀɢᴇ {math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages")
        ])
    elif off_set is None:
        btn.append([
            InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
            InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"next_{req}_{key}_{n_offset}")
        ])
    else:
        btn.append([
            InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"),
            InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
            InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"next_{req}_{key}_{n_offset}")
        ])
        
    if settings["link"]:
        await query.message.edit_text(cap + links + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
        return        
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()
    
@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):
    # ... (Yeh function Bot 1 jaisa hi rahega) ...
    _, key, offset, req = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(script.ALRT_TXT, show_alert=True)
    btn = [[InlineKeyboardButton(text=lang.title(), callback_data=f"lang_search#{lang.lower()}#{key}#0#{offset}#{req}"),] for lang in LANGUAGES]
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text("<b>ɪɴ ᴡʜɪᴄʜ ʟᴀɴɢᴜᴀɢᴇ ʏᴏᴜ ᴡᴀɴᴛ, ᴄʜᴏᴏsᴇ ʜᴇʀᴇ 👇</b>", reply_markup=InlineKeyboardMarkup(btn))

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
    settings = await get_settings(query.message.chat.id)
    temp.CHAT[query.from_user.id] = query.message.chat.id
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ...</b>" if settings["auto_delete"] else ''
    links = ""
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
        btn = [[
                InlineKeyboardButton(text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'),]
                   for file in files
              ]
        
    btn.insert(0, [
            InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ ♻️", callback_data=batch_link),
            InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium")
        ])
    
    # ... (Pagination logic) ...
    if n_offset == 0:
        btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"lang_search#{lang}#{key}#{offset- int(MAX_BTN)}#{orginal_offset}#{req}"),
             InlineKeyboardButton(f"{math.ceil(offset / int(MAX_BTN)) + 1}/{math.ceil(total / int(MAX_BTN))}", callback_data="pages",)])
    elif offset==0:
        btn.append([InlineKeyboardButton(f"{math.ceil(offset / int(MAX_BTN)) + 1}/{math.ceil(total / int(MAX_BTN))}",callback_data="pages",),
             InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"lang_search#{lang}#{key}#{n_offset}#{orginal_offset}#{req}"),])
    else:
        btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"lang_search#{lang}#{key}#{offset- int(MAX_BTN)}#{orginal_offset}#{req}"),
             InlineKeyboardButton(f"{math.ceil(offset / int(MAX_BTN)) + 1}/{math.ceil(total / int(MAX_BTN))}", callback_data="pages",),
             InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"lang_search#{lang}#{key}#{n_offset}#{orginal_offset}#{req}"),])

    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{orginal_offset}"),])
    await query.message.edit_text(cap + links + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
    
@Client.on_callback_query(filters.regex(r"^qualities#"))
async def quality_filter_cb_handler(client: Client, query: CallbackQuery):
    # ... (Yeh function Bot 1 jaisa hi rahega) ...
    _, key, offset, req = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer(script.ALRT_TXT, show_alert=True)
    search = BUTTONS.get(key)
    if not search: return await query.answer(script.OLD_ALRT_TXT, show_alert=True)
    available_qualities = await get_available_qualities(search)
    if not available_qualities or len(available_qualities) < 2: return await query.answer("No other qualities found.", show_alert=True)
    buttons = [[InlineKeyboardButton(text=q, callback_data=f"quality_set#{q}#{key}#0#{offset}#{req}")] for q in available_qualities]
    buttons.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text("<b>Select a quality to filter results:</b>", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^quality_set#"))
async def set_quality_cb_handler(client: Client, query: CallbackQuery):
    # ... (Poora function) ...
    _, quality, key, offset, original_offset, req = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer(script.ALRT_TXT, show_alert=True)
    offset = int(offset)
    search = BUTTONS.get(key)
    if not search: return await query.answer(script.OLD_ALRT_TXT, show_alert=True)

    files, n_offset, total = await get_search_results(search, offset=offset, quality=quality)
    try: n_offset = int(n_offset)
    except: n_offset = 0

    if not files:
        await query.answer(f"Sorry, no files found for '{quality}'!", show_alert=True)
        return

    temp.FILES_ID[key] = files
    batch_ids = files
    temp.FILES_ID[f"{query.message.chat.id}-{query.id}"] = batch_ids
    batch_link = f"batchfiles#{query.message.chat.id}#{query.id}#{query.from_user.id}"
    settings = await get_settings(query.message.chat.id)
    temp.CHAT[query.from_user.id] = query.message.chat.id
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ...</b>" if settings["auto_delete"] else ''
    links = ""
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
        btn = [[InlineKeyboardButton(text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'),]
                for file in files
              ]
    
    btn.insert(0,[
        InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=batch_link),
        InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium"),
    ])
    btn.append([InlineKeyboardButton("🤔 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🤔", url=settings['tutorial'])])

    # ... (Pagination logic) ...
    if 0 < offset <= int(MAX_BTN): off_set = 0
    elif offset == 0: off_set = None
    else: off_set = offset - int(MAX_BTN)

    if n_offset == 0:
        if total > int(MAX_BTN):
            btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"quality_set#{quality}#{key}#{off_set}#{original_offset}#{req}"),
                 InlineKeyboardButton(f"ᴘᴀɢᴇ {math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages")])
    elif off_set is None:
        btn.append([InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
             InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"quality_set#{quality}#{key}#{n_offset}#{original_offset}#{req}")])
    else:
        btn.append([
            InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"quality_set#{quality}#{key}#{off_set}#{original_offset}#{req}"),
            InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
            InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"quality_set#{quality}#{key}#{n_offset}#{original_offset}#{req}")
        ])

    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{original_offset}")])
    quality_cap = f"<b>📂 Results for {search} (Filtered by: {quality})</b>"
    CAP[key] = quality_cap
    
    if settings["link"]:
        await query.message.edit_text(quality_cap + links + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
    else:
        await query.message.edit_text(quality_cap + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
    await query.answer()

@Client.on_callback_query(filters.regex(r"^years#"))
async def years_cb_handler(client: Client, query: CallbackQuery):
    # ... (Yeh function Bot 1 jaisa hi rahega) ...
    _, key, offset, req = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer(script.ALRT_TXT, show_alert=True)
    search = BUTTONS.get(key)
    if not search: return await query.answer(script.OLD_ALRT_TXT, show_alert=True)
    available_years = await get_available_years(search)
    if not available_years or len(available_years) < 2: return await query.answer("No other years found.", show_alert=True)
    buttons = [[InlineKeyboardButton(text=y, callback_data=f"year_set#{y}#{key}#0#{offset}#{req}")] for y in available_years]
    buttons.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text("<b>Select a year to filter results:</b>", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^year_set#"))
async def set_year_cb_handler(client: Client, query: CallbackQuery):
    # ... (Poora function) ...
    _, year, key, offset, original_offset, req = query.data.split("#")
    if int(req) != query.from_user.id: return await query.answer(script.ALRT_TXT, show_alert=True)
    offset = int(offset)
    search = BUTTONS.get(key)
    if not search: return await query.answer(script.OLD_ALRT_TXT, show_alert=True)

    files, n_offset, total = await get_search_results(search, offset=offset, year=year)
    try: n_offset = int(n_offset)
    except: n_offset = 0

    if not files:
        await query.answer(f"Sorry, no files found for '{year}'!", show_alert=True)
        return

    temp.FILES_ID[key] = files
    batch_ids = files
    temp.FILES_ID[f"{query.message.chat.id}-{query.id}"] = batch_ids
    batch_link = f"batchfiles#{query.message.chat.id}#{query.id}#{query.from_user.id}"
    settings = await get_settings(query.message.chat.id)
    temp.CHAT[query.from_user.id] = query.message.chat.id
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ...</b>" if settings["auto_delete"] else ''
    links = ""
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
        btn = [[InlineKeyboardButton(text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'),]
                for file in files
              ]
    
    btn.insert(0,[
        InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=batch_link),
        InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium"),
    ])
    btn.append([InlineKeyboardButton("🤔 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🤔", url=settings['tutorial'])])
    
    # ... (Pagination logic) ...
    if 0 < offset <= int(MAX_BTN): off_set = 0
    elif offset == 0: off_set = None
    else: off_set = offset - int(MAX_BTN)
    if n_offset == 0:
        if total > int(MAX_BTN):
            btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"year_set#{year}#{key}#{off_set}#{original_offset}#{req}"),
                 InlineKeyboardButton(f"ᴘᴀɢᴇ {math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages")])
    elif off_set is None:
        btn.append([InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
             InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"year_set#{year}#{key}#{n_offset}#{original_offset}#{req}")])
    else:
        btn.append([
            InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"year_set#{year}#{key}#{off_set}#{original_offset}#{req}"),
            InlineKeyboardButton(f"{math.ceil(int(offset) / int(MAX_BTN)) + 1} / {math.ceil(total / int(MAX_BTN))}", callback_data="pages"),
            InlineKeyboardButton("ɴᴇxᴛ ⪼", callback_data=f"year_set#{year}#{key}#{n_offset}#{original_offset}#{req}")
        ])

    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{original_offset}")])
    year_cap = f"<b>📂 Results for {search} (Filtered by: {year})</b>"
    CAP[key] = year_cap
    
    if settings["link"]:
        await query.message.edit_text(year_cap + links + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
    else:
        await query.message.edit_text(year_cap + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
    await query.answer()

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    # ... (Yeh function Bot 1 jaisa hi rahega) ...
    _, id, user = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(script.ALRT_TXT, show_alert=True)
    movie = await get_poster(id, id=True)
    search = movie.get('title')
    await query.answer('ᴄʜᴇᴄᴋɪɴɢ ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀꜱᴇ 🌚')
    files, offset, total_results = await get_search_results(search)
    if files:
        k = (search, files, offset, total_results)
        await auto_filter(bot, query, k)
    else:
        k = await query.message.edit(script.NO_RESULT_TXT)
        await asyncio.sleep(60); await k.delete()

async def filter_non_index_callbacks(_, __, query):
    return not query.data.startswith("index")            

@Client.on_callback_query(filters.create(filter_non_index_callbacks))
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()
        try: await query.message.reply_to_message.delete()
        except: pass
          
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type
        if chat_type == enums.ChatType.PRIVATE:
            await query.message.reply_to_message.delete()
            await query.message.delete()
        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
                await query.message.delete()
                try: await query.message.reply_to_message.delete()
                except: pass
            else: await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)    
            
    # --- BOT 2 FIX: Add 'stream' logic back ---
    elif query.data.startswith("stream"):
        user_id = query.from_user.id
        if not await db.has_premium_access(user_id):
            d=await query.message.reply("<b>💔 ᴛʜɪꜱ ғᴇᴀᴛᴜʀᴇ ɪꜱ ᴏɴʟʏ ғᴏʀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ.\n\n/plan</b>")
            await asyncio.sleep(10); await d.delete()
            return
        
        # 'stream' callback_data se link_id nikalega
        try: _, link_id = query.data.split("#", 1)
        except: return await query.answer("Invalid stream link!")

        # Naya logic: link_id se file_data fetch karein
        from database.ia_filterdb import get_file_data_by_link_id
        file_data = await get_file_data_by_link_id(link_id)
        
        if not file_data:
            return await query.answer("File data not found!", show_alert=True)
            
        # Ab file_id aur file_ref ka istemaal karein
        AKS = await client.send_cached_media(
            chat_id=BIN_CHANNEL,
            file_id=file_data.file_id,
            file_ref=file_data.file_ref # file_ref add karein taaki stream reliable ho
        )
        online = f"https://{URL}/watch/{AKS.id}?hash={get_hash(AKS)}"
        download = f"https://{URL}/{AKS.id}?hash={get_hash(AKS)}"
        btn= [[
            InlineKeyboardButton("ᴡᴀᴛᴄʜ ᴏɴʟɪɴᴇ", url=online),
            InlineKeyboardButton("ꜰᴀsᴛ ᴅᴏᴡɴʟᴏᴀᴅ", url=download)
        ],[
            InlineKeyboardButton('❌ ᴄʟᴏsᴇ ❌', callback_data='close_data')
        ]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

    elif query.data == "buttons":
        await query.answer("ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇs 😊", show_alert=True)

    elif query.data == "pages":
        await query.answer("ᴛʜɪs ɪs ᴘᴀɢᴇs ʙᴜᴛᴛᴏɴ 😅")

    # ... (start, features, earn, telegraph, font, buy_premium logic waise hi rahega) ...
  
    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')
        ],[
            InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'),
            InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')
        ],[
            InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, get_status(), query.from_user.id),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )      
    elif query.data == "features":
        buttons = [[
            InlineKeyboardButton('📸 ᴛ-ɢʀᴀᴘʜ', callback_data='telegraph'),
            InlineKeyboardButton('🆎️ ғᴏɴᴛ', callback_data='font')    
        ], [ 
            InlineKeyboardButton('⋞ ʙᴀᴄᴋ', callback_data='start')
        ]] 
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(                     
            text=script.HELP_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    # ... (baaki menu buttons) ...

    # ... (all_files_delete, killfilesak, reset_grp_data, setgs logic waise hi rahega) ...
            
    # --- BOT 2 FIX: Add Request handling logic back ---
    elif query.data.startswith("show_options"):
        ident, user_id, msg_id = query.data.split("#")
        chnl_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[
            InlineKeyboardButton("✅️ ᴀᴄᴄᴇᴘᴛ ᴛʜɪꜱ ʀᴇǫᴜᴇꜱᴛ ✅️", callback_data=f"accept#{user_id}#{msg_id}")
        ],[
            InlineKeyboardButton("🚫 ʀᴇᴊᴇᴄᴛ ᴛʜɪꜱ ʀᴇǫᴜᴇꜱᴛ 🚫", callback_data=f"reject#{user_id}#{msg_id}")
        ]]
        try:
            st = await client.get_chat_member(chnl_id, userid)
            if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
                await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
            else:
                await query.answer(script.ALRT_TXT, show_alert=True)
        except pyrogram.errors.exceptions.bad_request_400.UserNotParticipant:
            await query.answer("⚠️ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀ ᴍᴇᴍʙᴇʀ ᴏꜰ ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ", show_alert=True)

    elif query.data.startswith("reject"):
        ident, user_id, msg_id = query.data.split("#")
        chnl_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[InlineKeyboardButton("✗ ʀᴇᴊᴇᴄᴛ ✗", callback_data=f"rj_alert#{user_id}")]]
        btn = [[InlineKeyboardButton("♻️ ᴠɪᴇᴡ sᴛᴀᴛᴜs ♻️", url=f"{query.message.link}")]]
        st = await client.get_chat_member(chnl_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            user = await client.get_users(user_id)
            request = query.message.text
            await query.answer("Message sent to requester")
            await query.message.edit_text(f"<s>{request}</s>")
            await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
            try:
                await client.send_message(chat_id=user_id, text="<b>sᴏʀʀʏ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ɪs ʀᴇᴊᴇᴄᴛᴇᴅ 😶</b>", reply_markup=InlineKeyboardMarkup(btn))
            except UserIsBlocked:
                await client.send_message(SUPPORT_GROUP, text=f"<b>💥 ʜᴇʟʟᴏ {user.mention},\n\nsᴏʀʀʏ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ɪs ʀᴇᴊᴇᴄᴛᴇᴅ 😶</b>", reply_markup=InlineKeyboardMarkup(btn), reply_to_message_id=int(msg_id))
        else:
            await query.answer(script.ALRT_TXT, show_alert=True)

    elif query.data.startswith("accept"):
        ident, user_id, msg_id = query.data.split("#")
        chnl_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [
            [InlineKeyboardButton("😊 ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ 😊", callback_data=f"already_available#{user_id}#{msg_id}")],
            [InlineKeyboardButton("‼️ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ‼️", callback_data=f"not_available#{user_id}#{msg_id}")],
            [InlineKeyboardButton("🥵 ᴛᴇʟʟ ᴍᴇ ʏᴇᴀʀ/ʟᴀɴɢᴜᴀɢᴇ 🥵", callback_data=f"year#{user_id}#{msg_id}")],
            [InlineKeyboardButton("🙃 ᴜᴘʟᴏᴀᴅᴇᴅ ɪɴ 1 ʜᴏᴜʀ 🙃", callback_data=f"upload_in#{user_id}#{msg_id}")],
            [InlineKeyboardButton("☇ ᴜᴘʟᴏᴀᴅᴇᴅ ☇", callback_data=f"uploaded#{user_id}#{msg_id}")]]
        try:
            st = await client.get_chat_member(chnl_id, userid)
            if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
                await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
            else:
                await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
        except pyrogram.errors.exceptions.bad_request_400.UserNotParticipant:
            await query.answer("⚠️ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀ ᴍᴇᴍʙᴇʀ ᴏꜰ ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ", show_alert=True)

    # ... (Baaki saare request handlers: "not_available", "uploaded", "already_available", "upload_in", "year", aur sabhi "_alert" handlers yahaan aayenge) ...

    elif query.data.startswith("batchfiles"):
        ident, group_id, message_id, user = query.data.split("#")
        group_id = int(group_id)
        message_id = int(message_id)
        user = int(user)
        if user != query.from_user.id:
            await query.answer(script.ALRT_TXT, show_alert=True)
            return
        # --- BOT 2 FIX: Point to self (temp.U_NAME) ---
        link = f"https://telegram.me/{temp.U_NAME}?start=allfiles_{group_id}-{message_id}"
        await query.answer(url=link)
        return

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
    temp.CHAT[message.from_user.id] = message.chat.id
    settings = await get_settings(message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ...</b>" if settings["auto_delete"] else ''
    links = ""
    if settings["link"]:
        btn = []
        for file_num, file in enumerate(files, start=1):
            # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
            links += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=get_{file.link_id}>[{get_size(file.file_size)}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file.file_name.split()))}</a></b>"""
    else:
        # --- BOT 2 FIX: Point to self (temp.U_NAME) & use link_id ---
        btn = [[InlineKeyboardButton(text=f"🔗 {get_size(file.file_size)}≽ {get_name(file.file_name)}", url=f'https://telegram.dog/{temp.U_NAME}?start=get_{file.link_id}'),]
               for file in files
              ]
    
    # ... (Insert buttons logic waise hi rahega) ...
    if offset != "":
        if total_results >= 3:
            btn.insert(0,[
                InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=batch_link),
                InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium"),
                InlineKeyboardButton("📰 ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}#0#{req}")
            ])
        else:
             btn.insert(0,[
                InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium"),
                InlineKeyboardButton("📰 ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}#0#{req}")
            ])
    else:
        if total_results >= 3:
            btn.insert(0,[
                InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=batch_link),
                InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium")
            ])
        else:
            btn.insert(0,[InlineKeyboardButton("🥇ʙᴜʏ🥇", url=f"https://t.me/{temp.U_NAME}?start=buy_premium")])

    filter_buttons = []
    if len(available_qualities) > 1:
        filter_buttons.append(InlineKeyboardButton("🎞️ Qᴜᴀʟɪᴛʏ", callback_data=f"qualities#{key}#0#{req}"))
    if len(available_years) > 1:
        filter_buttons.append(InlineKeyboardButton("📅 Yᴇᴀʀ", callback_data=f"years#{key}#0#{req}"))
    if filter_buttons:
        btn.append(filter_buttons)
    
    btn.append([InlineKeyboardButton("💰 ʀᴇꜰᴇʀ & ᴇᴀʀɴ 💰", url=f"https://t.me/{temp.U_NAME}?start=get_referral_{message.chat.id}")])
    btn.append([InlineKeyboardButton("🤔 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ 🤔", url=settings['tutorial'])])
                         
    if spoll:
        m = await msg.message.edit(f"<b><code>{search}</code> ɪs ꜰᴏᴜɴᴅ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ꜰᴏʀ ꜰɪʟᴇs 📫</b>")
        await asyncio.sleep(1.2); await m.delete()

    if offset != "":
        BUTTONS[key] = search
        btn.append([
            InlineKeyboardButton(text=f"1/{math.ceil(int(total_results) / int(MAX_BTN))}", callback_data="pages"),
            InlineKeyboardButton(text="ɴᴇxᴛ ⪼", callback_data=f"next_{req}_{key}_{offset}")
        ])
    
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    TEMPLATE = settings['template']
    if imdb:
        cap = TEMPLATE.format(query=search, title=imdb['title'], votes=imdb['votes'], aka=imdb["aka"], seasons=imdb["seasons"], box_office=imdb['box_office'], localized_title=imdb['localized_title'], kind=imdb['kind'], imdb_id=imdb["imdb_id"], cast=imdb["cast"], runtime=imdb["runtime"], countries=imdb["countries"], certificates=imdb["certificates"], languages=imdb["languages"], director=imdb["director"], writer=imdb["writer"], producer=imdb["producer"], composer=imdb["composer"], cinematographer=imdb["cinematographer"], music_team=imdb["music_team"], distributors=imdb["distributors"], release_date=imdb['release_date'], year=imdb['year'], genres=imdb['genres'], poster=imdb['poster'], plot=imdb['plot'], rating=imdb['rating'], url=imdb['url'], **locals())
    else:
        cap = f"<b>📂 ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ {search}</b>"
    
    CAP[key] = cap
    if imdb and imdb.get('poster'):
        try:
            k = await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024] + links + del_msg, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
            if settings['auto_delete']:
                await asyncio.sleep(DELETE_TIME); await k.delete()
                try: await message.delete()
                except: pass
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            k = await message.reply_photo(photo=poster, caption=cap[:1024] + links + del_msg, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn))
            if settings['auto_delete']:
                await asyncio.sleep(DELETE_TIME); await k.delete()
                try: await message.delete()
                except: pass
        except Exception as e:
            print(e)
            k = await message.reply_text(cap + links + del_msg, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
            if settings['auto_delete']:
                await asyncio.sleep(DELETE_TIME); await k.delete()
                try: await message.delete()
                except: pass
    else:
        k=await message.reply_text(text=cap + links + del_msg, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn), reply_to_message_id=message.id)
        if settings['auto_delete']:
            await asyncio.sleep(DELETE_TIME); await k.delete()
            try: await message.delete()
            except: pass

async def advantage_spell_chok(message):
    # ... (Spell check logic waise hi rahega) ...
    mv_id = message.id
    search = message.text
    chat_id = message.chat.id
    settings = await get_settings(chat_id)
    query = re.sub(r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)", "", message.text, flags=re.IGNORECASE)
    RQST = query.strip()
    query = query.strip() + " movie"
    try: movies = await get_poster(search, bulk=True)
    except:
        k = await message.reply(script.I_CUDNT.format(message.from_user.mention))
        await asyncio.sleep(60); await k.delete(); return
    if not movies:
        google = search.replace(" ", "+")
        button = [[InlineKeyboardButton("🔍 ᴄʜᴇᴄᴋ sᴘᴇʟʟɪɴɢ ᴏɴ ɢᴏᴏɢʟᴇ 🔍", url=f"https://www.google.com/search?q={google}")]]
        k = await message.reply_text(text=script.I_CUDNT.format(search), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(120); await k.delete(); return
    
    user = message.from_user.id if message.from_user else 0
    buttons = [[InlineKeyboardButton(text=movie.get('title'), callback_data=f"spol#{movie.movieID}#{user}")] for movie in movies]
    buttons.append([InlineKeyboardButton(text="🚫 ᴄʟᴏsᴇ 🚫", callback_data='close_data')])
    d = await message.reply_text(text=script.CUDNT_FND.format(message.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons), reply_to_message_id=message.id)
    await asyncio.sleep(120); await d.delete()

