import json
import os
import sys
import threading
import time

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from services.appwrite_service import AppwriteService
from services.openai_service import OpenAIService
# from services.whisper_service import WhisperService
from utils import utils

load_dotenv()
sys.path.append('../')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

openai_service = OpenAIService()
appwrite_service = AppwriteService()

@app.route('/progress-stream/<video_id>')
def progress_stream(video_id):

    return


@app.route('/transcribe')
def transcription_endpoint():
    # http://localhost:8080/transcribe?q=https://www.youtube.com/watch?v=sK5KMI2Xu98
    query = request.args.get('q')
    video_id = utils.extract_video_id(query)

    if video_id:
        transcription = openai_service.get_transcription(video_id)

    output = {}

    if not transcription:
        return jsonify("ERROR")

    else:
        lyrics_arr = transcription['lyrics']
        lyrics_len = len(lyrics_arr)
        timestamped_lyrics = transcription['timestamped_lyrics']

        # TODO: Add enhancer / quality check for lyrics in openai svc
        # TODO: Add check for whether youtube alr has lyrics, use those instead
        # ###

        eng_translation = openai_service.get_eng_translation(video_id, lyrics_arr, lyrics_len)
        chi_translation = openai_service.get_chi_translation(video_id, lyrics_arr, lyrics_len)
        romaji_lyrics = openai_service.get_romaji_lyrics(video_id, lyrics_arr, lyrics_len)
        kanji_lyrics = openai_service.get_kanji_lyrics(video_id, lyrics_arr, lyrics_len)

        
        output["full_lyrics"] = timestamped_lyrics
        output["plain_lyrics"] = lyrics_arr
        output["eng_translation"] = eng_translation
        output["chi_translation"] = chi_translation
        output["romaji"] = romaji_lyrics
        output["kanji_annotation"] = kanji_lyrics
        output["visit_count"] = 0

        appwrite_service.upload_lyrics(video_id, output)

        return jsonify("DONE")


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)