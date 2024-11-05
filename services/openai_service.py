import os
import json
import time
from openai import OpenAI
from openai import OpenAIError
from pathlib import Path
import yt_dlp
from utils import utils

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


class TranscriptionValidationError(Exception):
    """Custom exception for transcription validation errors"""

    pass


class OpenAIService:
    def __init__(self, api_key, organization, project, appwrite_service=None):
        self.PROJECT_ROOT = Path(__file__).parent.parent
        self.client = OpenAI(
            api_key=api_key,
            organization=organization,
            project=project,
        )
        self.MODEL = "gpt-4o"
        self.appwrite_service = appwrite_service
        Path("media").mkdir(exist_ok=True)

    def validate_video(self, video_id):
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
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
            "outtmpl": "./media/%(id)s.%(ext)s",
            "subtitlesoutopt": "./media/%(id)s.%(ext)s",
        }

        # Check storage status first
        song_exists_in_storage = False
        if self.appwrite_service:
            song_exists_in_storage = self.appwrite_service.file_exists_in_songs_bucket(
                f"{video_id}.m4a"
            )
            if song_exists_in_storage:
                yield utils.stream_message("update", "Song already exists in storage.")

        yield utils.stream_message("update", "Analyzing audio...")

        try:
            # Always download to get metadata and validate
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                error_code = ydl.download(
                    [f"https://www.youtube.com/watch?v={video_id}"]
                )
                if error_code:
                    result["error_msg"] = "Audio download failed"
                    yield utils.stream_message("error", result["error_msg"])
                    return

            # Check for expected files
            expected_files = [
                f"{video_id}.m4a",
                f"{video_id}.ja.vtt",
                f"{video_id}.info.json",
            ]

            print("Checking for files:", expected_files)
            for filename in expected_files:
                file_path = Path("media") / filename
                print(f"Checking if {file_path} exists:", file_path.exists())

                # Check for subtitle file
                if filename.endswith((".vtt", ".srt", ".ass", ".ssa")):
                    if file_path.exists():
                        result["subtitle_info"]["exist"] = True
                        result["subtitle_info"]["path"] = str(file_path)
                        result["subtitle_info"]["ext"] = filename[filename.find(".") :]
                        print(f"Found subtitle file: {file_path}")

            # Set audio path if file exists
            audio_path = Path("media") / f"{video_id}.m4a"
            if audio_path.exists():
                result["audio_file_path"] = str(audio_path)
                print(f"Found audio file: {audio_path}")

            result["audio_file_path"] = str(Path("media") / f"{video_id}.m4a")
            info_file_path = Path("media") / f"{video_id}.info.json"

            # Process video info from the downloaded json
            with open(info_file_path, "r", encoding="utf-8") as file:
                json_vid_info = json.load(file)

            # Process video info
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

            # Check if video is playable
            if not result["full_vid_info"]["playable_in_embed"]:
                result["error_msg"] = (
                    "Video is not playable outside of YouTube, please try another video."
                )
                yield utils.stream_message("error", result["error_msg"])
                return

            # Validate video
            result["passed"] = (
                result["full_vid_info"]["language"] == "ja"
                and "Music" in result["full_vid_info"]["categories"]
            ) or self.validate_youtube_video(result["vid_info_for_validation"])

            if not result["passed"]:
                result["error_msg"] = (
                    "This video is not a Japanese music video, please try another video."
                )
                yield utils.stream_message("error", result["error_msg"])
                return

            # Handle upload only if validation passed and song doesn't exist in storage
            if result["passed"] and self.appwrite_service:
                if not song_exists_in_storage:
                    # Upload song
                    yield utils.stream_message("update", "Uploading song to storage...")
                    upload_success = self.appwrite_service.upload_song(video_id)

                    if not upload_success:
                        yield utils.stream_message("error", "Failed to upload song.")
                        result["error_msg"] = "Failed to upload song."
                        result["passed"] = False
                        return

                    yield utils.stream_message(
                        "update", "Song upload completed successfully."
                    )

                # Handle subtitles if they exist
                if result["subtitle_info"]["exist"]:
                    yield utils.stream_message("update", "Uploading Japanese lyrics...")
                    if self.appwrite_service.file_exists_in_lyrics_bucket(
                        f"{video_id}{result['subtitle_info']['ext']}"
                    ):
                        yield utils.stream_message(
                            "update",
                            "Japanese lyrics already exist in storage, skipping upload.",
                        )
                    else:
                        subtitle_upload_success = (
                            self.appwrite_service.upload_youtube_subtitle(video_id)
                        )

                        if subtitle_upload_success:
                            yield utils.stream_message(
                                "update", "Japanese lyrics uploaded successfully."
                            )
                        else:
                            yield utils.stream_message(
                                "warning",
                                "Japanese lyrics upload failed, but video validation passed.",
                            )

            # Always yield the final result regardless of storage status
            yield utils.stream_message("update", "Validation completed.")
            time.sleep(1)
            yield utils.stream_message("vid_info", result)

        except Exception as e:
            result["error_msg"] = (
                f"Error processing video: {str(e)}, please try again or try another video."
            )
            yield utils.stream_message("error", result["error_msg"])
            return

    def get_transcription(self, video_id: str, audio_file_path: Path) -> str:
        """
        Get transcription for an audio file with comprehensive error checking.

        Args:
            video_id: Unique identifier for the video
            audio_file_path: Path to the audio file

        Returns:
            str: Path to the saved SRT file
        """
        # Create paths relative to project root
        media_dir = self.PROJECT_ROOT / "media"
        srt_save_path = media_dir / f"{video_id}.srt"

        # Basic validation
        if not video_id or not audio_file_path:
            raise TranscriptionValidationError(
                "video_id and audio_file_path cannot be empty"
            )

        # Convert relative path to absolute if necessary
        if not audio_file_path.is_absolute():
            audio_file_path = self.PROJECT_ROOT / audio_file_path

        if not audio_file_path.exists():
            raise TranscriptionValidationError(
                f"Audio file not found: {audio_file_path}"
            )

        # Check file size (OpenAI limit is 25MB)
        file_size = audio_file_path.stat().st_size
        if file_size > 25 * 1024 * 1024:
            raise TranscriptionValidationError("Audio file exceeds 25MB limit")

        try:
            # Ensure the output directory exists
            os.makedirs(media_dir, exist_ok=True)

            print("This is audio path")
            print(audio_file_path)

            # Open and transcribe the audio file
            with open(audio_file_path, "rb") as audio_file:
                try:
                    transcription = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ja",
                        prompt=whisper_prompt,
                        response_format="srt",
                        timestamp_granularities=["segment"],
                        temperature=0.77,
                    )
                except OpenAIError as api_error:
                    raise TranscriptionValidationError(
                        f"OpenAI API error: {str(api_error)}"
                    )

            # Validate transcription result
            if not transcription:
                raise TranscriptionValidationError("Empty transcription received")

            # Save transcription
            with open(srt_save_path, "w", encoding="utf-8") as output_file:
                output_file.write(transcription)

            # Upload to cloud storage
            try:
                self.appwrite_service.upload_srt_subtitle(video_id)
            except Exception as upload_error:
                raise TranscriptionValidationError(
                    f"Failed to upload to cloud storage: {str(upload_error)}"
                )

            return str(srt_save_path)

        except Exception as e:
            print(f"Error during transcription process: {str(e)}")
            return f"Failed to get transcription: {str(e)}"

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
