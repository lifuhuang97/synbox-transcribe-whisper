import time
import uuid
import re
from urllib.parse import urlparse, parse_qs
import dotenv

# load_dotenv()
# self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
# self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

store = {
    "video_ids": "",
    "unique_job_ids": "",
    "progress": {
        "stage": "",
        "info": []
    }
}

def generate_unique_job_id(video_id):
    # Current time in milliseconds
    timestamp = int(time.time() * 1000)
    # Generate a random UUID and convert to a string
    random_component = str(uuid.uuid4())
    # Construct the unique job ID
    unique_job_id = f"{video_id}-{timestamp}-{random_component}"
    return unique_job_id

def extract_video_id(self, youtube_url):
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

def create_transcribe_job(video_url):
    video_id = extract_video_id(video_url)
    response = ""

    if video_id:
        unique_job_id = generate_unique_job_id(video_id)
        # Logic to create a transcription job
        return unique_job_id
    else:
        return None
    
    data = {"message": "Custom Response"}
    return Response(response=json.dumps(data),
                    status=200,
                    mimetype='application/json')
