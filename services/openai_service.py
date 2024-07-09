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
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
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

            # TODO: change parameters to try to deal with fast songs
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ja",
                # TODO: Rewrite prompt
                # prompt="""
                # これは日本語の歌です。歌詞を正確に書き起こし、.srt形式で返してください。
                # 各行は2〜5秒以内に収め、非常に速い歌詞の場合は1秒単位で区切ってください。
                # 歌詞がない部分は「(間奏)」と表記してください。
                # 追加の応答やコメントは含めないでください。
                # """,
                # response_format="verbose_json",
                # timestamp_granularities=["word"],
                prompt="""
                あなたは日本語の歌詞を書き起こす専門家です。以下のガイドラインに従って、音声トラックから日本語の歌詞を正確に書き起こし、.srt形式で返してください:

                1. 各行は自然な間で区切り、原則として2〜8秒以内に収めてください。歌詞が非常に速い場合は、1秒単位の短い区切りも許容します。

                2. 各タイムスタンプが音声に正確に対応し、曲の範囲内であることを確認してください。

                3. 可能な限り正しい漢字を使用し、不明な場合は文脈に基づいて推測してください。

                4. 非常に速いテンポの歌詞の場合、無理に長い文を作らず、意味のある単位で区切ってください。

                5. アーティストが歌っている歌詞のみを含めてください。前奏、間奏、後奏などの楽器演奏のみの部分は含めないでください。

                6. このプロンプトの例文や説明文を出力に含めないでください。アーティストが実際に歌っている歌詞のみを書き起こしてください。

                7. 歌詞が始まる前や終わった後の無音や楽器演奏のみの部分は無視し、最初の歌詞から最後の歌詞までのみを書き起こしてください。

                .srt形式でタイムスタンプと歌詞の行のみを返してください。追加の応答やコメント、このプロンプトからの例文は一切含めないでください。音声トラック内でアーティストが実際に歌っている歌詞のみを正確に転記してください。
                
                例:
                1
                00:00:00,000 --> 00:00:30,000
                (前奏)
                2
                00:00:30,000 --> 00:00:33,000
                今、静かな夜の中で
                3
                00:00:33,000 --> 00:00:36,000
                無計画に車を
                4
                00:00:36,000 --> 00:00:39,000
                走らせた
                5
                00:00:39,000 --> 00:00:42,000
                左隣、あなたの
                6
                00:00:42,000 --> 00:00:45,000
                横顔を月が照らした
                7
                00:00:45,000 --> 00:00:55,000
                (間奏)
                """,
                response_format="srt",
                timestamp_granularities=["segment"],
            )

            srt_save_path = f"./output/response_srt/{video_id}.srt"
            print(transcription)
            print("Above is transcription")
            with open(srt_save_path, "w", encoding="utf-8") as output_file:
                output_file.write(transcription)

        tbr_output = self.process_gpt_transcription(transcription)

        print("GPT Transcription generated, processed, and saved successfully")

        # TODO: Consider adding a "cleansing step" through cgpt to remove any unwanted characters

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

    def stream_conversation_test(self):

        def generate():
            yield json.dumps({"status": "Starting transcription"})

            stream = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": "Write me a 10 line poem about a sunset, separated into multiple lines in the response",
                    },
                ],
                temperature=0,
                stream=True,
                stream_options={"include_usage": True},
            )

            for chunk in stream:
                if chunk.choices != [] and chunk.choices[0].delta.content is not None:
                    yield json.dumps(
                        {
                            "type": "gpt_response",
                            "content": chunk.choices[0].delta.content,
                        }
                    )
                    print("yielded: " + chunk.choices[0].delta.content)

            yield json.dumps({"status": "Translation complete"})

        return generate()

    def get_eng_translation_test(self, lyrics_arr):

        print("This is lyrics arr")
        print(lyrics_arr)

        messages = [
            translation_setup_system_message,
            {"role": "user", "content": json.dumps(lyrics_arr["timestamped_lyrics"])},
        ]

        def generate():
            stream = self.client.chat.completions.create(
                model=self.MODEL,
                messages=messages,
                tools=tools,
                stream=True,
                stream_options={"include_usage": True},
                temperature=0.9,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "translate_lyrics"},
                },
            )

            for chunk in stream:
                # Chunk:
                # ChatCompletionChunk(id='chatcmpl-9hXM9enudt3ToDK2Y4hxMKlKBfhm7',
                # choices=[Choice(delta=ChoiceDelta(content=None,
                # function_call=None, role=None,
                # tool_calls=[ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='暗', name=None),
                # type=None)]), finish_reason=None, index=0, logprobs=None)],
                # created=1720163353, model='gpt-4o-2024-05-13',
                # object='chat.completion.chunk',
                # service_tier=None,
                # system_fingerprint='fp_d576307f90',
                # usage=None)
                # print("Chunk: ")
                # print(chunk)
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content is not None:
                        yield json.dumps(
                            {
                                "type": "translation_chunk",
                                "content": delta.content,
                            }
                        )
                    elif delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            if (
                                tool_call.function
                                and tool_call.function.arguments is not None
                            ):
                                yield json.dumps(
                                    {
                                        "type": "tool_call_chunk",
                                        "content": tool_call.function.arguments,
                                    }
                                )
                elif chunk.choices and not chunk.choices[0].delta:
                    if chunk.choices[0].finish_reason == "stop":
                        print("<<< IN TRANSLATION COMPLETE BLOCK >>>")
                        yield json.dumps(
                            {
                                "type": "translation_complete",
                                "content": "Translation complete",
                            }
                        )
                else:
                    print("<<< IN ELSE BLOCK, LAST CHUNK >>>")
                    print(chunk)
                    if chunk.usage:
                        completion_tokens = chunk.usage.completion_tokens
                        prompt_tokens = chunk.usage.prompt_tokens
                        total_tokens = chunk.usage.total_tokens
                        usage_summary = f"Usage Summary: Completion Tokens = {completion_tokens}, Prompt Tokens = {prompt_tokens}, Total Tokens = {total_tokens}"
                        yield json.dumps(
                            {
                                "type": "usage_summary",
                                "content": usage_summary,
                            }
                        )
                        yield json.dumps(
                            {
                                "type": "plain_orig_lyrics",
                                "content": lyrics_arr["lyrics"],
                            }
                        )
                    else:
                        yield json.dumps(
                            {
                                "type": "system_error",
                                "content": "Something broke during the translation process, please try again",
                            }
                        )

        return generate()
