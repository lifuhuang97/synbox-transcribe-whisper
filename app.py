import glob
import json
import sys
import os
import re
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS

from services.appwrite_service import AppwriteService
from services.openai_service import OpenAIService

from utils import utils

load_dotenv()
sys.path.append("../")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

openai_service = OpenAIService(api_key=os.getenv("OPENAI_KEY"))
appwrite_service = AppwriteService()


@app.route("/")
def init_page():
    return "Hey"


@app.route("/test", methods=["OPTIONS", "POST"])
def test_endpoint():
    if request.method == "OPTIONS":
        response = app.make_response("")
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response

    def generate():
        if request.method == "POST":
            yield utils.stream_message("update", "Step One")
            time.sleep(1)
            yield utils.stream_message("data", "Data Fragment 1...")
            time.sleep(1)
            yield utils.stream_message("data", "Data Fragment 2...")
            # time.sleep(1)
            # yield utils.stream_message("error", "Something went wrong...")
            time.sleep(1)
            yield utils.stream_message("update", "Video validation completed")
            time.sleep(1)
            yield utils.stream_message(
                "vid_info",
                {
                    "id": "NDwqZIXOvKw",
                    "title": "【MV】KANA-BOON 『シルエット』",
                    "author": "KANA-BOON",
                    "views": 2000000,
                    "duration": 200,
                },
            )
            time.sleep(1)
            yield utils.stream_message("update", "Ending...")

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


#! Step 1
@app.route("/validate", methods=["OPTIONS", "POST"])
def validation_endpoint():
    if request.method == "OPTIONS":
        response = app.make_response("")
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        return response

    def generate():
        if request.method == "POST":
            yield utils.stream_message("update", "Receiving Updates...")
            time.sleep(2)
            yield utils.stream_message("update", "Retrieving video information...")
            try:
                # Extract the query parameter
                data = request.json
                print("Data: ", data)
                video_id = data.get("id")

                for update in openai_service.validate_video(video_id):
                    yield update

                yield utils.stream_message("update", "Validation complete.")

            except Exception as e:
                yield utils.stream_message("error", str(e))

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

                # Translation process with retry mechanism
                MAX_RETRIES = 3
                retry_count = 0
                eng_translation, chi_translation = None, None

                while retry_count < MAX_RETRIES:
                    try:
                        yield utils.stream_message(
                            "update",
                            f"Attempting translations (try {retry_count + 1}/{MAX_RETRIES})...",
                        )
                        eng_translation, chi_translation = (
                            openai_service.get_translations(
                                timestamped_lyrics, video_id
                            )
                        )
                        if eng_translation and chi_translation:
                            yield utils.stream_message(
                                "update", "Translations completed successfully."
                            )
                            break
                    except ValueError as e:
                        yield utils.stream_message(
                            "update",
                            f"Translation attempt {retry_count + 1} failed: {str(e)}",
                        )
                        retry_count += 1
                        if retry_count == MAX_RETRIES:
                            yield utils.stream_message(
                                "error",
                                "Max retries reached. Unable to get translations.",
                            )
                            return
                        else:
                            yield utils.stream_message(
                                "update",
                                f"Retrying translation (attempt {retry_count + 1})...",
                            )

                if eng_translation is None or chi_translation is None:
                    yield utils.stream_message("error", "Translation failed")
                    return

                # Romaji lyrics
                yield utils.stream_message("update", "Generating romaji lyrics...")
                romaji_lyrics = openai_service.get_romaji_lyrics(lyrics_arr, video_id)

                # Kanji annotations
                yield utils.stream_message("update", "Generating kanji annotations...")
                kanji_annotations = openai_service.get_kanji_annotations(
                    lyrics_arr, video_id
                )

                if romaji_lyrics is None or kanji_annotations is None:
                    yield utils.stream_message(
                        "error", "Romaji or kanji annotation failed"
                    )
                    return

                # Send final results
                yield utils.stream_message(
                    "result",
                    {
                        "eng_translation": eng_translation,
                        "chi_translation": chi_translation,
                        "romaji_lyrics": romaji_lyrics,
                        "kanji_annotations": kanji_annotations,
                    },
                )

                yield utils.stream_message(
                    "update", "Translation and annotation process completed."
                )

            except Exception as e:
                yield utils.stream_message("error", str(e))

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


