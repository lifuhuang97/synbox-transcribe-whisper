import re
from urllib.parse import urlparse, parse_qs

#? General Utils

def concatenate_strings(string_array):
    # Using the join() method with '\n' as the separator
    string_array = [str(item) for item in string_array]  # Convert all items to strings
    result = '\n'.join(string_array)
    return result

#? Returns videoID no matter if it's a youtube URL or just the videoID
def extract_video_id(youtube_url):
    
    youtube_url_pattern = r'^https?:\/\/(?:www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11})(&.*)?$'
    # Check if input is a valid YouTube URL
    if not re.match(youtube_url_pattern, youtube_url):
        return youtube_url

    # Regular expression for finding a YouTube video ID in various URL formats
    video_id_pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11})|youtu\.be\/([0-9A-Za-z_-]{11})'
    match = re.search(video_id_pattern, youtube_url)
    if match:
        # Check which group has the match
        video_id = match.group(1) if match.group(1) else match.group(2)
        
        # Further validation if the video ID is part of a query string
        parsed_url = urlparse(youtube_url)
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            # This check ensures that 'v' parameter is present and the video_id is from the 'v' parameter
            if 'v' in query_params and video_id in query_params['v']:
                return video_id
        
        # If the video ID didn't come from the 'v' parameter but was successfully extracted
        if video_id:
            return video_id
    else:
        return None
    

#? Utils for WhisperService
    
# ? Tester content - print everything
def print_full_content(obj, indent=0):
  # Set the indentation level for pretty printing
  ind = '    ' * indent
  
  # Check if the object is a dictionary
  if isinstance(obj, dict):
      for key, value in obj.items():
          print(f"{ind}{key}:")
          print_full_content(value, indent + 1)  # Recursively print the value

  # Check if the object is a list or a tuple
  elif isinstance(obj, (list, tuple)):
      for index, item in enumerate(obj):
          print(f"{ind}[{index}]")
          print_full_content(item, indent + 1)  # Recursively print the item

  # Base case: the object is neither a dictionary nor a list/tuple
  else:
      print(f"{ind}{obj}")


def time_to_seconds(time_str):
  # Convert timestamp from HH:MM:SS,mmm to seconds with milliseconds
  parts = time_str.split(":")
  hours = int(parts[0])
  minutes = int(parts[1])
  seconds, milliseconds = map(int, parts[2].split(","))
  total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
  return total_seconds

def convert_time_to_seconds(time_str: str) -> float:
    hours, minutes, seconds_milliseconds = time_str.split(':')
    seconds, milliseconds = seconds_milliseconds.split(',')
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
    return total_seconds

def process_gpt_transcription(srt_content):
    # Process the transcription response from OpenAI
    lyrics = []
    timestamped_lyrics = []

    srt_blocks = srt_content.strip().split("\n\n")
    for block in srt_blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            index = lines[0]
            timestamp = lines[1]
            lyric = ' '.join(lines[2:])

            lyrics.append(lyric)

            start_time_str, end_time_str = timestamp.split(' --> ')
            start_time = convert_time_to_seconds(start_time_str)
            end_time = convert_time_to_seconds(end_time_str)
            duration = end_time - start_time

            timestamped_lyrics.append({
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "lyric": lyric
            })

    return {
        "lyrics": lyrics,
        "timestamped_lyrics": timestamped_lyrics
    }

