import re

def extract_video_id(youtube_url):
    # Regular expression for finding a YouTube video ID
    video_id_pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11})'
    
    match = re.search(video_id_pattern, youtube_url)
    if match:
        return match.group(1)
    else:
        return None

# Example usage
url = "https://www.youtube.com/watch?v=x90-vUMKdx0"
video_id = extract_video_id(url)
print(video_id)