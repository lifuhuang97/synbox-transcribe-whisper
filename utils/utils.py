import json
import re
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Any, Tuple
import os
import glob
from config import TRANSCRIPTION_FILTER_SRT_ARRAY
import unicodedata


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

        matches = list(re.finditer(pattern, content, re.MULTILINE))

        for match in matches:
            start_time = round(parse_time(match.group(1)), 3)
            end_time = round(parse_time(match.group(2)), 3)
            lyric_block = match.group(3).strip()

            if not lyric_block:
                continue

            processed_lyric = process_japanese_subtitle(lyric_block)

            # Skip excluded strings while maintaining timing relationship
            if apply_filters and any(
                exclude_str in processed_lyric for exclude_str in exclude_strings
            ):
                continue

            # Store original timing with the lyric
            entry = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": round(end_time - start_time, 3),
                "lyric": lyric_block,
            }

            # Handle line length limits while preserving timing
            if len(processed_lyric) > max_lyric_length and " " in processed_lyric:
                words = processed_lyric.split()
                current_line = ""
                lines = []

                for word in words:
                    if len(current_line) + len(word) + 1 > max_lyric_length:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                    else:
                        current_line = f"{current_line} {word}".strip()

                if current_line:
                    lines.append(current_line)

                # Only split timing if we actually need to split the line
                if lines:
                    time_per_segment = entry["duration"] / len(lines)
                    for i, line in enumerate(lines):
                        segment_start = entry["start_time"] + (i * time_per_segment)
                        segment_end = segment_start + time_per_segment
                        timestamped_lyrics.append(
                            {
                                "start_time": round(segment_start, 3),
                                "end_time": round(segment_end, 3),
                                "duration": round(time_per_segment, 3),
                                "lyric": line,
                            }
                        )
            else:
                entry["lyric"] = processed_lyric
                timestamped_lyrics.append(entry)

        return timestamped_lyrics

    # Read and process content
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Process with filters first
    timestamped_lyrics = process_subtitle(
        content, file_format, exclude_strings, apply_filters=True
    )

    # Only try without filters if we got no results
    if not timestamped_lyrics:
        timestamped_lyrics = process_subtitle(
            content, file_format, exclude_strings, apply_filters=False
        )

    # Error checking for repeated content
    if apply_error_checks and timestamped_lyrics:
        content_count = {}
        for item in timestamped_lyrics:
            content = item["lyric"]
            content_count[content] = content_count.get(content, 0) + 1

        if content_count:
            most_common_content = max(content_count, key=content_count.get)
            most_common_count = content_count[most_common_content]
            total_lines = len(content_count)

            if most_common_count / total_lines >= 0.8:
                raise ValueError(
                    "The transcription may have errored out, please try again later [high repetition]."
                )

    # Generate outputs
    lyrics = [item["lyric"] for item in timestamped_lyrics]

    # Generate SRT maintaining original timing
    filtered_srt_lines = []
    for i, item in enumerate(timestamped_lyrics):
        start_time_str = format_timestamp(item["start_time"])
        end_time_str = format_timestamp(item["end_time"])
        filtered_srt_lines.extend(
            [str(i + 1), f"{start_time_str} --> {end_time_str}", item["lyric"], ""]
        )

    filtered_srt = "\n".join(filtered_srt_lines).strip()

    return {
        "lyrics": lyrics,
        "timestamped_lyrics": timestamped_lyrics,
        "filtered_srt": filtered_srt,
    }


def stream_message(type: str, data: str):
    return json.dumps({"type": type, "data": data}) + "\n"


# ! NEW
def is_metadata(line: str) -> bool:
    """Determine if a line is metadata rather than actual lyrics."""
    metadata_patterns = [
        # Title patterns
        r"(?i):\s*\w+",  # Key: value format
        r"(?i)(vocal|music|lyrics|artist|vocal|singer|composer|arrangement|illust|cover|歌|作詞|作曲)",
        r"(?i)(produced by|covered by|feat\.|ft\.|featuring)",
        # Formatting and markers
        r"^\s*-+\s*$",  # Divider lines
        r"(?i)^(chorus|verse|bridge|intro|outro)",
        # File metadata
        r"(?i)(subtitles?|closed\s*captions?|cc\s*:)",
        r"(?i)(uploaded|published|recorded)",
        # Time codes and duration
        r"^\d{2}:\d{2}",  # Timestamp format
        r"^\d{2}:\d{2}:\d{2}",  # Extended timestamp
        # General metadata indicators
        r"[/／]",  # Slashes often used in metadata
        r"^[\(\（][^\)\）]+[\)\）]$",  # Full line in parentheses
        r"(?i)(http|www\.)",  # URLs
        r"©|®|™",  # Copyright symbols
    ]

    return any(bool(re.search(pattern, line)) for pattern in metadata_patterns)


def is_valid_lyrics_line(line: str) -> bool:
    """
    Determine if a line is likely to be valid lyrics.
    Returns True if the line contains Japanese text or looks like valid English lyrics.
    """
    # Remove common formatting
    cleaned = re.sub(r"[\(\（\[\「][^\)\）\]\」]*[\)\）\]\」]", "", line).strip()

    if not cleaned:
        return False

    # Check for Japanese characters
    has_japanese = bool(
        re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", cleaned)
    )
    if has_japanese:
        return True

    # Check for valid English lyrics (at least 2 characters, not just numbers or symbols)
    has_english = bool(re.search(r"[a-zA-Z]{2,}", cleaned))
    if has_english and not is_metadata(line):
        return True

    return False


