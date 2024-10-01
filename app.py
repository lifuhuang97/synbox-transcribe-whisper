import sys
import os
import time

from dotenv import load_dotenv
from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS

from services.romaji_annotator import RomajiAnnotator
from services.appwrite_service import AppwriteService
from services.openai_service import OpenAIService

from utils import utils

load_dotenv()
sys.path.append("../")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

openai_service = OpenAIService(api_key=os.getenv("OPENAI_KEY"))
appwrite_service = AppwriteService()
romaji_annotator = RomajiAnnotator(api_key=os.getenv("OPENAI_KEY"))


@app.route("/")
def init_page():
    return "Hey"


#! Step 1
@app.route("/validate", methods=["OPTIONS", "POST"])
def validation_endpoint():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response

    def generate():
        if request.method == "POST":
            yield utils.stream_message("update", "Initializing...")
            time.sleep(0.5)
            yield utils.stream_message("update", "Parsing request data...")
            time.sleep(0.5)

            try:
                data = request.json
                video_id = data.get("id")

                if not video_id:
                    raise ValueError("Invalid or missing video ID in request.")

                yield utils.stream_message(
                    "update",
                    f"Video ID {video_id} received.",
                )
                time.sleep(1)

                yield utils.stream_message("update", "Fetching video data...")
                time.sleep(1.5)

                for update in openai_service.validate_video(video_id):
                    yield update

                yield utils.stream_message("update", "Finalizing validation process...")
                time.sleep(0.5)

                yield utils.stream_message(
                    "success",
                    "Validation complete.",
                )

            except ValueError as ve:
                yield utils.stream_message("error", f"Validation Error: {str(ve)}")
            except Exception as e:
                yield utils.stream_message(
                    "error", f"An unexpected error occurred: {str(e)}"
                )

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


#! Step 2
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
            print("data is ", data)
            video_id = data.get("id")
            subtitle_info = data.get("subtitle_info")
            print("subtitle info is ", subtitle_info)
            subtitle_exist = subtitle_info["exist"]

            try:
                if subtitle_exist:
                    subtitle_file_path = subtitle_info["path"]
                    subtitle_ext = subtitle_info["ext"]

                    transcription = utils.process_subtitle_file(
                        subtitle_file_path, subtitle_ext, apply_error_checks=False
                    )
                    ai_generated = False
                else:
                    audio_path = f"./output/track/{video_id}.m4a"
                    raw_transcription_path = openai_service.get_transcription(
                        video_id, audio_path
                    )
                    transcription = utils.process_subtitle_file(
                        raw_transcription_path, "srt", apply_error_checks=True
                    )
                    ai_generated = True

                yield utils.stream_message("update", "Transcription completed.")
                yield utils.stream_message("ai_generated", ai_generated)
                yield utils.stream_message("transcription", transcription)

            except Exception as e:
                error_message = f"An error occurred during transcription: {str(e)}"
                print(error_message)  # Log the error
                yield utils.stream_message("error", error_message)
                return  # Stop the generator after sending the error message

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


#! Step 3
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

                # Define the base directory for cached translations
                cache_dir = "./output/cached_translations"
                os.makedirs(cache_dir, exist_ok=True)

                # Define cache paths
                eng_cache_path = os.path.join(cache_dir, f"{video_id}_eng.txt")
                chi_cache_path = os.path.join(cache_dir, f"{video_id}_chi.txt")
                romaji_cache_path = os.path.join(cache_dir, f"{video_id}_romaji.txt")
                kanji_cache_path = os.path.join(cache_dir, f"{video_id}_kanji.txt")

                # Function to read cached data
                def read_cached_data(path):
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            return f.read().splitlines()
                    return None

                # Read cached data
                eng_translation = read_cached_data(eng_cache_path)
                chi_translation = read_cached_data(chi_cache_path)
                romaji_lyrics = read_cached_data(romaji_cache_path)
                kanji_annotations = read_cached_data(kanji_cache_path)

                # Check and generate translations if needed
                if eng_translation is None or chi_translation is None:
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
                                timestamped_lyrics, video_id, retry_count
                            ):
                                if translation_type == "eng_translation":
                                    eng_translation = translation
                                    with open(
                                        eng_cache_path, "w", encoding="utf-8"
                                    ) as f:
                                        f.write("\n".join(eng_translation))
                                elif translation_type == "chi_translation":
                                    chi_translation = translation
                                    with open(
                                        chi_cache_path, "w", encoding="utf-8"
                                    ) as f:
                                        f.write("\n".join(chi_translation))
                                yield utils.stream_message(
                                    translation_type, translation
                                )

                            translations_completed = True
                            yield utils.stream_message(
                                "update", "Translations completed successfully."
                            )
                        except ValueError as e:
                            retry_count += 1
                            if retry_count == MAX_RETRIES:
                                yield utils.stream_message(
                                    "error",
                                    f"Max retries reached. Unable to get translations. Error: {e}",
                                )
                                return
                            else:
                                yield utils.stream_message(
                                    "update",
                                    f"Retrying translation (attempt {retry_count + 1})...",
                                )
                else:
                    yield utils.stream_message("update", "Using cached translations...")
                    yield utils.stream_message("eng_translation", eng_translation)
                    yield utils.stream_message("chi_translation", chi_translation)

                # Generate Romaji lyrics if needed
                if romaji_lyrics is None:
                    yield utils.stream_message("update", "Generating romaji lyrics...")
                    try:
                        for (
                            message_type,
                            message_content,
                        ) in romaji_annotator.get_romaji_lyrics(lyrics_arr, video_id):
                            if message_type == "romaji_lyrics":
                                romaji_lyrics = message_content
                                yield utils.stream_message(message_type, romaji_lyrics)

                                with open(
                                    romaji_cache_path, "w", encoding="utf-8"
                                ) as f:
                                    f.write("\n".join(romaji_lyrics))
                            elif message_type == "error":
                                yield utils.stream_message(
                                    "error",
                                    f"Romaji generation failed: {message_content}",
                                )
                                pass
                    except ValueError:
                        # yield utils.stream_message(
                        #     "error", f"Romaji generation failed: {str(e)}"
                        # )
                        return
                else:
                    yield utils.stream_message(
                        "update", "Using cached romaji lyrics..."
                    )
                    yield utils.stream_message("romaji_lyrics", romaji_lyrics)

                # Generate Kanji annotations if needed
                if kanji_annotations is None:
                    yield utils.stream_message(
                        "update", "Generating kanji annotations..."
                    )
                    try:
                        for (
                            kanji_type,
                            kanji_annotations_part,
                        ) in openai_service.get_kanji_annotations(lyrics_arr, video_id):
                            kanji_annotations = kanji_annotations_part
                            yield utils.stream_message(kanji_type, kanji_annotations)

                        with open(kanji_cache_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(kanji_annotations))
                    except ValueError as e:
                        yield utils.stream_message(
                            "error", f"Kanji annotation failed: {str(e)}"
                        )
                        return
                else:
                    yield utils.stream_message(
                        "update", "Using cached kanji annotations..."
                    )
                    yield utils.stream_message("kanji_annotations", kanji_annotations)

                yield utils.stream_message(
                    "update", "Translation and annotation process completed."
                )
                
                utils.cleanup_files(video_id)
                yield utils.stream_message("update", "Cleanup completed.")

            except Exception as e:
                yield utils.stream_message("error", str(e))
                
                if 'video_id' in locals():
                    utils.cleanup_files(video_id)
                    yield utils.stream_message("update", "Cleanup completed after error.")

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
