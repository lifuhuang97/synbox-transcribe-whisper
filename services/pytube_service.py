import json
from pytube import YouTube, Playlist, Search
import sys
sys.path.append('../')

from utils.utils import utils

class PyTubeService:
    def get_video_info(self, video_id):
        """
        Get information about a single video based on its ID.

        Args:
        - video_id (str): The ID of the video.

        Returns:
        - dict: A dictionary containing information about the video.
        """

        # 'register_on_complete_callback', 'register_on_progress_callback',
        # ! Can actually use register on complete to upload data to appwrite

        try:
            video = YouTube(f"https://www.youtube.com/watch?v={video_id}")
            print(dir(video))
            utils.print_full_content(video)
            return {
                "title": video.title,
                "_title": video._title,
                "author": video.author,
                "video_id": video.video_id,
                "views": video.views,
                "length": video.length,
                "description": video.description,
                "thumbnail_url": video.thumbnail_url,
                "embed_url":video.embed_url,
                "keywords":video.keywords,
                "views": video.views,
            }
        except Exception as e:
            print(f"Error fetching video info: {e}")
            return None

    def get_playlist_info(self, playlist_id):
        """
        Get information about a playlist based on its ID.

        Args:
        - playlist_id (str): The ID of the playlist.

        Returns:
        - dict: A dictionary containing information about the playlist.
        """
        try:
            playlist = Playlist(f"https://www.youtube.com/playlist?list={playlist_id}")
            print(dir(playlist))  # Print the attributes and methods of the Playlist object
            return {
                "title": playlist.title,
                "video_count": len(playlist.video_urls),
                "videos": [self.get_video_info(video_id) for video_id in playlist.video_urls],
            }
        except Exception as e:
            print(f"Error fetching playlist info: {e}")
            return None

    def get_search_suggestions(self, keyword):
        suggestions = Search(keyword).completion_suggestions
        return suggestions

    def search_videos(self, keyword):
        try:
            search_results = Search(keyword).results
            results_list = []
            for video in search_results:
                # Check if video length is less than or equal to 480 (seconds)
                if video.length <= 480:
                    video_info = {
                        "title": video.title,
                        # _title is same as title
                        "_title": video._title,
                        "author": video.author,
                        "video_id": video.video_id,
                        "views": video.views,
                        "length": video.length,
                        "description": video.description,
                        "thumbnail_url": video.thumbnail_url,
                        # embed_url is basically the youtube url
                        # "embed_url":video.embed_url,
                        "keywords":video.keywords,
                        "views": video.views,
                        "metadata": video.metadata,
                        "_metadata": video._metadata,
                    }
                    results_list.append(video_info)

            return results_list
        except Exception as e:
            print(f"Error searching videos: {e}")
            return None

# Example usage:
pytube_service = PyTubeService()


def print_object(obj):
    # Convert the object to JSON format with indentation
    formatted_obj = json.dumps(obj, indent=2, ensure_ascii=False)

    # Replace problematic characters with a placeholder
    formatted_obj = formatted_obj.encode('utf-8', 'ignore').decode('utf-8')

    # Print each line of the formatted object
    for line in formatted_obj.split('\n'):
        print(line)


#? Testing getting video data
# video_info = pytube_service.get_video_info("VyvhvlYvRnc")
# print("Video Info:", video_info)

# ? Testing listing playlist info
# playlist_info = pytube_service.get_playlist_info("PLzJ1mqwxogpFuFCk1YfUE1c0gWtnIutfz")
# print("Playlist Info:", playlist_info)

#? Testing search by query
# search_results = pytube_service.search_videos("ado Ode")
# for result in search_results:
#     print_object(result)

#? completion
# suggestions = pytube_service.get_search_suggestions("ado kura")
# print("RESULTS ARE BACK, ABOVE ARE FROM INSIDE FUNCTION")
# for result in suggestions:
    # print_object(result)

# print("ABOVE ARE ALL AUTOCOMPLETE SUGGESTIONS")

# video_info = pytube_service.get_video_info("VyvhvlYvRnc")
# video_info = pytube_service.get_video_info("tLQLa6lM3Us")
# utils.print_full_content(video_info)
# print_object(video_info)
# print("ABOVE ARE VIDEO INFO")
        
testing_obj = YouTube.from_id("tLQLa6lM3Us")

                # "title": video.title,
                # "_title": video._title,
                # "author": video.author,
                # "video_id": video.video_id,
                # "views": video.views,
                # "length": video.length,
                # "description": video.description,
                # "thumbnail_url": video.thumbnail_url,
                # "embed_url":video.embed_url,
                # "keywords":video.keywords,
                # "views": video.views,

# print_object(testing_obj)
print(testing_obj.title)
print(testing_obj.author)
print(testing_obj.video_id)
print(testing_obj.views)
print(testing_obj.length)
print(testing_obj.description)
print(testing_obj.thumbnail_url)