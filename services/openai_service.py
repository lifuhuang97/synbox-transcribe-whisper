import os
import glob
import json
from openai import OpenAI
import yt_dlp
from utils import utils

transcription_filter_srt_array = [
    "初音ミク",
    "チャンネル登録",
    "Illustration & Movie 天月",
    "Vocal 天月",
    "ご視聴ありがとうございました",
    "サブタイトル キョウ",
    "※音声の最初から最後まで、すべての時間を漏らさず書き起こしてください。",
    "※",
    "【 】",
    "µµµ",
    "�",
    " 歌詞のない部分は",
    "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••",
    "ªªªªªªªªªªªªªªªªªªªªª",
    "🥀🥀🥀🥀",
    "🐻",
]

romaji_annotation_system_message = {
    "role": "system",
    "content": """
    以下の要件に従って、日本語の歌詞をローマ字に変換するためのシステムプロンプトを作成してください：
    各行をそのままローマ字に変換してください。外国語が検出された場合、その行をそのまま出力にコピーしてください。
    出力の行数は入力の行数と一致させてください。
    ローマ字は基本的にすべて小文字で記載し、特定の外国語や文脈で必要な場合のみ大文字を使用してください。また、句読点は適用する場合、そのまま保持してください。
    
    例：
    入力：
    こんにちは、世界！
    this is a test
    出力：
    konnichiwa, sekai!
    this is a test
    
    歌詞を以下の要件に従って変換してください。
    """,
}

kanji_annotation_system_message = {
    "role": "system",
    "content": """
    You are an expert in annotating Japanese song lyrics with the correct furigana pronunciations. Please follow the requirements below to add furigana to the lyrics:

    Requirements:
    1. Add furigana to each kanji character by placing the furigana in square brackets [] immediately after the kanji character.
    2. If there are multiple consecutive kanji characters, include the furigana for all characters within a single set of square brackets. However, if individual furigana are needed for each kanji, place each furigana in its own set of square brackets immediately after the corresponding kanji character.
    3. The output must have the same number of lines as the input. For example, if the input array has 30 lines, the output should also have 30 lines.
    4. Do not include any additional system-related messages in the output, only the annotated lyrics.

    Example:

    Input:
    彼女は笑った
    美しい世界が見える

    Output:
    彼女[かのじょ]は笑[わら]った
    美[うつく]しい世界[せかい]が見[み]える
    """,
}

translation_setup_system_message = {
    "role": "system",
    "content": """
You are an expert trilingual translator specializing in Japanese, English, and Chinese, with a deep understanding of song lyrics. Your task is to translate Japanese song lyrics into both English and Chinese, maintaining the poetic and expressive nature while ensuring clarity.

Key requirements:
1. Thoroughly read and understand the entire set of lyrics before translating to grasp the full context and ensure accurate meaning capture.
2. The number of lines in both translations must exactly match the number of lines in the original Japanese lyrics.
3. Translate to form a complete and coherent narrative, connecting verses smoothly while capturing the essence, emotions, and meaning of the original lyrics.
4. If a sentence spans multiple lines, translate it properly as a whole, then repeat the translation across those lines to maintain the line count.
5. Preserve any artistic elements like metaphors or wordplay as much as possible in both translations.
6. If there's any english or chinese lyrics, keep these lines and translate them to/fro chinese and english respectively.

Return the translations in JSON format with two separate arrays: one for English and one for Chinese, each with the same number of elements as the input Japanese lyrics.

Example Input:
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

Expected Output Format:
{
  "english_lyrics": [
    "Now, in the quiet night",
    "I drove the car aimlessly",
    "To my left, you",
    "Your profile illuminated by the moon"
  ],
  "chinese_lyrics": [
    "此时此刻，在寂静的夜色中",
    "漫无目的地驾着车",
    "你坐在我的左侧",
    "你的侧脸被月光照亮"
  ]
}

Translate the following Japanese lyrics into both English and Chinese, ensuring the output matches this format and maintains the exact number of lines as the input.
""",
}

