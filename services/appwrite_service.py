from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import os
from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.payload import Payload
from appwrite.exception import AppwriteException


@dataclass
class SubtitleFile:
    """Represents a subtitle file with its path and extension"""

    exists: bool
    path: Optional[Path]
    extension: Optional[str]


class AppwriteService:
    """Service for managing audio and subtitle files in Appwrite storage"""

    SUPPORTED_SUBTITLE_FORMATS = (".ja.vtt", ".ja.srt", ".ja.ass", ".ja.ssa")
    SUPPORTED_AUDIO_FORMATS = (".m4a", ".mp4")

    def __init__(self):
        # Check for required environment variables
        required_env_vars = ["APPWRITE_PROJECT_ID", "APPWRITE_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        # Initialize Appwrite client
        self.client = Client()
        self.client.set_endpoint("https://cloud.appwrite.io/v1")
        self.client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        self.client.set_key(os.getenv("APPWRITE_KEY"))

        # Initialize storage service
        self.storage = Storage(self.client)

        # Get bucket IDs from environment
        self.lyrics_bucket_id = os.getenv("APPWRITE_STORAGE_LYRICS_ID")
        self.songs_bucket_id = os.getenv("APPWRITE_STORAGE_SONGS_ID")

        if not all([self.lyrics_bucket_id, self.songs_bucket_id]):
            raise ValueError("Missing required bucket IDs")

    def file_exists_in_bucket(self, bucket_id: str, file_id: str) -> bool:
        """Check if a file exists in the specified bucket"""
        try:
            # Try to get the file view - if successful, file exists
            self.storage.get_file_view(bucket_id, file_id)
            return True
        except AppwriteException as e:
            # If file doesn't exist, Appwrite will return a 404 error
            if "404" in str(e):
                return False
            # For other errors, log and re-raise
            print(f"Error checking file existence: {str(e)}")
            raise

    def file_exists_in_lyrics_bucket(self, file_id: str) -> bool:
        """Check if a file exists in the lyrics bucket"""
        try:
            return self.file_exists_in_bucket(self.lyrics_bucket_id, file_id)
        except AppwriteException as e:
            print(f"Error checking lyrics file: {str(e)}")
            # Return False and log error instead of crashing
            return False

    def file_exists_in_songs_bucket(self, file_id: str) -> bool:
        """Check if a file exists in the songs bucket"""
        try:
            return self.file_exists_in_bucket(self.songs_bucket_id, file_id)
        except AppwriteException as e:
            print(f"Error checking song file: {str(e)}")
            # Return False and log error instead of crashing
            return False

    def find_youtube_subtitle(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> SubtitleFile:
        """
        Find YouTube subtitle file in various formats (.ja.vtt, .ja.srt, .ja.ass, .ja.ssa)
        """
        for ext in self.SUPPORTED_SUBTITLE_FORMATS:
            subtitle_path = media_dir / f"{video_id}{ext}"
            if subtitle_path.exists():
                return SubtitleFile(exists=True, path=subtitle_path, extension=ext)

        return SubtitleFile(exists=False, path=None, extension=None)

    def upload_youtube_subtitle(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> bool:
        """
        Upload YouTube subtitle file to lyrics bucket.
        The file should be in format: {video_id}.ja.{vtt/srt/ass/ssa}
        """
        subtitle = self.find_youtube_subtitle(video_id, media_dir)
        if not subtitle.exists:
            print(f"No YouTube subtitle found for video ID: {video_id}")
            return False

        file_id = f"{video_id}{subtitle.extension}"

        # Check if file already exists
        if self.file_exists_in_lyrics_bucket(file_id):
            print(f"Subtitle already exists in storage: {file_id}")
            return True

        try:
            payload = Payload.from_file(subtitle.path, filename=file_id)
            self.storage.create_file(
                bucket_id=self.lyrics_bucket_id, file_id=file_id, file=payload
            )
            print(f"Successfully uploaded YouTube subtitle: {file_id}")
            return True
        except Exception as e:
            print(f"Error uploading YouTube subtitle {file_id}: {str(e)}")
            return False

    def upload_srt_subtitle(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> bool:
        """
        Upload cleaned up .srt file to lyrics bucket.
        The file should be in format: {video_id}.srt
        """
        srt_path = media_dir / f"{video_id}.srt"
        if not srt_path.exists():
            print(f"No SRT file found for video ID: {video_id}")
            return False

        file_id = f"{video_id}.srt"

        # Check if file already exists
        if self.file_exists_in_lyrics_bucket(file_id):
            print(f"SRT file already exists in storage: {file_id}")
            return True

        try:
            payload = Payload.from_file(srt_path, filename=file_id)
            self.storage.create_file(
                bucket_id=self.lyrics_bucket_id, file_id=file_id, file=payload
            )
            print(f"Successfully uploaded SRT file: {file_id}")
            return True
        except Exception as e:
            print(f"Error uploading SRT file {file_id}: {str(e)}")
            return False

    def upload_song(self, video_id: str, media_dir: Path = Path("media")) -> bool:
        """
        Upload audio file to songs bucket.
        Supports .m4a and .mp4 formats
        """
        # Try to find the audio file
        audio_file = None
        for ext in self.SUPPORTED_AUDIO_FORMATS:
            potential_path = media_dir / f"{video_id}{ext}"
            if potential_path.exists():
                audio_file = potential_path
                break

        if not audio_file:
            print(f"No audio file found for video ID: {video_id}")
            return False

        file_id = audio_file.name

        try:
            # Check if file already exists
            if self.file_exists_in_songs_bucket(file_id):
                print(f"Audio file already exists in storage: {file_id}")
                return True

            payload = Payload.from_file(audio_file, filename=file_id)
            self.storage.create_file(
                bucket_id=self.songs_bucket_id, file_id=file_id, file=payload
            )
            print(f"Successfully uploaded audio file: {file_id}")
            return True
        except AppwriteException as e:
            print(f"Appwrite error uploading audio file {file_id}: {str(e)}")
            return False
        except Exception as e:
            print(f"Unexpected error uploading audio file {file_id}: {str(e)}")
            return False

    def download_file(self, bucket_id: str, file_id: str, save_path: Path) -> bool:
        """Download a file from specified bucket and save it locally"""
        try:
            # Ensure the directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Get file content
            result = self.storage.get_file_download(bucket_id, file_id)

            # Write to local file
            with open(save_path, "wb") as f:
                f.write(result)

            return True
        except AppwriteException as e:
            print(f"Error downloading file {file_id}: {str(e)}")
            return False

    def download_lyrics(self, file_id: str, save_path: Path) -> bool:
        """Download a lyrics file from the lyrics bucket"""
        return self.download_file(self.lyrics_bucket_id, file_id, save_path)

    def download_song(self, file_id: str, save_path: Path) -> bool:
        """Download a song file from the songs bucket"""
        return self.download_file(self.songs_bucket_id, file_id, save_path)

    def upload_metadata(self, video_id: str, media_dir: Path = Path("media")) -> bool:
        """Upload metadata JSON file to songs bucket"""
        metadata_path = media_dir / f"{video_id}.info.json"
        if not metadata_path.exists():
            print(f"No metadata file found for video ID: {video_id}")
            return False

        file_id = f"{video_id}.info.json"

        try:
            if self.file_exists_in_songs_bucket(file_id):
                print(f"Metadata file already exists in storage: {file_id}")
                return True

            payload = Payload.from_file(metadata_path, filename=file_id)
            self.storage.create_file(
                bucket_id=self.songs_bucket_id, file_id=file_id, file=payload
            )
            print(f"Successfully uploaded metadata file: {file_id}")
            return True
        except Exception as e:
            print(f"Error uploading metadata file {file_id}: {str(e)}")
            return False

    def download_metadata(self, file_id: str, save_path: Path) -> bool:
        """Download a metadata file from the songs bucket"""
        return self.download_file(self.songs_bucket_id, file_id, save_path)

    def upload_song_with_metadata(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> tuple[bool, bool]:
        """Upload both song and metadata files as a pair"""
        song_success = self.upload_song(video_id, media_dir)
        metadata_success = self.upload_metadata(video_id, media_dir)
        return song_success, metadata_success

    def get_or_download_video_files(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> tuple[bool, str]:
        """
        Check if files exist in storage and download them, or return False if they don't exist.
        Returns (success, error_message)
        """
        song_file = media_dir / f"{video_id}.m4a"
        metadata_file = media_dir / f"{video_id}.info.json"

        # Check if both files exist in storage
        song_exists = self.file_exists_in_songs_bucket(f"{video_id}.m4a")
        metadata_exists = self.file_exists_in_songs_bucket(f"{video_id}.info.json")

        # If either file is missing in storage, return False
        if not (song_exists and metadata_exists):
            return False, "Files not found in storage"

        # Download both files
        song_download = self.download_song(f"{video_id}.m4a", song_file)
        metadata_download = self.download_metadata(
            f"{video_id}.info.json", metadata_file
        )

        if not (song_download and metadata_download):
            return False, "Failed to download files from storage"

        return True, ""

    def verify_connection(self) -> bool:
        """Verify connection to Appwrite by attempting to list buckets"""
        try:
            # Try to list buckets or get a bucket to verify connection
            self.storage.list_buckets()
            return True
        except AppwriteException as e:
            print(f"Failed to verify Appwrite connection: {str(e)}")
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
