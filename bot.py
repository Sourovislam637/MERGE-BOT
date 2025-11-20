from dotenv import load_dotenv
from web_server import keep_alive

load_dotenv(
    "config.env",
    override=True,
)
import asyncio
import os
import shutil
import time

import psutil
import pyromod
from PIL import Image
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    FloodWait,
    InputUserDeactivated,
    PeerIdInvalid,
    UserIsBlocked,
)
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
)

from __init__ import (
    AUDIO_EXTENSIONS,
    BROADCAST_MSG,
    LOGGER,
    MERGE_MODE,
    SUBTITLE_EXTENSIONS,
    UPLOAD_AS_DOC,
    UPLOAD_TO_DRIVE,
    VIDEO_EXTENSIONS,
    bMaker,
    formatDB,
    gDict,
    queueDB,
    replyDB,
)
from config import Config
from helpers import database
from helpers.utils import UserSettings, get_readable_file_size, get_readable_time

botStartTime = time.time()
parent_id = Config.GDRIVE_FOLDER_ID


class MergeBot(Client):
    def start(self):
        super().start()
        try:
            self.send_message(chat_id=int(Config.OWNER), text="<b>Bot Started!</b>")
        except Exception as err:
            LOGGER.error("Boot alert failed! Please start bot in PM")
        return LOGGER.info("Bot Started!")

    def stop(self):
        super().stop()
        return LOGGER.info("Bot Stopped")


mergeApp = MergeBot(
    name="merge-bot",
    api_hash=Config.API_HASH,
    api_id=Config.TELEGRAM_API,
    bot_token=Config.BOT_TOKEN,
    workers=300,
    plugins=dict(root="plugins"),
    app_version="5.0+mallupuls-mergebot",
)


if os.path.exists("downloads") is False:
    os.makedirs("downloads")


@mergeApp.on_message(filters.command(["log"]) & filters.user(Config.OWNER_USERNAME))
async def sendLogFile(c: Client, m: Message):
    await m.reply_document(document="./mergebotlog.txt")
    return


@mergeApp.on_message(filters.command(["login"]) & filters.private)
async def loginHandler(c: Client, m: Message):
    user = UserSettings(m.from_user.id, m.from_user.first_name)
    if user.banned:
        await m.reply_text(
            text=f"**Banned User Detected!**\nYou cannot use this bot.\n\nContact: @{Config.OWNER_USERNAME}",
            quote=True,
        )
        return
    if user.user_id == int(Config.OWNER):
        user.allowed = True
    if user.allowed:
        await m.reply_text(
            text="**Do not spam.**\nYou can use the bot now.",
            quote=True,
        )
    else:
        try:
            passwd = m.text.split(" ", 1)[1]
        except Exception:
            await m.reply_text(
                "**Command:**\n  `/login <password>`\n\n**Usage:**\n  `password`: Get the password from owner",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN,
            )
            return
        passwd = passwd.strip()
        if passwd == Config.PASSWORD:
            user.allowed = True
            await m.reply_text(
                text="**Login passed ✅**\nYou can use the bot now.",
                quote=True,
            )
        else:
            await m.reply_text(
                text=f"**Login failed ❌**\nYou cannot use this bot.\n\nContact: @{Config.OWNER_USERNAME}",
                quote=True,
            )
    user.set()
    del user
    return


@mergeApp.on_message(filters.command(["stats"]) & filters.private)
async def stats_handler(c: Client, m: Message):
    currentTime = get_readable_time(time.time() - botStartTime)
    total, used, free = shutil.disk_usage(".")
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    cpuUsage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    stats = (
        f"<b>╭「 BOT STATISTICS 」</b>\n"
        f"<b>│</b>\n"
        f"<b>├⏳ Bot Uptime : {currentTime}</b>\n"
        f"<b>├💾 Total Disk Space : {total}</b>\n"
        f"<b>├📀 Total Used Space : {used}</b>\n"
        f"<b>├💿 Total Free Space : {free}</b>\n"
        f"<b>├🔺 Total Upload : {sent}</b>\n"
        f"<b>├🔻 Total Download : {recv}</b>\n"
        f"<b>├🖥 CPU : {cpuUsage}%</b>\n"
        f"<b>├⚙️ RAM : {memory}%</b>\n"
        f"<b>╰💿 DISK : {disk}%</b>"
    )
    await m.reply_text(text=stats, quote=True)


