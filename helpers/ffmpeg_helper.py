import asyncio
import subprocess
import shutil
import os
import time
import ffmpeg
from pyrogram.types import CallbackQuery
from config import Config
from pyrogram.types import Message
from __init__ import LOGGER
from helpers.utils import get_path_size


async def MergeVideo(input_file: str, user_id: int, message: Message, format_: str):
    """
    This is for Merging Videos Together!
    """
    output_vid = f"downloads/{str(user_id)}/[@yashoswalyo].{format_.lower()}"
    file_generator_command = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        input_file,
        "-map",
        "0",
        "-c",
        "copy",
        output_vid,
    ]
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *file_generator_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except NotImplementedError:
        await message.edit(
            text="Unable to Execute FFmpeg Command! Got `NotImplementedError` ...\n\nPlease run bot in a Linux/Unix Environment."
        )
        await asyncio.sleep(10)
        return None
    await message.edit("Merging Video Now ...\n\nPlease Keep Patience ...")
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    LOGGER.info(e_response)
    LOGGER.info(t_response)
    if os.path.lexists(output_vid):
        return output_vid
    else:
        return None


async def MergeSub(filePath: str, subPath: str, user_id):
    """
    This is for Merging Video + Subtitle Together.
    """
    LOGGER.info("Generating mux command")
    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")
    muxcmd.append("-i")
    muxcmd.append(filePath)
    muxcmd.append("-i")
    muxcmd.append(subPath)
    muxcmd.append("-map")
    muxcmd.append("0:v:0")
    muxcmd.append("-map")
    muxcmd.append("0:a:?")
    muxcmd.append("-map")
    muxcmd.append("0:s:?")
    muxcmd.append("-map")
    muxcmd.append("1:s")
    videoData = ffmpeg.probe(filename=filePath)
    videoStreamsData = videoData.get("streams")
    subTrack = 0
    for i in range(len(videoStreamsData)):
        if videoStreamsData[i]["codec_type"] == "subtitle":
            subTrack += 1
    muxcmd.append(f"-metadata:s:s:{subTrack}")
    subTrack += 1
    subTitle = f"Track {subTrack} - tg@yashoswalyo"
    muxcmd.append(f"title={subTitle}")
    muxcmd.append("-c:v")
    muxcmd.append("copy")
    muxcmd.append("-c:a")
    muxcmd.append("copy")
    muxcmd.append("-c:s")
    muxcmd.append("srt")
    muxcmd.append(f"./downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv")
    LOGGER.info("Muxing subtitles")
    subprocess.call(muxcmd)
    orgFilePath = shutil.move(
        f"downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv", filePath
    )
    return orgFilePath


def MergeSubNew(filePath: str, subPath: str, user_id, file_list):
    """
    Merging Video + Subtitle(s) Together.
    """
    LOGGER.info("Generating mux command")
    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")
    videoData = ffmpeg.probe(filename=filePath)
    videoStreamsData = videoData.get("streams")
    subTrack = 0
    for i in range(len(videoStreamsData)):
        if videoStreamsData[i]["codec_type"] == "subtitle":
            subTrack += 1
    for i in file_list:
        muxcmd.append("-i")
        muxcmd.append(i)
    muxcmd.append("-map")
    muxcmd.append("0:v:0")
    muxcmd.append("-map")
    muxcmd.append("0:a:?")
    muxcmd.append("-map")
    muxcmd.append("0:s:?")
    for j in range(1, (len(file_list))):
        muxcmd.append("-map")
        muxcmd.append(f"{j}:s")
        muxcmd.append(f"-metadata:s:s:{subTrack}")
        muxcmd.append(f"title=Track {subTrack+1} - tg@yashoswalyo")
        subTrack += 1
    muxcmd.append("-c:v")
    muxcmd.append("copy")
    muxcmd.append("-c:a")
    muxcmd.append("copy")
    muxcmd.append("-c:s")
    muxcmd.append("srt")
    muxcmd.append(f"./downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv")
    LOGGER.info("Sub muxing")
    subprocess.call(muxcmd)
    return f"downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv"


