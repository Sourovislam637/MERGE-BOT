import time
import os
import asyncio
import shutil

from pyrogram import Client
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from __init__ import LOGGER, queueDB
from bot import delete_all, gDict
from helpers.display_progress import Progress
from helpers.ffmpeg_helper import (
    extractAudios,
    extractSubtitles,
    extract_video_with_subs,
    get_audio_streams,
    clean_video_streams,
)
from helpers.uploader import uploadFiles

# Database for cleaner (per user)
# cleanDB[user_id] = {
#     "path": "<downloaded_file_path>",
#     "streams": {
#         index: {"lang": "...", "title": "...", "selected": True/False}
#     }
# }
cleanDB = {}


async def streamsExtractor(
    c: Client,
    cb: CallbackQuery,
    media_mid,
    mode: str = "extract",
    exType: str | None = None,
):
    """
    Main entry for stream extraction and cleaner.

    :param c: Pyrogram client
    :param cb: callback query
    :param media_mid: message id of the media to process
    :param mode: 'extract' or 'clean'
    :param exType: when mode == 'extract':
                   'audio' | 'subtitle' | 'video' | 'all'
    """
    user_id = cb.from_user.id

    # Ensure download directory
    base_dir = f"downloads/{str(user_id)}/"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    hold_msg = await cb.message.edit(text="Initializing...")

    # -------------------------------------------------------------------------
    # Fetch original message and media
    # -------------------------------------------------------------------------
    try:
        omess: Message = await c.get_messages(chat_id=user_id, message_ids=media_mid)
        media = omess.video or omess.document
        if not media:
            await hold_msg.edit("File not found.")
            return
    except Exception as e:
        LOGGER.error(f"Error while fetching media: {e}")
        await hold_msg.edit("Error: unable to fetch media.")
        return

    # -------------------------------------------------------------------------
    # Download media once (used by both extract and cleaner)
    # -------------------------------------------------------------------------
    file_dl_path = None
    try:
        c_time = time.time()
        prog = Progress(user_id, c, cb.message)
        file_dl_path = await c.download_media(
            message=media,
            file_name=f"{base_dir}{str(omess.id)}/vid.mkv",
            progress=prog.progress_for_pyrogram,
            progress_args=(f"Downloading: `{media.file_name}`", c_time),
        )
        if not os.path.exists(file_dl_path):
            await hold_msg.edit("Download failed.")
            return
        await hold_msg.edit("Download complete. Processing...")
    except Exception as e:
        LOGGER.error(f"Download error: {e}")
        await hold_msg.edit("Error: download failed.")
        return

    # =========================================================================
    # MODE: EXTRACT (Audio / Subtitle / Video(+Subs) / ALL)
    # =========================================================================
    if mode == "extract":
        extracted_files: list[str] = []

        # 1. Extract audios
        if exType in ["audio", "all"]:
            await hold_msg.edit("Extracting audio streams...")
            a_dir = await extractAudios(file_dl_path, user_id)
            if a_dir:
                for root, _, files in os.walk(a_dir):
                    for f in files:
                        extracted_files.append(os.path.join(root, f))

        # 2. Extract subtitles
        if exType in ["subtitle", "all"]:
            await hold_msg.edit("Extracting subtitle streams...")
            s_dir = await extractSubtitles(file_dl_path, user_id)
            if s_dir:
                for root, _, files in os.walk(s_dir):
                    for f in files:
                        extracted_files.append(os.path.join(root, f))

        # 3. Extract Video (+Subs, no audio)
        if exType in ["video", "all"]:
            await hold_msg.edit("Preparing video with subtitles (no audio)...")
            v_path = await extract_video_with_subs(file_dl_path, user_id)
            if v_path:
                extracted_files.append(v_path)

        # Upload all extracted files
        if extracted_files:
            total = len(extracted_files)
            await hold_msg.edit(f"Uploading {total} file(s)...")
            for i, f_path in enumerate(extracted_files, start=1):
                await uploadFiles(c, cb, f_path, i, total)

            try:
                await hold_msg.delete()
            except Exception:
                pass

            await cb.message.reply_text(
                f"Task completed.\nMode: {exType.upper() if exType else 'UNKNOWN'}",
                quote=True,
            )
        else:
            await hold_msg.edit("No streams extracted.")

        # Cleanup for extract mode
        await delete_all(root=f"downloads/{str(user_id)}")
        queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
        return

    # =========================================================================
    # MODE: CLEANER (Build audio checklist and store in cleanDB)
    # =========================================================================
    elif mode == "clean":
        # Probe audio streams
        audio_streams = await get_audio_streams(file_dl_path)
        if not audio_streams:
            await hold_msg.edit("No audio streams found for cleaning.")
            # Cleanup since cleaner will not proceed
            await delete_all(root=f"downloads/{str(user_id)}")
            return

        # Build cleanDB entry
        streams_map = {}
        for s in audio_streams:
            idx = s["index"]
            streams_map[idx] = {
                "lang": s["lang"],
                "title": s["title"],
                "selected": True,  # default: keep all
            }

        cleanDB[user_id] = {
            "path": file_dl_path,
            "streams": streams_map,
        }

        # Build inline keyboard with toggles
        keyboard = []
        for idx, info in streams_map.items():
            lang = info["lang"].upper()
            title = info["title"]
            mark = "✅" if info["selected"] else "❌"
            btn_text = f"{mark} [{lang}] {title}"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        btn_text,
                        callback_data=f"clean_toggle_{idx}",
                    )
                ]
            )

        # Process / cancel row
        keyboard.append(
            [
                InlineKeyboardButton("Process", callback_data="clean_process"),
                InlineKeyboardButton("Cancel", callback_data="cancel"),
            ]
        )

        await hold_msg.edit(
            text=(
                "Stream cleaner mode.\n\n"
                "Tap on the buttons below to enable or disable audio tracks.\n"
                "Video and subtitles will always be kept.\n\n"
                "When you are done, press Process."
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        # Note: cleanup for cleaner mode is done in clean_process (cb_handler)
        return