@mergeApp.on_message(
    filters.command(["broadcast"])
    & filters.private
    & filters.user(Config.OWNER_USERNAME)
)
async def broadcast_handler(c: Client, m: Message):
    msg = m.reply_to_message
    userList = await database.broadcast()
    len_users = userList.collection.count_documents({})
    status = await m.reply_text(
        text=BROADCAST_MSG.format(str(len_users), "0"), quote=True
    )
    success = 0
    for i in range(len_users):
        try:
            uid = userList[i]["_id"]
            if uid != int(Config.OWNER):
                await msg.copy(chat_id=uid)
            success = i + 1
            await status.edit_text(text=BROADCAST_MSG.format(len_users, success))
            LOGGER.info(f"Message sent to {userList[i]['name']} ")
        except FloodWait as e:
            await asyncio.sleep(e.x)
            await msg.copy(chat_id=userList[i]["_id"])
            LOGGER.info(f"Message sent to {userList[i]['name']} ")
        except InputUserDeactivated:
            await database.deleteUser(userList[i]["_id"])
            LOGGER.info(f"{userList[i]['_id']} - {userList[i]['name']} : deactivated\n")
        except UserIsBlocked:
            await database.deleteUser(userList[i]["_id"])
            LOGGER.info(
                f"{userList[i]['_id']} - {userList[i]['name']} : blocked the bot\n"
            )
        except PeerIdInvalid:
            await database.deleteUser(userList[i]["_id"])
            LOGGER.info(
                f"{userList[i]['_id']} - {userList[i]['name']} : user id invalid\n"
            )
        except Exception as err:
            LOGGER.warning(f"{err}\n")
        await asyncio.sleep(3)
    await status.edit_text(
        text=BROADCAST_MSG.format(len_users, success)
        + f"**Failed: {str(len_users-success)}**\n\n__Broadcast completed successfully.__",
    )


@mergeApp.on_message(filters.command(["start"]) & filters.private)
async def start_handler(c: Client, m: Message):
    user = UserSettings(m.from_user.id, m.from_user.first_name)

    if m.from_user.id != int(Config.OWNER):
        if user.allowed is False:
            await m.reply_text(
                text=(
                    f"Hi **{m.from_user.first_name}**\n\n"
                    f"You are not allowed to use this bot.\n\n"
                    f"Contact: @{Config.OWNER_USERNAME}"
                ),
                quote=True,
            )
            return
    else:
        user.allowed = True
        user.set()
    await m.reply_text(
        text=(
            f"Hi **{m.from_user.first_name}**\n\n"
            f"I am a file and video merger bot.\n\n"
            f"I can merge Telegram files and upload them.\n\n"
            f"Owner: @{Config.OWNER_USERNAME}"
        ),
        quote=True,
    )
    del user


