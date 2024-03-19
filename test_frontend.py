import json
import requests


video_urls = [
"https://www.youtube.com/watch?v=-tKVN2mAKRI",
]

# Loop over each video URL
for video_url in video_urls:
    # Specify the API endpoint
    api_endpoint = f"http://localhost:8080/transcribe?q={video_url}"
  
    # Make a POST request to the API with the video URL
    response = requests.get(api_endpoint)
    
    # Check if the request was successful
    if response.status_code == 200:
      try:
        data = response.json()
        print(f"Successfully processed {video_url}")
        print("data: ", data)

        if isinstance(data, dict):
                # Check and print each field if it exists
                for key in ['full_lyrics', 'eng_translation', 'chi_translation', 'romaji', 'kanji_annotation']:
                    if key in data:
                        print(data[key])
        else:
            print(f"Expected a JSON object but got a different type for {video_url}: {data}")
        # Process your JSON data here
      except json.decoder.JSONDecodeError:
          print("Error decoding JSON:", response.text)
    else:
        print(f"Failed to process {video_url}. Status code: {response.status_code}")