@app.route("/transcribe")
def transcription_endpoint():
    # http://localhost:8080/transcribe?q=https://www.youtube.com/watch?v=sK5KMI2Xu98
    query = request.args.get("q")
    video_id = utils.extract_video_id(query)

    transcription = None

    if video_id:
        # Check if an existing .srt file is available
        srt_file_path = f"./output/response_srt/{video_id}.srt"
        if os.path.exists(srt_file_path):
            print("SRT file exists, using it... ")
            transcription = utils.process_subtitle_file(
                srt_file_path,
                "srt",
                apply_error_checks=True,
            )
            with open(srt_file_path, "w", encoding="utf-8") as file:
                file.write(transcription["filtered_srt"])
        else:
            print("SRT file doesnt exist, transcribing...")
            # Fetch new transcription and process it

            # TODO: Make it re-try if detected all lyrics are same line >> probably errored out
            raw_transcription_output_path = openai_service.get_transcription(video_id)
            transcription = transcription = utils.process_subtitle_file(
                raw_transcription_output_path,
                "srt",
                apply_error_checks=True,
            )
            with open(srt_file_path, "w", encoding="utf-8") as file:
                file.write(transcription["filtered_srt"])

        # ? New code to generate plain text file

    if not transcription:
        return jsonify("ERROR: No transcription available")

    MAX_RETRIES = 3
    retry_count = 0

    lyrics_arr = transcription["lyrics"]
    timestamped_lyrics = transcription["timestamped_lyrics"]

    eng_translation, chi_translation = None, None

    # Make the retry mechanism change the temperature
    while retry_count < MAX_RETRIES:
        try:
            eng_translation, chi_translation = openai_service.get_translations(
                timestamped_lyrics, video_id
            )
            if eng_translation and chi_translation:
                break  # Success, exit the loop
        except ValueError as e:
            print(f"Attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            if retry_count == MAX_RETRIES:
                print("Max retries reached. Unable to get translations.")
                # Handle the error (e.g., return an error response)
            else:
                print("Retrying #" + str(retry_count + 1) + "...")

    if (
        lyrics_arr is not None
        and eng_translation is not None
        and chi_translation is not None
    ):
        print("Translated finish sia")
        print("Original Lyrics Len: " + str(len(lyrics_arr)))
        print("Eng Translation Len: " + str(len(eng_translation)))
        print("Chi Translation Len: " + str(len(chi_translation)))
    else:
        return jsonify("ERROR: Translation failed")

    romaji_lyrics = openai_service.get_romaji_lyrics(lyrics_arr, video_id)
    kanji_annotations = openai_service.get_kanji_annotations(lyrics_arr, video_id)

    if (
        eng_translation is None
        or chi_translation is None
        or romaji_lyrics is None
        or kanji_annotations is None
    ):
        return jsonify("ERROR: Romaji annotation or kanji annotation failed")

    return jsonify(
        {
            "lyrics": lyrics_arr,
            "eng_translation": eng_translation,
            "chi_translation": chi_translation,
            "romaji_lyrics": romaji_lyrics,
            "kanji_annotations": kanji_annotations,
        }
    )


# @app.route("/stream_conversation", methods=["POST"])
@app.route("/stream_conversation")
def stream_conversation():
    def generate():

        srt_path = "./output/track/NDwqZIXOvKw.ja.vtt"

        transcription = utils.process_subtitle_file(
            srt_path, "vtt", apply_error_checks=False
        )
        response = openai_service.get_eng_translation_test(transcription)
        for chunk in response:
            yield f"data: {json.dumps({'content': chunk})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
