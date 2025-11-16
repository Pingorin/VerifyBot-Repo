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

# --- FIX: Naye system ke liye saare zaroori imports ---
from database.ia_filterdb import (
    Media, MediaPrimary, MediaSecondary, MediaThird, MediaFourth, FilesData,
    get_file_data_by_link_id, get_bad_files, unpack_new_file_id
)
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

# --- FIX: Agar V3 text Script.py mein nahi hai toh crash hone se bachayega ---
if not hasattr(script, "THIRD_VERIFICATION_TEXT"):
    logger.warning("script.THIRD_VERIFICATION_TEXT not defined. Falling back to SECOND_VERIFICATION_TEXT.")
    script.THIRD_VERIFICATION_TEXT = script.SECOND_VERIFICATION_TEXT


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client:Client, message): 
    m = message
    user_id = m.from_user.id

    # --- NAYA REFERRAL CODE BLOCK (Waise hi rahega) ---
    if len(m.command) == 2 and m.command[1].startswith("get_referral_"):
        try:
            chat_id_str = m.command[1].replace("get_referral_", "")
            if not chat_id_str.lstrip('-').isdigit():
                return await m.reply_text("<b>Invalid referral link format.</b>")
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
            
    # --- YEH HAI 'NOTCOPY' (FIXED - Naya 'get_' link generate karega) ---
    if len(m.command) == 2 and m.command[1].startswith('notcopy'):
        try:
            # FIX: Aakhri parameter ab 'file_id' nahi, 'link_id' hai
            _, level, userid, verify_id, link_id = m.command[1].split("_", 4)
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
            await message.reply("<b>ʟɪɴᴋ ᴇxᴘɪʀᴇᴅ ᴛʀʏ ᴀɢᴀɪN...</b>")
            return
            
        ist_timezone = pytz.timezone('Asia/Kolkata')
        
        if level == 1:
            key = "last_verified"; num = 1
            readable_gap_time = get_readable_time(verify_gap_1_seconds)
            caption = script.VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_gap_1_seconds == 0: caption += f"\n\n<b>Step 1/3 Pura Hua!</b>\nAb agla step (V2) pura karein."
            else: caption += f"\n\n<b>Step 1/3 Pura Hua!</b>\nAapko <b>{readable_gap_time}</b> ke liye 'Gap Access 1' mil gaya hai."

        elif level == 2:
            key = "second_time_verified"; num = 2
            readable_gap_time = get_readable_time(verify_gap_2_seconds)
            caption = script.SECOND_VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_gap_2_seconds == 0: caption += f"\n\n<b>Step 2/3 Pura Hua!</b>\nAb aakhri step (V3) pura karein."
            else: caption += f"\n\n<b>Step 2/3 Pura Hua!</b>\nAapko <b>{readable_gap_time}</b> ke liye 'Gap Access 2' mil gaya hai."
        
        else: # level == 3
            key = "third_time_verified"; num = 3
            readable_access_time = get_readable_time(verify_duration_seconds)
            caption = script.THIRD_VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_duration_seconds == 0: access_msg = "Ab aap <b>sirf iss file</b> ko access kar sakte hain."
            else: access_msg = f"Aapko <b>{readable_access_time}</b> ke liye 'Full Access' mil gaya hai."
            caption += f"\n\n{access_msg}"
        
        current_time = datetime.now(tz=ist_timezone)  
        await db.update_notcopy_user(user_id, {key:current_time}) 
        await db.update_verify_id_info(user_id, verify_id, {"verified":True})
        
        await client.send_message(settings['log'], script.VERIFIED_LOG_TEXT.format(m.from_user.mention, user_id, datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %B %Y'), num))
        
        # --- FIX: Naya 'get_' link generate karein ---
        btn = [[
            InlineKeyboardButton("✅ ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ɢᴇᴛ ꜰɪʟᴇ / ɴᴇxᴛ sᴛᴇᴘ ✅", url=f"https://telegram.me/{temp.U_NAME}?start=get_{link_id}"),
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        
        await m.reply_photo(photo=(VERIFY_IMG), caption=caption, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        return 
        
    # --- Group Start (Waise hi rahega) ---
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        status = get_status()
        aks=await message.reply_text(f"<b>🔥 ʏᴇs {status},\nʜᴏᴡ ᴄᴀɴ ɪ ʜᴇʟᴘ ʏᴏᴜ??</b>")
        await asyncio.sleep(600); await aks.delete(); await m.delete()
        if (str(message.chat.id)).startswith("-100") and not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
            try: group_link = await message.chat.export_invite_link()
            except ChatAdminRequired: group_link = "N/A (Bot is not admin)"
            user = message.from_user.mention if message.from_user else "Dear" 
            await client.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(temp.B_LINK, message.chat.title, message.chat.id, message.chat.username, group_link, total, user))       
            await db.add_chat(message.chat.id, message.chat.title)
        return 
        
    # --- PM Start (Waise hi rahega) ---
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
            reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        return

    # --- FSub Logic (Channels 1, 2, 3) (Waise hi rahega) ---
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

    # --- `buy_premium` etc. commands (Waise hi rahenge) ---
    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help", "buy_premium"]:
        if message.command[1] == "buy_premium":
            btn = [[InlineKeyboardButton('📸 sᴇɴᴅ sᴄʀᴇᴇɴsʜᴏᴛ 📸', url=USERNAME)],[InlineKeyboardButton('🗑 ᴄʟᴏsᴇ 🗑', callback_data='close_data')]]            
            await message.reply_photo(photo=(QR_CODE), caption=script.PREMIUM_TEXT.format(message.from_user.mention), reply_markup=InlineKeyboardMarkup(btn))
            return
        buttons = [[InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(script.START_TXT.format(message.from_user.mention, get_status(), message.from_user.id), reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        return

    # --- NAYA PERMANENT FORWARDING LOGIC ---
    
    data = message.command[1]

    if data.startswith("get_"):
        link_id = data.replace("get_", "")
        user_id = m.from_user.id
        
        # grp_id ko cache se lein (group-specific settings ke liye)
        grp_id = temp.CHAT.get(user_id, 0)
        
        if not await db.has_premium_access(user_id):
            settings = await get_settings(int(grp_id))
            
            # --- 3-STEP VERIFICATION LOGIC (Aapke Bug Fix ke saath) ---
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
                shortener_level = 1
                
                if v3_time > v1_time and v3_time > v2_time:
                    time_since_v3 = (current_time - v3_time).total_seconds()
                    if duration_seconds == 0:
                        if time_since_v3 < 60: show_link = False # 60 sec grace period
                        else: show_link = True; shortener_level = 1
                    elif time_since_v3 <= duration_seconds: show_link = False
                    else: show_link = True; shortener_level = 1
                elif v2_time > v1_time and v2_time > v3_time:
                    time_since_v2 = (current_time - v2_time).total_seconds()
                    if gap_2_seconds == 0: show_link = True; shortener_level = 3
                    elif time_since_v2 <= gap_2_seconds: show_link = False
                    else: show_link = True; shortener_level = 3
                elif v1_time > v2_time and v1_time > v3_time:
                    time_since_v1 = (current_time - v1_time).total_seconds()
                    if gap_1_seconds == 0: show_link = True; shortener_level = 2
                    elif time_since_v1 <= gap_1_seconds: show_link = False
                    else: show_link = True; shortener_level = 2
                else: show_link = True; shortener_level = 1

                if show_link:
                    verify_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
                    await db.create_verify_id(user_id, verify_id)
                    temp.CHAT[user_id] = grp_id
                    
                    # FIX: link_id ko verification link mein pass karein
                    verify_link_url = f"https://telegram.me/{temp.U_NAME}?start=notcopy_{shortener_level}_{user_id}_{verify_id}_{link_id}"
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
                        protect_content = False, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML
                    )
                    await asyncio.sleep(300); await d.delete()
                    return # Verification ke liye rokein
            
            # --- FSUB 4 CHECK (Waise hi rahega) ---
            if AUTH_CHANNEL_4:
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
        
        # --- VERIFICATION AUR FSUB PURA HUA, AB FILE FORWARD KAREIN ---
        file_data = await get_file_data_by_link_id(link_id)
        
        if not file_data:
            return await message.reply('<b>File nahi mili ya link expire ho gaya hai.</b>')
            
        try:
            await client.forward_messages(
                chat_id=message.from_user.id,
                from_chat_id=file_data.channel_id,
                message_ids=file_data.message_id
            )
        except Exception as e:
            logger.error(f"File forward error: {e}")
            await message.reply_text("<b>File forward karte waqt error aa gaya. Shayad bot us channel mein admin nahi hai.</b>")
        
        return # Kaam khatam

    # --- Puraana 'allfiles' aur 'file_' logic poori tarah delete kar diya gaya hai ---
    
    # Agar koi aur anjaana start command (jaise puraana file_... link) aata hai
    buttons = [[InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text(script.START_TXT.format(message.from_user.mention, get_status(), message.from_user.id),
        reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)


# --- /delete COMMAND (FIXED) ---
@Client.on_message(filters.command('delete'))
async def delete(bot, message):
    if message.from_user.id not in ADMINS: return
    reply = message.reply_to_message
    if not (reply and reply.media):
        await message.reply('File delete karne ke liye file par reply karein', quote=True)
        return

    msg = await message.reply("ᴘʀᴏᴄᴇssɪɴɢ...⏳", quote=True)
    
    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None: break
    else:
        await msg.edit('<b>Yeh supported file format nahi hai.</b>')
        return
    
    link_id, file_ref = unpack_new_file_id(media.file_id)
    
    # Dono database se delete karein
    try:
        # 1. Master list (files_data) se delete karein
        result1 = await FilesData.collection.delete_one({'file_id': link_id})
        
        # 2. Sabhi Search Indexes (Media...) se delete karein
        result2 = await MediaPrimary.collection.delete_many({'link_id': link_id})
        result3 = await MediaSecondary.collection.delete_many({'link_id': link_id})
        result4 = await MediaThird.collection.delete_many({'link_id': link_id})
        result5 = await MediaFourth.collection.delete_many({'link_id': link_id})
        
        deleted_count = result1.deleted_count + result2.deleted_count + result3.deleted_count + result4.deleted_count + result5.deleted_count
        
        if deleted_count > 0:
            await msg.edit(f'<b>File ko sabhi ({deleted_count}) database entries se successfully delete kar diya gaya hai 💥</b>')
        else:
            await msg.edit('<b>File database mein nahi mili.</b>')
            
    except Exception as e:
        logger.error(f"Delete error: {e}")
        await msg.edit(f"<b>Delete karte waqt error:</b> <code>{e}</code>")


# --- Baaki saare commands (/deleteall, /settings, /send, etc.) waise hi rahenge ---

@Client.on_message(filters.command('deleteall'))
async def delete_all_index(bot, message):
    if message.from_user.id not in ADMINS: return
    # FIX: Yeh ab sirf search index (Media) ko delete karega.
    # Master list (FilesData) ko delete karne ke liye alag command banayein.
    files = await Media.count_documents() 
    if int(files) == 0:
        return await message.reply_text('Search Index (DB2) mein delete karne ke liye files nahi hain.')
    btn = [[InlineKeyboardButton(text="ʏᴇs (Delete Search Index)", callback_data="all_files_delete")], [InlineKeyboardButton(text="ᴄᴀɴᴄᴇʟ", callback_data="close_data")]]
    await message.reply_text('<b>Yeh sirf DB2 (Secondary) Search Index ko delete karega.\nMaster File List (files_data) safe rahegi.\nJaari rakhein?</b>', reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command('settings'))
async def settings(client, message):
    # (Yeh poora function waise hi rahega)
    user_id = message.from_user.id if message.from_user else None
    if not user_id: return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    settings = await get_settings(grp_id)
    title = message.chat.title
    if settings is not None:
            buttons = [
                [InlineKeyboardButton('ᴀᴜᴛᴏ ꜰɪʟᴛᴇʀ', callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{grp_id}'), InlineKeyboardButton('ᴏɴ ✔️' if settings["auto_filter"] else 'ᴏғғ ✗', callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{grp_id}')],
                [InlineKeyboardButton('ꜰɪʟᴇ sᴇᴄᴜʀᴇ', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}'), InlineKeyboardButton('ᴏɴ ✔️' if settings["file_secure"] else 'ᴏғғ ✗', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}')],
                [InlineKeyboardButton('ɪᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}'), InlineKeyboardButton('ᴏɴ ✔️' if settings["imdb"] else 'ᴏғғ ✗', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}')],
                [InlineKeyboardButton('sᴘᴇʟʟ ᴄʜᴇᴄᴋ', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}'), InlineKeyboardButton('ᴏɴ ✔️' if settings["spell_check"] else 'ᴏғғ ✗', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}')],
                [InlineKeyboardButton('ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}'), InlineKeyboardButton(f'{get_readable_time(DELETE_TIME)}' if settings["auto_delete"] else 'ᴏғғ ✗', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}')],
                [InlineKeyboardButton('ʀᴇsᴜʟᴛ ᴍᴏᴅᴇ', callback_data=f'setgs#link#{settings["link"]}#{str(grp_id)}'), InlineKeyboardButton('ʟɪɴᴋ' if settings["link"] else 'ʙᴜᴛᴛᴏN', callback_data=f'setgs#link#{settings["link"]}#{str(grp_id)}')],
                [InlineKeyboardButton('ᴠᴇʀɪғʏ', callback_data=f'setgs#is_verify#{settings["is_verify"]}#{grp_id}'), InlineKeyboardButton('ᴏɴ ✔️' if settings["is_verify"] else 'ᴏғғ ✗', callback_data=f'setgs#is_verify#{settings["is_verify"]}#{grp_id}')],
                [InlineKeyboardButton('☕️ ᴄʟᴏsᴇ ☕️', callback_data='close_data')]
            ]
            await message.reply_text(
                text=f"ᴄʜᴀɴɢᴇ ʏᴏᴜʀ sᴇᴛᴛɪɴɢs ꜰᴏʀ <b>'{title}'</b> ᴀs ʏᴏᴜʀ ᴡɪsʜ ✨",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
    pass

@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    # (Yeh poora function waise hi rahega)
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    try:
        template = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("Command Incomplete!")    
    await save_group_settings(grp_id, 'template', template)
    await message.reply_text(f"Successfully changed template for {message.chat.title} to\n\n{template}", disable_web_page_preview=True)
    
@Client.on_message(filters.command("send"))
async def send_msg(bot, message):
    # (Yeh poora function waise hi rahega)
    if message.from_user.id not in ADMINS: return
    if message.reply_to_message:
        target_ids = message.text.split(" ")[1:]
        if not target_ids:
            return await message.reply_text("<b>ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴏɴᴇ ᴏʀ ᴍᴏʀᴇ ᴜꜱᴇʀ ɪᴅꜱ...</b>")
        out = "...\n"
        success_count = 0
        try:
            for target_id in target_ids:
                try:
                    user = await bot.get_users(target_id)
                    out += f"{user.id}\n"
                    await message.reply_to_message.copy(int(user.id))
                    success_count += 1
                except Exception as e:
                    out += f"‼️ ᴇʀʀᴏʀ ɪɴ ᴛʜɪꜱ ɪᴅ - <code>{target_id}</code> <code>{str(e)}</code>\n"
            await message.reply_text(f"<b>✅️ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴍᴇꜱꜱᴀɢᴇ ꜱᴇɴᴛ ɪɴ `{success_count}` ɪᴅ\n<code>{out}</code></b>")
        except Exception as e:
            await message.reply_text(f"<b>‼️ ᴇʀʀᴏʀ - <code>{e}</code></b>")
    else:
        await message.reply_text("<b>ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴀꜱ ᴀ ʀᴇᴘʟʏ...</b>")

@Client.on_message(filters.regex("#request"))
async def send_request(bot, message):
    # (Yeh poora function waise hi rahega)
    try:
        request = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("<b>‼️ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ɪs ɪɴᴄᴏᴍᴘʟᴇᴛᴇ</b>")
    buttons = [[InlineKeyboardButton('👀 ᴠɪᴇᴡ ʀᴇǫᴜᴇꜱᴛ 👀', url=f"{message.link}")], [InlineKeyboardButton('⚙ sʜᴏᴡ ᴏᴘᴛɪᴏɴ ⚙', callback_data=f'show_options#{message.from_user.id}#{message.id}')]]
    sent_request = await bot.send_message(REQUEST_CHANNEL, script.REQUEST_TXT.format(message.from_user.mention, message.from_user.id, request), reply_markup=InlineKeyboardMarkup(buttons))
    btn = [[InlineKeyboardButton('✨ ᴠɪᴇᴡ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ✨', url=f"{sent_request.link}")]]
    await message.reply_text("<b>✅ sᴜᴄᴄᴇꜱꜱғᴜʟʟʏ ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ʙᴇᴇN ᴀᴅᴅᴇᴅ...</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command("search"))
async def search_files(bot, message):
    # (Yeh poora function waise hi rahega)
    if message.from_user.id not in ADMINS: return
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE: return
    try:
        keyword = message.text.split(" ", 1)[1]
    except IndexError:
        return await message.reply_text("<b>...</b>")
    files, total = await get_bad_files(keyword) # Yeh files_search se search karega
    if int(total) == 0:
        return await message.reply_text('<i>...</i>')
    file_names = "\n\n".join(f"{index + 1}. {item['file_name']}" for index, item in enumerate(files))
    file_data = f"🚫 Your search - '{keyword}':\n\n{file_names}"    
    with open("file_names.txt", "w") as file:
        file.write(file_data)
    await message.reply_document(document="file_names.txt", caption=f"<b>♻️ ... <code>{total}</code> ꜰɪʟᴇs</b>", parse_mode=enums.ParseMode.HTML)
    os.remove("file_names.txt")

@Client.on_message(filters.command("deletefiles"))
async def deletemultiplefiles(bot, message):
    # (Yeh poora function waise hi rahega)
    if message.from_user.id not in ADMINS: return
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE: return
    try:
        keyword = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("<b>...</b>")
    files, total = await get_bad_files(keyword)
    if int(total) == 0:
        return await message.reply_text('<i>...</i>')
    btn = [[InlineKeyboardButton("ʏᴇs, ᴄᴏɴᴛɪɴᴜᴇ ✅", callback_data=f"killfilesak#{keyword}")], [InlineKeyboardButton("ɴᴏ, ᴀʙᴏʀᴛ ᴏᴘᴇʀᴀᴛɪᴏN 😢", callback_data="close_data")]]
    await message.reply_text(text=f"<b>ᴛᴏᴛᴀʟ ꜰɪʟᴇs ꜰᴏᴜɴᴅ - <code>{total}</code>\n\n(Yeh sirf search index se delete karega)</b>", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command("del_file"))
async def delete_files(bot, message):
    # (Yeh poora function waise hi rahega)
    if message.from_user.id not in ADMINS: return
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE: return
    try:
        keywords = message.text.split(" ", 1)[1].split(",")
    except IndexError:
        return await message.reply_text("<b>...</b>")   
    deleted_files_count = 0
    not_found_files = []
    for keyword in keywords:
        # Yeh sirf default (MediaSecondary) search index se delete karega
        result = await Media.collection.delete_many({'file_name': keyword.strip()})
        if result.deleted_count:
            deleted_files_count += 1
        else:
            not_found_files.append(keyword.strip())
    if deleted_files_count > 0:
        await message.reply_text(f'<b>{deleted_files_count} file successfully deleted from DB2 Search Index...</b>')
    if not_found_files:
        await message.reply_text(f'<b>Files not found in DB2 Search Index... <code>{", ".join(not_found_files)}</code></b>')

@Client.on_message(filters.command('set_caption'))
async def save_caption(client, message):
    # (Yeh poora function waise hi rahega)
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    try:
        caption = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("Command Incomplete!")
    await save_group_settings(grp_id, 'caption', caption)
    await message.reply_text(f"Successfully changed caption for {message.chat.title} to\n\n{caption}", disable_web_page_preview=True) 
    
@Client.on_message(filters.command('set_tutorial'))
async def save_tutorial(client, message):
    # (Yeh poora function waise hi rahega)
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    try:
        tutorial = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("<b>Command Incomplete!!...</b>")    
    await save_group_settings(grp_id, 'tutorial', tutorial)
    await message.reply_text(f"<b>Successfully changed tutorial for {message.chat.title} to</b>\n\n{tutorial}", disable_web_page_preview=True)
    
@Client.on_message(filters.command('set_shortner'))
async def set_shortner(c, m):
    # (Yeh poora function waise hi rahega)
    grp_id = m.chat.id
    if not await is_check_admin(c, grp_id, m.from_user.id): return
    if len(m.text.split()) < 3:
        await m.reply("<b>Use this command like this - \n\n`/set_shortner tnshort.net ...`</b>")
        return
    sts = await m.reply("<b>♻️ ᴄʜᴇᴄᴋɪɴɢ...</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    chat_type = m.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    try:
        URL = m.command[1]
        API = m.command[2]
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://{URL}/api?api={API}&url=https://telegram.dog') as resp:
                data = await resp.json()
        if data.get('status') == 'success':
            SHORT_LINK = data['shortenedUrl']
        else:
            raise Exception(f"API Error: {data.get('message', 'Unknown error')}")
            
        await save_group_settings(grp_id, 'shortner', URL)
        await save_group_settings(grp_id, 'api', API)
        await m.reply_text(f"<b><u>✅ sᴜᴄᴄᴇssꜰᴜʟʟʏ ʏᴏᴜʀ (V1) sʜᴏʀᴛɴᴇʀ ɪs ᴀᴅᴅᴇᴅ...</u></b>", quote=True)
    except Exception as e:
        await save_group_settings(grp_id, 'shortner', SHORTENER_WEBSITE)
        await save_group_settings(grp_id, 'api', SHORTENER_API)
        await m.reply_text(f"<b><u>💢 ᴇʀʀᴏʀ ᴏᴄᴄᴏᴜʀᴇᴅ!!</u>...</b>\n<code>{e}</code>", quote=True)

@Client.on_message(filters.command('set_shortner_2'))
async def set_shortner_2(c, m):
    # (Yeh poora function waise hi rahega)
    grp_id = m.chat.id
    if not await is_check_admin(c, grp_id, m.from_user.id): return
    if len(m.text.split()) < 3:
        await m.reply("<b>Use this command like this - \n\n`/set_shortner_2 tnshort.net ...`</b>")
        return
    sts = await m.reply("<b>♻️ ᴄʜᴇᴄᴋɪɴɢ...</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    chat_type = m.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    try:
        URL = m.command[1]
        API = m.command[2]
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://{URL}/api?api={API}&url=https://telegram.dog') as resp:
                data = await resp.json()
        if data.get('status') == 'success':
            SHORT_LINK = data['shortenedUrl']
        else:
            raise Exception(f"API Error: {data.get('message', 'Unknown error')}")
            
        await save_group_settings(grp_id, 'shortner_two', URL)
        await save_group_settings(grp_id, 'api_two', API)
        await m.reply_text(f"<b><u>✅ sᴜᴄᴄᴇssꜰᴜʟʟʏ ʏᴏᴜʀ (V2) sʜᴏʀᴛɴᴇʀ ɪs ᴀᴅᴅᴇᴅ...</u></b>", quote=True)
    except Exception as e:
        await save_group_settings(grp_id, 'shortner_two', SHORTENER_WEBSITE2)
        await save_group_settings(grp_id, 'api_two', SHORTENER_API2)
        await m.reply_text(f"<b><u>💢 ᴇʀʀᴏʀ ᴏᴄᴄᴏᴜʀᴇᴅ!!</u>...</b>\n<code>{e}</code>", quote=True)

@Client.on_message(filters.command('set_shortner_3'))
async def set_shortner_3(c, m):
    # (Yeh poora function waise hi rahega)
    grp_id = m.chat.id
    if not await is_check_admin(c, grp_id, m.from_user.id):
        return await m.reply_text('<b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪN ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ</b>')
    if len(m.text.split()) < 3:
        await m.reply("<b>Use this command like this - \n\n`/set_shortner_3 tnshort.net 06b2...`</b>")
        return
    sts = await m.reply("<b>♻️ ᴄʜᴇᴄᴋɪɴɢ...</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    chat_type = m.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await m.reply_text("<b>ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ɪɴ ɢʀᴏᴜᴘ...</b>")
    try:
        URL = m.command[1]
        API = m.command[2]
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://{URL}/api?api={API}&url=https://telegram.dog') as resp:
                if resp.status != 200: raise Exception(f"HTTP Error {resp.status}")
                data = await resp.json()
        
        if data.get('status') == 'success':
            SHORT_LINK = data['shortenedUrl']
        else:
            raise Exception(f"API Error: {data.get('message', 'Unknown error')}")
            
        await save_group_settings(grp_id, 'shortner_three', URL)
        await save_group_settings(grp_id, 'api_three', API)
        await m.reply_text(f"<b><u>✅ sᴜᴄᴄᴇssꜰᴜʟʟʏ ʏᴏᴜʀ (V3) sʜᴏʀᴛɴᴇʀ ɪs ᴀᴅᴅᴇᴅ</u>\n\nᴅᴇᴍᴏ - {SHORT_LINK}\n\nsɪᴛᴇ - `{URL}`\n\nᴀᴘɪ - `{API}`</b>", quote=True)
        
        user_id = m.from_user.id
        user_info = f"@{m.from_user.username}" if m.from_user.username else f"{m.from_user.mention}"
        try:
            link = (await c.get_chat(m.chat.id)).invite_link
            grp_link = f"[{m.chat.title}]({link})"
        except:
             grp_link = f"{m.chat.title} (No invite link)"
        log_message = f"#New_Shortner_Set_For_3rd_Verify\n\nName - {user_info}\nId - `{user_id}`\n\nDomain name - {URL}\nApi - `{API}`\nGroup link - {grp_link}"
        await c.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
    except Exception as e:
        await save_group_settings(grp_id, 'shortner_three', SHORTENER_WEBSITE3)
        await save_group_settings(grp_id, 'api_three', SHORTENER_API3)
        await m.reply_text(f"<b><u>💢 ᴇʀʀᴏʀ ᴏᴄᴄᴏᴜʀᴇᴅ!!</u>\n\n...[Error message]...\n\n💔 ᴇʀʀᴏʀ - <code>{e}</code></b>", quote=True)

@Client.on_message(filters.command('set_log_channel'))
async def set_log(client, message):
    # (Yeh poora function waise hi rahega)
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    if len(message.text.split()) == 1:
        await message.reply("<b>Use this command like this - \n\n`/set_log_channel -100******`</b>")
        return
    sts = await message.reply("<b>♻️ ᴄʜᴇᴄᴋɪɴɢ...</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    try:
        log = int(message.text.split(" ", 1)[1])
    except:
        return await message.reply_text("<b><u>ɪɴᴠᴀɪʟᴅ ꜰᴏʀᴍᴀᴛ!!</u>...</b>")
    try:
        t = await client.send_message(chat_id=log, text="<b>ʜᴇʏ ᴡʜᴀᴛ's ᴜᴘ!!</b>")
        await asyncio.sleep(3)
        await t.delete()
    except Exception as e:
        return await message.reply_text(f'<b><u>😐 ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜɪs ʙᴏᴛ ᴀᴅᴍɪN...</u>\n\n💔 ᴇʀʀᴏʀ - <code>{e}</code></b>')
    await save_group_settings(grp_id, 'log', log)
    await message.reply_text(f"<b>✅ sᴜᴄᴄᴇssꜰᴜʟʟʏ sᴇᴛ ʏᴏᴜʀ ʟᴏɢ ᴄʜᴀɴɴᴇʟ...</b>", disable_web_page_preview=True)

@Client.on_message(filters.command('details'))
async def all_settings(client, message):
    # (Yeh poora function waise hi rahega)
    grp_id = message.chat.id
    title = message.chat.title
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text('<b>ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪN ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ</b>')
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪɴ ɢʀᴏᴜᴘ...</b>")
    
    settings = await get_settings(grp_id)
    readable_duration = get_readable_time(settings.get('verify_time', DEFAULT_VERIFY_DURATION))
    readable_gap_1 = get_readable_time(settings.get('verify_gap_1', TWO_VERIFY_GAP))
    readable_gap_2 = get_readable_time(settings.get('verify_gap_2', THIRD_VERIFY_GAP))

    text = f"""<b><u>⚙️ ʏᴏᴜʀ sᴇᴛᴛɪɴɢs ꜰᴏʀ -</u> {title}

<u>✅️ ᴠᴇʀɪꜰʏ 1 sʜᴏʀᴛɴᴇʀ (V1)</u>
ɴᴀᴍᴇ - `{settings["shortner"]}`
ᴀᴘɪ - `{settings["api"]}`
<u>✅️ ᴠᴇʀɪꜰʏ 2 sʜᴏʀᴛɴᴇʀ (V2)</u>
ɴᴀᴍᴇ - `{settings["shortner_two"]}`
ᴀᴘɪ - `{settings["api_two"]}`
<u>✅️ ᴠᴇʀɪꜰʏ 3 sʜᴏʀᴛɴᴇʀ (V3)</u>
ɴᴀᴍᴇ - `{settings.get("shortner_three", "N/A")}`
ᴀᴘɪ - `{settings.get("api_three", "N/A")}`
<u>⏰ ᴠᴇʀɪꜰʏ ᴛɪᴍɪɴɢꜱ</u>
ɢᴀᴘ 1 (V1→V2) - `{readable_gap_1}`
ɢᴀᴘ 2 (V2→V3) - `{readable_gap_2}`
ᴅᴜʀᴀᴛɪᴏɴ (V3→End) - `{readable_duration}`
📝 ʟᴏɢ ᴄʜᴀɴɴᴇʟ ɪᴅ - `{settings['log']}`
📍 ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ - {settings['tutorial']}
🎯 ɪᴍᴅʙ ᴛᴇᴍᴘʟᴀᴛᴇ - `{settings['template']}`
📂 ꜰɪʟᴇ ᴄᴀᴘᴛɪᴏN - `{settings['caption']}`</b>"""
    
    btn = [[InlineKeyboardButton("ʀᴇꜱᴇᴛ ᴅᴀᴛᴀ", callback_data="reset_grp_data")], [InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_data")]]
    reply_markup=InlineKeyboardMarkup(btn)
    dlt=await message.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    await asyncio.sleep(300)
    await dlt.delete()

@Client.on_message(filters.command('set_verify_time'))
async def set_verify_time(client, message):
    # (Yeh poora function waise hi rahega)
    userid = message.from_user.id if message.from_user else None
    if not userid: return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    try:
        time_string = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("<b>Command poora nahi hai! (Yeh V3 ke baad ka 'Full Access' DURATION set karta hai)</b>\n\n...")
    
    seconds = await get_seconds(time_string)
    if seconds == 0 and time_string != "0" and not time_string.startswith("0"):
         return await message.reply_text("<b>Galat time format!</b>\n\n...")
    await save_group_settings(grp_id, 'verify_time', seconds)
    reply_text = f"<b>✅ 'Full Access' DURATION {message.chat.title} ke liye set ho gaya hai.</b>\n\n<b>Naya Access Time (V3 ke baad):</b> <code>{time_string}</code>\n\n..."
    await message.reply_text(reply_text)

@Client.on_message(filters.command('set_verify_gap_1'))
async def set_verify_gap_1(client, message):
    # (Yeh poora function waise hi rahega)
    userid = message.from_user.id if message.from_user else None
    if not userid: return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    try:
        time_string = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text(
            "<b>Command poora nahi hai! (Yeh V1 ke baad ka 'Gap 1 Access' DURATION set karta hai)</b>\n\n"
            "Example:\n<code>/set_verify_gap_1 10 mins</code>\n"
            "<code>/set_verify_gap_1 0</code> (V1 ke turant baad V2)"
        )
    seconds = await get_seconds(time_string)
    if seconds == 0 and time_string != "0" and not time_string.startswith("0"):
         return await message.reply_text("<b>Galat time format!</b>\n\n...")
    await save_group_settings(grp_id, 'verify_gap_1', seconds)
    reply_text = f"<b>✅ 'Gap 1 Access' DURATION {message.chat.title} ke liye set ho gaya hai.</b>\n\n<b>Naya Gap Time (V1 aur V2 ke beech):</b> <code>{time_string}</code>\n\n..."
    await message.reply_text(reply_text)

@Client.on_message(filters.command('set_verify_gap_2'))
async def set_verify_gap_2(client, message):
    # (Yeh poora function waise hi rahega)
    userid = message.from_user.id if message.from_user else None
    if not userid: return
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]: return
    grp_id = message.chat.id
    if not await is_check_admin(client, grp_id, message.from_user.id): return
    try:
        time_string = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text(
            "<b>Command poora nahi hai! (Yeh V2 ke baad ka 'Gap 2 Access' DURATION set karta hai)</b>\n\n"
            "Example:\n<code>/set_verify_gap_2 5 mins</code>\n"
            "<code>/set_verify_gap_2 0</code> (V2 ke turant baad V3)"
        )
    seconds = await get_seconds(time_string)
    if seconds == 0 and time_string != "0" and not time_string.startswith("0"):
         return await message.reply_text("<b>Galat time format!</b>\n\n...")
    await save_group_settings(grp_id, 'verify_gap_2', seconds)
    reply_text = f"<b>✅ 'Gap 2 Access' DURATION {message.chat.title} ke liye set ho gaya hai.</b>\n\n<b>Naya Gap Time (V2 aur V3 ke beech):</b> <code>{time_string}</code>\n\n..."
    await message.reply_text(reply_text)


@Client.on_chat_member_updated()
async def combined_chat_member_handler(client: Client, member: ChatMemberUpdated):
    # (Yeh poora function waise hi rahega)
    # Logic 1: FSUB Cleanup
    try:
        if str(member.chat.id) in [str(AUTH_CHANNEL), str(AUTH_CHANNEL_2), str(AUTH_CHANNEL_4)]: 
            if member.new_chat_member and member.new_chat_member.user:
                user_id = member.new_chat_member.user.id
                channel_id = member.chat.id
                new_status = member.new_chat_member.status
                if new_status not in [enums.ChatMemberStatus.RESTRICTED]:
                    if await db.is_join_request_pending(user_id, channel_id):
                        await db.remove_join_request(user_id, channel_id)
                        logger.info(f"[ADV-FSUB] User {user_id} (New Status: {new_status}) ko pending list se remove kar diya.")
    except Exception as e:
        logger.error(f"FSUB Cleanup error: {e}")
    
    # Logic 2: Referral Handler
    try:
        if (
            member.invite_link
            and member.new_chat_member
            and member.new_chat_member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.RESTRICTED]
            and (not member.old_chat_member or member.old_chat_member.status in [enums.ChatType.LEFT, enums.ChatType.BANNED]) # FIX: Status enums
        ):
            new_user_id = member.new_chat_member.user.id
            chat_id = member.chat.id
            invite_link_str = member.invite_link.invite_link
            referrer = await db.get_user_by_referral_link(invite_link_str)
            if not referrer: return
            referrer_id = referrer['referrer_id']
            if new_user_id == referrer_id: return
            if await db.has_been_referred_in_group(new_user_id, chat_id): return
                
            await db.log_referral(new_user_id, referrer_id, chat_id)
            await db.increment_referral_count(referrer_id)
            new_count = await db.get_referral_count(referrer_id)
            
            referrer_mention = ""
            try:
                referrer_user = await client.get_users(referrer_id)
                referrer_mention = referrer_user.mention
            except Exception:
                referrer_data = await db.get_user_data(referrer_id) 
                if referrer_data and 'name' in referrer_data:
                    referrer_mention = f"<a href='tg://user?id={referrer_id}'>{escape(referrer_data['name'])}</a>"
                else:
                    referrer_mention = f"<a href='tg://user?id={referrer_id}'>Referrer</a>"
            
            if new_count >= REFERRAL_TARGET:
                expiry_time = datetime.now() + timedelta(days=PREMIUM_MONTH_DURATION)
                await db.update_user_data(referrer_id, {"expiry_time": expiry_time, "referral_count": 0})
                try:
                    await client.send_message(chat_id=referrer_id, text=f"🎉 <b>Congratulations, {referrer_mention}!</b> 🎉\n\nYou have earned <b>1 Month of Free Premium Access</b>!")
                except (UserIsBlocked, PeerIdInvalid): pass
            else:
                try:
                    await client.send_message(chat_id=referrer_id, text=f"👍 <b>Referral Success!</b>\n\nUser {member.new_chat_member.user.mention} joined.\n\nYour new count is <b>{new_count} / {REFERRAL_TARGET}</b>.")
                except (UserIsBlocked, PeerIdInvalid): pass
    except Exception as e:
        logger.error(f"Referral (welcome_handler) error: {e}")

