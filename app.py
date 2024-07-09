import json
import sys
import os

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


@app.route("/transcribe")
def transcription_endpoint():
    # http://localhost:8080/transcribe?q=https://www.youtube.com/watch?v=sK5KMI2Xu98
    query = request.args.get("q")
    video_id = utils.extract_video_id(query)

    if video_id:
        transcription = openai_service.get_transcription(video_id)

    if not transcription:
        return jsonify("ERROR")

    else:
        lyrics_arr = transcription["lyrics"]
        timestamped_lyrics = transcription["timestamped_lyrics"]

        # TODO: Add enhancer / quality check for lyrics in openai svc
        # TODO: Add check for whether youtube alr has lyrics, use those instead
        # ###

        eng_translation, chi_translation = openai_service.get_eng_translation(
            timestamped_lyrics, video_id
        )

        # romaji_lyrics = openai_service.get_romaji_lyrics(video_id, lyrics_arr, lyrics_len)
        # kanji_lyrics = openai_service.get_kanji_lyrics(video_id, lyrics_arr, lyrics_len)

        print("Translated finish sia")
        print(timestamped_lyrics)
        print("Original Lyrics Len: " + str(len(lyrics_arr)))
        print(eng_translation)
        print("Eng Translation Len: " + str(len(eng_translation)))
        print(chi_translation)
        print("Chi Translation Len: " + str(len(chi_translation)))

        # output["full_lyrics"] = timestamped_lyrics
        # output["plain_lyrics"] = lyrics_arr
        # output["eng_translation"] = eng_translation
        # output["chi_translation"] = chi_translation
        # output["romaji"] = romaji_lyrics
        # output["kanji_annotation"] = kanji_lyrics
        # output["visit_count"] = 0

        return jsonify("DONE")


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
