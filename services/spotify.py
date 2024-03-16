import os
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SpotifyService:
    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.token_cache = {"access_token": None, "expires_at": 0}  # Epoch time format

    def get_spotify_token(self):
        """Fetches a new access token from Spotify if the current one is expired."""
        current_time = time.time()

        if self.token_cache['access_token'] and self.token_cache['expires_at'] > current_time:
            return self.token_cache['access_token']

        token_url = "https://accounts.spotify.com/api/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()

        token_info = response.json()
        access_token = token_info['access_token']
        expires_in = token_info['expires_in']

        # Update the cache with the new token and its expiry time
        self.token_cache['access_token'] = access_token
        self.token_cache['expires_at'] = current_time + expires_in

        print("this is token: " + access_token)
        print("token expires in: " + str(expires_in))

        return access_token

    def search_song(self, song_name='優しい彗星', market="JP"):
        """Searches for a song on Spotify."""
        query_url = 'https://api.spotify.com/v1/search'
        access_token = self.get_spotify_token()
        print("This is token: " + access_token)
        print("This is song_name: " + str(song_name))
        headers = {"Authorization": f"Bearer {access_token}"}

        params = {
            "q": song_name,
            "type": 'track',
            "market": market,
            "limit": 10,
        }

        response = requests.get(query_url, params=params, headers=headers)
        response.raise_for_status()

        results = response.json()
        return results["tracks"]['items']

