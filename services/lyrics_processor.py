import re
from typing import List, Dict, Any, Tuple


class LyricsProcessor:
    @staticmethod
    def is_metadata(line: str) -> bool:
        """Determine if a line is metadata rather than actual lyrics."""
        metadata_patterns = [
            # Title patterns
            r"『[^』]+』",  # Japanese quotation marks with title
            r"【[^】]+】",  # Japanese brackets
            r"\[[^\]]+\]",  # Square brackets
            r"^\s*\d+\s*$",  # Just numbers (track numbers)
            # Credit patterns
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

    @staticmethod
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
        if has_english and not LyricsProcessor.is_metadata(line):
            return True

        return False

    @staticmethod
    def clean_lyrics_array(lyrics: List[str]) -> List[str]:
        """Clean an array of lyrics lines, removing metadata and invalid lines."""
        cleaned = []

        for line in lyrics:
            line = line.strip()
            if not line:
                continue

            if LyricsProcessor.is_valid_lyrics_line(
                line
            ) and not LyricsProcessor.is_metadata(line):
                cleaned.append(line)

        return cleaned

    @staticmethod
    def clean_timestamped_lyrics(
        timestamped_lyrics: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Clean timestamped lyrics by removing metadata entries while preserving timing."""
        cleaned = []

        for entry in timestamped_lyrics:
            lyric = entry.get("lyric", "").strip()
            if not lyric:
                continue

            if LyricsProcessor.is_valid_lyrics_line(
                lyric
            ) and not LyricsProcessor.is_metadata(lyric):
                cleaned.append(entry)

        return cleaned

    @staticmethod
    def process_lyrics_for_translation(
        lyrics_arr: List[str], timestamped_lyrics: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Process both lyrics array and timestamped lyrics for translation,
        ensuring they remain synchronized.
        """
        # Clean both arrays
        cleaned_lyrics = LyricsProcessor.clean_lyrics_array(lyrics_arr)
        cleaned_timestamped = LyricsProcessor.clean_timestamped_lyrics(
            timestamped_lyrics
        )

        # Verify synchronization
        if len(cleaned_lyrics) != len(cleaned_timestamped):
            raise ValueError("Lyrics arrays lost synchronization during cleaning")

        return cleaned_lyrics, cleaned_timestamped