@mergeApp.on_message(
    (filters.document | filters.video | filters.audio) & filters.private
)
async def files_handler(c: Client, m: Message):
    user_id = m.from_user.id
    user = UserSettings(user_id, m.from_user.first_name)
    if user_id != int(Config.OWNER):
        if user.allowed is False:
            await m.reply_text(
                text=(
                    f"Hi **{m.from_user.first_name}**\n\n"
                    f"You are not allowed to use this bot.\n\n"
                    f"Contact: @{Config.OWNER_USERNAME}"
                ),
                quote=True,
            )
            return
    if user.merge_mode == 4:  # extract mode
        return
    input_ = f"downloads/{str(user_id)}/input.txt"
    if os.path.exists(input_):
        await m.reply_text(
            "One process is already in progress. Please wait until it finishes."
        )
        return
    media = m.video or m.document or m.audio
    if media.file_name is None:
        await m.reply_text("File name not found.")
        return
    currentFileNameExt = media.file_name.rsplit(sep=".")[-1].lower()
    if currentFileNameExt in "conf":
        await m.reply_text(
            text="Config file found. Do you want to save it?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Yes", callback_data="rclone_save"),
                        InlineKeyboardButton("No", callback_data="rclone_discard"),
                    ]
                ]
            ),
            quote=True,
        )
        return

    if user.merge_mode == 1:

        if queueDB.get(user_id, None) is None:
            formatDB.update({user_id: currentFileNameExt})
        if (
            formatDB.get(user_id, None) is not None
            and currentFileNameExt != formatDB.get(user_id)
        ):
            await m.reply_text(
                f"You first sent a {formatDB.get(user_id).upper()} file. "
                f"Now send only that type of file.",
                quote=True,
            )
            return
        if currentFileNameExt not in VIDEO_EXTENSIONS:
            await m.reply_text(
                "This video format is not allowed. Only send MP4, MKV or WEBM.",
                quote=True,
            )
            return
        editable = await m.reply_text("Please wait...", quote=True)
        MessageText = "Now send the next video or press Merge Now."

        if queueDB.get(user_id, None) is None:
            queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
        if (
            len(queueDB.get(user_id)["videos"]) >= 0
            and len(queueDB.get(user_id)["videos"]) < 10
        ):
            queueDB.get(user_id)["videos"].append(m.id)
            queueDB.get(m.from_user.id)["subtitles"].append(None)

            if len(queueDB.get(user_id)["videos"]) == 1:
                reply_ = await editable.edit(
                    "Send more videos to merge them into a single file.",
                    reply_markup=InlineKeyboardMarkup(
                        bMaker.makebuttons(["Cancel"], ["cancel"])
                    ),
                )
                replyDB.update({user_id: reply_.id})
                return
            if queueDB.get(user_id, None)["videos"] is None:
                formatDB.update({user_id: currentFileNameExt})
            if replyDB.get(user_id, None) is not None:
                await c.delete_messages(
                    chat_id=m.chat.id, message_ids=replyDB.get(user_id)
                )
            if len(queueDB.get(user_id)["videos"]) == 10:
                MessageText = "Maximum 10 videos allowed. Now press Merge Now."
            markup = await makeButtons(c, m, queueDB)
            reply_ = await editable.edit(
                text=MessageText, reply_markup=InlineKeyboardMarkup(markup)
            )
            replyDB.update({user_id: reply_.id})
        elif len(queueDB.get(user_id)["videos"]) > 10:
            markup = await makeButtons(c, m, queueDB)
            await editable.edit(
                "Maximum 10 videos allowed.",
                reply_markup=InlineKeyboardMarkup(markup),
            )

    elif user.merge_mode == 2:
        editable = await m.reply_text("Please wait...", quote=True)
        MessageText = "Now send more audios or press Merge Now."

        if queueDB.get(user_id, None) is None:
            queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
        if len(queueDB.get(user_id)["videos"]) == 0:
            queueDB.get(user_id)["videos"].append(m.id)
            reply_ = await editable.edit(
                text="Now send all the audios you want to merge.",
                reply_markup=InlineKeyboardMarkup(
                    bMaker.makebuttons(["Cancel"], ["cancel"])
                ),
            )
            replyDB.update({user_id: reply_.id})
            return
        elif (
            len(queueDB.get(user_id)["videos"]) >= 1
            and currentFileNameExt in AUDIO_EXTENSIONS
        ):
            queueDB.get(user_id)["audios"].append(m.id)
            if replyDB.get(user_id, None) is not None:
                await c.delete_messages(
                    chat_id=m.chat.id, message_ids=replyDB.get(user_id)
                )
            markup = await makeButtons(c, m, queueDB)

            reply_ = await editable.edit(
                text=MessageText, reply_markup=InlineKeyboardMarkup(markup)
            )
            replyDB.update({user_id: reply_.id})
        else:
            await m.reply("This file type is not valid.")
            return

    elif user.merge_mode == 3:

        editable = await m.reply_text("Please wait...", quote=True)
        MessageText = "Now send more subtitles or press Merge Now."
        if queueDB.get(user_id, None) is None:
            queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
        if len(queueDB.get(user_id)["videos"]) == 0:
            queueDB.get(user_id)["videos"].append(m.id)
            reply_ = await editable.edit(
                text="Now send all the subtitles you want to merge.",
                reply_markup=InlineKeyboardMarkup(
                    bMaker.makebuttons(["Cancel"], ["cancel"])
                ),
            )
            replyDB.update({user_id: reply_.id})
            return
        elif (
            len(queueDB.get(user_id)["videos"]) >= 1
            and currentFileNameExt in SUBTITLE_EXTENSIONS
        ):
            queueDB.get(user_id)["subtitles"].append(m.id)
            if replyDB.get(user_id, None) is not None:
                await c.delete_messages(
                    chat_id=m.chat.id, message_ids=replyDB.get(user_id)
                )
            markup = await makeButtons(c, m, queueDB)

            reply_ = await editable.edit(
                text=MessageText, reply_markup=InlineKeyboardMarkup(markup)
            )
            replyDB.update({user_id: reply_.id})
        else:
            await m.reply("This file type is not valid.")
            return


