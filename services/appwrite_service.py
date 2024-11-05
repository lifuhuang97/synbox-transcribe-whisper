from pathlib import Path
from dotenv import load_dotenv
import os
from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.input_file import InputFile

# Get the project root directory (assuming this file is in the root)
ROOT_DIR = Path(__file__).parent.parent.resolve()

# Default paths relative to project root
load_dotenv()

DEFAULT_LYRICS_DIR = ROOT_DIR / "output" / "response_srt"
DEFAULT_SONGS_DIR = ROOT_DIR / "output" / "track"
DEFAULT_TRANSCRIPTIONS_DIR = ROOT_DIR / "output" / "cached_translations"
DEFAULT_SUBTITLES_DIR = (
    ROOT_DIR / "output" / "track"
)  # Same as songs dir based on validate_video


class AppwriteService:
    def __init__(self, lyrics_dir=DEFAULT_LYRICS_DIR, songs_dir=DEFAULT_SONGS_DIR):
        self.client = Client()
        self.project_id = os.getenv("APPWRITE_PROJECT_ID")
        self.api_secret = os.getenv("APPWRITE_KEY")
        self.client.set_endpoint("https://cloud.appwrite.io/v1")
        self.client.set_project(self.project_id)
        self.client.set_key(self.api_secret)

        self.songs_storage_id = os.getenv("APPWRITE_STORAGE_SONGS_ID")
        self.lyrics_storage_id = os.getenv("APPWRITE_STORAGE_LYRICS_ID")

        self.storage = Storage(self.client)
        self.lyrics_dir = lyrics_dir
        self.songs_dir = songs_dir

    def upload_lyrics(self, video_id, data, lyrics_type=None):
        print("appwrite upload lyrics for id: ", video_id)

        # Determine filename and file_id based on lyrics_type
        if lyrics_type:
            filename = f"{video_id}_{lyrics_type}.txt"
            file_id = f"{video_id}_{lyrics_type}"
        else:
            filename = f"{video_id}.srt"
            file_id = video_id

        result = self.storage.create_file(
            bucket_id=self.lyrics_storage_id,
            file_id=file_id,
            file=InputFile.from_bytes(data, filename),
        )

        print(result)

    def upload_subtitles(self, video_id, subtitle_info):
        """
        Upload subtitle file from validate_video result

        Args:
            video_id (str): The video ID
            subtitle_info (dict): Dictionary containing subtitle information with keys:
                - exist (bool): Whether subtitles exist
                - path (str): Path to the subtitle file
                - ext (str): File extension of the subtitle file
        """
        if not subtitle_info["exist"] or not subtitle_info["path"]:
            print(f"No subtitle file found for video ID: {video_id}")
            return False

        try:
            with open(subtitle_info["path"], "rb") as f:
                # Create a unique file_id for subtitles
                file_id = f"{video_id}_original_subtitle"
                filename = f"{video_id}.ja{subtitle_info['ext']}"

                result = self.storage.create_file(
                    bucket_id=self.lyrics_storage_id,
                    file_id=file_id,
                    file=InputFile.from_bytes(f.read(), filename),
                )
                print(f"Successfully uploaded subtitle file for {video_id}")
                return True
        except Exception as e:
            print(f"Error uploading subtitles for {video_id}: {str(e)}")
            return False

    def upload_song(self, video_id, song_data):
        print("appwrite upload song file for id: ", video_id)

        filename = f"{video_id}.m4a"
        result = self.storage.create_file(
            bucket_id=self.songs_storage_id,
            file_id=video_id,
            file=InputFile.from_bytes(song_data, filename),
        )

        print(result)

    def find_song_file(self, video_id: str, songs_dir: Path = None) -> Path | None:
        """
        Find a song file for a specific video ID
        Expected format: {video_id}.m4a
        """
        search_dir = songs_dir or self.songs_dir
        song_path = search_dir / f"{video_id}.m4a"
        return song_path if song_path.exists() else None

    def find_lyrics_file(
        self, video_id: str, lyrics_type: str = None, lyrics_dir: Path = None
    ) -> Path | None:
        """
        Find a lyrics file for a specific video ID and optional type
        If lyrics_type is provided: {video_id}_{type}.txt
        If no lyrics_type: {video_id}.srt
        """
        search_dir = lyrics_dir or self.lyrics_dir

        if lyrics_type:
            search_dir = DEFAULT_TRANSCRIPTIONS_DIR

        if lyrics_type:
            lyrics_path = search_dir / f"{video_id}_{lyrics_type}.txt"
        else:
            lyrics_path = search_dir / f"{video_id}.srt"

        return lyrics_path if lyrics_path.exists() else None

    def upload_song_by_id(self, video_id: str, songs_dir: Path = None) -> bool:
        """
        Find and upload a song file by video ID
        Returns True if successful, False otherwise
        """
        song_file = self.find_song_file(video_id, songs_dir)
        if not song_file:
            print(f"No song file found for video ID: {video_id}")
            return False

        try:
            with open(song_file, "rb") as f:
                self.upload_song(video_id, f.read())
            return True
        except Exception as e:
            print(f"Error uploading song {video_id}: {str(e)}")
            return False

    def upload_lyrics_by_id(
        self, video_id: str, lyrics_type: str = None, lyrics_dir: Path = None
    ) -> bool:
        """
        Find and upload a lyrics file by video ID and optional type
        If lyrics_type is provided: looks for {video_id}_{type}.txt
        If no lyrics_type: looks for {video_id}.srt
        Returns True if successful, False otherwise
        """
        lyrics_file = self.find_lyrics_file(video_id, lyrics_type, lyrics_dir)
        if not lyrics_file:
            type_msg = f" and type: {lyrics_type}" if lyrics_type else ""
            print(f"No lyrics file found for video ID: {video_id}{type_msg}")
            return False

        try:
            with open(lyrics_file, "rb") as f:
                self.upload_lyrics(video_id, f.read(), lyrics_type)
            return True
        except Exception as e:
            print(f"Error uploading lyrics {video_id}: {str(e)}")
            return False


# if __name__ == "__main__":
#     # Example video ID
#     video_id = "aOKa-5AHCtU"
#     appwrite_service = AppwriteService()


#     # Example 1: Upload a song
#     # print("\nUploading song...")
#     # appwrite_service.upload_song_by_id(video_id)

#     # Example 2: Upload lyrics with type (will look for {video_id}_standard.txt)
#     print("\nUploading typed lyrics...")
#     appwrite_service.upload_lyrics_by_id(video_id, "romaji")

#     # Example 3: Upload default lyrics (will look for {video_id}.srt)
#     print("\nUploading default lyrics...")
#     appwrite_service.upload_lyrics_by_id(video_id)
