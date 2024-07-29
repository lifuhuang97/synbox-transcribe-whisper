import os
from dotenv import load_dotenv
from openai import OpenAI
from pytube import YouTube
import yt_dlp

load_dotenv()

def convert_time_to_seconds(time_str: str) -> float:
    hours, minutes, seconds_milliseconds = time_str.split(':')
    seconds, milliseconds = seconds_milliseconds.split(',')
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
    return total_seconds

client = OpenAI(
    api_key=os.getenv("OPENAI_KEY"),
)

video_id = "sK5KMI2Xu98"
root_dir = os.getcwd()
audio_track_dir = os.path.join(root_dir, "output/track")
audio_filename = os.path.join(audio_track_dir, video_id + ".mp4")

full_vid_url = "https://www.youtube.com/watch?v=" + video_id

def longer_than_five_mins(info, *, incomplete):
    """Download only videos longer than a minute (or with unknown duration)"""
    duration = info.get('duration')
    if duration and duration > 300:
        return 'The video is too long'

ydl_opts = {
    'match_filter': longer_than_five_mins,
    'format': 'm4a/bestaudio/best',
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
    }],
    'outtmpl': "./output/track/ydl/%(id)s.%(ext)s",
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    error_code = ydl.download(full_vid_url)
    print('Some videos failed to download' if error_code
      else 'All videos successfully downloaded')


audio_file_path = "./output/track/ydl/"+video_id+".m4a"

with open(audio_file_path, "rb") as audio_file:
    transcription = client.audio.transcriptions.create(
    model="whisper-1", 
    file=audio_file, 
    language="ja",
    prompt="日本語の歌を文章に書き起こしてください。歌詞を意味のある場所で改行し、各行は5~7秒以内にしてください。タイムスタンプは常に曲の範囲内である必要があります。可能な限り正しい漢字を推測して使用してください",
    response_format="srt",
    timestamp_granularities=["segment"]
    )

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
            duration = round(end_time - start_time, 3)

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


output = process_gpt_transcription(transcription)

print(output)