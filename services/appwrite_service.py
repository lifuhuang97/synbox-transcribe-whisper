from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import os
from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.input_file import InputFile
from appwrite.exception import AppwriteException
from appwrite.query import Query
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app.log")],
)
logger = logging.getLogger(__name__)


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
    APPWRITE_ID_PREFIX = "yt_"

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

        # Get the directory where the application code is running
        self.PROJECT_ROOT = Path(__file__).parent.parent
        # Create media directory relative to the application root
        self.media_dir = self.PROJECT_ROOT / "media"
        self.media_dir.mkdir(exist_ok=True, parents=True)

        if not all([self.lyrics_bucket_id, self.songs_bucket_id]):
            raise ValueError("Missing required bucket IDs")

    @staticmethod
    def validate_youtube_id_for_appwrite(id: str) -> bool:
        """
        Check if YouTube ID is valid for Appwrite.
        Only encode if it starts with '-' or '_' since these are the only invalid starting characters.
        """
        return not id.startswith(("-", "_"))

    @classmethod
    def encode_youtube_id_for_appwrite(cls, id: str) -> str:
        """
        Encode YouTube ID for Appwrite storage only if necessary.
        Only IDs starting with '-' or '_' need encoding.
        """
        if id.startswith("-"):
            return f"{cls.APPWRITE_ID_PREFIX}h{id[1:]}"
        elif id.startswith("_"):
            return f"{cls.APPWRITE_ID_PREFIX}u{id[1:]}"
        return id  # Return unchanged if no encoding needed

    @classmethod
    def decode_appwrite_id_to_youtube(cls, appwrite_id: str) -> str:
        """
        Decode Appwrite ID back to YouTube ID.
        Only decode if it starts with the prefix and has an encoding character.
        """
        if appwrite_id.startswith(cls.APPWRITE_ID_PREFIX):
            encoded_part = appwrite_id[len(cls.APPWRITE_ID_PREFIX) :]
            if encoded_part.startswith("h"):
                return f"-{encoded_part[1:]}"
            elif encoded_part.startswith("u"):
                return f"_{encoded_part[1:]}"
        return appwrite_id

    def create_appwrite_id(self, youtube_id: str) -> str:
        """
        Convert YouTube ID to valid Appwrite ID only if necessary.
        Most YouTube IDs are already valid Appwrite IDs.
        """
        if not self.validate_youtube_id_for_appwrite(youtube_id):
            return self.encode_youtube_id_for_appwrite(youtube_id)
        return youtube_id

    def get_file_id_with_extension(self, youtube_id: str, extension: str) -> str:
        """Create file ID with extension using encoded ID if necessary"""
        base_id = self.create_appwrite_id(youtube_id)
        return f"{base_id}{extension}"

    def file_exists_in_bucket(
        self, bucket_id: str, youtube_id: str, extension: str = ""
    ) -> bool:
        """Check if a file exists in the specified bucket using encoded ID if necessary"""
        file_id = self.get_file_id_with_extension(youtube_id, extension)
        try:
            self.storage.get_file_view(bucket_id, file_id)
            return True
        except AppwriteException as e:
            if "404" in str(e):
                return False
            print(f"Error checking file existence: {str(e)}")
            raise

    def file_exists_in_lyrics_bucket(
        self, youtube_id: str, extension: str = ""
    ) -> bool:
        """Check if a file exists in the lyrics bucket using encoded ID if necessary"""
        try:
            return self.file_exists_in_bucket(
                self.lyrics_bucket_id, youtube_id, extension
            )
        except AppwriteException as e:
            print(f"Error checking lyrics file: {str(e)}")
            return False

    def file_exists_in_songs_bucket(self, youtube_id: str, extension: str = "") -> bool:
        """Check if a file exists in the songs bucket using encoded ID if necessary"""
        try:
            return self.file_exists_in_bucket(
                self.songs_bucket_id, youtube_id, extension
            )
        except AppwriteException as e:
            print(f"Error checking song file: {str(e)}")
            return False

    def upload_youtube_subtitle(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> bool:
        """Upload YouTube subtitle file with encoded ID if necessary"""
        subtitle = self.find_youtube_subtitle(video_id, media_dir)
        if not subtitle.exists:
            print(f"No YouTube lyrics found for video ID: {video_id}")
            return False

        file_id = self.get_file_id_with_extension(video_id, subtitle.extension)

        if self.file_exists_in_lyrics_bucket(video_id, subtitle.extension):
            print(f"Subtitle already exists in storage: {file_id}")
            return True

        try:
            input_file = InputFile.from_path(str(subtitle.path))
            self.storage.create_file(
                bucket_id=self.lyrics_bucket_id, file_id=file_id, file=input_file
            )
            print(f"Successfully uploaded lyrics: {file_id}")
            return True
        except Exception as e:
            print(f"Error uploading lyrics {file_id}: {str(e)}")
            return False

    def download_lyrics_file(
        self, bucket_id: str, file_name: str, save_path: Path
    ) -> bool:
        """Download a lyrics file from storage and save it to the specified path"""
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Get file from storage
            response = self.storage.get_file_download(bucket_id, file_name)

            # Write bytes response to file
            with open(save_path, "wb") as f:
                f.write(response)

            logger.debug(f"Successfully downloaded lyrics file to: {save_path}")
            return True

        except Exception as e:
            logger.error(f"Error downloading lyrics file: {str(e)}")
            return False

    def download_file(
        self, bucket_id: str, youtube_id: str, extension: str, save_path: Path
    ) -> bool:
        """Download a file using encoded ID if necessary"""
        try:
            file_id = self.get_file_id_with_extension(youtube_id, extension)
            save_path.parent.mkdir(parents=True, exist_ok=True)

            response = self.storage.get_file_download(bucket_id, file_id)

            if isinstance(response, bytes):
                file_content = response
                write_mode = "wb"
            elif isinstance(response, dict):
                import json

                file_content = json.dumps(response, indent=2)
                write_mode = "w"
            else:
                raise ValueError(f"Unexpected response type: {type(response)}")

            with open(save_path, write_mode) as f:
                if write_mode == "wb":
                    f.write(file_content)
                else:
                    f.write(file_content)

            return True
        except Exception as e:
            print(f"Error downloading file: {str(e)}")
            return False

    # def find_youtube_subtitle(
    #     self, video_id: str, media_dir: Path = Path("media")
    # ) -> SubtitleFile:
    #     """
    #     Find YouTube subtitle file in various formats (.ja.vtt, .ja.srt, .ja.ass, .ja.ssa)
    #     """
    #     for ext in self.SUPPORTED_SUBTITLE_FORMATS:
    #         subtitle_path = media_dir / f"{video_id}{ext}"
    #         if subtitle_path.exists():
    #             return SubtitleFile(exists=True, path=subtitle_path, extension=ext)

    #     return SubtitleFile(exists=False, path=None, extension=None)

    def find_youtube_subtitle(
        self, video_id: str, media_dir: Optional[Path] = None
    ) -> SubtitleFile:
        """
        Find YouTube subtitle file in various formats (.ja.vtt, .ja.srt, .ja.ass, .ja.ssa)
        """
        # Use the class media directory if none provided
        if media_dir is None:
            media_dir = self.media_dir

        logger.debug(f"Looking for subtitles in: {media_dir}")
        logger.debug(f"Directory exists: {media_dir.exists()}")
        logger.debug(f"Directory contents: {list(media_dir.glob('*'))}")

        for ext in self.SUPPORTED_SUBTITLE_FORMATS:
            subtitle_path = media_dir / f"{video_id}{ext}"
            logger.debug(f"Checking path: {subtitle_path}")
            if subtitle_path.exists():
                logger.debug(f"Found subtitle at: {subtitle_path}")
                return SubtitleFile(exists=True, path=subtitle_path, extension=ext)

        logger.debug("No subtitles found")
        return SubtitleFile(exists=False, path=None, extension=None)

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

        file_id = self.get_file_id_with_extension(video_id, ".srt")

        # Check if file already exists
        if self.file_exists_in_lyrics_bucket(video_id, ".srt"):
            print(f"SRT file already exists in storage: {file_id}")
            return True

        try:
            input_file = InputFile.from_path(str(srt_path))
            self.storage.create_file(
                bucket_id=self.lyrics_bucket_id, file_id=file_id, file=input_file
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

        file_id = self.get_file_id_with_extension(video_id, audio_file.suffix)

        try:
            # Check if file already exists
            if self.file_exists_in_songs_bucket(video_id, audio_file.suffix):
                print(f"Audio file already exists in storage: {file_id}")
                return True

            input_file = InputFile.from_path(str(audio_file))
            self.storage.create_file(
                bucket_id=self.songs_bucket_id, file_id=file_id, file=input_file
            )
            print(f"Successfully uploaded audio file: {file_id}")
            return True
        except AppwriteException as e:
            print(f"Appwrite error uploading audio file {file_id}: {str(e)}")
            return False
        except Exception as e:
            print(f"Unexpected error uploading audio file {file_id}: {str(e)}")
            return False

    # def get_or_download_video_files(
    #     self, video_id: str, media_dir: Path = Path("media")
    # ) -> tuple[bool, str]:
    #     """
    #     Check if files exist in storage and download them, or return False if they don't exist.
    #     Returns (success, error_message)
    #     """
    #     song_file = media_dir / f"{video_id}.m4a"
    #     metadata_file = media_dir / f"{video_id}.info.json"

    #     try:
    #         # Use encoded IDs for storage operations
    #         appwrite_id = self.create_appwrite_id(video_id)

    #         # Check if both files exist in storage
    #         song_exists = self.file_exists_in_songs_bucket(appwrite_id, ".m4a")
    #         metadata_exists = self.file_exists_in_songs_bucket(
    #             appwrite_id, ".info.json"
    #         )

    #         # If either file is missing in storage, return False
    #         if not (song_exists and metadata_exists):
    #             return False, "Files not found in storage"

    #         # Download both files using encoded IDs
    #         song_download = self.download_file(
    #             self.songs_bucket_id, video_id, ".m4a", song_file
    #         )
    #         if not song_download:
    #             return False, "Failed to download audio file"

    #         metadata_download = self.download_file(
    #             self.songs_bucket_id, video_id, ".info.json", metadata_file
    #         )
    #         if not metadata_download:
    #             return False, "Failed to download metadata file"

    #         # Verify files exist and are not empty
    #         if not song_file.exists() or song_file.stat().st_size == 0:
    #             return False, "Downloaded audio file is empty or missing"

    #         if not metadata_file.exists() or metadata_file.stat().st_size == 0:
    #             return False, "Downloaded metadata file is empty or missing"

    #         return True, ""

    #     except Exception as e:
    #         return False, f"Error during file download: {str(e)}"

    def get_or_download_video_files(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> tuple[bool, str]:
        """
        Check if files exist in storage and download them, or return False if they don't exist.
        Also checks and downloads any available subtitle files.
        Returns (success, error_message)
        """
        song_file = media_dir / f"{video_id}.m4a"
        metadata_file = media_dir / f"{video_id}.info.json"

        try:
            # Use encoded IDs for storage operations
            appwrite_id = self.create_appwrite_id(video_id)

            # Check if both files exist in storage
            song_exists = self.file_exists_in_songs_bucket(appwrite_id, ".m4a")
            metadata_exists = self.file_exists_in_songs_bucket(
                appwrite_id, ".info.json"
            )

            # If either file is missing in storage, return False
            if not (song_exists and metadata_exists):
                return False, "Files not found in storage"

            # Download both files using encoded IDs
            song_download = self.download_file(
                self.songs_bucket_id, video_id, ".m4a", song_file
            )
            if not song_download:
                return False, "Failed to download audio file"

            metadata_download = self.download_file(
                self.songs_bucket_id, video_id, ".info.json", metadata_file
            )
            if not metadata_download:
                return False, "Failed to download metadata file"

            # Query for subtitle files
            try:
                # Create individual contains queries for each format
                subtitle_queries = [
                    Query.contains("name", [f"{appwrite_id}{ext}"])
                    for ext in self.SUPPORTED_SUBTITLE_FORMATS
                ]

                # Combine queries with OR
                query = [Query.or_queries(subtitle_queries)]

                # List files with the combined query
                subtitle_files = self.storage.list_files(
                    bucket_id=self.lyrics_bucket_id, queries=query
                )
                logger.debug(f"[NEW] Subtitle Files List: {subtitle_files}")

                # Download any found subtitle files
                for file in subtitle_files.get("files", []):
                    file_name = file.get("$id")
                    logger.debug(f"[NEW] Subtitle File name: {file_name}")

                    if file_name:
                        # Extract the extension from the file name
                        _, ext = os.path.splitext(file_name)
                        subtitle_path = media_dir / f"{file_name}"

                        subtitle_download = self.download_lyrics_file(
                            self.lyrics_bucket_id, file_name, subtitle_path
                        )

                        logger.debug(f"Subtitle download: {subtitle_download}")

                        if not subtitle_download:
                            logger.warning(
                                f"Failed to download subtitle file: {file_name}"
                            )
                        else:
                            logger.info(
                                f"Successfully downloaded subtitle file: {file_name}"
                            )

            except Exception as e:
                logger.error(f"Error querying/downloading subtitle files: {str(e)}")
                # Don't fail the whole operation if subtitle download fails
                pass

            # Verify main files exist and are not empty
            if not song_file.exists() or song_file.stat().st_size == 0:
                return False, "Downloaded audio file is empty or missing"

            if not metadata_file.exists() or metadata_file.stat().st_size == 0:
                return False, "Downloaded metadata file is empty or missing"

            return True, ""

        except Exception as e:
            return False, f"Error during file download: {str(e)}"

    def upload_song_with_metadata(
        self, video_id: str, media_dir: Path = Path("media")
    ) -> tuple[bool, bool]:
        """Upload both song and metadata files as a pair"""
        try:
            # Handle song file
            audio_file = None
            for ext in self.SUPPORTED_AUDIO_FORMATS:
                potential_path = media_dir / f"{video_id}{ext}"
                if potential_path.exists():
                    audio_file = potential_path
                    break

            if not audio_file:
                print(f"No audio file found for video ID: {video_id}")
                return False, False

            # Get encoded IDs for storage
            song_file_id = self.get_file_id_with_extension(video_id, audio_file.suffix)
            metadata_file_id = self.get_file_id_with_extension(video_id, ".info.json")

            print(f"Encoded song file ID: {song_file_id}")
            print(f"Encoded metadata file ID: {metadata_file_id}")

            # Upload song
            song_success = False
            try:
                if not self.file_exists_in_songs_bucket(video_id, audio_file.suffix):
                    input_file = InputFile.from_path(str(audio_file))
                    self.storage.create_file(
                        bucket_id=self.songs_bucket_id,
                        file_id=song_file_id,
                        file=input_file,
                    )
                    print(f"Successfully uploaded song: {song_file_id}")
                song_success = True
            except Exception as e:
                print(f"Error uploading audio file {song_file_id}: {str(e)}")

            # Upload metadata
            metadata_success = False
            try:
                metadata_path = media_dir / f"{video_id}.info.json"
                if metadata_path.exists() and not self.file_exists_in_songs_bucket(
                    video_id, ".info.json"
                ):
                    input_file = InputFile.from_path(str(metadata_path))
                    self.storage.create_file(
                        bucket_id=self.songs_bucket_id,
                        file_id=metadata_file_id,
                        file=input_file,
                    )
                    print(f"Successfully uploaded metadata: {metadata_file_id}")
                metadata_success = True
            except Exception as e:
                print(f"Error uploading metadata file {metadata_file_id}: {str(e)}")

            return song_success, metadata_success

        except Exception as e:
            print(f"Unexpected error in upload_song_with_metadata: {str(e)}")
            return False, False

    def download_lyrics(self, file_id: str, save_path: Path) -> bool:
        """
        Download a lyrics file from the lyrics bucket
        Args:
            file_id: The original file ID (e.g., "video_id.srt")
            save_path: Where to save the downloaded file
        """
        # Split the file_id into base ID and extension
        base_name, extension = os.path.splitext(file_id)
        return self.download_file(
            self.lyrics_bucket_id, base_name, extension, save_path
        )

    def download_song(self, file_id: str, save_path: Path) -> bool:
        """
        Download a song file from the songs bucket
        Args:
            file_id: The original file ID (e.g., "video_id.m4a")
            save_path: Where to save the downloaded file
        """
        # Split the file_id into base ID and extension
        base_name, extension = os.path.splitext(file_id)
        return self.download_file(self.songs_bucket_id, base_name, extension, save_path)

    def download_metadata(self, file_id: str, save_path: Path) -> bool:
        """
        Download a metadata file from the songs bucket
        Args:
            file_id: The original file ID (e.g., "video_id.info.json")
            save_path: Where to save the downloaded file
        """
        # Split the file_id into base ID and extension
        base_name, extension = os.path.splitext(file_id)
        return self.download_file(self.songs_bucket_id, base_name, extension, save_path)

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

            input_file = InputFile.from_path(str(metadata_path))
            self.storage.create_file(
                bucket_id=self.songs_bucket_id, file_id=file_id, file=input_file
            )
            print(f"Successfully uploaded metadata file: {file_id}")
            return True
        except Exception as e:
            print(f"Error uploading metadata file {file_id}: {str(e)}")
            return False

    # def verify_connection(self) -> bool:
    #     """Verify connection to Appwrite by attempting to list buckets"""
    #     try:
    #         # Try to list buckets or get a bucket to verify connection
    #         self.storage.list_buckets()
    #         return True
    #     except AppwriteException as e:
    #         print(f"Failed to verify Appwrite connection: {str(e)}")
    #         return False
