import os
import logging
import random
import asyncio
import string
import pytz
import urllib.parse
from datetime import datetime, timedelta
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberUpdated
from database.ia_filterdb import Media, get_file_details, get_bad_files, unpack_new_file_id
from database.users_chats_db import db
from info import (
    ADMINS, LOG_CHANNEL, USERNAME, VERIFY_IMG, IS_VERIFY, FILE_CAPTION, 
    AUTH_CHANNEL, AUTH_CHANNEL_2, AUTH_CHANNEL_3, AUTH_CHANNEL_4, AUTH_CHANNEL_4_TEXT, 
    SHORTENER_WEBSITE, SHORTENER_API, SHORTENER_WEBSITE2, SHORTENER_API2, 
    SHORTENER_WEBSITE3, SHORTENER_API3, LOG_API_CHANNEL, 
    TWO_VERIFY_GAP, THIRD_VERIFY_GAP, DEFAULT_VERIFY_DURATION,
    QR_CODE, DELETE_TIME, REQUEST_CHANNEL, REFERRAL_TARGET, PREMIUM_MONTH_DURATION
)
from utils import (
    get_settings, save_group_settings, get_size, get_shortlink, 
    is_check_admin, get_status, temp, get_readable_time, 
    check_fsub_status, check_fsub_4_status, get_seconds
)
import re
import json
import base64
import aiohttp
from html import escape 

logger = logging.getLogger(__name__)

