import os
import json
from openai import OpenAI
import yt_dlp
from tenacity import retry, wait_random_exponential, stop_after_attempt
from utils import utils
from termcolor import colored

translation_setup_system_message = {
    "role": "system",
    "content": """
    You are an expert translator with a deep understanding of Japanese lyrics. Your task is to translate song lyrics into English and Chinese and return them in JSON. The translations must be tonally consistent with the original song and capture the full context and emotion of the lyrics.

Requirements:
1. Translate the lyrics to form a complete and coherent narrative, connecting each verse smoothly, and capture the essence of the original lyrics, conveying the same emotions and meaning accurately.
2. Provide the output in .srt format with timestamps matching the original lyrics. Each translated line should have a corresponding line with the same timestamp.
3. If it is unavoidable to combine two lines into one, duplicate the resulting line to maintain the original number of lines.
4. Translate the full sentence properly, regardless of its length, ensuring it conveys the same meaning as the original.

Example Input (Japanese Lyrics with Timestamps):
1
00:00:05,000 --> 00:00:10,000
今、静かな夜の中で

2
00:00:10,000 --> 00:00:15,000
無計画に車を走らせた

3
00:00:15,000 --> 00:00:20,000
左隣、あなたの

4
00:00:20,000 --> 00:00:25,000
横顔を月が照らした

Example Output (English Lyrics in .srt format):
1
00:00:05,000 --> 00:00:10,000
Now, in the quiet night

2
00:00:10,000 --> 00:00:15,000
I drove the car aimlessly

3
00:00:15,000 --> 00:00:20,000
To my left, you

4
00:00:20,000 --> 00:00:25,000
Your profile illuminated by the moon

Please translate the following Japanese lyrics into English and Chinese and return the translations in .srt format with matching timestamps.
""",
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "translate_lyrics",
            "parameters": {
                "type": "object",
                "properties": {
                    "english_lyrics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "chinese_lyrics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["english_lyrics", "chinese_lyrics"],
            },
        },
    },
]


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_KEY"),
        )
        self.MODEL = "gpt-4o"

    def get_transcription(self, video_id):

        ydl_opts = {
            "match_filter": self.longer_than_eight_mins,
            "format": "m4a/bestaudio/best",
            "postprocessors": [
                {  # Extract audio using ffmpeg
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
            "outtmpl": "./output/track/%(id)s.%(ext)s",
        }

        # TODO: Clean up, only validate URL once across the process
        full_vid_url = "https://www.youtube.com/watch?v=" + video_id

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download(full_vid_url)
            print("Audio download failed" if error_code else "Audio track downloaded")

        audio_file_path = "./output/track/" + video_id + ".m4a"

        with open(audio_file_path, "rb") as audio_file:

            # TODO: Check whether this can guarantee good results, if not convert to function call
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ja",
                # TODO: Rewrite prompt
                prompt="""
                あなたは日本語の歌詞を書き起こす専門家です。以下のガイドラインに従って、音声トラックから日本語の歌詞を正確に書き起こし、.srt形式で返してください:
                1. 各行は自然な間で区切り、5〜7秒以内に収めてください。
                2. 各タイムスタンプが音声に正確に対応し、曲の範囲内であることを確認してください。
                3. 可能な限り正しい漢字を使用し、不明な場合は文脈に基づいて推測してください。

                以下の例のように、.srt形式でタイムスタンプと歌詞の行のみを返してください。追加の応答やコメントは含めないでください。

                例:
                1
                00:00:05,000 --> 00:00:10,000
                今、静かな夜の中で

                2
                00:00:10,000 --> 00:00:15,000
                無計画に車を走らせた

                3
                00:00:15,000 --> 00:00:20,000
                左隣、あなたの

                4
                00:00:20,000 --> 00:00:25,000
                横顔を月が照らした

                音声トラックから正確に歌詞を転記し、.srt形式で返してください。
                """,
                response_format="srt",
                timestamp_granularities=["segment"],
            )

            srt_save_path = f"./output/response_srt/{video_id}.srt"
            with open(srt_save_path, "w", encoding="utf-8") as output_file:
                output_file.write(transcription)

        tbr_output = self.process_gpt_transcription(transcription)

        print("GPT Transcription generated, processed, and saved successfully")

        #TODO: Consider adding a "cleansing step" through cgpt to remove any unwanted characters

        if tbr_output:

            return tbr_output
        else:
            return "Failed to get transcription"

    def get_eng_translation(self, lyrics_arr, video_id):

        messages = [
            translation_setup_system_message,
            {"role": "user", "content": json.dumps(lyrics_arr)},
        ]

        gpt_response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=messages,
            tools=tools,
            temperature=0.9,
            response_format={"type": "json_object"},
            tool_choice={"type": "function", "function": {"name": "translate_lyrics"}},
        )

        print("This is response message in ENG translation")
        print(gpt_response.choices[0])

        if (
            gpt_response.choices[0].message
            and gpt_response.choices[0].message.tool_calls
        ):
            tool_call = gpt_response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "translate_lyrics":
                function_response = tool_call.function.arguments
                lyrics_response = json.loads(function_response)
                english_lyrics = lyrics_response.get("english_lyrics", "")
                chinese_lyrics = lyrics_response.get("chinese_lyrics", "")
            else:
                raise ValueError("Unexpected function call in GPT response")
        else:
            raise ValueError("No function call found in GPT response")

        # Ensure the output directory exists
        os.makedirs("./output/response_4o_translate/", exist_ok=True)

        # Define the output file paths
        eng_output_file_path = f"./output/response_4o_translate/{video_id}_eng.json"
        chi_output_file_path = f"./output/response_4o_translate/{video_id}_chi.json"

        # Save the English lyrics to a JSON file
        with open(eng_output_file_path, "w", encoding="utf-8") as eng_file:
            json.dump(
                {"english_lyrics": english_lyrics},
                eng_file,
                ensure_ascii=False,
                indent=4,
            )

        # Save the Chinese lyrics to a JSON file
        with open(chi_output_file_path, "w", encoding="utf-8") as chi_file:
            json.dump(
                {"chinese_lyrics": chinese_lyrics},
                chi_file,
                ensure_ascii=False,
                indent=4,
            )

        print(f"English lyrics saved successfully to {eng_output_file_path}")
        print(f"Chinese lyrics saved successfully to {chi_output_file_path}")

        return english_lyrics, chinese_lyrics

    #! Helper Function - check video length
    def longer_than_eight_mins(self, info):
        """Download only videos shorter than 5mins"""
        duration = info.get("duration")
        if duration and duration > 480:
            return "The video is too long"

    #! Helper Function - process GPT Whisper transcription
    def process_gpt_transcription(self, gpt_output):
        # Process the transcription response from OpenAI
        lyrics = []
        timestamped_lyrics = []

        srt_blocks = gpt_output.strip().split("\n\n")
        for block in srt_blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                timestamp = lines[1]
                lyric = " ".join(lines[2:])

                lyrics.append(lyric)

                start_time_str, end_time_str = timestamp.split(" --> ")
                start_time = utils.convert_time_to_seconds(start_time_str)
                end_time = utils.convert_time_to_seconds(end_time_str)
                duration = round(end_time - start_time, 3)

                timestamped_lyrics.append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration,
                        "lyric": lyric,
                    }
                )

        return {"lyrics": lyrics, "timestamped_lyrics": timestamped_lyrics}

    @retry(
        wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3)
    )
    def chat_completion_request(
        self, messages, tools=None, tool_choice=None, model="gpt-4o"
    ):
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
                print(
                    colored(
                        f"system: {message['content']}\n",
                        role_to_color[message["role"]],
                    )
                )
            elif message["role"] == "user":
                print(
                    colored(
                        f"user: {message['content']}\n", role_to_color[message["role"]]
                    )
                )
            elif message["role"] == "assistant" and message.get("function_call"):
                print(
                    colored(
                        f"assistant: {message['function_call']}\n",
                        role_to_color[message["role"]],
                    )
                )
            elif message["role"] == "assistant" and not message.get("function_call"):
                print(
                    colored(
                        f"assistant: {message['content']}\n",
                        role_to_color[message["role"]],
                    )
                )
            elif message["role"] == "function":
                print(
                    colored(
                        f"function ({message['name']}): {message['content']}\n",
                        role_to_color[message["role"]],
                    )
                )