def clean_lyrics_array(lyrics: List[str]) -> List[str]:
    """Clean an array of lyrics lines, removing metadata and invalid lines."""
    cleaned = []

    for line in lyrics:
        line = line.strip()
        if not line:
            continue

        if is_valid_lyrics_line(line) and not is_metadata(line):
            cleaned.append(line)

    return cleaned


def clean_timestamped_lyrics(
    timestamped_lyrics: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Clean lyrics while preserving timestamp relationships.
    """
    return [
        entry
        for entry in timestamped_lyrics
        if entry.get("lyric")
        and is_valid_lyrics_line(entry["lyric"])
        and not is_metadata(entry["lyric"])
    ]


def process_lyrics_for_translation(
    lyrics_arr: List[str], timestamped_lyrics: List[Dict[str, Any]]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Process lyrics while strictly preserving timestamp-lyric pairs.
    If a lyric is filtered out, its corresponding timestamp entry is also removed,
    preventing lyrics from shifting to incorrect timestamps.

    Args:
        lyrics_arr: List of lyrics lines
        timestamped_lyrics: List of dictionaries containing timing information

    Returns:
        Tuple[List[str], List[Dict[str, Any]]]: Processed lyrics and their corresponding timing data
    """
    if len(lyrics_arr) != len(timestamped_lyrics):
        raise ValueError(
            f"Input arrays must have matching lengths. Lyrics: {len(lyrics_arr)}, Timestamps: {len(timestamped_lyrics)}"
        )

    def is_valid_line(line: str) -> bool:
        """
        Determine if a line should be kept in the processed output.
        """
        # Keep instrumental markers
        if line.strip() in ["[音楽]", "(音楽)", "［音楽］"]:
            return True

        # Remove empty lines
        if not line or line.isspace():
            return False

        # Keep lines with actual content
        return True

    # Create paired list of (lyric, timestamp) tuples
    paired_data = list(zip(lyrics_arr, timestamped_lyrics))

    # Filter pairs together, keeping valid lines and their corresponding timestamps
    processed_pairs = []

    for i, (lyric, timestamp) in enumerate(paired_data):
        if is_valid_line(lyric):
            # Create a new timestamp dict to avoid modifying the original
            processed_pairs.append(
                (
                    lyric.strip(),
                    {
                        "start_time": timestamp["start_time"],
                        "end_time": timestamp["end_time"],
                        "duration": timestamp["duration"],
                        "lyric": lyric.strip(),
                    },
                )
            )

    # Unzip the pairs into separate lists
    if processed_pairs:
        processed_lyrics, processed_timestamps = zip(*processed_pairs)
        return list(processed_lyrics), list(processed_timestamps)

    return [], []


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", ",")


def sanitize_text(text: str) -> str:
    """
    Enhanced sanitization for lyrics content handling.
    """
    if not isinstance(text, str):
        return ""

    # Strip VTT timing information
    text = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}", "", text)

    # Remove parenthetical translations/notes
    text = re.sub(r"\(.*?\)", "", text)

    # Normalize Unicode characters
    text = unicodedata.normalize("NFKC", text)

    # Remove mathematical alphanumeric symbols
    text = re.sub(
        r"[\U0001D400-\U0001D7FF]", "", text
    )  # Mathematical Alphanumeric Symbols
    text = re.sub(
        r"[\U0001F100-\U0001F1FF]", "", text
    )  # Enclosed Alphanumeric Supplement

    # Remove VTT metadata headers
    text = re.sub(r"^WEBVTT|^Kind:|^Language:", "", text, flags=re.MULTILINE)

    # Clean up specific formatting
    text = re.sub(r"/.*$", "", text)  # Remove slash and everything after it on a line
    text = re.sub(r'["""]', '"', text)  # Normalize quotes

    # Standard character replacements
    replacements = {
        "＆": "&",
        "：": ":",
        "―": "-",
        "–": "-",
        "—": "-",
        "～": "~",
        "\u200b": "",
        "\ufeff": "",
        "「": "",
        "」": "",
        "『": "",
        "』": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove control characters while preserving valid newlines
    text = "".join(
        char for char in text if unicodedata.category(char)[0] != "C" or char in "\n\r"
    )

    # Clean up empty lines and extra whitespace
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

    return text.strip()


# Keep existing utility functions but update them to use new functions where appropriate
def convert_time_to_seconds(time_str: str) -> float:
    hours, minutes, seconds_milliseconds = time_str.split(":")
    seconds, milliseconds = seconds_milliseconds.split(",")
    total_seconds = (
        int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
    )
    return total_seconds


def has_japanese_characters(text: str) -> bool:
    japanese_ranges = [
        (0x3040, 0x309F),  # Hiragana
        (0x30A0, 0x30FF),  # Katakana
        (0x4E00, 0x9FFF),  # Kanji
        (0xFF66, 0xFF9F),  # Half-width katakana
    ]

    return any(
        any(start <= ord(char) <= end for start, end in japanese_ranges)
        for char in text
    )


def extract_video_id(youtube_url: str) -> str:
    youtube_url_pattern = r"^https?:\/\/(?:www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11})(&.*)?$"

    # Return as-is if it's already just a video ID
    if not re.match(youtube_url_pattern, youtube_url):
        return youtube_url

    video_id_pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11})|youtu\.be\/([0-9A-Za-z_-]{11})"
    match = re.search(video_id_pattern, youtube_url)

    if match:
        video_id = match.group(1) if match.group(1) else match.group(2)
        parsed_url = urlparse(youtube_url)

        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            if "v" in query_params and video_id in query_params["v"]:
                return video_id

        if video_id:
            return video_id

    return None


def cleanup_files(video_id: str) -> None:
    """Clean up temporary files and empty directories."""
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
