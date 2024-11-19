import json
from pathlib import Path
import sys
import os
import time
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS, cross_origin
from werkzeug.middleware.proxy_fix import ProxyFix
import logging

from services.romaji_annotator import RomajiAnnotator
from services.appwrite_service import AppwriteService
from services.openai_service import OpenAIService
from utils import utils

load_dotenv(override=True)
sys.path.append("../")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config.update(
    PROPAGATE_EXCEPTIONS=True, PREFERRED_URL_SCHEME="https", STREAMING_TIMEOUT=300
)
CORS(app, resources={r"/*": {"origins": "*"}})

# Create necessary directories
MEDIA_DIR = "media"
OUTPUT_TRACK_DIR = os.path.join("output", "track")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app.log")],
)
logger = logging.getLogger(__name__)

# Ensure directories exist
if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)
if not os.path.exists(OUTPUT_TRACK_DIR):
    os.makedirs(OUTPUT_TRACK_DIR)

appwrite_service = AppwriteService()
openai_service = OpenAIService(
    api_key=os.getenv("OPENAI_KEY"),
    organization=os.getenv("OPENAI_ORG"),
    project=os.getenv("OPENAI_PROJ"),
    appwrite_service=appwrite_service,
)
romaji_annotator = RomajiAnnotator(
    api_key=os.getenv("OPENAI_KEY"),
    organization=os.getenv("OPENAI_ORG"),
    project=os.getenv("OPENAI_PROJ"),
)


@cross_origin(origin=["*"], headers=["Content-Type", "Authorization"])
@app.route("/")
def init_page():
    return "Hey"


#! Cors Test Endpoint
@cross_origin(origin=["*"], headers=["Content-Type", "Authorization"])
@app.route("/cors-test", methods=["GET", "OPTIONS"])
def cors_test():
    return jsonify({"message": "CORS test successful", "status": "ok"})


#! Step 1
@cross_origin(origin=["*"], headers=["Content-Type", "Authorization"])
@app.route("/validate", methods=["OPTIONS", "POST"])
def validation_endpoint():
    logger.info("Received validation request")
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response

    def generate():
        if request.method == "POST":

            yield utils.stream_message("update", "Initializing...")
            time.sleep(0.3)

            try:
                data = request.json
                video_id = data.get("id")
                if not video_id:
                    raise ValueError("Invalid or missing video ID in request.")

                yield utils.stream_message(
                    "update", f"Received request for ID {video_id}"
                )
                time.sleep(0.3)

                yield utils.stream_message("update", "Gathering video metadata...")
                time.sleep(0.4)

                # Stream validation updates (now includes upload)
                for update in openai_service.validate_video(video_id):
                    if isinstance(update, str) and "vid_info" in update:
                        try:
                            vid_info = json.loads(update)
                            if "data" in vid_info:
                                subtitle_info = vid_info["data"].get(
                                    "subtitle_info", {}
                                )
                                logger.info("Subtitle Info Details:")
                                logger.info(
                                    f"Exists: {subtitle_info.get('exist', False)}"
                                )
                                logger.info(f"Path: {subtitle_info.get('path', 'N/A')}")
                                logger.info(
                                    f"Extension: {subtitle_info.get('ext', 'N/A')}"
                                )
                                logger.info("-" * 50)
                        except json.JSONDecodeError:
                            logger.error("Failed to parse vid_info JSON")
                        except Exception as e:
                            logger.error(f"Error processing vid_info: {str(e)}")
                    logger.debug(f"Yielding update: {update[:200]}...")
                    yield update

            except ValueError as ve:
                yield utils.stream_message("error", f"Validation Error: {str(ve)}")
            except Exception as e:
                print("VALIDATION ERROR ")
                yield utils.stream_message(
                    "error", f"An unexpected error occurred: {str(e)}"
                )

    response = Response(
        stream_with_context(generate()), mimetype="application/x-ndjson"
    )
    # Add crucial headers for streaming
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["Transfer-Encoding"] = "chunked"
    return response


