import os
import json
import time
from openai import OpenAI
from openai import OpenAIError
from pathlib import Path
import yt_dlp
from utils import utils
import logging

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

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TranscriptionValidationError(Exception):
    """Custom exception for transcription validation errors"""

    pass


class OpenAIService:
    # def __init__(self, api_key, organization, project, appwrite_service=None):
    #     if not all([api_key, organization, project]):
    #         raise ValueError("Missing required OpenAI credentials")

    #     self.PROJECT_ROOT = Path(__file__).parent.parent
    #     self.client = OpenAI(
    #         api_key=api_key,
    #         organization=organization,
    #         project=project,
    #     )
    #     self.MODEL = "gpt-4o"
    #     self.appwrite_service = appwrite_service
    #     Path("media").mkdir(exist_ok=True)
    def __init__(self, api_key, organization, project, appwrite_service=None):
        if not all([api_key, organization, project]):
            raise ValueError("Missing required OpenAI credentials")

        # Get the directory where the application code is running
        self.PROJECT_ROOT = Path(__file__).parent.parent
        # Create media directory relative to the application root
        self.media_dir = self.PROJECT_ROOT / "media"
        self.media_dir.mkdir(exist_ok=True, parents=True)

        self.client = OpenAI(
            api_key=api_key,
            organization=organization,
            project=project,
        )
        self.MODEL = "gpt-4o"
        self.appwrite_service = appwrite_service

    def validate_video(self, video_id):
        logger.debug(f"Project root: {self.PROJECT_ROOT}")
        logger.debug(f"Media directory: {self.media_dir}")
        logger.debug(f"Media dir exists: {self.media_dir.exists()}")
        logger.debug(f"Media dir contents: {list(self.media_dir.glob('*'))}")
        # Check if appwrite service is available when needed
        if not self.appwrite_service:
            logger.error("Storage service not configured")
            yield utils.stream_message("error", "Storage service not configured")
            return

        result = {
            "passed": False,
            "audio_file_path": None,
            "full_vid_info": None,
            "vid_info_for_validation": None,
            "subtitle_info": {"exist": False, "path": None, "ext": None},
            "error_msg": None,
        }

        media_dir = Path("media")
        media_dir.mkdir(exist_ok=True)

        try:
            # First, try to get files from storage
            logger.info("Querying databases...")
            yield utils.stream_message("update", "Querying databases...")
            files_exist, error = self.appwrite_service.get_or_download_video_files(
                video_id
            )

            logger.debug(f"[NEW] Subtitle Files Exist ? -- {files_exist}")
            logger.debug(f"[NEW] Subtitle Files Error ? -- {error}")

            if not files_exist:
                # If files don't exist in storage, download them using yt-dlp
                logger.info("Files don't exist, downloading...")
                yield utils.stream_message("update", "Retrieving audio...")

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
                    # "outtmpl": "./media/%(id)s.%(ext)s",
                    # "subtitlesoutopt": "./media/%(id)s.%(ext)s",
                    "outtmpl": str(self.media_dir / "%(id)s.%(ext)s"),
                    "subtitlesoutopt": str(self.media_dir / "%(id)s.%(ext)s"),
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    error_code = ydl.download(
                        [f"https://www.youtube.com/watch?v={video_id}"]
                    )
                    if error_code:
                        result["error_msg"] = "Failed to receive audio"
                        yield utils.stream_message("error", result["error_msg"])
                        print("Yielded error msg from dlp")
                        print(result["error_msg"][:200])
                        return

                # Upload both files to storage as a pair
                yield utils.stream_message("update", "Saving audio...")
                song_success, metadata_success = (
                    self.appwrite_service.upload_song_with_metadata(video_id)
                )

                if not (song_success and metadata_success):
                    result["error_msg"] = "Failed to save audio"
                    yield utils.stream_message("error", result["error_msg"])
                    return

                yield utils.stream_message("update", "Files saved successfully")

            # Process video info from the metadata file
            info_file_path = media_dir / f"{video_id}.info.json"
            logger.info(f"Reading info file from: {info_file_path}")
            if not info_file_path.exists():
                logger.error(f"Info file not found at: {info_file_path}")
                raise FileNotFoundError(f"Info file missing for video {video_id}")

            try:
                with open(info_file_path, "r", encoding="utf-8") as file:
                    json_vid_info = json.load(file)
                    logger.info("Successfully loaded video info JSON")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Error reading info file: {str(e)}")
                raise

            logger.info("Processing video info...")
            # Use get() with default empty string/list for all fields

            result["full_vid_info"] = {
                "id": video_id,
                "thumbnail": json_vid_info.get("thumbnail", ""),
                "duration": json_vid_info.get("duration", 0),
                "likes": json_vid_info.get("like_count", 0),
                "playable_in_embed": json_vid_info.get("playable_in_embed", True),
                "title": json_vid_info.get("fulltitle", json_vid_info.get("title", "")),
                "channel_name": json_vid_info.get("channel", ""),
            }

            # Remove the validation of required fields since we're providing defaults
            result["vid_info_for_validation"] = {
                "title": result["full_vid_info"]["title"],
                "categories": json_vid_info.get("categories", []),
                "description": json_vid_info.get("description", ""),
                "channel_name": result["full_vid_info"]["channel_name"],
                "uploader": json_vid_info.get("uploader", ""),
                "language": json_vid_info.get("language", ""),
            }

            # Set audio path
            result["audio_file_path"] = str(media_dir / f"{video_id}.m4a")

            if not result["full_vid_info"]["playable_in_embed"]:
                result["error_msg"] = (
                    "Video is not playable outside of YouTube, please try another video."
                )
                yield utils.stream_message("error", result["error_msg"])
                return

            # Modified validation logic to handle missing language field
            is_japanese = result["vid_info_for_validation"]["language"] == "ja"
            has_music_category = (
                "Music" in result["vid_info_for_validation"]["categories"]
            )

            result["passed"] = (
                is_japanese and has_music_category
            ) or self.validate_youtube_video(result["vid_info_for_validation"])

            if not result["passed"]:
                result["error_msg"] = (
                    "This video is not a Japanese song, please try another video."
                )
                yield utils.stream_message("error", result["error_msg"])
                return

            logger.info("Before SELF APPWRITE SERVICE...")

            # Handle subtitles if they exist
            if self.appwrite_service:
                logger.info("HAS APPWRITE SERVICE - FINDING YOUTUBE SUB")
                subtitle = self.appwrite_service.find_youtube_subtitle(video_id)
                if subtitle.exists:
                    logger.info("SUBTITLE FOUND!")
                    result["subtitle_info"] = {
                        "exist": True,
                        "path": str(subtitle.path),
                        "ext": subtitle.extension,
                    }
                    logger.info("SUBTITLE INFO UPDATED")
                    logger.info(str(result["subtitle_info"]))

                    yield utils.stream_message("update", "Saving existing lyrics...")
                    if not self.appwrite_service.file_exists_in_lyrics_bucket(
                        f"{video_id}{subtitle.extension}"
                    ):
                        subtitle_upload_success = (
                            self.appwrite_service.upload_youtube_subtitle(video_id)
                        )
                        if subtitle_upload_success:
                            yield utils.stream_message(
                                "update", "Lyrics saved successfully."
                            )
                    else:
                        yield utils.stream_message(
                            "update", "Lyrics found in database."
                        )
                logger.info("---------------")
                logger.info("SUBTITLE INFO MIGHT NOT BE UPDATED")
                logger.info(str(result["subtitle_info"]))

            logger.info("Preparing to yield vid_info")
            logger.debug(f"Result object: {result}")
            try:
                logger.info("Yielding vid_info message")
                yield utils.stream_message("vid_info", result)
                logger.info("Successfully yielded vid_info message")
            except Exception as e:
                logger.error(f"Error yielding vid_info message: {str(e)}")
                raise

            time.sleep(1)
            yield utils.stream_message("update", "Validation completed.")

        except Exception as e:
            error_str = str(e)
            logger.error(f"Error in validation process: {error_str}")
            result["error_msg"] = f"Error processing video: {error_str}"
            if "stopping due to --break-match-filter" in error_str:
                result["error_msg"] = (
                    "The song must be 1-8 minutes long, please try another song."
                )
            else:
                result["error_msg"] = (
                    f"Error processing video: {error_str}, please try again or try another song."
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
        """Process only videos shorter than 5mins or longer than 1min"""
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
