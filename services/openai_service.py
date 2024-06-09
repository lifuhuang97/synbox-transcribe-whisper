import os
import json
from openai import OpenAI
import yt_dlp
from utils import utils
from tenacity import retry, wait_random_exponential, stop_after_attempt
from termcolor import colored  

tools = [
    {
        "type": "function",
        "function": {
            "name": "translate_lyrics_to_target_language",
            "description": "Translate the given Japanese lyrics to the chosen language",
            "parameters": {
                "type": "object",
                "properties": {
                    "lyrics": {
                        "type": "",
                        "description":"",
                    },
                    "lyrics_length": {
                        "type": "integer",
                        "description": "",
                    },
                    "target_language": {
                        "type": "string",
                        "enum": ["en", "zh-cn"],
                        "description": "",
                    },
                },
                "required": ["lyrics", "lyrics_length", "target_language"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_n_day_weather_forecast",
            "description": "Get an N-day weather forecast",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "The temperature unit to use. Infer this from the users location.",
                    },
                    "num_days": {
                        "type": "integer",
                        "description": "The number of days to forecast",
                    }
                },
                "required": ["location", "format", "num_days"]
            },
        }
    },
]

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_KEY"),
        )
        self.MODEL = "gpt-4o"

    def get_eng_translation(self, video_id, lyrics_arr, lyrics_len):
        
        messages = [
            {
                "role": "system",
                "content": "",
            },
            {
                "role": "user",
                "content": "",
            },
        ]



        return ""

    def get_transcription(self, video_id):
        root_dir = os.getcwd()
        audio_track_dir = os.path.join(root_dir, "output/track")
        audio_filename = os.path.join(audio_track_dir, video_id + ".mp4")

        ydl_opts = {
            'match_filter': self.longer_than_five_mins,
            'format': 'm4a/bestaudio/best',
            'postprocessors': [{  # Extract audio using ffmpeg
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            'outtmpl': "./output/track/%(id)s.%(ext)s",
        }

        full_vid_url = "https://www.youtube.com/watch?v=" + video_id

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download(full_vid_url)
            print('Audio download failed' if error_code
            else 'Audio successfully downloaded')

        audio_file_path = "./output/track/"+video_id+".m4a"

        with open(audio_file_path, "rb") as audio_file:
            transcription = self.client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file, 
            language="ja",
            prompt="日本語の歌を文章に書き起こしてください。歌詞を意味のある場所で改行し、各行は5~7秒以内にしてください。タイムスタンプは常に曲の範囲内である必要があります。可能な限り正しい漢字を推測して使用してください",
            response_format="srt",
            timestamp_granularities=["segment"]
            )

        output = self.process_gpt_transcription(transcription)
        print(output)
        print("GPT Transcription generated successfully")
        return output

    #! Helper Functions
    def longer_than_five_mins(self, info):
        """Download only videos shorter than 5mins"""
        duration = info.get('duration')
        if duration and duration > 300:
            return 'The video is too long'
        

    def process_gpt_transcription(self, gpt_output):
        # Process the transcription response from OpenAI
        lyrics = []
        timestamped_lyrics = []

        srt_blocks = gpt_output.strip().split("\n\n")
        for block in srt_blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                index = lines[0]
                timestamp = lines[1]
                lyric = ' '.join(lines[2:])

                lyrics.append(lyric)

                start_time_str, end_time_str = timestamp.split(' --> ')
                start_time = utils.convert_time_to_seconds(start_time_str)
                end_time = utils.convert_time_to_seconds(end_time_str)
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
    
    @retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
    def chat_completion_request(self, messages, tools=None, tool_choice=None, model="gpt-4o"):
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            return response
        except Exception as e:
            print("Unable to generate ChatCompletion response")
            print(f"Exception: {e}")
            return e
        
    def pretty_print_conversation(self, messages):
        role_to_color = {
            "system": "red",
            "user": "green",
            "assistant": "blue",
            "function": "magenta",
        }
        
        for message in messages:
            if message["role"] == "system":
                print(colored(f"system: {message['content']}\n", role_to_color[message["role"]]))
            elif message["role"] == "user":
                print(colored(f"user: {message['content']}\n", role_to_color[message["role"]]))
            elif message["role"] == "assistant" and message.get("function_call"):
                print(colored(f"assistant: {message['function_call']}\n", role_to_color[message["role"]]))
            elif message["role"] == "assistant" and not message.get("function_call"):
                print(colored(f"assistant: {message['content']}\n", role_to_color[message["role"]]))
            elif message["role"] == "function":
                print(colored(f"function ({message['name']}): {message['content']}\n", role_to_color[message["role"]]))