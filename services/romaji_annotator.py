import json
import time
from openai import OpenAI
from config import TOOLS, ROMAJI_ANNOTATION_SYSTEM_MESSAGE

tools = TOOLS


class RomajiAnnotator:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.MODEL = "gpt-4o"
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 2  # seconds

    def get_romaji_lyrics(self, lyrics_arr, video_id):
        for attempt in range(self.MAX_RETRIES):
            try:
                romaji_lyrics = self._attempt_romaji_conversion(lyrics_arr)

                if len(romaji_lyrics["romaji"]) != len(lyrics_arr):
                    romaji_lyrics["romaji"] = self._fix_missing_lines(
                        lyrics_arr, romaji_lyrics["romaji"]
                    )

                yield "romaji_lyrics", romaji_lyrics["romaji"]
                return

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.MAX_RETRIES - 1:
                    yield "error", f"Failed to get Romaji lyrics after {self.MAX_RETRIES} attempts"
                    return
                time.sleep(self.RETRY_DELAY)

    def _attempt_romaji_conversion(self, lyrics_arr):
        romaji_messages = [
            ROMAJI_ANNOTATION_SYSTEM_MESSAGE,
            {
                "role": "user",
                "content": f"以下の日本語の歌詞をローマ字に変換してください。JSON形式で応答してください。歌詞: {json.dumps(lyrics_arr)}",
            },
        ]

        gpt_response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=romaji_messages,
            tools=tools,
            temperature=0.25,
            response_format={"type": "json_object"},
            tool_choice={
                "type": "function",
                "function": {"name": "convert_to_romaji"},
            },
        )

        if gpt_response.choices[0].message.tool_calls:
            function_call = gpt_response.choices[0].message.tool_calls[0].function
            romaji_lyrics = json.loads(function_call.arguments)
        else:
            raise ValueError("No function call found in the response")

        if "romaji" not in romaji_lyrics:
            raise ValueError("Response is missing required keys")

        return romaji_lyrics

    def _fix_missing_lines(self, original_lyrics, romaji_lyrics):
        fixed_romaji = []
        for i, (orig, roma) in enumerate(zip(original_lyrics, romaji_lyrics)):
            if not roma:
                print(f"Attempting to fix missing Romaji for line {i + 1}")
                fixed_line = self._get_single_line_romaji(orig)
                fixed_romaji.append(fixed_line)
            else:
                fixed_romaji.append(roma)
        return fixed_romaji

    def _get_single_line_romaji(self, line):
        try:
            romaji_messages = [
                ROMAJI_ANNOTATION_SYSTEM_MESSAGE,
                {
                    "role": "user",
                    "content": f"以下の1行の日本語をローマ字に変換してください。JSON形式で応答してください。歌詞: {json.dumps([line])}",
                },
            ]

            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=romaji_messages,
                tools=tools,
                temperature=0.25,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "convert_to_romaji"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                romaji_line = json.loads(function_call.arguments)
                return romaji_line["romaji"][0] if romaji_line["romaji"] else line
            else:
                return line
        except Exception as e:
            print(f"Error fixing single line: {str(e)}")
            return line  # Return original line if conversion fails
