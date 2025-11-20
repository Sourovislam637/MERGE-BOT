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
from plugins.streams_extractor import streamsExtractor
from plugins.usettings import userSettings
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
                            "To Telegram", callback_data="to_telegram"
                        ),
                        InlineKeyboardButton("To Drive", callback_data="to_drive"),
                    ],
                    [InlineKeyboardButton("Cancel", callback_data="cancel")],
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
            await cb.message.reply_text("Rclone config not found. Unable to upload.")
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
            text=(
                "Okay, I will upload to drive.\n"
                "Do you want to rename? Default file name is "
                "**[@MalluPuls]_merged.mkv**"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Use Default", callback_data="rename_NO"),
                        InlineKeyboardButton("Rename", callback_data="rename_YES"),
                    ],
                    [InlineKeyboardButton("Cancel", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "to_telegram":
        UPLOAD_TO_DRIVE.update({f"{cb.from_user.id}": False})
        await cb.message.edit(
            text="How do you want to upload file?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Video", callback_data="video"),
                        InlineKeyboardButton("File", callback_data="document"),
                    ],
                    [InlineKeyboardButton("Cancel", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "document":
        UPLOAD_AS_DOC.update({f"{cb.from_user.id}": True})
        await cb.message.edit(
            text=(
                "Do you want to rename? Default file name is "
                "**[@MalluPuls]_merged.mkv**"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Use Default", callback_data="rename_NO"),
                        InlineKeyboardButton("Rename", callback_data="rename_YES"),
                    ],
                    [InlineKeyboardButton("Cancel", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "video":
        UPLOAD_AS_DOC.update({f"{cb.from_user.id}": False})
        await cb.message.edit(
            text=(
                "Do you want to rename? Default file name is "
                "**[@MalluPuls]_merged.mkv**"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Use Default", callback_data="rename_NO"),
                        InlineKeyboardButton("Rename", callback_data="rename_YES"),
                    ],
                    [InlineKeyboardButton("Cancel", callback_data="cancel")],
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
                "Current filename: **[@MalluPuls]_merged.mkv**\n\n"
                "Send new file name without extension. You have 1 minute."
            )
            res: Message = await c.listen(
                chat_id=cb.message.chat.id,
                filters=filters.text,
                listener_type=ListenerTypes.MESSAGE,
                timeout=120,
                user_id=cb.from_user.id,
            )
            if res.text:
                new_file_name = f"downloads/{str(cb.from_user.id)}/{res.text}.mkv"
                await res.delete(True)
            else:
                new_file_name = (
                    f"downloads/{str(cb.from_user.id)}/[@MalluPuls]_merged.mkv"
                )
            if user.merge_mode == 1:
                await mergeNow(c, cb, new_file_name)
            elif user.merge_mode == 2:
                await mergeAudio(c, cb, new_file_name)
            elif user.merge_mode == 3:
                await mergeSub(c, cb, new_file_name)
            return

        if "NO" in cb.data:
            new_file_name = f"downloads/{str(cb.from_user.id)}/[@MalluPuls]_merged.mkv"
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
        await cb.message.edit("Cancelled successfully.")
        await asyncio.sleep(5)
        await cb.message.delete(True)
        return

    elif cb.data.startswith("gUPcancel"):
        cmf = cb.data.split("/")
        chat_id, mes_id, from_usr = cmf[1], cmf[2], cmf[3]
        if int(cb.from_user.id) == int(from_usr):
            await c.answer_callback_query(
                cb.id, text="Going to cancel...", show_alert=False
            )
            gDict[int(chat_id)].append(int(mes_id))
        else:
            await c.answer_callback_query(
                callback_query_id=cb.id,
                text=(
                    "You are not allowed to cancel this upload.\n"
                    "Only the original user can cancel."
                ),
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
        except Exception:
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
                    text=f"File: {m.video.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Remove",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "Add Subtitle",
                                    callback_data=f"addSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("Back", callback_data="back")],
                        ]
                    ),
                )
            except Exception:
                await cb.message.edit(
                    text=f"File: {m.document.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Remove",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "Add Subtitle",
                                    callback_data=f"addSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("Back", callback_data="back")],
                        ]
                    ),
                )
            return
        else:
            sMessId = queueDB.get(cb.from_user.id)["subtitles"][sIndex]
            s = await c.get_messages(chat_id=cb.message.chat.id, message_ids=sMessId)
            try:
                await cb.message.edit(
                    text=(
                        f"File: {m.video.file_name}\n\n"
                        f"Subtitle: {s.document.file_name}"
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Remove File",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "Remove Subtitle",
                                    callback_data=f"removeSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("Back", callback_data="back")],
                        ]
                    ),
                )
            except Exception:
                await cb.message.edit(
                    text=(
                        f"File: {m.document.file_name}\n\n"
                        f"Subtitle: {s.document.file_name}"
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Remove File",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "Remove Subtitle",
                                    callback_data=f"removeSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("Back", callback_data="back")],
                        ]
                    ),
                )
            return

    elif cb.data.startswith("addSub_"):
        sIndex = int(cb.data.split(sep="_")[1])
        vMessId = queueDB.get(cb.from_user.id)["videos"][sIndex]
        rmess = await cb.message.edit(
            text="Send a subtitle file. You have 1 minute.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Back", callback_data=f"showFileName_{vMessId}"
                        )
                    ]
                ]
            ),
        )
        subs: Message = await c.listen(
            chat_id=cb.message.chat.id,
            filters=filters.document,
            listener_type=ListenerTypes.MESSAGE,
            timeout=120,
            user_id=cb.from_user.id,
        )
        if subs is not None:
            media = subs.document or subs.video
            if media.file_name.rsplit(".")[-1] not in "srt":
                await subs.reply_text(
                    text="Only .srt subtitles are supported. Please go back.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Back", callback_data=f"showFileName_{vMessId}"
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
                                "Back", callback_data=f"showFileName_{vMessId}"
                            )
                        ]
                    ]
                ),
                quote=True,
            )
            await rmess.delete(True)
            LOGGER.info("Added subtitle to list")
        return

    elif cb.data.startswith("removeSub_"):
        sIndex = int(cb.data.rsplit("_")[-1])
        vMessId = queueDB.get(cb.from_user.id)["videos"][sIndex]
        queueDB.get(cb.from_user.id)["subtitles"][sIndex] = None
        await cb.message.edit(
            text="Subtitle removed. Go back or send next video.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Back", callback_data=f"showFileName_{vMessId}"
                        )
                    ]
                ]
            ),
        )
        LOGGER.info("Subtitle removed from list")
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
        await cb.answer(text="Use the other button.", show_alert=False)
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
    # UPDATED EXTRACTOR HANDLERS
    # ============================================================
    elif cb.data.startswith("extract_"):
        parts = cb.data.split("_")
        if len(parts) < 3:
            return
        action = parts[1]  # audio, subtitle, videosub, all, clean
        try:
            media_mid = int(parts[2])
        except ValueError:
            return

        try:
            if action == "clean":
                # Cleaner mode: download and build checklist
                await streamsExtractor(c, cb, media_mid, mode="clean")

            elif action == "videosub":
                await streamsExtractor(
                    c, cb, media_mid, mode="extract", exType="video"
                )

            elif action == "audio":
                await streamsExtractor(
                    c, cb, media_mid, mode="extract", exType="audio"
                )

            elif action == "subtitle":
                await streamsExtractor(
                    c, cb, media_mid, mode="extract", exType="subtitle"
                )

            elif action == "all":
                await streamsExtractor(c, cb, media_mid, mode="extract", exType="all")

        except Exception as e:
            LOGGER.error(f"Extract button error: {e}")
        return

    # ============================================================
    # CLEANER: TOGGLE SELECTIONS
    # ============================================================
    elif cb.data.startswith("clean_toggle_"):
        from plugins.streams_extractor import cleanDB

        user_id = cb.from_user.id
        if user_id not in cleanDB:
            await cb.answer("Session expired.", show_alert=True)
            return

        try:
            idx = int(cb.data.split("_")[-1])
        except ValueError:
            return

        data = cleanDB[user_id]
        streams = data["streams"]

        if idx not in streams:
            await cb.answer("Stream not found.", show_alert=True)
            return

        # Toggle current state
        streams[idx]["selected"] = not streams[idx]["selected"]

        # Rebuild keyboard
        keyboard = []
        for s_idx, info in streams.items():
            lang = info["lang"].upper()
            title = info["title"]
            mark = "✅" if info["selected"] else "❌"
            btn_text = f"{mark} [{lang}] {title}"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        btn_text,
                        callback_data=f"clean_toggle_{s_idx}",
                    )
                ]
            )
        keyboard.append(
            [
                InlineKeyboardButton("Process", callback_data="clean_process"),
                InlineKeyboardButton("Cancel", callback_data="cancel"),
            ]
        )

        await cb.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ============================================================
    # CLEANER: PROCESSING AND REPORTING
    # ============================================================
    elif cb.data == "clean_process":
        from plugins.streams_extractor import cleanDB
        from helpers.ffmpeg_helper import clean_video_streams

        user_id = cb.from_user.id
        if user_id not in cleanDB:
            await cb.answer("Session expired.", show_alert=True)
            return

        data = cleanDB[user_id]
        input_file = data["path"]
        all_streams = data["streams"]

        # Determine which indices to keep and which were removed
        keep_indices = [
            idx for idx, info in all_streams.items() if info["selected"]
        ]
        removed_list = [
            info["lang"].upper()
            for idx, info in all_streams.items()
            if not info["selected"]
        ]

        await cb.message.edit(
            "Cleaning video...\nRemoving unwanted audio tracks."
        )

        cleaned_path = await clean_video_streams(input_file, keep_indices, user_id)

        if not cleaned_path:
            await cb.message.edit("Cleaning failed.")
            await delete_all(root=f"downloads/{str(user_id)}")
            del cleanDB[user_id]
            return

        await cb.message.edit("Uploading cleaned video...")

        # Upload cleaned file
        await uploadFiles(c, cb, cleaned_path, 1, 1)

        # Build report caption
        caption = "**Cleaned Video Report**\n\n"
        caption += "Removed audio languages:\n"
        if removed_list:
            for lang in removed_list:
                caption += f"❌ {lang}\n"
        else:
            caption += "None (all tracks kept)\n"

        await cb.message.reply_text(caption, quote=True)

        try:
            await cb.message.delete()
        except Exception:
            pass

        await delete_all(root=f"downloads/{str(user_id)}")
        del cleanDB[user_id]
        return
