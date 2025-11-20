import asyncio
import os
from pyrogram import filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from pyromod.types import ListenerTypes
from pyromod.listen import Client

from helpers import database
from helpers.utils import UserSettings
from bot import (
    LOGGER,
    UPLOAD_AS_DOC,
    UPLOAD_TO_DRIVE,
    delete_all,
    formatDB,
    gDict,
    queueDB,
    showQueue,
)
from plugins.mergeVideo import mergeNow
from plugins.mergeVideoAudio import mergeAudio
from plugins.mergeVideoSub import mergeSub
# Import streamsExtractor and cleanDB (Ensure streams_extractor.py is updated as per previous step)
from plugins.streams_extractor import streamsExtractor, cleanDB
from plugins.usettings import userSettings

# We will add clean_video_streams in the next step (ffmpeg_helper.py), but we import it here for the button logic
try:
    from helpers.ffmpeg_helper import clean_video_streams
except ImportError:
    pass # It will be available after you update ffmpeg_helper.py
from helpers.uploader import uploadFiles


@Client.on_callback_query()
async def callback_handler(c: Client, cb: CallbackQuery):
    
    if cb.data == "merge":
        await cb.message.edit(
            text="Where do you want to upload?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📤 To Telegram", callback_data="to_telegram"
                        ),
                        InlineKeyboardButton("🌫️ To Drive", callback_data="to_drive"),
                    ],
                    [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "to_drive":
        try:
            urc = await database.getUserRcloneConfig(cb.from_user.id)
            await c.download_media(
                message=urc, file_name=f"userdata/{cb.from_user.id}/rclone.conf"
            )
        except Exception:
            await cb.message.reply_text("Rclone not Found, Unable to upload to drive")
        if os.path.exists(f"userdata/{cb.from_user.id}/rclone.conf") is False:
            await cb.message.delete()
            await delete_all(root=f"downloads/{cb.from_user.id}/")
            queueDB.update(
                {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}}
            )
            formatDB.update({cb.from_user.id: None})
            return
        UPLOAD_TO_DRIVE.update({f"{cb.from_user.id}": True})
        await cb.message.edit(
            text="Okay I'll upload to drive\nDo you want to rename? Default file name is **[@yashoswalyo]_merged.mkv**",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("👆 Default", callback_data="rename_NO"),
                        InlineKeyboardButton("✍️ Rename", callback_data="rename_YES"),
                    ],
                    [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "to_telegram":
        UPLOAD_TO_DRIVE.update({f"{cb.from_user.id}": False})
        await cb.message.edit(
            text="How do yo want to upload file",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("🎞️ Video", callback_data="video"),
                        InlineKeyboardButton("📁 File", callback_data="document"),
                    ],
                    [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "document":
        UPLOAD_AS_DOC.update({f"{cb.from_user.id}": True})
        await cb.message.edit(
            text="Do you want to rename? Default file name is **[@yashoswalyo]_merged.mkv**",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("👆 Default", callback_data="rename_NO"),
                        InlineKeyboardButton("✍️ Rename", callback_data="rename_YES"),
                    ],
                    [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "video":
        UPLOAD_AS_DOC.update({f"{cb.from_user.id}": False})
        await cb.message.edit(
            text="Do you want to rename? Default file name is **[@yashoswalyo]_merged.mkv**",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("👆 Default", callback_data="rename_NO"),
                        InlineKeyboardButton("✍️ Rename", callback_data="rename_YES"),
                    ],
                    [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data.startswith("rclone_"):
        if "save" in cb.data:
            message_id = cb.message.reply_to_message.document.file_id
            LOGGER.info(message_id)
            await c.download_media(
                message=cb.message.reply_to_message,
                file_name=f"./userdata/{cb.from_user.id}/rclone.conf",
            )
            await database.addUserRcloneConfig(cb, message_id)
        else:
            await cb.message.delete()
        return

    elif cb.data.startswith("rename_"):
        user = UserSettings(cb.from_user.id, cb.from_user.first_name)
        if "YES" in cb.data:
            await cb.message.edit(
                "Current filename: **[@yashoswalyo]_merged.mkv**\n\nSend me new file name without extension: You have 1 minute"
            )
            res: Message = await c.listen(chat_id=cb.message.chat.id, filters=filters.text, listener_type=ListenerTypes.MESSAGE, timeout=120, user_id=cb.from_user.id)
            if res.text:
                new_file_name = f"downloads/{str(cb.from_user.id)}/{res.text}.mkv"
                await res.delete(True)
            if user.merge_mode == 1:
                await mergeNow(c, cb, new_file_name)
            elif user.merge_mode == 2:
                await mergeAudio(c, cb, new_file_name)
            elif user.merge_mode == 3:
                await mergeSub(c, cb, new_file_name)
            return

        if "NO" in cb.data:
            new_file_name = (
                f"downloads/{str(cb.from_user.id)}/[@yashoswalyo]_merged.mkv"
            )
            if user.merge_mode == 1:
                await mergeNow(c, cb, new_file_name)
            elif user.merge_mode == 2:
                await mergeAudio(c, cb, new_file_name)
            elif user.merge_mode == 3:
                await mergeSub(c, cb, new_file_name)

    elif cb.data == "cancel":
        await delete_all(root=f"downloads/{cb.from_user.id}/")
        queueDB.update({cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit("Sucessfully Cancelled")
        await asyncio.sleep(5)
        await cb.message.delete(True)
        return

    elif cb.data.startswith("gUPcancel"):
        cmf = cb.data.split("/")
        chat_id, mes_id, from_usr = cmf[1], cmf[2], cmf[3]
        if int(cb.from_user.id) == int(from_usr):
            await c.answer_callback_query(
                cb.id, text="Going to Cancel . . . 🛠", show_alert=False
            )
            gDict[int(chat_id)].append(int(mes_id))
        else:
            await c.answer_callback_query(
                callback_query_id=cb.id,
                text="⚠️ Opps ⚠️ \n I Got a False Visitor 🚸 !! \n\n 📛 Stay At Your Limits !!📛",
                show_alert=True,
                cache_time=0,
            )
        await delete_all(root=f"downloads/{cb.from_user.id}/")
        queueDB.update({cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return

    elif cb.data == "close":
        await cb.message.delete(True)
        try:
            await cb.message.reply_to_message.delete(True)
        except Exception as err:
            pass

    elif cb.data.startswith("showFileName_"):
        message_id = int(cb.data.rsplit("_", 1)[-1])
        LOGGER.info(queueDB.get(cb.from_user.id)["videos"])
        LOGGER.info(queueDB.get(cb.from_user.id)["subtitles"])
        sIndex = queueDB.get(cb.from_user.id)["videos"].index(message_id)
        m = await c.get_messages(chat_id=cb.message.chat.id, message_ids=message_id)
        if queueDB.get(cb.from_user.id)["subtitles"][sIndex] is None:
            try:
                await cb.message.edit(
                    text=f"File Name: {m.video.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "📜 Add Subtitle",
                                    callback_data=f"addSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            except Exception:
                await cb.message.edit(
                    text=f"File Name: {m.document.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "📜 Add Subtitle",
                                    callback_data=f"addSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            return
        else:
            sMessId = queueDB.get(cb.from_user.id)["subtitles"][sIndex]
            s = await c.get_messages(chat_id=cb.message.chat.id, message_ids=sMessId)
            try:
                await cb.message.edit(
                    text=f"File Name: {m.video.file_name}\n\nSubtitles: {s.document.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove File",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "❌ Remove Subtitle",
                                    callback_data=f"removeSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            except Exception:
                await cb.message.edit(
                    text=f"File Name: {m.document.file_name}\n\nSubtitles: {s.document.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove File",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "❌ Remove Subtitle",
                                    callback_data=f"removeSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            return

    elif cb.data.startswith("addSub_"):
        sIndex = int(cb.data.split(sep="_")[1])
        vMessId = queueDB.get(cb.from_user.id)["videos"][sIndex]
        rmess = await cb.message.edit(
            text=f"Send me a subtitle file, you have 1 minute",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back", callback_data=f"showFileName_{vMessId}"
                        )
                    ]
                ]
            ),
        )
        subs: Message = await c.listen(
            chat_id=cb.message.chat.id, filters=filters.document, listener_type=ListenerTypes.MESSAGE, timeout=120, user_id=cb.from_user.id
        )
        if subs is not None:
            media = subs.document or subs.video
            if media.file_name.rsplit(".")[-1] not in "srt":
                await subs.reply_text(
                    text=f"Please go back first",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🔙 Back", callback_data=f"showFileName_{vMessId}"
                                )
                            ]
                        ]
                    ),
                    quote=True,
                )
                return
            queueDB.get(cb.from_user.id)["subtitles"][sIndex] = subs.id
            await subs.reply_text(
                f"Added {subs.document.file_name}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔙 Back", callback_data=f"showFileName_{vMessId}"
                            )
                        ]
                    ]
                ),
                quote=True,
            )
            await rmess.delete(True)
            LOGGER.info("Added sub to list")
        return

    elif cb.data.startswith("removeSub_"):
        sIndex = int(cb.data.rsplit("_")[-1])
        vMessId = queueDB.get(cb.from_user.id)["videos"][sIndex]
        queueDB.get(cb.from_user.id)["subtitles"][sIndex] = None
        await cb.message.edit(
            text=f"Subtitle Removed Now go back or send next video",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back", callback_data=f"showFileName_{vMessId}"
                        )
                    ]
                ]
            ),
        )
        LOGGER.info("Sub removed from list")
        return

    elif cb.data == "back":
        await showQueue(c, cb)
        return

    elif cb.data.startswith("removeFile_"):
        sIndex = queueDB.get(cb.from_user.id)["videos"].index(
            int(cb.data.split("_", 1)[-1])
        )
        queueDB.get(cb.from_user.id)["videos"].remove(int(cb.data.split("_", 1)[-1]))
        await showQueue(c, cb)
        return

    elif cb.data.startswith("ch@ng3M0de_"):
        uid = cb.data.split("_")[1]
        user = UserSettings(int(uid), cb.from_user.first_name)
        mode = int(cb.data.split("_")[2])
        user.merge_mode = mode
        user.set()
        await userSettings(
            cb.message, int(uid), cb.from_user.first_name, cb.from_user.last_name, user
        )
        return

    elif cb.data == "tryotherbutton":
        await cb.answer(text="Try other button → ☛")
        return

    elif cb.data.startswith("toggleEdit_"):
        uid = int(cb.data.split("_")[1])
        user = UserSettings(uid, cb.from_user.first_name)
        user.edit_metadata = False if user.edit_metadata else True
        user.set()
        await userSettings(
            cb.message, uid, cb.from_user.first_name, cb.from_user.last_name, user
        )
        return

    # ============================================================
    # UPDATED EXTRACTOR & CLEANER LOGIC
    # ============================================================

    elif cb.data.startswith('extract'):
        edata = cb.data.split('_')[1]
        media_mid = int(cb.data.split('_')[2])
        try:
            if edata == 'audio':
                await streamsExtractor(c, cb, media_mid, exAudios=True)
            elif edata == 'subtitle':
                await streamsExtractor(c, cb, media_mid, exSubs=True)
            elif edata == 'all':
                # FIX: Call with both True
                await streamsExtractor(c, cb, media_mid, exAudios=True, exSubs=True)
            elif edata == 'clean':
                # FEATURE: Stream Cleaner Mode
                await streamsExtractor(c, cb, media_mid, mode="clean")
        except Exception as e:
            LOGGER.error(e)
    
    # ============================================================
    # STREAM CLEANER CHECKBOX TOGGLE
    # ============================================================
    
    elif cb.data.startswith("clean_toggle_"):
        user_id = cb.from_user.id
        idx = int(cb.data.split("_")[-1])
        
        if user_id in cleanDB:
            # Toggle Selection
            current_status = cleanDB[user_id]['streams'][idx]['selected']
            cleanDB[user_id]['streams'][idx]['selected'] = not current_status
            
            # Refresh Buttons
            await show_clean_buttons(cb.message, user_id)
        else:
            await cb.answer("Session Expired or Invalid Request", show_alert=True)

    elif cb.data == "clean_process":
        user_id = cb.from_user.id
        
        if user_id not in cleanDB:
            await cb.answer("Session Expired", show_alert=True)
            return
            
        data = cleanDB[user_id]
        input_file = data['path']
        
        # Collect indexes that are True (Selected)
        keep_indices = [idx for idx, info in data['streams'].items() if info['selected']]
        
        # Validation: At least one audio must be selected? 
        # If user unchecks ALL, we might produce a video with no audio. That is also a valid use case.
        # But let's show a warning just in case.
        if not keep_indices:
             await cb.answer("⚠️ Warning: No Audio Selected! Video will be muted.", show_alert=True)
        
        await cb.message.edit("🧹 **Cleaning Video...**\nRemoving unwanted audio streams...")
        
        try:
            # Calling the function we will add in ffmpeg_helper.py
            from helpers.ffmpeg_helper import clean_video_streams
            cleaned_path = await clean_video_streams(input_file, keep_indices, user_id)
            
            if cleaned_path:
                await cb.message.edit("📤 **Uploading Cleaned Video...**")
                await uploadFiles(c, cb, cleaned_path, 1, 1)
                
                await cb.message.delete()
                await delete_all(root=f"downloads/{str(user_id)}")
                del cleanDB[user_id]
            else:
                await cb.message.edit("❌ **Failed to clean video.**\nCheck logs.")
        except Exception as e:
             LOGGER.error(f"Clean Process Error: {e}")
             await cb.message.edit("❌ Error during processing.")

# ==================================================================
# HELPER FUNCTION FOR CLEANER BUTTONS
# ==================================================================
async def show_clean_buttons(message, user_id):
    data = cleanDB.get(user_id)
    if not data:
        return
    
    streams = data['streams']
    buttons = []
    
    # Create Checkbox Buttons
    for idx, info in streams.items():
        status = "✅" if info['selected'] else "❌"
        lang_code = info.get('lang', 'unk').upper()
        title = info.get('title', '')
        label = f"{status} {lang_code} {title}"
        
        # Callback: clean_toggle_{index}
        buttons.append([InlineKeyboardButton(label, callback_data=f"clean_toggle_{idx}")])
    
    # Control Buttons
    buttons.append([
        InlineKeyboardButton("🧹 START CLEANING", callback_data="clean_process")
    ])
    buttons.append([
        InlineKeyboardButton("⛔ Cancel", callback_data="cancel")
    ])
    
    await message.edit(
        text="**🔉 Audio Stream Remover**\n\n"
             "👇 **Tick (✅)** the audios you want to **KEEP**.\n"
             "👇 **Untick (❌)** the audios you want to **REMOVE**.\n\n"
             "_(Subtitles and Video are kept automatically)_",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
