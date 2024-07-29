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
from services.whisper_service import WhisperService
from utils import utils

load_dotenv()
sys.path.append('../')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

whisper_service = WhisperService()
openai_service = OpenAIService()
appwrite_service = AppwriteService()


@app.route('/available_models')
def available_models():
    models = whisper_service.get_available_models()
    return jsonify(models)

@app.route('/progress-stream/<video_id>')
def progress_stream(video_id):
    print("hey")
    # def generate():
        # while True:
            # Logic to wait for and fetch the latest progress
            # print("Task id is: ", video_id)
            # progress = whisper_service.get_progress_by_video_id(video_id)
            # print("This is progress in progress_stream", progress)
            # yield f"data: {json.dumps({'progress': progress})}\n\n"
            # time.sleep(2)  # Adjust the sleep time as needed

    # return Response(generate(), mimetype='text/event-stream')


@app.route('/transcribe')
def transcription_endpoint():
    # http://localhost:8080/transcribe?q=https://www.youtube.com/watch?v=sK5KMI2Xu98
    query = request.args.get('q')
    print("Query received: ", query)
    video_id = utils.extract_video_id(query)
    print("This is video_id", video_id)
    if video_id:
        print("Starting transcribev3 function..")
        lyrics_file = whisper_service.transcribev3(video_id)

    if(lyrics_file):
        lyrics_obj = whisper_service.parse_srt_file(lyrics_file)
        # print("lyrics parsed")
        # print("This is lyrics obj")
        # print(lyrics_obj)
        lyrics = lyrics_obj['lyrics']
        # print("This is lyrics variable")
        #? lyrics is {"lyrics", "lines"}

        lyrics_string = utils.concatenate_strings(lyrics)
        # print(lyrics)
        # print("lyrics variable above")
        # print(lyrics_string)
        filename = video_id + '.txt'
        output_path = os.path.join('output', 'plain_lyrics', filename)
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(lyrics_string)

        # ? Return before openai_service is fixed
        # return jsonify(lyrics_string)

        # eng_translation = openai_service.get_eng_translation(lyrics_string, video_id)
        # print(eng_translation)
        chi_translation = openai_service.get_chi_translation(lyrics_string, video_id)
        print(chi_translation)
        romaji = openai_service.get_romaji(lyrics_string, video_id)
        print(romaji)
        kanji_annotation = openai_service.get_kanji_annotation(lyrics_string, video_id)
        print(kanji_annotation)

        data = {"full_lyrics": lyrics_obj, 
                # "eng_translation": eng_translation, 
                "chi_translation": chi_translation, "romaji": romaji, "kanji_annotation": kanji_annotation,}
        
        return jsonify(data)
    else:
        return jsonify("No response given")



if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)