def MergeAudio(videoPath: str, files_list: list, user_id):
    LOGGER.info("Generating Mux Command")
    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")
    videoData = ffmpeg.probe(filename=videoPath)
    videoStreamsData = videoData.get("streams")
    audioTracks = 0
    for i in files_list:
        muxcmd.append("-i")
        muxcmd.append(i)
    muxcmd.append("-map")
    muxcmd.append("0:v:0")
    muxcmd.append("-map")
    muxcmd.append("0:a:?")
    audioTracks = 0
    for i in range(len(videoStreamsData)):
        if videoStreamsData[i]["codec_type"] == "audio":
            muxcmd.append(f"-disposition:a:{audioTracks}")
            muxcmd.append("0")
            audioTracks += 1
    fAudio = audioTracks
    for j in range(1, len(files_list)):
        muxcmd.append("-map")
        muxcmd.append(f"{j}:a")
        muxcmd.append(f"-metadata:s:a:{audioTracks}")
        muxcmd.append(f"title=Track {audioTracks+1} - tg@yashoswalyo")
        audioTracks += 1
    muxcmd.append(f"-disposition:s:a:{fAudio}")
    muxcmd.append("default")
    muxcmd.append("-map")
    muxcmd.append("0:s:?")
    muxcmd.append("-c:v")
    muxcmd.append("copy")
    muxcmd.append("-c:a")
    muxcmd.append("copy")
    muxcmd.append("-c:s")
    muxcmd.append("copy")
    muxcmd.append(f"downloads/{str(user_id)}/[@yashoswalyo]_export.mkv")

    LOGGER.info(muxcmd)
    process = subprocess.call(muxcmd)
    LOGGER.info(process)
    return f"downloads/{str(user_id)}/[@yashoswalyo]_export.mkv"