@mergeApp.on_message(filters.photo & filters.private)
async def photo_handler(c: Client, m: Message):
    user = UserSettings(m.chat.id, m.from_user.first_name)
    if not user.allowed:
        await m.reply_text(
            text=(
                f"Hi **{m.from_user.first_name}**\n\n"
                f"You are not allowed to use this bot.\n\n"
                f"Contact: @{Config.OWNER_USERNAME}"
            ),
            quote=True,
        )
        del user
        return
    thumbnail = m.photo.file_id
    msg = await m.reply_text("Saving thumbnail...", quote=True)
    user.thumbnail = thumbnail
    user.set()
    LOCATION = f"downloads/{m.from_user.id}_thumb.jpg"
    await c.download_media(message=m, file_name=LOCATION)
    await msg.edit_text(text="Custom thumbnail saved.")
    del user


@mergeApp.on_message(filters.command(["extract"]) & filters.private)
async def media_extracter(c: Client, m: Message):
    user = UserSettings(uid=m.from_user.id, name=m.from_user.first_name)
    if not user.allowed:
        return
    if user.merge_mode == 4:
        if m.reply_to_message is None:
            await m.reply(text="Reply /extract to a video or document file.")
            return
        rmess = m.reply_to_message
        if rmess.video or rmess.document:
            media = rmess.video or rmess.document
            mid = rmess.id
            file_name = media.file_name
            if file_name is None:
                await m.reply(
                    f"File name not found. Contact @{Config.OWNER_USERNAME}."
                )
                return

            # Updated extraction menu
            markup = [
                [
                    InlineKeyboardButton(
                        "📹 Video (+Subs)", callback_data=f"extract_videosub_{mid}"
                    ),
                    InlineKeyboardButton(
                        "🎵 Audio", callback_data=f"extract_audio_{mid}"
                    ),
                    InlineKeyboardButton(
                        "📜 Subtitle", callback_data=f"extract_subtitle_{mid}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📂 Extract ALL (Video+Audio+Sub)",
                        callback_data=f"extract_all_{mid}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🧹 Stream Cleaner (Remove Audio)",
                        callback_data=f"extract_clean_{mid}",
                    ),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
            ]

            await m.reply(
                text=(
                    "**Choose extraction mode:**\n\n"
                    "📹 Video (+Subs): Get video file with subtitles (no audio)\n"
                    "🎵 Audio: Extract audio files only\n"
                    "📜 Subtitle: Extract subtitle files only\n"
                    "📂 Extract ALL: Get everything (video, audios, subs)\n"
                    "🧹 Stream Cleaner: Select specific audio streams to keep or remove"
                ),
                quote=True,
                reply_markup=InlineKeyboardMarkup(markup),
            )
    else:
        await m.reply(
            text="Change settings and set mode to extract, then use /extract command."
        )


@mergeApp.on_message(filters.command(["help"]) & filters.private)
async def help_msg(c: Client, m: Message):
    await m.reply_text(
        text=(
            "**Follow these steps:**\n\n"
            "1) Send a custom thumbnail (optional).\n"
            "2) Send two or more videos that you want to merge.\n"
            "3) After sending all files select merge options.\n"
            "4) Select the upload mode.\n"
            "5) Select rename if you want a custom file name or press default."
        ),
        quote=True,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Close", callback_data="close")]]
        ),
    )


@mergeApp.on_message(filters.command(["about"]) & filters.private)
async def about_handler(c: Client, m: Message):
    await m.reply_text(
        text="""
**Features:**
• Ban and unban users
• Extract all audios and subtitles from Telegram media
• Merge video and audio
• Merge video and subtitles
• Upload to drive using your own rclone config
• Merged video preserves all streams of the first video you send (all audio tracks and subtitles)
• Merge up to 10 videos in one file
• Upload as documents or video
• Custom thumbnail support
• Users can log in using a password
• Owner can broadcast messages to all users
        """,
        quote=True,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Developer", url="https://t.me/MalluPuls")],
                [
                    InlineKeyboardButton(
                        "Source Code", url="https://t.me/MalluPuls"
                    ),
                    InlineKeyboardButton(
                        "Deployed By", url=f"https://t.me/{Config.OWNER_USERNAME}"
                    ),
                ],
                [InlineKeyboardButton("Close", callback_data="close")],
            ]
        ),
    )


