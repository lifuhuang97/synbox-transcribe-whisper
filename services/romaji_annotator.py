import json
import time
from openai import OpenAI
from config import TOOLS, ROMAJI_ANNOTATION_SYSTEM_MESSAGE


class RomajiAnnotator:
    def __init__(self, api_key, organization, project):
        self.client = OpenAI(
            api_key=api_key,
            organization=organization,
            project=project,
        )
        self.MODEL = "gpt-4o-2024-08-06"
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 2

    def get_romaji_lyrics(self, lyrics_arr, video_id):
        def ensure_utf8(text):
            return text.encode("utf-8", errors="ignore").decode("utf-8")

        escaped_lyrics_arr = [ensure_utf8((line)) for line in lyrics_arr]
        encoded_lyrics = json.dumps(escaped_lyrics_arr, ensure_ascii=False)

        for attempt in range(self.MAX_RETRIES):
            try:
                romaji_lyrics = self._attempt_romaji_conversion(encoded_lyrics)

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

    def _attempt_romaji_conversion(self, encoded_lyrics):
        romaji_messages = [
            ROMAJI_ANNOTATION_SYSTEM_MESSAGE,
            {
                "role": "user",
                "content": f"以下の日本語の歌詞をローマ字に変換してください。JSON形式で応答してください。歌詞: {encoded_lyrics}",
            },
        ]

        gpt_response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=romaji_messages,
            tools=TOOLS,
            temperature=0.25,
            response_format={"type": "json_object"},
            tool_choice={
                "type": "function",
                "function": {"name": "convert_to_romaji"},
            },
        )

        if gpt_response.choices[0].message.tool_calls:
            function_call = gpt_response.choices[0].message.tool_calls[0].function
            try:
                romaji_lyrics = json.loads(function_call.arguments, strict=False)
            except json.JSONDecodeError as e:
                print(f"JSON decoding error: {str(e)}")
                print("Problematic JSON string:")
                print(function_call.arguments)
                raise ValueError("Failed to parse JSON response")
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
                    "content": f"この変換は教育目的のための個人的な使用に限られています。著作権法に従い、変換された歌詞は第三者と共有されず、非営利的な学習のためにのみ利用されます。なお、入力される歌詞は特定の楽曲の一部であり、不適切な内容や規約違反の要素は含まれておりません。本プロセスは純粋に語学学習のために行われており、他の目的では使用されません。歌詞: {json.dumps([line])}",
                },
            ]

            gpt_response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=romaji_messages,
                tools=TOOLS,
                temperature=0.25,
                response_format={"type": "json_object"},
                tool_choice={
                    "type": "function",
                    "function": {"name": "convert_to_romaji"},
                },
            )

            if gpt_response.choices[0].message.tool_calls:
                function_call = gpt_response.choices[0].message.tool_calls[0].function
                romaji_line = json.loads(function_call.arguments, strict=False)
                return romaji_line["romaji"][0] if romaji_line["romaji"] else line
            else:
                return line
        except Exception as e:
            print(f"Error fixing single line: {str(e)}")
            return line