#! Step 2
@cross_origin(origin=["*"], headers=["Content-Type", "Authorization"])
@app.route("/transcribev2", methods=["POST"])
def transcription_endpoint_v2():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response

    def generate():
        if request.method == "POST":
            data = request.json
            video_id = data.get("id")
            subtitle_info = data.get("subtitle_info")
            force_ai_transcription = data.get("force_ai_transcription", False)
            subtitle_exist = subtitle_info["exist"] and not force_ai_transcription

            try:
                temp_dir = Path("./temp")
                temp_dir.mkdir(exist_ok=True)
                yield utils.stream_message("update", "Initializing transcription...")
                time.sleep(2)
                if subtitle_exist:
                    yield utils.stream_message(
                        "update", "Retrieving saved subtitles..."
                    )

                    subtitle_ext = subtitle_info["ext"]
                    subtitle_file_path = temp_dir / f"{video_id}{subtitle_ext}"

                    if appwrite_service.download_lyrics(
                        f"{video_id}{subtitle_ext}", subtitle_file_path
                    ):
                        if subtitle_file_path.stat().st_size > 0:
                            processed_srt_path = temp_dir / f"{video_id}.srt"
                            transcription_result = utils.process_subtitle_file(
                                str(subtitle_file_path),
                                subtitle_ext.lstrip(".").split(".")[-1],
                                apply_error_checks=False,
                            )

                            # Extract the filtered_srt content
                            srt_content = transcription_result["filtered_srt"]

                            # Debug logging
                            print(f"SRT content type: {type(srt_content)}")
                            print(
                                f"SRT content preview: {srt_content[:200]}..."
                            )  # First 200 chars

                            with open(processed_srt_path, "w", encoding="utf-8") as f:
                                f.write(srt_content)

                            # appwrite_service.upload_srt_subtitle(video_id, temp_dir)

                            ai_generated = False
                            yield utils.stream_message(
                                "update",
                                "Subtitles retrieved and processed successfully.",
                            )
                        else:
                            subtitle_exist = False
                    else:
                        subtitle_exist = False

                if not subtitle_exist:
                    yield utils.stream_message("update", "Transcription in progress...")

                    audio_path = temp_dir / f"{video_id}.m4a"
                    if not appwrite_service.download_song(
                        f"{video_id}.m4a", audio_path
                    ):
                        audio_path = temp_dir / f"{video_id}.mp4"
                        if not appwrite_service.download_song(
                            f"{video_id}.mp4", audio_path
                        ):
                            raise Exception("Failed to download audio file")

                    raw_transcription_path = openai_service.get_transcription(
                        video_id, audio_path
                    )

                    if raw_transcription_path == "Failed to get transcription":
                        raise Exception("Failed to generate transcription")

                    if not os.path.exists(raw_transcription_path):
                        raise FileNotFoundError(
                            f"Generated SRT file not found: {raw_transcription_path}"
                        )

                    transcription_result = utils.process_subtitle_file(
                        raw_transcription_path, "srt", apply_error_checks=True
                    )

                    # Extract the filtered_srt content
                    srt_content = transcription_result["filtered_srt"]

                    processed_srt_path = temp_dir / f"{video_id}.srt"
                    with open(processed_srt_path, "w", encoding="utf-8") as f:
                        f.write(srt_content)

                    ai_generated = True
                    yield utils.stream_message(
                        "update", "Transcription generated successfully."
                    )

                for file in temp_dir.glob(f"{video_id}*"):
                    file.unlink(missing_ok=True)

                yield utils.stream_message("ai_generated", ai_generated)
                yield utils.stream_message(
                    "transcription",
                    {
                        "lyrics": transcription_result["lyrics"],
                        "timestamped_lyrics": transcription_result[
                            "timestamped_lyrics"
                        ],
                    },
                )

            except Exception as e:
                error_message = f"An error occurred during transcription: {str(e)}"
                print(error_message)
                yield utils.stream_message("error", error_message)
                return

    response = Response(
        stream_with_context(generate()), mimetype="application/x-ndjson"
    )
    # Add crucial headers for streaming
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["Transfer-Encoding"] = "chunked"
    return response


