import json

plain = "plain_lyrics"
chi = "chi_translation"
eng = "eng_translation"
kanji = "kanji_translation"
romaji = "romaji_annotation"


def create_lyrics_string(subdir, videoId):
    # Specify the file path based on the videoId
    file_path = f'output/{subdir}/{videoId}.txt'

    lyrics = []

    with open(file_path, 'r') as f:
        # Read the file line by line and add each line to the lyrics array
        lyrics.extend(f.readlines())

    # Convert the lyrics array to a JSON-formatted string
    lyrics_string = json.dumps(lyrics)

    # Write the lyrics string to a file
    with open(f'jsonstr_{videoId}_{subdir}, lyrics.json', 'w') as f:
        f.write(lyrics_string)

# Replace 'your_video_id' with your actual videoId
create_lyrics_string(plain, 'K1Tz2yNmamI')  