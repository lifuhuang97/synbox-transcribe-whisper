import os
import glob
import json
from openai import OpenAI
import yt_dlp
from utils import utils

from config import (
    TOOLS,
    VALIDATE_YOUTUBE_VIDEO_SYSTEM_MESSAGE,
    TRANSLATION_SETUP_SYSTEM_MESSAGE,
    KANJI_ANNOTATION_SYSTEM_MESSAGE,
    ROMAJI_ANNOTATION_SYSTEM_MESSAGE,
    WHISPER_PROMPT
)

tools = TOOLS
validate_youtube_video_system_message = VALIDATE_YOUTUBE_VIDEO_SYSTEM_MESSAGE
translation_setup_system_message = TRANSLATION_SETUP_SYSTEM_MESSAGE
kanji_annotation_system_message = KANJI_ANNOTATION_SYSTEM_MESSAGE
romaji_annotation_system_message = ROMAJI_ANNOTATION_SYSTEM_MESSAGE
whisper_prompt = WHISPER_PROMPT


class OpenAIService:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.MODEL = "gpt-4o"

    def validate_video(self, video_id):
        result = {
            "passed": False,
            "audio_file_path": None,
            "full_vid_info": None,
            "vid_info_for_validation": None,
            "subtitle_info": {"exist": False, "path": None, "ext": None},
            "error_msg": None,
        }

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

        full_vid_url = "https://www.youtube.com/watch?v=" + video_id

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                error_code = ydl.download(full_vid_url)
                if error_code:
                    result["error_msg"] = "Audio download failed"
                    yield utils.stream_message("error", result["error_msg"])
                    yield utils.stream_message("data", result)
                    return
        except Exception as e:
            result["error_msg"] = f"An error occurred during video download: {str(e)}"
            if (
                str(e)
                == "Encountered a video that did not match filter, stopping due to --break-match-filter"
            ):
                result["error_msg"] = (
                    "The video length is invalid for processing, please try a different video."
                )
            yield utils.stream_message("error", result["error_msg"])
            return

        result["audio_file_path"] = "./output/track/" + video_id + ".m4a"
        info_file_path = "./output/track/" + video_id + ".info.json"
        yield utils.stream_message("update", "Analyzing Video...")

        try:
            with open(info_file_path, "r", encoding="utf-8") as file:
                json_vid_info = json.load(file)
        except Exception as e:
            result["error_msg"] = (
                f"Error reading video info: {str(e)}, please try again or try another video."
            )
            yield utils.stream_message("error", result["error_msg"])
            return

        result["full_vid_info"] = {
            "id": video_id,
            "thumbnail": json_vid_info.get("thumbnail"),
            "views": json_vid_info.get("view_count"),
            "duration": json_vid_info.get("duration"),
            "likes": json_vid_info.get("like_count"),
            "playable_in_embed": json_vid_info.get("playable_in_embed"),
            "title": json_vid_info.get("fulltitle", json_vid_info.get("title")),
            "categories": json_vid_info.get("categories", []),
            "description": json_vid_info.get("description"),
            "channel_name": json_vid_info.get("channel"),
            "uploader": json_vid_info.get("uploader"),
            "language": json_vid_info.get("language"),
        }

        result["vid_info_for_validation"] = {
            "title": result["full_vid_info"]["title"],
            "categories": result["full_vid_info"]["categories"],
            "description": result["full_vid_info"]["description"],
            "channel_name": result["full_vid_info"]["channel_name"],
            "uploader": result["full_vid_info"]["uploader"],
            "language": result["full_vid_info"]["language"],
        }

        subtitle_pattern = f"./output/track/{video_id}.ja.*"
        subtitle_files = glob.glob(subtitle_pattern)
        if subtitle_files:
            result["subtitle_info"]["exist"] = True
            subtitle_file = subtitle_files[0]
            result["subtitle_info"]["path"] = subtitle_file
            _, ext = os.path.splitext(subtitle_file)
            result["subtitle_info"]["ext"] = ext

        if not result["full_vid_info"]["playable_in_embed"]:
            result["error_msg"] = (
                "Video is not playable outside of YouTube, please try another video."
            )
            yield utils.stream_message("error", result["error_msg"])
            return

        if (
            result["full_vid_info"]["language"] == "ja"
            and "Music" in result["full_vid_info"]["categories"]
        ):
            result["passed"] = True
        else:
            result["passed"] = self.validate_youtube_video(
                result["vid_info_for_validation"]
            )
            if not result["passed"]:
                result["error_msg"] = (
                    "This video is not a Japanese music video, please try another video."
                )
                yield utils.stream_message("error", result["error_msg"])
                return

        yield utils.stream_message("update", "Validation Completed")
        yield utils.stream_message("vid_info", result)

    def get_transcription(self, video_id, audio_file_path):
        # subtitle_file_path = "./output/track/" + video_id + ".ja.vtt"

        with open(audio_file_path, "rb") as audio_file:

            # TODO: change parameters to try to deal with fast songs
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ja",
                # TODO: Rewrite prompt
                prompt=whisper_prompt,
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
            return srt_save_path
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
        """Download only videos shorter than 5mins or longer than 1min"""
        duration = info.get("duration")
        if duration and duration > 480:
            return "The video is too long"
        elif duration and duration < 60:
            return "The video is too short"

    # #! Helper Function - process GPT Whisper transcription
    # def process_gpt_transcription(self, gpt_output):
    #     # Process the transcription response from OpenAI
    #     lyrics = []
    #     timestamped_lyrics = []
    #     filtered_srt_content = []

    #     srt_blocks = gpt_output.strip().split("\n\n")

    #     # Check for if majority of blocks have the same content
    #     content_count = {}
    #     for block in srt_blocks:
    #         lines = block.strip().split("\n")
    #         if len(lines) >= 3:
    #             content = " ".join(lines[2:])
    #             content_count[content] = content_count.get(content, 0) + 1

    #     most_common_content = max(content_count, key=content_count.get)
    #     most_common_count = content_count[most_common_content]

    #     if most_common_count / len(srt_blocks) >= 0.8:
    #         raise ValueError(
    #             "Error: 80% or more of the SRT blocks have the same content. The transcription model may have errored out."
    #         )

    #     for index, block in enumerate(srt_blocks, 1):
    #         lines = block.strip().split("\n")
    #         if len(lines) >= 3:
    #             timestamp = lines[1]
    #             lyric = " ".join(lines[2:])
    #             start_time_str, end_time_str = timestamp.split(" --> ")
    #             start_time = utils.convert_time_to_seconds(start_time_str)
    #             end_time = utils.convert_time_to_seconds(end_time_str)
    #             duration = round(end_time - start_time, 3)

    #             if (
    #                 not any(
    #                     exclude_str in lyric
    #                     for exclude_str in transcription_filter_srt_array
    #                 )
    #                 and not (duration >= 30 and len(lyric) > 20)
    #                 and not (len(lyric) > 50)
    #             ):

    #                 lyrics.append(lyric)
    #                 start_time_str, end_time_str = timestamp.split(" --> ")
    #                 start_time = utils.convert_time_to_seconds(start_time_str)
    #                 end_time = utils.convert_time_to_seconds(end_time_str)
    #                 duration = round(end_time - start_time, 3)

    #                 timestamped_lyrics.append(
    #                     {
    #                         "start_time": start_time,
    #                         "end_time": end_time,
    #                         "duration": duration,
    #                         "lyric": lyric,
    #                     }
    #                 )

    #                 filtered_srt_content.append(f"{index}\n{timestamp}\n{lyric}\n")

    #     filtered_srt = "\n".join(filtered_srt_content)

    #     return {
    #         "lyrics": lyrics,
    #         "timestamped_lyrics": timestamped_lyrics,
    #         "filtered_srt": filtered_srt,
    #     }

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