@mergeApp.on_message(
    filters.command(["savethumb", "setthumb", "savethumbnail"]) & filters.private
)
async def save_thumbnail(c: Client, m: Message):
    if m.reply_to_message:
        if m.reply_to_message.photo:
            await photo_handler(c, m.reply_to_message)
        else:
            await m.reply(text="Please reply to a valid photo.")
    else:
        await m.reply(text="Please reply to a message.")
    return


@mergeApp.on_message(filters.command(["showthumbnail"]) & filters.private)
async def show_thumbnail(c: Client, m: Message):
    try:
        user = UserSettings(m.from_user.id, m.from_user.first_name)
        thumb_id = user.thumbnail
        LOCATION = f"downloads/{str(m.from_user.id)}_thumb.jpg"
        if os.path.exists(LOCATION):
            await m.reply_photo(
                photo=LOCATION, caption="Your custom thumbnail.", quote=True
            )
        elif thumb_id is not None:
            await c.download_media(message=str(thumb_id), file_name=LOCATION)
            await m.reply_photo(
                photo=LOCATION, caption="Your custom thumbnail.", quote=True
            )
        else:
            await m.reply_text(text="Custom thumbnail not found.", quote=True)
        del user
    except Exception as err:
        LOGGER.info(err)
        await m.reply_text(text="Custom thumbnail not found.", quote=True)


@mergeApp.on_message(filters.command(["deletethumbnail"]) & filters.private)
async def delete_thumbnail(c: Client, m: Message):
    try:
        user = UserSettings(m.from_user.id, m.from_user.first_name)
        user.thumbnail = None
        user.set()
        thumb_path = f"downloads/{str(m.from_user.id)}_thumb.jpg"
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
            await m.reply_text("Deleted successfully.", quote=True)
            del user
        else:
            raise Exception("Thumbnail file not found")
    except Exception:
        await m.reply_text(text="Custom thumbnail not found.", quote=True)


@mergeApp.on_message(filters.command(["ban", "unban"]) & filters.private)
async def ban_user(c: Client, m: Message):
    incoming = m.text.split(" ")[0]
    if incoming == "/ban":
        if m.from_user.id == int(Config.OWNER):
            try:
                abuser_id = int(m.text.split(" ")[1])
                if abuser_id == int(Config.OWNER):
                    await m.reply_text(
                        "You cannot ban yourself.", quote=True
                    )
                else:
                    try:
                        user_obj: User = await c.get_users(abuser_id)
                        udata = UserSettings(
                            uid=abuser_id, name=user_obj.first_name
                        )
                        udata.banned = True
                        udata.allowed = False
                        udata.set()
                        await m.reply_text(
                            f"{user_obj.first_name} has been banned.",
                            quote=True,
                        )
                        acknowledgement = f"""
Dear {user_obj.first_name},
Your account has been banned from using this bot.

You cannot merge videos, audios, subtitles or extract streams.

Your account can be unbanned only by @{Config.OWNER_USERNAME}."""
                        try:
                            await c.send_message(
                                chat_id=abuser_id, text=acknowledgement
                            )
                        except Exception as e:
                            await m.reply_text(
                                f"An error occurred while sending acknowledgement\n\n`{e}`",
                                quote=True,
                            )
                            LOGGER.error(e)
                    except Exception as e:
                        LOGGER.error(e)
            except Exception:
                await m.reply_text(
                    "**Command:**\n  `/ban <user_id>`\n\n**Usage:**\n  `user_id`: User ID of the user",
                    quote=True,
                    parse_mode=enums.ParseMode.MARKDOWN,
                )
        else:
            await m.reply_text(
                "**(Only for OWNER)\nCommand:**\n  `/ban <user_id>`\n\n**Usage:**\n  `user_id`: User ID of the user",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN,
            )
        return
    elif incoming == "/unban":
        if m.from_user.id == int(Config.OWNER):
            try:
                abuser_id = int(m.text.split(" ")[1])
                if abuser_id == int(Config.OWNER):
                    await m.reply_text(
                        "You cannot ban yourself.", quote=True
                    )
                else:
                    try:
                        user_obj: User = await c.get_users(abuser_id)
                        udata = UserSettings(
                            uid=abuser_id, name=user_obj.first_name
                        )
                        udata.banned = False
                        udata.allowed = True
                        udata.set()
                        await m.reply_text(
                            f"{user_obj.first_name} has been unbanned.",
                            quote=True,
                        )
                        release_notice = f"""
Good news {user_obj.first_name}, the ban on your account has been removed."""
                        try:
                            await c.send_message(
                                chat_id=abuser_id, text=release_notice
                            )
                        except Exception as e:
                            await m.reply_text(
                                f"An error occurred while sending release notice\n\n`{e}`",
                                quote=True,
                            )
                            LOGGER.error(e)
                    except Exception as e:
                        LOGGER.error(e)
            except Exception:
                await m.reply_text(
                    "**Command:**\n  `/unban <user_id>`\n\n**Usage:**\n  `user_id`: User ID of the user",
                    quote=True,
                    parse_mode=enums.ParseMode.MARKDOWN,
                )
        else:
            await m.reply_text(
                "**(Only for OWNER)\nCommand:**\n  `/unban <user_id>`\n\n**Usage:**\n  `user_id`: User ID of the user",
                quote=True,
                parse_mode=enums.ParseMode.MARKDOWN,
            )
        return


