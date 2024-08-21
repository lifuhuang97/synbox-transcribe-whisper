import json
import re
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Any

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
    "字幕閲覧ありがとうございました",
    "🥀🥀🥀🥀",
    "🐻",
]


# ? General Utils
def concatenate_strings(string_array):
    # Using the join() method with '\n' as the separator
    string_array = [str(item) for item in string_array]  # Convert all items to strings
    result = "\n".join(string_array)
    return result


# ? Returns videoID no matter if it's a youtube URL or just the videoID
def extract_video_id(youtube_url):

    youtube_url_pattern = r"^https?:\/\/(?:www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11})(&.*)?$"
    # Check if input is a valid YouTube URL
    if not re.match(youtube_url_pattern, youtube_url):
        return youtube_url

    # Regular expression for finding a YouTube video ID in various URL formats
    video_id_pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11})|youtu\.be\/([0-9A-Za-z_-]{11})"
    match = re.search(video_id_pattern, youtube_url)
    if match:
        # Check which group has the match
        video_id = match.group(1) if match.group(1) else match.group(2)

        # Further validation if the video ID is part of a query string
        parsed_url = urlparse(youtube_url)
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            # This check ensures that 'v' parameter is present and the video_id is from the 'v' parameter
            if "v" in query_params and video_id in query_params["v"]:
                return video_id

        # If the video ID didn't come from the 'v' parameter but was successfully extracted
        if video_id:
            return video_id
    else:
        return None


# ? Utils for WhisperService


# ? Tester content - print everything
def print_full_content(obj, indent=0):
    # Set the indentation level for pretty printing
    ind = "    " * indent

    # Check if the object is a dictionary
    if isinstance(obj, dict):
        for key, value in obj.items():
            print(f"{ind}{key}:")
            print_full_content(value, indent + 1)  # Recursively print the value

    # Check if the object is a list or a tuple
    elif isinstance(obj, (list, tuple)):
        for index, item in enumerate(obj):
            print(f"{ind}[{index}]")
            print_full_content(item, indent + 1)  # Recursively print the item

    # Base case: the object is neither a dictionary nor a list/tuple
    else:
        print(f"{ind}{obj}")


def convert_time_to_seconds(time_str: str) -> float:
    hours, minutes, seconds_milliseconds = time_str.split(":")
    seconds, milliseconds = seconds_milliseconds.split(",")
    total_seconds = (
        int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
    )
    return total_seconds


def process_subtitle_file(
    file_path: str,
    file_format: str,
    exclude_strings: List[str] = transcription_filter_srt_array,
    max_duration: float = 30,
    max_lyric_length: int = 20,
    apply_error_checks: bool = False,
) -> Dict[str, Any]:

    def parse_time(time_str: str) -> float:
        if "," in time_str:  # SRT format
            time_str = time_str.replace(",", ".")
        elif "." not in time_str:  # ASS/SSA format
            time_str += ".000"
        h, m, s = time_str.split(":")
        return float(h) * 3600 + float(m) * 60 + float(s)

    def process_subtitle(content: str, subtitle_format: str) -> List[Dict[str, Any]]:
        timestamped_lyrics = []

        if subtitle_format == "srt" or subtitle_format == ".srt":
            pattern = r"(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)\n((?:.+\n?)+)"
        elif subtitle_format == "vtt" or subtitle_format == ".vtt":
            pattern = r"(\d+:\d+:\d+\.\d+) --> (\d+:\d+:\d+\.\d+)\n((?:.+\n?)+)"
        elif subtitle_format in ["ass", "ssa", ".ssa", ".ass"]:
            pattern = r"Dialogue: [^,]*,(\d+:\d+:\d+\.\d+),(\d+:\d+:\d+\.\d+),[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,(.*)"
        else:
            raise ValueError(f"Unsupported subtitle format: {subtitle_format}")

        for match in re.finditer(pattern, content, re.MULTILINE):
            start_time = round(parse_time(match.group(1)), 3)
            end_time = round(parse_time(match.group(2)), 3)
            lyric = match.group(3).strip().replace("\n", " ")

            duration = round(end_time - start_time, 3)

            if not apply_error_checks or (
                not any(exclude_str in lyric for exclude_str in exclude_strings)
                and not (duration >= max_duration and len(lyric) > 20)
                and not (len(lyric) > max_lyric_length)
            ):
                if (
                    len(lyric) > max_lyric_length and " " in lyric
                ):  # Check if there is a space
                    # Split long lyrics into multiple SRT blocks
                    words = lyric.split()
                    current_line = ""
                    lines = []
                    for word in words:
                        if len(current_line) + len(word) + 1 > max_lyric_length:
                            lines.append(current_line)
                            current_line = word
                        else:
                            if current_line:
                                current_line += " "
                            current_line += word
                    if current_line:
                        lines.append(current_line)

                    split_duration = duration / len(lines)
                    for i, line in enumerate(lines):
                        new_start_time = round(start_time + i * split_duration, 3)
                        new_end_time = round(start_time + (i + 1) * split_duration, 3)
                        timestamped_lyrics.append(
                            {
                                "start_time": new_start_time,
                                "end_time": new_end_time,
                                "duration": round(new_end_time - new_start_time, 3),
                                "lyric": line,
                            }
                        )
                else:
                    timestamped_lyrics.append(
                        {
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": duration,
                            "lyric": lyric,
                        }
                    )

        return timestamped_lyrics

    # Read file content
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Process subtitles
    timestamped_lyrics = process_subtitle(content, file_format)

    # Check for repeated content if apply_error_checks is True
    if apply_error_checks:
        content_count = {}
        for item in timestamped_lyrics:
            content = item["lyric"]
            content_count[content] = content_count.get(content, 0) + 1

        most_common_content = max(content_count, key=content_count.get)
        most_common_count = content_count[most_common_content]

        if most_common_count / len(timestamped_lyrics) >= 0.8:
            raise ValueError(
                "Error: 80% or more of the subtitle blocks have the same content. The transcription may have errored out."
            )

    # Generate other required outputs
    lyrics = [item["lyric"] for item in timestamped_lyrics]
    filtered_srt = "\n\n".join(
        [
            f"{i + 1}\n{item['start_time']:.3f} --> {item['end_time']:.3f}\n{item['lyric']}"
            for i, item in enumerate(timestamped_lyrics)
        ]
    )

    return {
        "lyrics": lyrics,
        "timestamped_lyrics": timestamped_lyrics,
        "filtered_srt": filtered_srt,
    }


def stream_message(type: str, data: str):
    return json.dumps({"type": type, "data": data}) + "\n"
