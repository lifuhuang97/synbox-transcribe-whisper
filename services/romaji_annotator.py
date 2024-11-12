import json
import time
import re
from openai import OpenAI
from config import TOOLS, ROMAJI_ANNOTATION_SYSTEM_MESSAGE
import unicodedata


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

    def sanitize_text(self, text):
        """
        Enhanced sanitization for VTT content handling
        """
        if not isinstance(text, str):
            return ""

        # Strip VTT timing information if present
        text = re.sub(
            r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}", "", text
        )

        # Remove parenthetical translations/notes
        text = re.sub(r"\(.*?\)", "", text)

        # Normalize Unicode characters
        text = unicodedata.normalize("NFKC", text)

        # Remove mathematical alphanumeric symbols more comprehensively
        text = re.sub(
            r"[\U0001D400-\U0001D7FF]", "", text
        )  # Mathematical Alphanumeric Symbols
        text = re.sub(
            r"[\U0001F100-\U0001F1FF]", "", text
        )  # Enclosed Alphanumeric Supplement

        # Remove VTT metadata headers
        text = re.sub(r"^WEBVTT|^Kind:|^Language:", "", text, flags=re.MULTILINE)

        # Clean up specific formatting seen in the VTT file
        text = re.sub(
            r"/.*$", "", text
        )  # Remove slash and everything after it on a line
        text = re.sub(r'["""]', '"', text)  # Normalize quotes

        # Standard character replacements
        replacements = {
            "＆": "&",
            "：": ":",
            "―": "-",
            "–": "-",
            "—": "-",
            "～": "~",
            "\u200b": "",  # Zero-width space
            "\ufeff": "",  # BOM
            "「": "",
            "」": "",
            "『": "",
            "』": "",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Remove control characters while preserving valid newlines
        text = "".join(
            char
            for char in text
            if unicodedata.category(char)[0] != "C" or char in "\n\r"
        )

        # Clean up any resulting empty lines or extra whitespace
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        return text.strip()

    def validate_lyrics_structure(self, lyrics):
        """
        Enhanced validation for VTT-sourced lyrics
        """
        if not isinstance(lyrics, list):
            return []

        valid_lyrics = []
        for line in lyrics:
            # Skip empty or non-string lines
            if not line or not isinstance(line, str):
                continue

            # Skip metadata and formatting lines
            skip_patterns = [
                r"^WEBVTT",
                r"^Kind:",
                r"^Language:",
                r"^\d{2}:\d{2}:\d{2}",
                r"^Vocal\s*:",
                r"^Music\s*:",
                r"^Director\s*:",
                r"^Illustrator\s*:",
                r"^\(.*\)$",  # Skip pure translation lines
                r"^[\u0020-\u002F\u003A-\u0040\u005B-\u0060\u007B-\u007E]+$",  # Skip lines with only punctuation
            ]

            if any(
                re.search(pattern, line, re.IGNORECASE) for pattern in skip_patterns
            ):
                continue

            sanitized_line = self.sanitize_text(line)
            if sanitized_line and not sanitized_line.isspace():
                valid_lyrics.append(sanitized_line)

        return valid_lyrics

    def _attempt_romaji_conversion(self, encoded_lyrics):
        """
        Enhanced error handling for API conversion
        """
        try:
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

            if (
                not gpt_response.choices
                or not gpt_response.choices[0].message.tool_calls
            ):
                raise ValueError("No valid response from API")

            function_call = gpt_response.choices[0].message.tool_calls[0].function

            # Additional safety check for response
            response_text = self.sanitize_text(function_call.arguments)

            # Ensure the response is properly terminated JSON
            if not response_text.strip().endswith("}"):
                response_text = response_text.strip() + '"]}'

            try:
                result = json.loads(response_text)
                if not isinstance(result, dict) or "romaji" not in result:
                    raise ValueError("Invalid response structure")
                return result
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
                print("Problematic JSON string:")
                print(response_text)
                raise ValueError("Failed to parse API response")

        except Exception as e:
            raise ValueError(f"API request failed: {str(e)}")

    def get_romaji_lyrics(self, lyrics_arr, video_id):
        try:
            # Validate and clean the input lyrics
            cleaned_lyrics = self.validate_lyrics_structure(lyrics_arr)

            if not cleaned_lyrics:
                yield "error", "No valid lyrics found after sanitization"
                return

            # Convert to UTF-8 and ensure proper encoding
            encoded_lyrics = json.dumps(cleaned_lyrics, ensure_ascii=False)

            for attempt in range(self.MAX_RETRIES):
                try:
                    romaji_lyrics = self._attempt_romaji_conversion(encoded_lyrics)

                    # Verify the response structure
                    if (
                        not isinstance(romaji_lyrics, dict)
                        or "romaji" not in romaji_lyrics
                    ):
                        raise ValueError("Invalid response structure from API")

                    romaji_array = romaji_lyrics["romaji"]
                    if not isinstance(romaji_array, list):
                        raise ValueError("Romaji response is not an array")

                    # Ensure matching lengths and fix if necessary
                    if len(romaji_array) != len(cleaned_lyrics):
                        romaji_array = self._fix_missing_lines(
                            cleaned_lyrics, romaji_array
                        )

                    # Final validation of output
                    validated_romaji = [
                        self.sanitize_text(line) if line else "[Invalid]"
                        for line in romaji_array
                    ]

                    yield "romaji_lyrics", validated_romaji
                    return

                except Exception as e:
                    print(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == self.MAX_RETRIES - 1:
                        yield "error", f"Failed to get Romaji lyrics after {self.MAX_RETRIES} attempts: {str(e)}"
                        return
                    time.sleep(self.RETRY_DELAY * (attempt + 1))  # Exponential backoff

        except Exception as e:
            yield "error", f"Unexpected error in get_romaji_lyrics: {str(e)}"

    def _fix_missing_lines(self, original_lyrics, romaji_lyrics):
        """
        Fix missing or mismatched lines in romaji conversion
        """
        max_length = max(len(original_lyrics), len(romaji_lyrics))
        fixed_romaji = []

        for i in range(max_length):
            if i < len(romaji_lyrics) and romaji_lyrics[i]:
                fixed_romaji.append(romaji_lyrics[i])
            elif i < len(original_lyrics):
                fixed_line = self._get_single_line_romaji(original_lyrics[i])
                fixed_romaji.append(fixed_line)
            else:
                fixed_romaji.append("[Missing]")

        return fixed_romaji

    def _get_single_line_romaji(self, line):
        """
        Convert a single line to romaji with error handling
        """
        try:
            sanitized_line = self.sanitize_text(line)
            if not sanitized_line:
                return "[Invalid]"

            romaji_messages = [
                ROMAJI_ANNOTATION_SYSTEM_MESSAGE,
                {
                    "role": "user",
                    "content": f"この一行の日本語をローマ字に変換してください: {json.dumps([sanitized_line])}",
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
                cleaned_response = self.sanitize_text(function_call.arguments)
                romaji_line = json.loads(cleaned_response)
                return (
                    romaji_line["romaji"][0]
                    if romaji_line.get("romaji")
                    else "[Failed]"
                )

            return "[Failed]"

        except Exception as e:
            print(f"Error in single line conversion: {str(e)}")
            return "[Failed]"
