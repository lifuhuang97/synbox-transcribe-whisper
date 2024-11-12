import json
import re
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Any, Tuple
import os
import glob
from config import TRANSCRIPTION_FILTER_SRT_ARRAY


# ? General Utils
def concatenate_strings(string_array):
    # Using the join() method with '\n' as the separator
    string_array = [str(item) for item in string_array]  # Convert all items to strings
    result = "\n".join(string_array)
    return result


def is_likely_japanese(text: str) -> bool:
    return any(
        "\u4e00" <= char <= "\u9fff"
        or "\u3040" <= char <= "\u309f"
        or "\u30a0" <= char <= "\u30ff"
        for char in text
    )


def process_japanese_subtitle(lyric_block: str) -> str:
    lyric_lines = lyric_block.split("\n")
    if len(lyric_lines) > 1:
        filtered_lines = []
        for i, line in enumerate(lyric_lines):
            if is_likely_japanese(line):
                filtered_lines.append(line)
                # If the next line exists and is likely romaji, skip it
                if i + 1 < len(lyric_lines) and not is_likely_japanese(
                    lyric_lines[i + 1]
                ):
                    continue
        return " ".join(filtered_lines)
    return lyric_block


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


def is_metadata_line(line: str) -> bool:
    """
    Determines if a line is likely metadata rather than lyrics.

    Args:
        line: String to check

    Returns:
        bool: True if line appears to be metadata
    """
    # Common metadata patterns
    metadata_patterns = [
        r"^[\w\s]+\s*[:：]\s*[\w\s]+$",  # Key: Value format
        r"^[𝚅𝚘𝚌𝚊𝚕𝙼𝚞𝚜𝚒𝚌𝙸𝚕𝚕𝚞𝚜𝚝𝚛𝚊𝚝𝚘𝚛𝙳𝚒𝚛𝚎𝚌𝚝𝚘𝚛]",  # Styled text often used in headers
        r"^\s*[\(\［【［\[].+[\)\］】］\]]\s*$",  # Bracketed text only
        r"^[-—]+$",  # Divider lines
        r"^\s*[Cc]horus\s*:?\s*$",  # Chorus marker
        r"^\s*[Vv]erse\s*\d*\s*:?\s*$",  # Verse marker
        r"^[\w\s]+\s*[/／]\s*[\w\s]+$",  # Slash-separated metadata
        r"^\s*[©®™]\s*\d{4}\s*",  # Copyright lines
        r"^\s*[Pp]erformed\s+[Bb]y\s*:",  # Performance credits
        r"^\s*[Ww]ritten\s+[Bb]y\s*:",  # Writing credits
        r"^\s*[Cc]omposed\s+[Bb]y\s*:",  # Composition credits
    ]

    # Check if line matches any metadata pattern
    return any(re.match(pattern, line) for pattern in metadata_patterns)


def is_valid_lyric_line(line: str) -> bool:
    """
    Determines if a line is likely to be valid lyrics.

    Args:
        line: String to check

    Returns:
        bool: True if line appears to be valid lyrics
    """
    # Strip whitespace and check if line is empty
    if not line.strip():
        return False

    # Check if line contains any Japanese characters
    has_japanese = bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", line))

    # Check if line contains English words (allowing for stylized text)
    has_english = bool(re.search(r"[a-zA-Z]{2,}", line))

    # Accept lines with Japanese characters
    if has_japanese:
        return True

    # Accept English lines that don't match metadata patterns
    if has_english and not is_metadata_line(line):
        return True

    return False


def clean_lyrics(content: str) -> Tuple[List[str], List[str]]:
    """
    Cleans lyrics content by removing metadata and invalid lines.

    Args:
        content: Raw lyrics content

    Returns:
        Tuple[List[str], List[str]]: (cleaned_lines, removed_lines)
    """
    lines = content.split("\n")
    cleaned_lines = []
    removed_lines = []

    # Process lines
    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Check if line is valid lyrics
        if is_valid_lyric_line(line):
            cleaned_lines.append(line)
        else:
            removed_lines.append(line)

    return cleaned_lines, removed_lines