validate_youtube_video_system_message = {
    "role": "system",
    "content": """
    I will give you the relevant details of a youtube video in JSON format. Help me analyze whether the given details can tell you with extremely high certainty that the video is a video of a Japanese song or a Japanese music video of a song, nothing else. Reply with 1 character only and nothing else (Y / N) to represent your judgment.
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
    {
        "type": "function",
        "function": {
            "name": "convert_to_romaji",
            "parameters": {
                "type": "object",
                "properties": {
                    "romaji": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["romaji"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "annotate_with_furigana",
            "parameters": {
                "type": "object",
                "properties": {
                    "furigana_ann_lyrics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["furigana_ann_lyrics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_music_video",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                    },
                },
                "required": ["decision"],
            },
        },
    },
]


class OpenAIService:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.MODEL = "gpt-4o"

    def validate_video(self, video_id):

        passed = False

        ydl_opts = {
            "match_filter": self.longer_than_eight_mins,
            "format": "m4a/bestaudio/best",
            "writesubtitles": True,
            "subtitlesformat": "vtt/srt/ass/ssa",
            "subtitleslangs": ["ja"],
            "break_on_reject": True,
            "writeinfojson": True,
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
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                error_code = ydl.download(full_vid_url)
                print(
                    "Audio download failed" if error_code else "Audio track downloaded"
                )
        except Exception as e:
            error_msg = str(e)
            print(f"An error occurred in validate_video: {error_msg}")
            return (
                False,
                None,
                None,
                None,
                {"exist": False, "path": None, "ext": None},
                error_msg,
            )

        audio_file_path = "./output/track/" + video_id + ".m4a"
        info_file_path = "./output/track/" + video_id + ".info.json"

        with open(info_file_path, "r", encoding="utf-8") as file:
            vid_info = file.read()
            json_vid_info = json.loads(vid_info)
            thumbnail = json_vid_info.get("thumbnail")
            views = json_vid_info.get("view_count")
            likes = json_vid_info.get("like_count")
            playable_in_embed = json_vid_info.get("playable_in_embed")
            title = json_vid_info.get("fulltitle", json_vid_info.get("title"))
            categories = json_vid_info.get("categories", [])
            description = json_vid_info.get("description")
            channel_name = json_vid_info.get("channel")
            uploader = json_vid_info.get("uploader")
            language = json_vid_info.get("language")

            full_vid_info = {
                "thumbnail": thumbnail,
                "views": views,
                "likes": likes,
                "playable_in_embed": playable_in_embed,
                # ? For AI analysis
                "title": title,
                "categories": categories,
                "description": description,
                "channel_name": channel_name,
                "uploader": uploader,
                "language": language,
            }

            vid_info_for_validation = {
                "title": title,
                "categories": categories,
                "description": description,
                "channel_name": channel_name,
                "uploader": uploader,
                "language": language,
            }

        subtitle_info = {
            "exist": False,
            "path": None,
            "ext": None,
        }
        subtitle_pattern = f"./output/track/{video_id}.*.*"
        subtitle_files = glob.glob(subtitle_pattern)
        if subtitle_files:
            subtitle_info["exist"] = True
            subtitle_file = subtitle_files[0]
            subtitle_info["path"] = subtitle_file
            _, ext = os.path.splitext(subtitle_file)
            subtitle_info["ext"] = ext

        passed = self.validate_youtube_video(vid_info_for_validation)

        return (
            passed,
            audio_file_path,
            full_vid_info,
            vid_info_for_validation,
            subtitle_info,
            None,
        )

    def get_transcription(self, video_id, audio_file_path):
        # subtitle_file_path = "./output/track/" + video_id + ".ja.vtt"

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
                #                 prompt="""あなたは日本語の音声ファイルから日本語の歌詞を.srt形式で正確に書き起こす専門家です。以下の指示を守ってください：
                # 1. 音声全体を連続的に書き起こしてくださいが、歌詞のない部分にはタイムスタンプと空白を残してください。
                # 2. タイムスタンプを音声に正確に合わせてください。歌詞がない部分に歌詞を埋め込まないでください。
                # 3. 各行を10~15文字以内に収め、長い歌詞は複数行に分割してください。
                # 4. 歌詞のない部分は (前奏)、(間奏)、(後奏) と表記してください。
                # 5. 歌詞のみを記載し、説明は省いてください。
                # 例：
                # 1
                # 00:00:00,000 --> 00:00:18,000
                # (前奏)
                # 2
                # 00:00:20,000 --> 00:00:22,870
                # いつの間にやら日付は変わって
                # 3
                # 00:00:23,010 --> 00:00:26,450
                # なんで年ってとるんだろう
                # 4
                # 00:00:27,030 --> 00:00:32,780
                # もう背は伸びないくせに
                # ...
                # 音声の最初から最後まで、すべての時間を漏らさず書き起こしてください。
                # 歌詞がない場合は適切に空白を保持してください。""",
                prompt="""
あなたは日本語の音声ファイルから日本語の歌詞を.srt形式で正確に書き起こす専門家です。以下の指示を守ってください：

1. 音声全体を連続的に書き起こしてください
2. タイムスタンプを音声に正確に合わせてください
3. 各行を10～15文字以内に収め、長い歌詞は複数行に分割してください
4. 歌詞のない部分は (前奏)、(間奏)、(後奏)、(楽器演奏) と表記してください
5. 歌詞のみを記載し、説明は省いてください

例：
1
00:00:00,000 --> 00:00:18,000
(前奏)

2
00:00:20,000 --> 00:00:22,870
いつの間にやら日付は変わって

3
00:00:23,010 --> 00:00:26,450
なんで年ってとるんだろう

4
00:00:27,030 --> 00:00:32,780
もう背は伸びないくせに
...

音声の最初から最後まで、すべての時間を漏らさず書き起こしてください
""",
                response_format="srt",
                timestamp_granularities=["segment"],
                temperature=0.8,
            )

            srt_save_path = f"./output/response_srt/{video_id}.srt"
            print(transcription)
            print("Above is transcription")
            with open(srt_save_path, "w", encoding="utf-8") as output_file:
                output_file.write(transcription)

        print("GPT Transcription generated, processed, and saved successfully")

        # TODO: Consider adding a "cleansing step" through cgpt to remove any unwanted characters

        if transcription:
            return transcription
        else:
            return "Failed to get transcription"

    def get_translations(self, lyrics_arr, video_id):
        messages = [
            translation_setup_system_message,
            {
                "role": "user",
                "content": f"Translate the following lyrics to English and Chinese. Respond in JSON format. Lyrics: {json.dumps(lyrics_arr)}",
            },
        ]
        gpt_response = None

        try:
            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=messages,
                tools=tools,
                temperature=0.8,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "translate_lyrics"},
                },
            )

            # print("This is response message in ENG translation")
            # print(gpt_response.choices[0])

            # Check if there's a function call in the response
            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                translations = json.loads(function_call.arguments)
            else:
                print("In else block here in gpt tool calls check")
                raise ValueError("No function call found in the response")

            if not all(
                key in translations for key in ["english_lyrics", "chinese_lyrics"]
            ):
                print("In check for all translations keys exists")
                raise ValueError("Response is missing required keys")

            if len(translations["english_lyrics"]) != len(lyrics_arr) or len(
                translations["chinese_lyrics"]
            ) != len(lyrics_arr):
                print("In check for length of translations dont work")
                raise ValueError(
                    f"Number of translated lines does not match the original. "
                    f"Original: {len(lyrics_arr)}, English: {len(translations['english_lyrics'])}, "
                    f"Chinese: {len(translations['chinese_lyrics'])}"
                )

            # Ensure the output directory exists
            output_dir = "./output/response_4o_translate/"
            os.makedirs(output_dir, exist_ok=True)

            for lang in ["english", "chinese"]:
                # Save as JSON
                json_file_path = f"{output_dir}{video_id}_{lang[:3]}.json"
                with open(json_file_path, "w", encoding="utf-8") as file:
                    json.dump(
                        {f"{lang}_lyrics": translations[f"{lang}_lyrics"]},
                        file,
                        ensure_ascii=False,
                        indent=4,
                    )
                print(f"{lang.capitalize()} lyrics saved to {json_file_path}")

                # Save as TXT
                txt_file_path = f"{output_dir}{video_id}_{lang[:3]}.txt"
                with open(txt_file_path, "w", encoding="utf-8") as file:
                    for line in translations[f"{lang}_lyrics"]:
                        file.write(line + "\n")
                print(f"{lang.capitalize()} lyrics saved to {txt_file_path}")

            return translations["english_lyrics"], translations["chinese_lyrics"]

        except Exception as e:
            print(f"An error occurred in get_translations: {str(e)}")
            print(
                f"Response: {gpt_response.choices[0] if gpt_response else 'No response'}"
            )
            raise ValueError(
                "Error in GPT response: " + str(gpt_response.choices[0])
                if gpt_response
                else "Unexpected error"
            )

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
        filtered_srt_content = []

        srt_blocks = gpt_output.strip().split("\n\n")

        # Check for if majority of blocks have the same content
        content_count = {}
        for block in srt_blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                content = " ".join(lines[2:])
                content_count[content] = content_count.get(content, 0) + 1

        most_common_content = max(content_count, key=content_count.get)
        most_common_count = content_count[most_common_content]

        if most_common_count / len(srt_blocks) >= 0.8:
            raise ValueError(
                "Error: 80% or more of the SRT blocks have the same content. The transcription model may have errored out."
            )

        for index, block in enumerate(srt_blocks, 1):
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                timestamp = lines[1]
                lyric = " ".join(lines[2:])
                start_time_str, end_time_str = timestamp.split(" --> ")
                start_time = utils.convert_time_to_seconds(start_time_str)
                end_time = utils.convert_time_to_seconds(end_time_str)
                duration = round(end_time - start_time, 3)

                if (
                    not any(
                        exclude_str in lyric
                        for exclude_str in transcription_filter_srt_array
                    )
                    and not (duration >= 30 and len(lyric) > 20)
                    and not (len(lyric) > 50)
                ):

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

                    filtered_srt_content.append(f"{index}\n{timestamp}\n{lyric}\n")

        filtered_srt = "\n".join(filtered_srt_content)

        return {
            "lyrics": lyrics,
            "timestamped_lyrics": timestamped_lyrics,
            "filtered_srt": filtered_srt,
        }

    def validate_youtube_video(self, video_info):
        validation_msg = [
            validate_youtube_video_system_message,
            {
                "role": "user",
                "content": json.dumps(video_info),
            },
        ]
        gpt_response = None

        try:
            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=validation_msg,
                tools=tools,
                temperature=0,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "validate_music_video"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                verdict = json.loads(function_call.arguments)
            else:
                raise ValueError("No function call found in the response")

            if "decision" not in verdict:
                raise ValueError("Response is missing required keys")

            # print("This is decision")
            # print(verdict["decision"])

            affirmative_responses = {"y", "yes"}
            if verdict["decision"].strip().lower() in affirmative_responses:
                return True
            else:
                return False

        except Exception as e:
            print(f"An error occurred in validate_youtube_video: {str(e)}")
            print(
                f"Response: {gpt_response.choices[0] if gpt_response else 'No response'}"
            )
            return None

    def get_romaji_lyrics(self, lyrics_arr, video_id):
        romaji_messages = [
            romaji_annotation_system_message,
            {
                "role": "user",
                "content": f"以下の日本語の歌詞をローマ字に変換してください。JSON形式で応答してください。歌詞: {json.dumps(lyrics_arr)}",
            },
        ]
        gpt_response = None

        try:
            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=romaji_messages,
                tools=tools,
                temperature=0.2,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "convert_to_romaji"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                romaji_lyrics = json.loads(function_call.arguments)
                print("Romaji fn: received gpt response")
                print(gpt_response.choices[0].message.tool_calls)
                print("Romaji fn: end of printing received gpt response")

            else:
                raise ValueError("No function call found in the response")

            if "romaji" not in romaji_lyrics:
                raise ValueError("Response is missing required keys")

            if len(romaji_lyrics["romaji"]) != len(lyrics_arr):
                raise ValueError(
                    f"Number of Romaji lines does not match the original. "
                    f"Original: {len(lyrics_arr)}, Romaji: {len(romaji_lyrics['romaji'])}"
                )

            # Ensure the output directory exists
            output_dir = "./output/response_4o_translate/"
            os.makedirs(output_dir, exist_ok=True)

            json_file_path = f"{output_dir}{video_id}_romaji.json"
            with open(json_file_path, "w", encoding="utf-8") as file:
                json.dump(
                    {"romaji_lyrics": romaji_lyrics["romaji"]},
                    file,
                    ensure_ascii=False,
                    indent=4,
                )
            print(f"Romaji lyrics saved to {json_file_path}")

            # Save as TXT
            txt_file_path = f"{output_dir}{video_id}_romaji.txt"
            with open(txt_file_path, "w", encoding="utf-8") as file:
                for line in romaji_lyrics["romaji"]:
                    file.write(line + "\n")
            print(f"Romaji lyrics saved to {txt_file_path}")

            return romaji_lyrics["romaji"]

        except Exception as e:
            print(f"An error occurred in get_romaji_lyrics: {str(e)}")
            print(
                f"Response: {gpt_response.choices[0] if gpt_response else 'No response'}"
            )
            return None

    def get_kanji_annotations(self, lyrics_arr, video_id):
        kanji_messages = [
            kanji_annotation_system_message,
            {
                "role": "user",
                "content": f"Please annotate the following Japanese lyrics with furigana pronunciations. Respond in JSON format. Lyrics: {json.dumps(lyrics_arr)}",
            },
        ]
        gpt_response = None

        try:
            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=kanji_messages,
                tools=tools,
                temperature=0.2,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "annotate_with_furigana"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                kanji_annotations = json.loads(function_call.arguments)
                print("Kanji fn: received results")
                print(gpt_response.choices[0].message.tool_calls)
            else:
                raise ValueError("No function call found in the response")

            if "furigana_ann_lyrics" not in kanji_annotations:
                raise ValueError("Response is missing required keys")

            if len(kanji_annotations["furigana_ann_lyrics"]) != len(lyrics_arr):
                raise ValueError(
                    f"Number of annotated lines does not match the original. "
                    f"Original: {len(lyrics_arr)}, Annotated: {len(kanji_annotations['furigana_ann_lyrics'])}"
                )

            # Ensure the output directory exists
            output_dir = "./output/response_4o_translate/"
            os.makedirs(output_dir, exist_ok=True)

            json_file_path = f"{output_dir}{video_id}_kanji.json"
            with open(json_file_path, "w", encoding="utf-8") as file:
                json.dump(
                    {"kanji_annotations": kanji_annotations["furigana_ann_lyrics"]},
                    file,
                    ensure_ascii=False,
                    indent=4,
                )
            print(f"Kanji annotations saved to {json_file_path}")

            # Save as TXT
            txt_file_path = f"{output_dir}{video_id}_kanji.txt"
            with open(txt_file_path, "w", encoding="utf-8") as file:
                for line in kanji_annotations["furigana_ann_lyrics"]:
                    file.write(line + "\n")
            print(f"Kanji annotations saved to {txt_file_path}")

            return kanji_annotations["furigana_ann_lyrics"]

        except Exception as e:
            print(f"An error occurred in get_kanji_annotations: {str(e)}")
            print(
                f"Response: {gpt_response.choices[0] if gpt_response else 'No response'}"
            )
            return None

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
                temperature=0.2,
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
        # TODO: This is a test function for streaming, use it later
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
                temperature=0,
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
