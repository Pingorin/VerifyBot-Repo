import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import ADMINS, LOG_CHANNEL, CHANNELS
from database.ia_filterdb import save_file 
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp, get_readable_time
import re, time

lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    # ... (Yeh function waise hi rahega) ...
    data = query.data.split("#")
    ident = data[1]
    
    if ident == 'yes':
        db_choice = data[2]
        chat = data[3]
        lst_msg_id = data[4]
        skip = data[5]
        
        msg = query.message
        await msg.edit(f"<b>Indexing to `{db_choice}` database started...</b>") 
        try: chat = int(chat)
        except: chat = chat
        await index_files_to_db(int(lst_msg_id), chat, msg, bot, int(skip), db_choice)
        
    elif ident == 'cancel':
        temp.CANCEL = True
        await query.message.edit("Trying to cancel Indexing...")


@Client.on_message(filters.command('index') & filters.private & filters.incoming & filters.user(ADMINS))
async def send_for_index(bot, message):
    if lock.locked():
        return await message.reply('Wait until previous process complete.')
    i = await message.reply("Forward last message or send last message link.")
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await i.delete()
    if msg.text and msg.text.startswith("https://t.me"):
        try:
            msg_link = msg.text.split("/")
            last_msg_id = int(msg_link[-1])
            chat_id = msg_link[-2]
            if chat_id.isnumeric(): chat_id = int(("-100" + chat_id))
        except: return await message.reply('Invalid message link!')
    
    # --- YEH HAI FIX (Deprecation Warning ke liye) ---
    elif msg.forward_origin and msg.forward_origin.type == enums.MessageOriginType.CHANNEL:
        last_msg_id = msg.forward_origin.message_id
        chat_id = msg.forward_origin.chat.username or msg.forward_origin.chat.id
    # --- FIX KHATAM ---
    
    else:
        return await message.reply('This is not forwarded message or link.')
    
    try: chat = await bot.get_chat(chat_id)
    except Exception as e: return await message.reply(f'Errors - {e}')
    if chat.type != enums.ChatType.CHANNEL: return await message.reply("I can index only channels.")
    
    s = await message.reply("Send skip message number.")
    msg = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id)
    await s.delete()
    try: skip = int(msg.text)
    except: return await message.reply("Number is invalid.")
    
    buttons = [[
        InlineKeyboardButton('📥 Index to Primary DB 1', callback_data=f'index#yes#primary#{chat_id}#{last_msg_id}#{skip}')
    ],[
        InlineKeyboardButton('💾 Index to Secondary DB 2', callback_data=f'index#yes#secondary#{chat_id}#{last_msg_id}#{skip}')
    ],[
        InlineKeyboardButton('🗃️ Index to Third DB 3', callback_data=f'index#yes#third#{chat_id}#{last_msg_id}#{skip}')
    ],[
        InlineKeyboardButton('🗄️ Index to Fourth DB 4', callback_data=f'index#yes#fourth#{chat_id}#{last_msg_id}#{skip}')
    ],[
        InlineKeyboardButton('❌ Cancel', callback_data='close_data'),
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply(
        f'**Channel:** {chat.title}\n'
        f'**Total Messages:** <code>{last_msg_id}</code>\n'
        f'**Skip Messages:** <code>{skip}</code>\n\n'
        '**Please select the database to save these files:**',
        reply_markup=reply_markup
    )

@Client.on_message(filters.command('channel'))
async def channel_info(bot, message):
    # ... (Yeh function waise hi rahega) ...
    if message.from_user.id not in ADMINS: return
    ids = CHANNELS
    if not ids: return await message.reply("Not set CHANNELS")
    text = '**Indexed Channels:**\n\n'
    for id in ids:
        try:
            chat = await bot.get_chat(id)
            text += f'{chat.title}\n'
        except:
            text += f"Couldn't get info for `{id}` (Maybe bot is not in chat)\n"
    text += f'\n**Total:** {len(ids)}'
    await message.reply(text)


async def index_files_to_db(lst_msg_id, chat, msg, bot, skip, db_choice):
    # ... (Yeh function waise hi rahega) ...
    start_time = time.time()
    total_files, duplicate, errors, deleted, no_media, unsupported = 0, 0, 0, 0, 0, 0
    current = skip
    
    async with lock:
        try:
            async for message in bot.iter_messages(chat, lst_msg_id, skip):
                time_taken = get_readable_time(time.time()-start_time)
                if temp.CANCEL:
                    temp.CANCEL = False
                    await msg.edit(f"Successfully Cancelled!\nCompleted in {time_taken}\n\nSaved <code>{total_files}</code> files to DB: `{db_choice}`!\nDuplicate: <code>{duplicate}</code>\nDeleted: <code>{deleted}</code>\nNon-Media: <code>{no_media + unsupported}</code>\nErrors: <code>{errors}</code>")
                    return
                
                current += 1
                if current % 30 == 0:
                    btn = [[InlineKeyboardButton('CANCEL', callback_data=f'index#cancel')]]
                    await msg.edit_text(text=f"DB: `{db_choice}`\nTotal: <code>{current}</code>\nSaved: <code>{total_files}</code>\nDuplicate: <code>{duplicate}</code>\nDeleted: <code>{deleted}</code>\nNon-Media: <code>{no_media + unsupported}</code>\nErrors: <code>{errors}</code>", reply_markup=InlineKeyboardMarkup(btn))
                
                if message.empty: deleted += 1; continue
                elif not message.media: no_media += 1; continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]: unsupported += 1; continue
                
                media = getattr(message, message.media.value, None)
                if not media: unsupported += 1; continue
                elif media.mime_type not in ['video/mp4', 'video/x-matroska']: unsupported += 1; continue
                
                # (Yeh pehle se hi theek hai)
                media.caption = message.caption
                media.message_id = message.id
                media.channel_id = message.chat.id
                
                sts = await save_file(media, db_choice)
                
                if sts == 'suc': total_files += 1
                elif sts == 'dup': duplicate += 1
                elif sts == 'err': errors += 1
        except Exception as e:
            await msg.reply(f'Index canceled due to Error - {e}')
        else:
            time_taken = get_readable_time(time.time()-start_time)
            await msg.edit(f'Succesfully saved <code>{total_files}</code> to DB: `{db_choice}`!\nCompleted in {time_taken}\n\nDuplicate: <code>{duplicate}</code>\nDeleted: <code>{deleted}</code>\nNon-Media: <code>{no_media + unsupported}</code>\nErrors: <code>{errors}</code>')
