from flask import Flask, jsonify, request
from flask_cors import CORS

from services.spotify import SpotifyService
from services.transcribe import TranscribeService

app = Flask(__name__)
CORS(app)

spotify_service = SpotifyService()
transcribe_service = TranscribeService()

@app.route('/test')
def spotify_endpoint():
    song_name = request.args.get('q')
    song_list = spotify_service.search_song(song_name)

    songs_data = [{"author": song['artists'][0]['name'], "title": song['name'], "id": song['id'], "images":song["album"]["images"][0]["url"]} for song in song_list]

    print("This is song data")
    print(songs_data)
    return jsonify(songs_data)

if __name__ == '__main__':
    app.run(debug=True)

