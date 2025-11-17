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
# --- ZAROORI IMPORTS (MessageNotModified add kiya gaya hai) ---
from pyrogram.errors import ChatAdminRequired, FloodWait, UserIsBlocked, PeerIdInvalid, MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberUpdated
# --- NAYA IMPORT (get_file_details ki jagah) ---
from database.ia_filterdb import Media, get_bad_files, unpack_new_file_id, get_file_data_by_link_id
from database.users_chats_db import db
from info import (
    ADMINS, LOG_CHANNEL, USERNAME, VERIFY_IMG, IS_VERIFY, FILE_CAPTION, 
    AUTH_CHANNEL, AUTH_CHANNEL_2, 
    AUTH_CHANNEL_3, 
    AUTH_CHANNEL_4, AUTH_CHANNEL_4_TEXT, 
    SHORTENER_WEBSITE, SHORTENER_API, 
    SHORTENER_WEBSITE2, SHORTENER_API2, 
    SHORTENER_WEBSITE3, SHORTENER_API3,
    LOG_API_CHANNEL, 
    TWO_VERIFY_GAP, THIRD_VERIFY_GAP, DEFAULT_VERIFY_DURATION,
    QR_CODE, DELETE_TIME, 
    REQUEST_CHANNEL, REFERRAL_TARGET, PREMIUM_MONTH_DURATION
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

# --- Fallback (Agar V3 text Script.py mein nahi hai) ---
if not hasattr(script, "THIRD_VERIFICATION_TEXT"):
    logger.warning("script.THIRD_VERIFICATION_TEXT not defined. Falling back to SECOND_VERIFICATION_TEXT.")
    script.THIRD_VERIFICATION_TEXT = script.SECOND_VERIFICATION_TEXT

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client:Client, message): 
    m = message
    user_id = m.from_user.id

    # --- NAYA REFERRAL CODE BLOCK --
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
    # --- REFERRAL CODE KHATAM ---
            
    # --- YEH HAI 'NOTCOPY' (VERIFICATION CALLBACK) ---
    if len(m.command) == 2 and m.command[1].startswith('notcopy'):
        try:
            # Naya format: notcopy_{level}_{userid}_{verify_id}_{grp_id_str}_{link_id}
            _, level, userid, verify_id, grp_id_str, link_id = m.command[1].split("_", 5)
            level = int(level)
            user_id = int(userid)
            grp_id = int(grp_id_str)
        except Exception:
            await m.reply("<b>Link galat hai ya expire ho gaya hai.</b>")
            return
            
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
            if verify_gap_1_seconds == 0: caption += f"\n\n<b>Step 1/3 Pura Hua!</b>\nAb agla step (V2) pura karne ke liye 'Get File' button ko dabayein."
            else: caption += f"\n\n<b>Step 1/3 Pura Hua!</b>\nAapko <b>{readable_gap_time}</b> ke liye 'Gap Access 1' mil gaya hai."

        elif level == 2:
            key = "second_time_verified"
            num = 2
            readable_gap_time = get_readable_time(verify_gap_2_seconds)
            caption = script.SECOND_VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_gap_2_seconds == 0: caption += f"\n\n<b>Step 2/3 Pura Hua!</b>\nAb aakhri step (V3) pura karne ke liye 'Get File' button ko dabayein."
            else: caption += f"\n\n<b>Step 2/3 Pura Hua!</b>\nAapko <b>{readable_gap_time}</b> ke liye 'Gap Access 2' mil gaya hai."
        
        else: # level == 3
            key = "third_time_verified"
            num = 3
            readable_access_time = get_readable_time(verify_duration_seconds)
            caption = script.THIRD_VERIFY_COMPLETE_TEXT.format(message.from_user.mention)
            if verify_duration_seconds == 0: access_msg = "Ab aap <b>sirf iss file</b> ko access kar sakte hain."
            else: access_msg = f"Aapko <b>{readable_access_time}</b> ke liye 'Full Access' mil gaya hai."
            caption += f"\n\n{access_msg}"
        
        current_time = datetime.now(tz=ist_timezone)  
        await db.update_notcopy_user(user_id, {key:current_time}) 
        await db.update_verify_id_info(user_id, verify_id, {"verified":True})
        
        await client.send_message(settings['log'], script.VERIFIED_LOG_TEXT.format(m.from_user.mention, user_id, datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %B %Y'), num))
        
        # Naya "Get File" button
        btn = [[
            InlineKeyboardButton("✅ ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ɢᴇᴛ ꜰɪʟᴇ ✅", 
                url=f"https://telegram.me/{temp.U_NAME}?start=get_{grp_id_str}_{link_id}"
            ),
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        
        await m.reply_photo(
            photo=(VERIFY_IMG),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return 
        
    # --- Group Start ---
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
            # ... (Poora FSub button logic yahaan) ...
            await message.reply_text(
                "**File lene ke liye, pehle upar diye gaye sabhi channel(s) ko join karein...**",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return
    # --- FSUB LOGIC KHATAM ---

    # --- Premium/Plan button handling ---
    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help", "buy_premium"]:
        if message.command[1] == "buy_premium":
            btn = [[InlineKeyboardButton('📸 sᴇɴᴅ sᴄʀᴇᴇɴsʜᴏᴛ 📸', url=USERNAME)],[InlineKeyboardButton('🗑 ᴄʟᴏsᴇ 🗑', callback_data='close_data')]]            
            await message.reply_photo(photo=(QR_CODE), caption=script.PREMIUM_TEXT.format(message.from_user.mention), reply_markup=InlineKeyboardMarkup(btn))
            return
        # Fallback to start menu
        buttons = [[InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(script.START_TXT.format(message.from_user.mention, get_status(), message.from_user.id), reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        return

    # --- YEH POORA FILE FORWARDING LOGIC HAI (BAN-PROOF) ---
    
    data = message.command[1]

    # --- NAYA FORWARDING LOGIC (get_) ---
    if data.startswith("get_"):
        try:
            _, grp_id_str, link_id = data.split("_", 2)
            grp_id = int(grp_id_str)
        except Exception:
            await message.reply_text("<b>Link format galat hai. Group se file dobara search karein.</b>")
            return
            
        user_id = m.from_user.id
        
        if not await db.has_premium_access(user_id):
            settings = await get_settings(grp_id)
            
            # --- 3-STEP VERIFICATION LOGIC ---
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
                
                show_link, shortener_level = False, 1 # Default
                
                if v3_time > v1_time and v3_time > v2_time:
                    time_since_v3 = (current_time - v3_time).total_seconds()
                    if duration_seconds == 0: show_link = True
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
                    
                    verify_link_url = f"https://telegram.me/{temp.U_NAME}?start=notcopy_{shortener_level}_{user_id}_{verify_id}_{grp_id_str}_{link_id}"
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
                        reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML
                    )
                    await asyncio.sleep(300); await d.delete()
                    return # Verification ke liye rokein
            
            # --- FSUB 4 LOGIC (Verify ke baad) ---
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
                            reply_markup=InlineKeyboardMarkup(btn)
                        )
                        return # FSub 4 ke liye rokein
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

    # --- Puraana logic (allfiles, file_, send_cached_media) delete kar diya gaya hai ---
    
    # Fallback (Agar user koi galat link ya puraana link daalta hai)
    buttons = [[
        InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')
    ]]   
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text(script.START_TXT.format(message.from_user.mention, get_status(), message.from_user.id),
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )

# --- [Baaqi saare commands (delete, deleteall) waise hi rahenge] ---

@Client.on_message(filters.command('delete'))
async def delete(bot, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('deleteall'))
async def delete_all_index(bot, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

# --------------------------------------------------------------------------------
# --- NAYA /SETTINGS COMMAND (PM + GROUP SUPPORT) ---
# --------------------------------------------------------------------------------

@Client.on_message(filters.command('settings'))
async def settings_command(client, message):
    user_id = message.from_user.id
    chat_type = message.chat.type

    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        # --- Group Logic ---
        grp_id = message.chat.id
        if not await is_check_admin(client, grp_id, user_id):
            return await message.reply("Aap yahaan admin nahi hain.")
        
        settings = await get_settings(grp_id)
        title = message.chat.title
        buttons = await get_settings_buttons(settings, grp_id)
        await message.reply_text(
            text=f"<b>'{title}'</b> ke liye settings badlein ✨",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
    
    elif chat_type == enums.ChatType.PRIVATE:
        # --- NAYA PM LOGIC ---
        loading_msg = await message.reply("Aap jin groups mein admin hain, unhein dhoondh raha hoon...")
        
        admin_groups = []
        all_groups = await db.get_all_chats()
        
        async for group in all_groups:
            group_id = group['id']
            try:
                member = await client.get_chat_member(group_id, user_id)
                if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    admin_groups.append({'title': group['title'], 'id': group_id})
            except Exception:
                continue
        
        if not admin_groups:
            return await loading_msg.edit("Mujhe aisa koi group nahi mila jisme aap aur main, dono hain aur aap admin hain.")
        
        buttons = []
        for grp in admin_groups:
            buttons.append(
                [InlineKeyboardButton(text=grp['title'], callback_data=f"pm_settings_select#{grp['id']}")]
            )
        
        await loading_msg.edit(
            "Aap kis group ki settings badalna chahte hain, kripya chunein:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# --- NAYA HELPER FUNCTION (Settings buttons banane ke liye) ---
async def get_settings_buttons(settings, grp_id):
    buttons = [
        [
            InlineKeyboardButton('ᴀᴜᴛᴏ ꜰɪʟᴛᴇʀ', callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{grp_id}'),
            InlineKeyboardButton('ᴏɴ ✔️' if settings["auto_filter"] else 'ᴏғғ ✗', callback_data=f'setgs#auto_filter#{settings["auto_filter"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('ꜰɪʟᴇ sᴇᴄᴜʀᴇ', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}'),
            InlineKeyboardButton('ᴏɴ ✔️' if settings["file_secure"] else 'ᴏғғ ✗', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('ɪᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}'),
            InlineKeyboardButton('ᴏɴ ✔️' if settings["imdb"] else 'ᴏғғ ✗', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('sᴘᴇʟʟ ᴄʜᴇᴄᴋ', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}'),
            InlineKeyboardButton('ᴏɴ ✔️' if settings["spell_check"] else 'ᴏғғ ✗', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}'),
            InlineKeyboardButton(f'{get_readable_time(DELETE_TIME)}' if settings["auto_delete"] else 'ᴏғғ ✗', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}')
        ],
        [
            InlineKeyboardButton('ʀᴇsᴜʟᴛ ᴍᴏᴅᴇ', callback_data=f'setgs#link#{settings["link"]}#{str(grp_id)}'),
            InlineKeyboardButton('ʟɪɴᴋ' if settings["link"] else 'ʙᴜᴛᴛᴏN', callback_data=f'setgs#link#{settings["link"]}#{str(grp_id)}')
        ],
        [
            InlineKeyboardButton('ᴠᴇʀɪғʏ', callback_data=f'setgs#is_verify#{settings["is_verify"]}#{grp_id}'),
            InlineKeyboardButton('ᴏɴ ✔️' if settings["is_verify"] else 'ᴏғғ ✗', callback_data=f'setgs#is_verify#{settings["is_verify"]}#{grp_id}')
        ],
        [InlineKeyboardButton('☕️ ᴄʟᴏsᴇ ☕️', callback_data='close_data')]
    ]
    return buttons

# --- NAYA CALLBACK HANDLER (PM mein group select karne ke liye) ---
@Client.on_callback_query(filters.regex(r"^pm_settings_select#"))
async def pm_settings_select(client, query):
    user_id = query.from_user.id
    try:
        grp_id = int(query.data.split("#")[1])
    except:
        return await query.answer("Invalid group ID.", show_alert=True)
        
    if not await is_check_admin(client, grp_id, user_id):
        return await query.message.edit("Aap ab is group ke admin nahi hain.")
        
    settings = await get_settings(grp_id)
    chat = await client.get_chat(grp_id)
    title = chat.title
    
    buttons = await get_settings_buttons(settings, grp_id)
    
    await query.message.edit_text(
        text=f"Aap <b>'{title}'</b> group ki settings badal rahe hain:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )

# --- YEH HAI FIX (BUTTON CLICK HANDLE KARNE KE LIYE) ---
@Client.on_callback_query(filters.regex(r"^setgs#"))
async def setgs_callback_handler(client: Client, query: CallbackQuery):
    try:
        ident, set_type, status, grp_id = query.data.split("#")
        grp_id = int(grp_id)
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)
        return

    userid = query.from_user.id if query.from_user else None
    
    if not await is_check_admin(client, grp_id, userid):
        await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        return
        
    if status == "True":
        await save_group_settings(grp_id, set_type, False)
        await query.answer("ᴏғғ ❌")
    else:
        await save_group_settings(grp_id, set_type, True)
        await query.answer("ᴏɴ ✅")
        
    settings = await get_settings(grp_id)      
    if settings is not None:
        buttons = await get_settings_buttons(settings, grp_id) 
        reply_markup = InlineKeyboardMarkup(buttons)
        try:
            await query.message.edit_reply_markup(reply_markup)
        except MessageNotModified:
            pass
    else:
        await query.message.edit_text("<b>ꜱᴏᴍᴇᴛʜɪɴɢ ᴡᴇɴᴛ ᴡʀᴏɴɢ</b>")

# --------------------------------------------------------------------------------
# --- BAAKI COMMANDS WAISE HI RAHENGE ---
# --------------------------------------------------------------------------------

@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass
    
@Client.on_message(filters.command("send"))
async def send_msg(bot, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.regex("#request"))
async def send_request(bot, message):
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command("search"))
async def search_files(bot, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command("deletefiles"))
async def deletemultiplefiles(bot, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command("del_file"))
async def delete_files(bot, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('set_caption'))
async def save_caption(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass
    
@Client.on_message(filters.command('set_tutorial'))
async def save_tutorial(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass
    
@Client.on_message(filters.command('set_shortner'))
async def set_shortner(c, m):
    if m.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('set_shortner_2'))
async def set_shortner_2(c, m):
    if m.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('set_shortner_3'))
async def set_shortner_3(c, m):
    if m.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('set_log_channel'))
async def set_log(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('details'))
async def all_settings(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('set_verify_time'))
async def set_verify_time(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('set_verify_gap_1'))
async def set_verify_gap_1(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_message(filters.command('set_verify_gap_2'))
async def set_verify_gap_2(client, message):
    if message.from_user.id not in ADMINS: return
    # ... (poora code waise hi rahega) ...
    pass

@Client.on_chat_member_updated()
async def combined_chat_member_handler(client: Client, member: ChatMemberUpdated):
    # ... (poora code waise hi rahega) ...
    pass