async def cult_small_video(video_file, output_directory, start_time, end_time, format_):
    out_put_file_name = (
        output_directory + str(round(time.time())) + "." + format_.lower()
    )
    file_generator_command = [
        "ffmpeg",
        "-ss",
        str(start_time),
        "-to",
        str(end_time),
        "-i",
        video_file,
        "-async",
        "1",
        "-strict",
        "-2",
        out_put_file_name,
    ]
    process = await asyncio.create_subprocess_exec(
        *file_generator_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    LOGGER.info(e_response)
    LOGGER.info(t_response)
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    else:
        return None


async def take_screen_shot(video_file, output_directory, ttl):
    out_put_file_name = os.path.join(output_directory, str(time.time()) + ".jpg")
    if video_file.upper().endswith(
        ("MKV","MP4","WEBM","AVI","MOV","OGG","WMV","M4V","TS","MPG","MTS","M2TS","3GP")
    ):
        file_genertor_command = [
            "ffmpeg",
            "-ss",
            str(ttl),
            "-i",
            video_file,
            "-vframes",
            "1",
            out_put_file_name,
        ]
        process = await asyncio.create_subprocess_exec(
            *file_genertor_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        e_response = stderr.decode().strip()
        t_response = stdout.decode().strip()
    if os.path.exists(out_put_file_name):
        return out_put_file_name
    else:
        return None


async def extractAudios(path_to_file, user_id):
    dir_name = os.path.dirname(os.path.dirname(path_to_file))
    if not os.path.exists(path_to_file):
        return None
    if not os.path.exists(dir_name + "/extract"):
        os.makedirs(dir_name + "/extract")
    videoStreamsData = ffmpeg.probe(path_to_file)
    extract_dir = dir_name + "/extract"
    audios = []
    for stream in videoStreamsData.get("streams"):
        try:
            if stream["codec_type"] == "audio":
                audios.append(stream)
        except Exception as e:
            LOGGER.warning(e)
    for audio in audios:
        extractcmd = []
        extractcmd.append("ffmpeg")
        extractcmd.append("-hide_banner")
        extractcmd.append("-i")
        extractcmd.append(path_to_file)
        extractcmd.append("-map")
        try:
            index = audio["index"]
            extractcmd.append(f"0:{index}")
            try:
                output_file: str = (
                    "("
                    + audio["tags"]["language"]
                    + ") "
                    + audio["tags"]["title"]
                    + "."
                    + audio["codec_type"]
                    + ".mka"
                )
                output_file = output_file.replace(" ", ".")
            except:
                output_file = str(audio["index"]) + "." + audio["codec_type"] + ".mka"
            extractcmd.append("-c")
            extractcmd.append("copy")
            extractcmd.append(f"{extract_dir}/{output_file}")
            LOGGER.info(extractcmd)
            subprocess.call(extractcmd)
        except Exception as e:
            LOGGER.error(f"Something went wrong: {e}")
    if get_path_size(extract_dir) > 0:
        return extract_dir
    else:
        LOGGER.warning(f"{extract_dir} is empty")
        return None


async def extractSubtitles(path_to_file, user_id):
    dir_name = os.path.dirname(os.path.dirname(path_to_file))
    if not os.path.exists(path_to_file):
        return None
    if not os.path.exists(dir_name + "/extract"):
        os.makedirs(dir_name + "/extract")
    videoStreamsData = ffmpeg.probe(path_to_file)
    extract_dir = dir_name + "/extract"
    subtitles = []
    for stream in videoStreamsData.get("streams"):
        try:
            if stream["codec_type"] == "subtitle":
                subtitles.append(stream)
        except Exception as e:
            LOGGER.warning(e)
    for subtitle in subtitles:
        extractcmd = []
        extractcmd.append("ffmpeg")
        extractcmd.append("-hide_banner")
        extractcmd.append("-i")
        extractcmd.append(path_to_file)
        extractcmd.append("-map")
        try:
            index = subtitle["index"]
            extractcmd.append(f"0:{index}")
            try:
                output_file: str = (
                    "("
                    + subtitle["tags"]["language"]
                    + ") "
                    + subtitle["tags"]["title"]
                    + "."
                    + subtitle["codec_type"]
                    + ".srt"
                )
                output_file = output_file.replace(" ", ".")
            except:
                try:
                    output_file = (
                        str(subtitle["index"])
                        + "."
                        + subtitle["tags"]["language"]
                        + "."
                        + subtitle["codec_type"]
                        + ".srt"
                    )
                except:
                    output_file = (
                        str(subtitle["index"]) + "." + subtitle["codec_type"] + ".srt"
                    )
            extractcmd.append("-c")
            extractcmd.append("copy")
            extractcmd.append(f"{extract_dir}/{output_file}")
            LOGGER.info(extractcmd)
            subprocess.call(extractcmd)
        except Exception as e:
            LOGGER.error(f"Something went wrong: {e}")
    if get_path_size(extract_dir) > 0:
        return extract_dir
    else:
        LOGGER.warning(f"{extract_dir} is empty")
        return None

# ==============================================================================
# NEW FUNCTIONS FOR STREAM CLEANING (AUDIO REMOVER)
# ==============================================================================

async def get_audio_streams(input_file):
    """
    Returns a list of audio streams with index and language.
    Used for generating checkboxes.
    """
    try:
        probe = ffmpeg.probe(input_file)
        audio_streams = []
        for stream in probe['streams']:
            if stream['codec_type'] == 'audio':
                index = stream['index']
                tags = stream.get('tags', {})
                lang = tags.get('language', 'unk')
                title = tags.get('title', str(index))
                audio_streams.append({'index': index, 'lang': lang, 'title': title})
        return audio_streams
    except Exception as e:
        LOGGER.error(f"Probe Error: {e}")
        return None

async def clean_video_streams(input_file, keep_indices, user_id):
    """
    Removes unselected audio streams.
    Keeps:
    1. Original Video Track (0:v)
    2. ALL Subtitles (0:s?) -> This ensures subtitles are NEVER removed.
    3. Only Selected Audio Tracks (from keep_indices)
    """
    output_file = f"downloads/{str(user_id)}/[Cleaned]_video.mkv"
    
    # Start building FFmpeg command logic
    # We use asyncio subprocess instead of ffmpeg-python wrapper for better control over mapping logic
    
    command = ['ffmpeg', '-hide_banner', '-i', input_file]
    
    # 1. MAP VIDEO (Always keep the first video track)
    command.extend(['-map', '0:v'])
    
    # 2. MAP SELECTED AUDIOS (Loop through the indexes user ticked)
    if keep_indices:
        for idx in keep_indices:
            command.extend(['-map', f"0:{idx}"])
    else:
        # If user deselected ALL audios, we map no audio. 
        # Video will be muted. This is valid behavior.
        pass
            
    # 3. MAP ALL SUBTITLES (Critical: Never remove subtitles)
    # "0:s?" means map all subtitle streams from input 0 if they exist.
    command.extend(['-map', '0:s?'])
    
    # 4. COPY CODEC (No re-encoding, very fast)
    command.extend(['-c', 'copy'])
    
    command.append(output_file)
    
    LOGGER.info(f"Running Clean Command: {command}")
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    
    if os.path.exists(output_file):
        return output_file
    else:
        LOGGER.error(f"Clean Error: {stderr.decode()}")
        return None