#! Step 3
@cross_origin(origin=["*"], headers=["Content-Type", "Authorization"])
@app.route("/translate-annotate", methods=["OPTIONS", "POST"])
def translate_annotate_endpoint():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response

    def generate():
        if request.method == "POST":
            yield utils.stream_message(
                "update", "Starting translation and annotation process..."
            )

            try:
                data = request.json
                video_id = data.get("id")
                lyrics_arr = data.get("lyrics")
                timestamped_lyrics = data.get("timestamped_lyrics")

                # Process lyrics while preserving timestamp relationships
                try:
                    cleaned_lyrics, cleaned_timestamped = (
                        utils.process_lyrics_for_translation(
                            lyrics_arr, timestamped_lyrics
                        )
                    )

                    # Verify timing preservation
                    if len(cleaned_lyrics) != len(cleaned_timestamped):
                        raise ValueError(
                            f"Timing mismatch after processing. Lyrics: {len(cleaned_lyrics)}, "
                            f"Timestamps: {len(cleaned_timestamped)}"
                        )

                    # Log processing results for debugging
                    print(f"Original lyrics count: {len(lyrics_arr)}")
                    print(f"Processed lyrics count: {len(cleaned_lyrics)}")

                    # Verify timestamp preservation
                    for i, (orig, processed) in enumerate(
                        zip(timestamped_lyrics, cleaned_timestamped)
                    ):
                        if orig["start_time"] != processed["start_time"]:
                            print(f"Timestamp mismatch at index {i}")
                            print(f"Original: {orig}")
                            print(f"Processed: {processed}")

                except ValueError as e:
                    yield utils.stream_message(
                        "error", f"Error processing lyrics: {str(e)}"
                    )
                    return

                # Translation step
                yield utils.stream_message("task_update", "translation")
                yield utils.stream_message("update", "Generating translations...")

                MAX_RETRIES = 3
                retry_count = 0
                translations_completed = False

                while retry_count < MAX_RETRIES and not translations_completed:
                    try:
                        for (
                            translation_type,
                            translation,
                        ) in openai_service.get_translations(
                            cleaned_lyrics, video_id, retry_count
                        ):
                            yield utils.stream_message(translation_type, translation)

                        translations_completed = True
                        yield utils.stream_message(
                            "update", "Lyrics translated successfully!"
                        )
                        time.sleep(1)
                    except ValueError as e:
                        print(e)
                        retry_count += 1
                        if retry_count == MAX_RETRIES:
                            yield utils.stream_message(
                                "error",
                                "We failed to translate the given lyrics, please try again :(",
                            )
                            return
                        else:
                            match retry_count:
                                case 1:
                                    yield utils.stream_message(
                                        "update",
                                        "Retrying translations with an AI who's more creative...",
                                    )
                                case 2:
                                    yield utils.stream_message(
                                        "update",
                                        "Retrying translations with an AI who's more serious...",
                                    )
                                case 3:
                                    yield utils.stream_message(
                                        "update",
                                        "Final attempt: Unleashing maximum AI creativity for the task!",
                                    )

                # Romaji annotation step
                yield utils.stream_message("task_update", "romaji")
                yield utils.stream_message("update", "Generating romaji lyrics...")

                try:
                    for (
                        message_type,
                        message_content,
                    ) in romaji_annotator.get_romaji_lyrics(cleaned_lyrics, video_id):
                        if message_type == "romaji_lyrics":
                            yield utils.stream_message(message_type, message_content)
                            yield utils.stream_message(
                                "update", "Romaji annotated successfully!"
                            )
                            yield utils.stream_message("task_update", "kanji")
                        elif message_type == "error":
                            yield utils.stream_message(
                                "error",
                                f"Romaji generation failed: {message_content}",
                            )
                except ValueError:
                    yield utils.stream_message(
                        "error",
                        "We failed to generate romaji for the given lyrics, please try again :(",
                    )

                # Kanji annotation step
                yield utils.stream_message("task_update", "kanji")
                yield utils.stream_message("update", "Generating kanji annotations...")

                try:
                    for (
                        kanji_type,
                        kanji_annotations,
                    ) in openai_service.get_kanji_annotations(cleaned_lyrics, video_id):
                        yield utils.stream_message(kanji_type, kanji_annotations)
                        yield utils.stream_message(
                            "update", "Kanji annotated successfully!"
                        )
                except ValueError as e:
                    yield utils.stream_message(
                        "error", f"Kanji annotation failed: {str(e)}"
                    )
                    return

                time.sleep(1)
                yield utils.stream_message("task_update", "completion")
                yield utils.stream_message("update", "All processes completed!")

            except Exception as e:
                yield utils.stream_message("error", str(e))

    response = Response(
        stream_with_context(generate()), mimetype="application/x-ndjson"
    )
    # Add crucial headers for streaming
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["Transfer-Encoding"] = "chunked"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