async def showQueue(c: Client, cb: CallbackQuery):
    try:
        markup = await makeButtons(c, cb.message, queueDB)
        await cb.message.edit(
            text="Now send the next video or press Merge Now.",
            reply_markup=InlineKeyboardMarkup(markup),
        )
    except ValueError:
        await cb.message.edit("Send some more videos.")
    return


async def delete_all(root):
    try:
        shutil.rmtree(root)
    except Exception as e:
        LOGGER.info(e)


async def makeButtons(bot: Client, m: Message, db: dict):
    markup = []
    user = UserSettings(m.chat.id, m.chat.first_name)
    if user.merge_mode == 1:
        for i in await bot.get_messages(
            chat_id=m.chat.id, message_ids=db.get(m.chat.id)["videos"]
        ):
            media = i.video or i.document or None
            if media is None:
                continue
            else:
                markup.append(
                    [
                        InlineKeyboardButton(
                            f"{media.file_name}",
                            callback_data=f"showFileName_{i.id}",
                        )
                    ]
                )

    elif user.merge_mode == 2:
        msgs = await bot.get_messages(
            chat_id=m.chat.id, message_ids=db.get(m.chat.id)["audios"]
        )
        msgs = list(msgs)
        msgs.insert(
            0,
            await bot.get_messages(
                chat_id=m.chat.id, message_ids=db.get(m.chat.id)["videos"][0]
            ),
        )
        for i in msgs:
            media = i.audio or i.document or i.video or None
            if media is None:
                continue
            else:
                markup.append(
                    [
                        InlineKeyboardButton(
                            f"{media.file_name}",
                            callback_data="tryotherbutton",
                        )
                    ]
                )

    elif user.merge_mode == 3:
        msgs = await bot.get_messages(
            chat_id=m.chat.id, message_ids=db.get(m.chat.id)["subtitles"]
        )
        msgs = list(msgs)
        msgs.insert(
            0,
            await bot.get_messages(
                chat_id=m.chat.id, message_ids=db.get(m.chat.id)["videos"][0]
            ),
        )
        for i in msgs:
            media = i.video or i.document or None

            if media is None:
                continue
            else:
                markup.append(
                    [
                        InlineKeyboardButton(
                            f"{media.file_name}",
                            callback_data="tryotherbutton",
                        )
                    ]
                )

    markup.append([InlineKeyboardButton("Merge Now", callback_data="merge")])
    markup.append([InlineKeyboardButton("Clear Files", callback_data="cancel")])
    return markup


LOGCHANNEL = Config.LOGCHANNEL
try:
    if Config.USER_SESSION_STRING is None:
        raise KeyError
    LOGGER.info("Starting user session")
    userBot = Client(
        name="merge-bot-user",
        session_string=Config.USER_SESSION_STRING,
        no_updates=True,
    )

except KeyError:
    userBot = None
    LOGGER.warning("No user session. Default bot session will be used.")


if __name__ == "__main__":
    if userBot is not None:
        try:
            with userBot:
                userBot.send_message(
                    chat_id=int(LOGCHANNEL),
                    text="Bot booted with premium account...",
                    disable_web_page_preview=True,
                )
                user = userBot.get_me()
                Config.IS_PREMIUM = user.is_premium
        except Exception as err:
            LOGGER.error(f"{err}")
            Config.IS_PREMIUM = False
    else:
        Config.IS_PREMIUM = False

    keep_alive()

    mergeApp.run()
