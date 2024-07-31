import glob
import json
import sys
import os
import re

from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
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


# @app.route("/stream_conversation", methods=["POST"])
@app.route("/stream_conversation")
def stream_conversation():
    def generate():

        srt_path = "./output/response_srt/ZRtdQ81jPUQ.srt"

        with open(srt_path, "r", encoding="utf-8") as file:
            content = file.read()
            transcription = openai_service.process_gpt_transcription(content)
            response = openai_service.get_eng_translation_test(transcription)
            for chunk in response:
                yield f"data: {json.dumps({'content': chunk})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/validate")
def validation_endpoint():
    # http://localhost:8080/validate?q=https://www.youtube.com/watch?v=sK5KMI2Xu98
    try:
        # Extract the query parameter
        query = request.args.get("q")
        video_id = utils.extract_video_id(query)

        # Validate the video and get the necessary information
        validated, audio_path, vid_info, validation_info, subtitle_info, error_msg = (
            openai_service.validate_video(video_id)
        )

        # Return the JSON response
        return (
            jsonify(
                {
                    "validated": validated,
                    "audio_path": audio_path,
                    "vid_info": vid_info,
                    "validation_info": validation_info,
                    "subtitle_info": subtitle_info,
                    "error_msg": error_msg,
                }
            ),
            200,
        )
    except Exception as e:
        # Return a JSON response in case of an error
        return jsonify({"error": str(e)}), 500


@app.route("/transcribev2", methods=['POST'])
def transcription_endpoint_v2():
    data = request.json
    video_id = data.get("id")
    subtitle_info = data.get("subtitle_info")
    subtitle_exist = subtitle_info.exist
    
    # ? Check for whether there was downloaded subtitles
    if subtitle_exist:
        subtitle_file = subtitle_info.path
        subtitle_ext = subtitle_info.ext

        # with open(srt_file_path, "r", encoding="utf-8") as file:
        #     # Read the .srt file content
        #     srt_content = file.read()
        #     # Process the existing transcription
        #     transcription = openai_service.process_gpt_transcription(srt_content)
        # with open(srt_file_path, "w", encoding="utf-8") as file:
        #     file.write(transcription["filtered_srt"])
    else:
        # ? Audio file path
        audio_path = f"./output/track/{video_id}.m4a"
        raw_transcription = openai_service.get_transcription(video_id, audio_path)
        transcription = openai_service.process_gpt_transcription(raw_transcription)


    return "Yo"


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
            with open(srt_file_path, "r", encoding="utf-8") as file:
                # Read the .srt file content
                srt_content = file.read()
                # Process the existing transcription
                transcription = openai_service.process_gpt_transcription(srt_content)
            with open(srt_file_path, "w", encoding="utf-8") as file:
                file.write(transcription["filtered_srt"])
        else:
            print("SRT file doesnt exist, transcribing...")
            # Fetch new transcription and process it

            # TODO: Make it re-try if detected all lyrics are same line >> probably errored out
            raw_transcription = openai_service.get_transcription(video_id)
            transcription = openai_service.process_gpt_transcription(raw_transcription)
            with open(srt_file_path, "w", encoding="utf-8") as file:
                file.write(transcription["filtered_srt"])

        # ? New code to generate plain text file
        txt_save_path = f"./output/response_srt/{video_id}_plain.txt"

        try:
            with open(srt_file_path, "r", encoding="utf-8") as srt_file, open(
                txt_save_path, "w", encoding="utf-8"
            ) as txt_file:
                for line in srt_file:
                    # Remove indexes, timestamps, and newlines
                    if re.match(r"^\d+$", line) or re.match(
                        r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$",
                        line,
                    ):
                        continue  # Skip indexes and timestamps
                    if line.strip():  # Check if the line is not empty
                        txt_file.write(line)

            print(f"Plain text lyrics saved to {txt_save_path}")
        except Exception as e:
            print(f"An error occurred while creating plain text file: {e}")

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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