def process_subtitle_file(
    file_path: str,
    file_format: str,
    exclude_strings: List[str] = TRANSCRIPTION_FILTER_SRT_ARRAY,
    max_duration: float = 30,
    max_lyric_length: int = 50,
    apply_error_checks: bool = False,
) -> Dict[str, Any]:

    def parse_time(time_str: str) -> float:
        if "," in time_str:  # SRT format
            time_str = time_str.replace(",", ".")
        elif "." not in time_str:  # ASS/SSA format
            time_str += ".000"
        h, m, s = time_str.split(":")
        return float(h) * 3600 + float(m) * 60 + float(s)

    def process_subtitle(
        content: str,
        subtitle_format: str,
        exclude_strings: List[str],
        apply_filters: bool = True,
    ) -> List[Dict[str, Any]]:
        timestamped_lyrics = []

        if subtitle_format.lower() in ["srt", ".srt"]:
            pattern = r"(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)\n((?:.+\n?)+)"
        elif subtitle_format.lower() in ["vtt", ".vtt"]:
            pattern = r"(\d+:\d+:\d+\.\d+) --> (\d+:\d+:\d+\.\d+)\n((?:.+\n?)+)"
        elif subtitle_format.lower() in ["ass", "ssa", ".ssa", ".ass"]:
            pattern = r"Dialogue: [^,]*,(\d+:\d+:\d+\.\d+),(\d+:\d+:\d+\.\d+),[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,(.*)"
        else:
            raise ValueError(f"Unsupported subtitle format: {subtitle_format}")

        for match in re.finditer(pattern, content, re.MULTILINE):
            start_time = round(parse_time(match.group(1)), 3)
            end_time = round(parse_time(match.group(2)), 3)
            lyric_block = match.group(3).strip()

            # First clean the lyrics block
            cleaned_lines, _ = clean_lyrics(lyric_block)

            if not cleaned_lines:
                continue

            # Join cleaned lines and process Japanese subtitles
            cleaned_lyric = " ".join(cleaned_lines)
            lyric = process_japanese_subtitle(cleaned_lyric)

            duration = round(end_time - start_time, 3)

            # Replace filtered content with redaction message instead of skipping
            if apply_filters and any(
                exclude_str in lyric for exclude_str in exclude_strings
            ):
                lyric = "「不正確なため削除されました」"

            if not apply_filters or (
                not (duration >= max_duration and len(lyric) > 20)
                and not (len(lyric) > max_lyric_length)
            ):
                if (
                    len(lyric) > max_lyric_length
                    and " " in lyric
                    and lyric != "「不正確なため削除されました」"
                ):
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

    # Process subtitles with filters
    timestamped_lyrics = process_subtitle(
        content, file_format, exclude_strings, apply_filters=True
    )

    # Modified: We don't need to reprocess without filters since we're keeping all lines now
    # The following block can be removed if you want to keep only the filtered version
    if not timestamped_lyrics:
        timestamped_lyrics = process_subtitle(
            content, file_format, exclude_strings, apply_filters=False
        )

    # Check for repeated content if apply_error_checks is True and timestamped_lyrics is not empty
    if apply_error_checks and timestamped_lyrics:
        content_count = {}
        for item in timestamped_lyrics:
            content = item["lyric"]
            if (
                content != "「不正確なため削除されました」"
            ):  # Don't count redacted lines in repetition check
                content_count[content] = content_count.get(content, 0) + 1

        if content_count:  # Only check if there are non-redacted lines
            most_common_content = max(content_count, key=content_count.get)
            most_common_count = content_count[most_common_content]
            total_non_redacted = sum(content_count.values())

            if most_common_count / total_non_redacted >= 0.8:
                raise ValueError(
                    "The transcription may have errored out, please try again later [high repetition]."
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


def cleanup_files(video_id):
    # Define paths to clean up
    paths_to_clean = [
        f"./output/cached_translations/{video_id}_*.txt",
        f"./output/response_srt/{video_id}.srt",
        f"./output/track/{video_id}.*",
    ]

    for path in paths_to_clean:
        for file in glob.glob(path):
            try:
                os.remove(file)
                print(f"Removed: {file}")
            except Exception as e:
                print(f"Error removing {file}: {str(e)}")

    # Check if the directories are empty and remove them if they are
    directories_to_check = [
        "./output/cached_translations",
        "./output/response_srt",
        "./output/track",
    ]

    for directory in directories_to_check:
        if os.path.exists(directory) and not os.listdir(directory):
            try:
                os.rmdir(directory)
                print(f"Removed empty directory: {directory}")
            except Exception as e:
                print(f"Error removing directory {directory}: {str(e)}")

    print("Cleanup completed.")