# --- FIX: Agar Script.py mein V3 text nahi hai toh V2 use karein ---
if not hasattr(script, "THIRD_VERIFICATION_TEXT"):
    logger.warning("script.THIRD_VERIFICATION_TEXT not defined. Falling back to SECOND_VERIFICATION_TEXT.")
    script.THIRD_VERIFICATION_TEXT = script.SECOND_VERIFICATION_TEXT

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client:Client, message): 
    m = message
    user_id = m.from_user.id

    # --- Referral Logic ---
    if len(m.command) == 2 and m.command[1].startswith("get_referral_"):
        try:
            chat_id_str = m.command[1].replace("get_referral_", "")
            if not chat_id_str.lstrip('-').isdigit():
                await m.reply_text("<b>Invalid referral link format.</b>")
                return
            chat_id = int(chat_id_str)
            user_mention = m.from_user.mention
            user_data = await db.get_user_data(user_id)
            if not user_data:
                await db.add_user(user_id, m.from_user.first_name)
                user_data = await db.get_user_data(user_id)

            link_data = await db.get_referral_link(user_id, chat_id)
            referral_link = link_data.get('_id') if link_data else None
            
            if not referral_link:
                link = await client.create_chat_invite_link(chat_id=chat_id, name=f"ref_{user_id}_{chat_id}", creates_join_request=False)
                referral_link = link.invite_link
                await db.update_referral_link(user_id, referral_link, chat_id)
            
            current_count = user_data.get('referral_count', 0)
            share_text = f"Join this awesome Telegram group! {referral_link}"
            encoded_share_text = urllib.parse.quote(share_text)
            
            await m.reply_text(
                text=script.REFERRAL_TXT.format(
                    user_mention=user_mention, referral_link=referral_link,
                    target=REFERRAL_TARGET, current_count=current_count
                ),
                disable_web_page_preview=False, 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Share Link 🔗", url=f"https://t.me/share/url?url={encoded_share_text}")],
                    [InlineKeyboardButton("Close ❌", callback_data="close_data")]
                ])
            )
        except ChatAdminRequired:
            await m.reply_text("<b>Bot ko 'Invite users' permission nahi hai!</b>")
        except Exception as e:
            await m.reply_text(f"<b>Referral Error:</b> <code>{e}</code>")
        return
            
    # --- 3-Step Verification Callback Logic ---
    if len(m.command) == 2 and m.command[1].startswith('notcopy'):
        try:
            _, level, userid, verify_id, file_id = m.command[1].split("_", 4)
            level = int(level)
        except Exception:
            await m.reply("<b>Link galat hai ya expire ho gaya hai.</b>")
            return
            
        user_id = int(userid)
        grp_id = temp.CHAT.get(user_id, 0)
        settings = await get_settings(grp_id)
        
        verify_duration_seconds = settings.get('verify_time', DEFAULT_VERIFY_DURATION)
        verify_gap_1_seconds = settings.get('verify_gap_1', TWO_VERIFY_GAP)
        verify_gap_2_seconds = settings.get('verify_gap_2', THIRD_VERIFY_GAP)
        
        verify_id_info = await db.get_verify_id_info(user_id, verify_id)
        
        if not verify_id_info or verify_id_info["verified"]:
            await message.reply("<b>ʟɪɴᴋ ᴇxᴘɪʀᴇᴅ ᴛʀʏ ᴀɢᴀIɴ...</b>")
            return
            
        ist_timezone = pytz.timezone('Asia/Kolkata')
        
        if level == 1:
            key = "last_verified"
            num = 1
            readable_gap_time = get_readable_time(verify_gap_1_seconds)
            caption = script.VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_gap_1_seconds == 0:
                 caption += f"\n\n<b>Step 1/3 Pura Hua!</b>\nAb agla step (V2) pura karne ke liye neeche diye gaye 'Get File' button ko dabayein."
            else:
                 caption += f"\n\n<b>Step 1/3 Pura Hua!</b>\nAapko <b>{readable_gap_time}</b> ke liye 'Gap Access 1' mil gaya hai."

        elif level == 2:
            key = "second_time_verified"
            num = 2
            readable_gap_time = get_readable_time(verify_gap_2_seconds)
            caption = script.SECOND_VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_gap_2_seconds == 0:
                 caption += f"\n\n<b>Step 2/3 Pura Hua!</b>\nAb aakhri step (V3) pura karne ke liye neeche diye gaye 'Get File' button ko dabayein."
            else:
                 caption += f"\n\n<b>Step 2/3 Pura Hua!</b>\nAapko <b>{readable_gap_time}</b> ke liye 'Gap Access 2' mil gaya hai."
        
        else: # level == 3
            key = "third_time_verified"
            num = 3
            readable_access_time = get_readable_time(verify_duration_seconds)
            caption = script.THIRD_VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_duration_seconds == 0:
                access_msg = "Ab aap <b>sirf iss file</b> ko access kar sakte hain."
            else:
                access_msg = f"Aapko <b>{readable_access_time}</b> ke liye 'Full Access' mil gaya hai."
            caption += f"\n\n{access_msg}"
        
        current_time = datetime.now(tz=ist_timezone)  
        await db.update_notcopy_user(user_id, {key:current_time}) 
        await db.update_verify_id_info(user_id, verify_id, {"verified":True})
        
        await client.send_message(settings['log'], script.VERIFIED_LOG_TEXT.format(m.from_user.mention, user_id, datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %B %Y'), num))
        
        btn = [[
            InlineKeyboardButton("✅ ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ɢᴇᴛ ꜰɪʟᴇ / ɴᴇxᴛ sᴛᴇᴘ ✅", url=f"https://telegram.me/{temp.U_NAME}?start=file_{grp_id}_{file_id}"),
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        
        await m.reply_photo(photo=(VERIFY_IMG), caption=caption, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        return 
        
    # --- Group Start ---
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        status = get_status()
        aks=await message.reply_text(f"<b>🔥 ʏᴇs {status},\nʜᴏᴡ ᴄᴀɴ ɪ ʜᴇʟᴘ ʏᴏᴜ??</b>")
        await asyncio.sleep(600)
        await aks.delete()
        await m.delete()
        if (str(message.chat.id)).startswith("-100") and not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
            try: group_link = await message.chat.export_invite_link()
            except ChatAdminRequired: group_link = "N/A (Bot is not admin)"
            user = message.from_user.mention if message.from_user else "Dear" 
            await client.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(temp.B_LINK, message.chat.title, message.chat.id, message.chat.username, group_link, total, user))       
            await db.add_chat(message.chat.id, message.chat.title)
        return 
        
    # --- PM Start ---
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.NEW_USER_TXT.format(temp.B_LINK, message.from_user.id, message.from_user.mention))
        
    if len(message.command) != 2:
        buttons = [[
            InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')
        ],[
            InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'),
            InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')
        ],[
            InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛH ʙᴏᴛ 🚫', callback_data='earn')
        ]]   
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(script.START_TXT.format(message.from_user.mention, get_status(), message.from_user.id),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return

    # --- FSub Logic (Channels 1, 2, 3) ---
    if AUTH_CHANNEL or AUTH_CHANNEL_2 or AUTH_CHANNEL_3:
        status_1, status_2, status_3 = await check_fsub_status(client, message.from_user.id)
        all_joined = (status_1 in ["MEMBER", "PENDING"] and status_2 in ["MEMBER", "PENDING"] and status_3 == "MEMBER")
        
        if not all_joined:
            btn = []
            fsub_row_1 = []
            if status_1 == "NOT_JOINED":
                try:
                    link_1 = await client.create_chat_invite_link(int(AUTH_CHANNEL), creates_join_request=True)
                    fsub_row_1.append(InlineKeyboardButton("Request Channel 1 🔗", url=link_1.invite_link))
                except Exception as e: logger.error(f"Channel 1 link error: {e}")
            if status_2 == "NOT_JOINED":
                try:
                    link_2 = await client.create_chat_invite_link(int(AUTH_CHANNEL_2), creates_join_request=True)
                    fsub_row_1.append(InlineKeyboardButton("Request Channel 2 🔗", url=link_2.invite_link))
                except Exception as e: logger.error(f"Channel 2 link error: {e}")
            if fsub_row_1: btn.append(fsub_row_1)
            
            fsub_row_2 = []
            if status_3 == "NOT_JOINED":
                try:
                    invite_link_3 = await client.export_chat_invite_link(AUTH_CHANNEL_3)
                    fsub_row_2.append(InlineKeyboardButton("Join Channel 3 🔗", url=invite_link_3))
                except Exception as e:
                    logger.error(f"Channel 3 link error (exporting link): {e}")
                    if isinstance(AUTH_CHANNEL_3, str) and AUTH_CHANNEL_3.startswith("@"):
                         fsub_row_2.append(InlineKeyboardButton("Join Channel 3 🔗", url=f"https://t.me/{AUTH_CHANNEL_3.replace('@', '')}"))
            if fsub_row_2: btn.append(fsub_row_2)

            if len(message.command) > 1 and message.command[1] != "subscribe":
                btn.append([InlineKeyboardButton("Try Again ♻️", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
            if not btn:
                await message.reply_text("<b>Error: FSub channels not configured correctly.</b>")
                return
            await message.reply_text(
                "**File lene ke liye, pehle upar diye gaye sabhi channel(s) ko join karein (ya request karein).**\n\n"
                "Sabhi steps poore karke **Try Again** button dabayein.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return

    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help", "buy_premium"]:
        if message.command[1] == "buy_premium":
            btn = [[InlineKeyboardButton('📸 sᴇɴᴅ sᴄʀᴇᴇɴsʜᴏᴛ 📸', url=USERNAME)], [InlineKeyboardButton('🗑 ᴄʟᴏsᴇ 🗑', callback_data='close_data')]]            
            await message.reply_photo(photo=(QR_CODE), caption=script.PREMIUM_TEXT.format(message.from_user.mention), reply_markup=InlineKeyboardMarkup(btn))
            return
        # Fallback to start menu
        buttons = [[InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(script.START_TXT.format(message.from_user.mention, get_status(), message.from_user.id), reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        return

    data = message.command[1]
    try:
        pre, grp_id, file_id = data.split('_', 2)
    except:
        pre, grp_id, file_id = "", 0, data
             
    user_id = m.from_user.id
    if not await db.has_premium_access(user_id):
        grp_id = int(grp_id)
        
        # --- 3-Step Verification Logic ---
        settings = await get_settings(grp_id)
        if settings.get("is_verify", IS_VERIFY):
            duration_seconds = settings.get('verify_time', DEFAULT_VERIFY_DURATION)
            gap_1_seconds = settings.get('verify_gap_1', TWO_VERIFY_GAP)
            gap_2_seconds = settings.get('verify_gap_2', THIRD_VERIFY_GAP)
            
            user_data = await db.get_notcopy_user(user_id)
            ist_timezone = pytz.timezone('Asia/Kolkata')
            v1_time = user_data["last_verified"].astimezone(ist_timezone)
            v2_time = user_data["second_time_verified"].astimezone(ist_timezone)
            v3_time = user_data["third_time_verified"].astimezone(ist_timezone)
            current_time = datetime.now(tz=ist_timezone)
            
            show_link = False
            shortener_level = 1 # Default: V1
            
            if v3_time > v1_time and v3_time > v2_time:
                time_since_v3 = (current_time - v3_time).total_seconds()
                if duration_seconds == 0: show_link = True # One-time access
                elif time_since_v3 <= duration_seconds: show_link = False # Full Access
                else: show_link = True; shortener_level = 1 # Expired, show V1
            
            elif v2_time > v1_time and v2_time > v3_time:
                time_since_v2 = (current_time - v2_time).total_seconds()
                if gap_2_seconds == 0: show_link = True; shortener_level = 3 # No Gap 2, show V3
                elif time_since_v2 <= gap_2_seconds: show_link = False # Gap 2 Access
                else: show_link = True; shortener_level = 3 # Expired, show V3
            
            elif v1_time > v2_time and v1_time > v3_time:
                time_since_v1 = (current_time - v1_time).total_seconds()
                if gap_1_seconds == 0: show_link = True; shortener_level = 2 # No Gap 1, show V2
                elif time_since_v1 <= gap_1_seconds: show_link = False # Gap 1 Access
                else: show_link = True; shortener_level = 2 # Expired, show V2
            
            else: show_link = True; shortener_level = 1 # Fresh user, show V1

            if show_link:
                verify_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
                await db.create_verify_id(user_id, verify_id)
                temp.CHAT[user_id] = grp_id
                
                verify_link_url = f"https://telegram.me/{temp.U_NAME}?start=notcopy_{shortener_level}_{user_id}_{verify_id}_{file_id}"
                verify = await get_shortlink(verify_link_url, grp_id, shortener_level)
                
                button_text = f"✅️ ᴠᴇʀɪғʏ ({shortener_level}/3) ✅️"
                buttons = [
                    [InlineKeyboardButton(text=button_text, url=verify), InlineKeyboardButton(text="⁉️ ʜᴏᴡ ᴛᴏ ᴠᴇʀɪғʏ ⁉️", url=settings['tutorial'])],
                    [InlineKeyboardButton("😁 ʙᴜʏ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏN - ɴᴏ ɴᴇᴇᴅ ᴛᴏ ᴠᴇʀɪғʏ 😁", callback_data='buy_premium')]
                ]
                reply_markup=InlineKeyboardMarkup(buttons)
                
                if shortener_level == 1: msg_text = script.VERIFICATION_TEXT
                elif shortener_level == 2: msg_text = script.SECOND_VERIFICATION_TEXT
                else: msg_text = script.THIRD_VERIFICATION_TEXT
                
                d = await m.reply_text(
                    text=msg_text.format(message.from_user.mention, get_status()),
                    protect_content = False,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                await asyncio.sleep(300); await d.delete()
                return
            
    # --- FSub 4 Logic (After verification) ---
    if not await db.has_premium_access(user_id) and AUTH_CHANNEL_4:
        fsub_4_status = await check_fsub_4_status(client, user_id)
        if fsub_4_status == "NOT_JOINED":
            try:
                invite_link = await client.create_chat_invite_link(int(AUTH_CHANNEL_4), creates_join_request=True)
                btn = [
                    [InlineKeyboardButton(f"{AUTH_CHANNEL_4_TEXT}", url=invite_link.invite_link)],
                    [InlineKeyboardButton("Try Again ♻️", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")]
                ]
                await message.reply_photo(
                    photo=(VERIFY_IMG),
                    caption=f"**Aakhri Step!**\n\nFile lene ke liye, kripya neeche diye gaye channel ko join karein. Phir 'Try Again' button dabayein.",
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.HTML
                )
                return
            except Exception as e:
                logger.error(f"FSub 4 link generation error: {e}")
                pass
            
    # --- File Sending Logic ---
    if data and data.startswith("allfiles"):
        _, key = data.split("_", 1)
        files = temp.FILES_ID.get(key)
        if not files:
            await message.reply_text("<b>⚠️ ᴀʟʟ ꜰɪʟᴇs ɴᴏᴛ ꜰᴏᴜɴᴅ ⚠️</b>")
            return
        for file in files:
            user_id= message.from_user.id 
            grp_id = temp.CHAT.get(user_id, 0) # Get grp_id from cache
            settings = await get_settings(int(grp_id))
            CAPTION = settings['caption']
            f_caption = CAPTION.format(file_name = file.file_name, file_size = get_size(file.file_size), file_caption=file.caption)
            btn=[[InlineKeyboardButton("✛ ᴡᴀᴛᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ✛", callback_data=f'stream#{file.file_id}')]]
            await client.send_cached_media(
                chat_id=message.from_user.id, file_id=file.file_id, caption=f_caption,
                protect_content=settings['file_secure'], reply_markup=InlineKeyboardMarkup(btn)
            )
            await asyncio.sleep(1) # Rate limit
        return

    files_ = await get_file_details(file_id)           
    if not files_:
        try:
            pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
            files_ = await get_file_details(file_id)
            if not files_: return await message.reply('<b>⚠️ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ⚠️</b>')
        except:
            return await message.reply('<b>⚠️ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ / ʟɪɴᴋ ᴇxᴘɪʀᴇᴅ ⚠️</b>')
            
    files = files_[0]
    settings = await get_settings(int(grp_id))
    CAPTION = settings['caption']
    f_caption = CAPTION.format(file_name = files.file_name, file_size = get_size(files.file_size), file_caption=files.caption)
    btn = [[InlineKeyboardButton("✛ ᴡᴀᴛᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ✛", callback_data=f'stream#{file_id}')]]
    d=await client.send_cached_media(
        chat_id=message.from_user.id, file_id=file_id, caption=f_caption,
        protect_content=settings['file_secure'], reply_markup=InlineKeyboardMarkup(btn)
    )
    await asyncio.sleep(3600) # 1 Hour
    await d.delete()
    await client.send_message(
        chat_id=message.from_user.id,
        text="<b>⚠️ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛᴇᴅ ᴍᴏᴠɪᴇ ꜰɪʟᴇ ɪs ᴅᴇʟᴇᴛᴇᴅ, ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ ɪɴ ʙᴏᴛ, ɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴀɢᴀɪN ᴛʜᴇɴ sᴇᴀʀᴄʜ ᴀɢᴀɪN ☺️</b>"
    )

# --- Other Commands ---
(Yahaan /delete, /settings, /set_template, /send, #request, /search, /deletefiles, /del_file, /set_caption, /set_tutorial, /set_shortner, /set_shortner_2, /set_shortner_3, /set_log_channel, /details, /set_verify_time, /set_verify_gap_1, /set_verify_gap_2, aur combined_chat_member_handler (referral) aayenge... jaisa aapne `Commands.py` mein diya tha.)
