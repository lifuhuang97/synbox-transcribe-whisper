import os
import glob
import json
import time
from openai import OpenAI
import yt_dlp
from utils import utils

from services.directory_manager import DirectoryManager
from config import (
    TOOLS,
    VALIDATE_YOUTUBE_VIDEO_SYSTEM_MESSAGE,
    TRANSLATION_SETUP_SYSTEM_MESSAGE,
    KANJI_ANNOTATION_SYSTEM_MESSAGE,
    ROMAJI_ANNOTATION_SYSTEM_MESSAGE,
    WHISPER_PROMPT,
)

tools = TOOLS
validate_youtube_video_system_message = VALIDATE_YOUTUBE_VIDEO_SYSTEM_MESSAGE
translation_setup_system_message = TRANSLATION_SETUP_SYSTEM_MESSAGE
kanji_annotation_system_message = KANJI_ANNOTATION_SYSTEM_MESSAGE
romaji_annotation_system_message = ROMAJI_ANNOTATION_SYSTEM_MESSAGE
whisper_prompt = WHISPER_PROMPT


class OpenAIService:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        # self.MODEL = "gpt-4o-mini"
        self.MODEL = "gpt-4o"
        DirectoryManager.ensure_all_directories()

    def validate_video(self, video_id):
        track_dir = DirectoryManager.get_path("output", "track")
        DirectoryManager.ensure_directory(track_dir)
        result = {
            "passed": False,
            "audio_file_path": None,
            "full_vid_info": None,
            "vid_info_for_validation": None,
            "subtitle_info": {"exist": False, "path": None, "ext": None},
            "error_msg": None,
        }

        ydl_opts = {
            "match_filter": self.longer_than_eight_mins,
            "format": "m4a/bestaudio/best",
            "writesubtitles": True,
            "subtitlesformat": "vtt/srt/ass/ssa",
            "subtitleslangs": ["ja.*"],
            "break_on_reject": True,
            "writeinfojson": True,
            "postprocessors": [
                {  # Extract audio using ffmpeg
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
            "outtmpl": "./output/track/%(id)s.%(ext)s",
            "subtitlesoutopt": "./output/track/%(id)s.%(ext)s",
        }

        full_vid_url = "https://www.youtube.com/watch?v=" + video_id

        yield utils.stream_message("update", "Analyzing audio...")

        if not os.path.exists(track_dir):
            DirectoryManager.ensure_directory(track_dir)
            files_before = set()
        else:
            files_before = set(os.listdir(track_dir))

        files_before = set(os.listdir("./output/track"))

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                error_code = ydl.download(full_vid_url)
                if error_code:
                    result["error_msg"] = "Audio download failed"
                    yield utils.stream_message("error", result["error_msg"])
                    yield utils.stream_message("data", result)
                    return
        except Exception as e:
            result["error_msg"] = f"An error occurred during video download: {str(e)}"
            if (
                str(e)
                == "Encountered a video that did not match filter, stopping due to --break-match-filter"
            ):
                result["error_msg"] = (
                    "The video length is invalid for processing, please try a different video."
                )
            yield utils.stream_message("error", result["error_msg"])
            return

        # Get the list of files after download
        files_after = set(os.listdir("./output/track"))

        # Find new files
        new_files = files_after - files_before

        # Look for new subtitle files
        subtitle_extensions = (".vtt", ".srt", ".ass", ".ssa")
        for file in new_files:
            if file.endswith(subtitle_extensions) and video_id in file:
                old_path = os.path.join("./output/track", file)
                _, ext = os.path.splitext(file)
                new_filename = f"{video_id}.ja{ext}"
                new_path = os.path.join("./output/track", new_filename)
                os.rename(old_path, new_path)
                result["subtitle_info"]["exist"] = True
                result["subtitle_info"]["path"] = new_path
                result["subtitle_info"]["ext"] = ext
                break

        result["audio_file_path"] = "./output/track/" + video_id + ".m4a"
        info_file_path = "./output/track/" + video_id + ".info.json"

        try:
            with open(info_file_path, "r", encoding="utf-8") as file:
                json_vid_info = json.load(file)
        except Exception as e:
            result["error_msg"] = (
                f"Error reading video info: {str(e)}, please try again or try another video."
            )
            yield utils.stream_message("error", result["error_msg"])
            return

        result["full_vid_info"] = {
            "id": video_id,
            "thumbnail": json_vid_info.get("thumbnail"),
            "views": json_vid_info.get("view_count"),
            "duration": json_vid_info.get("duration"),
            "likes": json_vid_info.get("like_count"),
            "playable_in_embed": json_vid_info.get("playable_in_embed"),
            "title": json_vid_info.get("fulltitle", json_vid_info.get("title")),
            "categories": json_vid_info.get("categories", []),
            "description": json_vid_info.get("description"),
            "channel_name": json_vid_info.get("channel"),
            "uploader": json_vid_info.get("uploader"),
            "language": json_vid_info.get("language"),
        }

        result["vid_info_for_validation"] = {
            "title": result["full_vid_info"]["title"],
            "categories": result["full_vid_info"]["categories"],
            "description": result["full_vid_info"]["description"],
            "channel_name": result["full_vid_info"]["channel_name"],
            "uploader": result["full_vid_info"]["uploader"],
            "language": result["full_vid_info"]["language"],
        }

        subtitle_pattern = f"./output/track/{video_id}.ja.*"
        subtitle_files = glob.glob(subtitle_pattern)
        if subtitle_files:
            result["subtitle_info"]["exist"] = True
            subtitle_file = subtitle_files[0]
            result["subtitle_info"]["path"] = subtitle_file
            _, ext = os.path.splitext(subtitle_file)
            result["subtitle_info"]["ext"] = ext

        if not result["full_vid_info"]["playable_in_embed"]:
            result["error_msg"] = (
                "Video is not playable outside of YouTube, please try another video."
            )
            yield utils.stream_message("error", result["error_msg"])
            return

        if (
            result["full_vid_info"]["language"] == "ja"
            and "Music" in result["full_vid_info"]["categories"]
        ):
            result["passed"] = True
        else:
            result["passed"] = self.validate_youtube_video(
                result["vid_info_for_validation"]
            )
            if not result["passed"]:
                result["error_msg"] = (
                    "This video is not a Japanese music video, please try another video."
                )
                yield utils.stream_message("error", result["error_msg"])
                return

        yield utils.stream_message("update", "Validation completed.")
        time.sleep(1)
        yield utils.stream_message("vid_info", result)

    def get_transcription(self, video_id, audio_file_path):
        response_srt_dir = DirectoryManager.get_path("output", "response_srt")
        DirectoryManager.ensure_directory(response_srt_dir)
        srt_save_path = f"./output/response_srt/{video_id}.srt"

        # Check if the .srt file already exists
        if os.path.exists(srt_save_path):
            print(f"Existing .srt file found for {video_id}. Using the existing file.")
            return srt_save_path

        with open(audio_file_path, "rb") as audio_file:
            # ? change parameters to try to deal with fast songs
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ja",
                prompt=whisper_prompt,
                response_format="srt",
                timestamp_granularities=["segment"],
                temperature=0.77,
                # temperature=0.77,
                # 0.37 0.77 0.82
            )

            print(transcription)
            print("Above is transcription")

            # Ensure the directory exists
            os.makedirs(os.path.dirname(srt_save_path), exist_ok=True)

            with open(srt_save_path, "w", encoding="utf-8") as output_file:
                output_file.write(transcription)

        print("GPT Transcription generated, processed, and saved successfully")

        if transcription:
            return srt_save_path
        else:
            return "Failed to get transcription"

    #! Helper Function - check video length
    def longer_than_eight_mins(self, info):
        """Download only videos shorter than 5mins or longer than 1min"""
        duration = info.get("duration")
        if duration and duration > 480:
            return "The video is too long"
        elif duration and duration < 60:
            return "The video is too short"

    def validate_youtube_video(self, video_info):
        validation_msg = [
            validate_youtube_video_system_message,
            {
                "role": "user",
                "content": json.dumps(video_info),
            },
        ]
        gpt_response = None

        try:
            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=validation_msg,
                tools=tools,
                temperature=0,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "validate_music_video"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                verdict = json.loads(function_call.arguments)
            else:
                raise ValueError("No function call found in the response")

            if "decision" not in verdict:
                raise ValueError("Response is missing required keys")

            affirmative_responses = {"y", "yes"}
            if verdict["decision"].strip().lower() in affirmative_responses:
                return True
            else:
                return False

        except Exception as e:
            print(f"An error occurred in validate_youtube_video: {str(e)}")
            print(
                f"Response: {gpt_response.choices[0] if gpt_response else 'No response'}"
            )
            return None

    def get_translations(self, lyrics_arr, video_id, retry_count):

        TEMPERATURE_VALUES = [0.35, 0.15, 0.65]

        temperature = TEMPERATURE_VALUES[retry_count % len(TEMPERATURE_VALUES)]

        print("This is the length of the input lyrics arr, ")
        print(len(lyrics_arr))

        messages = [
            translation_setup_system_message,
            {
                "role": "user",
                "content": f"Translate the following lyrics to English and Chinese. Strictly translate them in 1:1 ratio. You must maintain the same number of lyrics lines. Respond in JSON format. Lyrics: {json.dumps(lyrics_arr)}",
            },
        ]
        gpt_response = None

        try:
            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=messages,
                tools=tools,
                temperature=temperature,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "translate_lyrics"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                translations = json.loads(function_call.arguments)
            else:
                raise ValueError("No function call found in the response")

            if not all(
                key in translations for key in ["english_lyrics", "chinese_lyrics"]
            ):
                raise ValueError("Response is missing required keys")

            if len(translations["english_lyrics"]) != len(lyrics_arr) or len(
                translations["chinese_lyrics"]
            ) != len(lyrics_arr):
                raise ValueError(
                    f"Number of translated lines does not match the original. "
                    f"Original: {len(lyrics_arr)}, English: {len(translations['english_lyrics'])}, "
                    f"Chinese: {len(translations['chinese_lyrics'])}"
                )

            yield "eng_translation", translations["english_lyrics"]
            yield "chi_translation", translations["chinese_lyrics"]

        except Exception as e:
            print(f"An error occurred in get_translations: {str(e)}")
            print(
                f"Response: {gpt_response.choices[0] if gpt_response else 'No response'}"
            )
            raise ValueError(
                "Error in GPT response" if gpt_response else "Unexpected error"
            )

    def get_kanji_annotations(self, lyrics_arr, video_id):
        kanji_messages = [
            kanji_annotation_system_message,
            {
                "role": "user",
                "content": f"Please annotate the following Japanese lyrics with furigana pronunciations. Respond in JSON format. Lyrics: {json.dumps(lyrics_arr)}",
            },
        ]
        gpt_response = None

        try:
            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=kanji_messages,
                tools=tools,
                temperature=0.2,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "annotate_with_furigana"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                kanji_annotations = json.loads(function_call.arguments)
            else:
                raise ValueError("No function call found in the response")

            if "furigana_ann_lyrics" not in kanji_annotations:
                raise ValueError("Response is missing required keys")

            if len(kanji_annotations["furigana_ann_lyrics"]) != len(lyrics_arr):
                raise ValueError(
                    f"Number of annotated lines does not match the original. "
                    f"Original: {len(lyrics_arr)}, Annotated: {len(kanji_annotations['furigana_ann_lyrics'])}"
                )

            yield "kanji_annotations", kanji_annotations["furigana_ann_lyrics"]

        except Exception as e:
            print(f"An error occurred in get_kanji_annotations: {str(e)}")
            print(
                f"Response: {gpt_response.choices[0] if gpt_response else 'No response'}"
            )
            raise ValueError("Error in getting Kanji annotations")
