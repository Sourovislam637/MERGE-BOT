import time
import os
import asyncio
import shutil
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from __init__ import LOGGER, queueDB
from bot import delete_all, gDict
from helpers.display_progress import Progress
from helpers.ffmpeg_helper import extractAudios, extractSubtitles
from helpers.uploader import uploadFiles

# Database to store user selection for cleaning (Will be used in next step)
cleanDB = {}

async def streamsExtractor(c: Client, cb: CallbackQuery, media_mid, exAudios=False, exSubs=False, mode="extract"):
    """
    Handles extracting streams (Audio/Subs) and preparing for Cleaning mode.
    """
    user_id = cb.from_user.id
    
    # Create directory for user if not exists
    if not os.path.exists(f"downloads/{str(user_id)}/"):
        os.makedirs(f"downloads/{str(user_id)}/")
    
    # Initial Status Message
    _hold = await cb.message.edit(text="🚀 **Initializing Process...**")
    
    # Get the message containing the media
    try:
        omess: Message = await c.get_messages(chat_id=user_id, message_ids=media_mid)
        media = omess.video or omess.document
        if not media:
            await _hold.edit("❌ **File not found!**\nPlease send the file again.")
            return
        LOGGER.info(f'Starting Download: {media.file_name}')
    except Exception as e:
        LOGGER.error(f"Download failed: Unable to find media {e}")
        await _hold.edit("❌ **Error:** Unable to find media.")
        return

    # Download the Video/File
    file_dl_path = None
    try:
        c_time = time.time()
        prog = Progress(user_id, c, cb.message)
        progress_msg = f"📥 **Downloading:** `{media.file_name}`"
        
        file_dl_path = await c.download_media(
            message=media,
            file_name=f"downloads/{str(user_id)}/{str(omess.id)}/vid.mkv", 
            progress=prog.progress_for_pyrogram,
            progress_args=(progress_msg, c_time),
        )
        
        if not os.path.exists(file_dl_path):
            await _hold.edit("❌ **Download Failed!**")
            return
            
        await _hold.edit(f"✅ **Downloaded Successfully:** `{media.file_name}`")
        await asyncio.sleep(2)
        
    except Exception as downloadErr:
        LOGGER.error(f"Failed to download Error: {downloadErr}")
        await _hold.edit("❌ **Download Error!**\nProcess Cancelled.")
        await asyncio.sleep(4)
        return

    # ==================================================================
    # MODE 1: EXTRACTOR (Audio / Subtitle / All)
    # ==================================================================
    if mode == "extract":
        await _hold.edit("⚙️ **Processing Streams...**")
        
        extract_dir = None
        
        # Logic for Extract ALL (Audio + Subs)
        if exAudios and exSubs:
            await _hold.edit("🔄 **Extracting ALL Streams (Audios & Subtitles)...**")
            # We run both. They usually output to the same 'extract' folder.
            # We capture the directory path from one of them.
            ad = await extractAudios(file_dl_path, user_id)
            sd = await extractSubtitles(file_dl_path, user_id)
            # If any extraction happened, set the directory
            extract_dir = ad if ad else sd
            
        # Logic for Audio Only
        elif exAudios:
            await _hold.edit("🔊 **Extracting Audios...**")
            extract_dir = await extractAudios(file_dl_path, user_id)
            
        # Logic for Subtitle Only
        elif exSubs:
            await _hold.edit("📜 **Extracting Subtitles...**")
            extract_dir = await extractSubtitles(file_dl_path, user_id)

        # Upload Logic
        if extract_dir and os.path.exists(extract_dir):
            # Count files
            files_to_upload = []
            for dirpath, _, filenames in os.walk(extract_dir):
                for f in filenames:
                    files_to_upload.append(os.path.join(dirpath, f))
            
            total_files = len(files_to_upload)
            
            if total_files > 0:
                await _hold.edit(f"📤 **Uploading {total_files} Extracted Files...**")
                
                for i, up_path in enumerate(files_to_upload):
                    await uploadFiles(
                        c=c,
                        cb=cb,
                        up_path=up_path,
                        n=i+1,
                        all=total_files,
                    )
                    LOGGER.info(f"Uploaded: {up_path}")
                
                await _hold.delete()
                await cb.message.reply_text(
                    f"✅ **Extraction Completed!**\n📁 Files: {total_files}\n🎥 Source: `{media.file_name}`", 
                    quote=True
                )
            else:
                await _hold.edit("⚠️ **No Streams Found!**\n(The file might not have any tracks of that type).")
        else:
            await _hold.edit("❌ **Extraction Failed!**\nCould not extract any streams.")

    # ==================================================================
    # MODE 2: CLEANER (Structure ready for next step)
    # ==================================================================
    elif mode == "clean":
        # We will implement the logic here in the next steps as you requested.
        # This placeholder ensures the code doesn't break if called.
        await _hold.edit("🚧 **Cleaner Mode Loading...** (Next Step)")
        pass

    # Cleanup: Delete downloaded files to save space
    await delete_all(root=f"downloads/{str(user_id)}")
    
    # Reset Queue DB if needed
    queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
    
    return
