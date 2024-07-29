import os
import re
import threading
from functools import partial

import pandas as pd
import stable_whisper
import whisper
from pytube import Channel, YouTube, request

from utils import utils

class WhisperTestService:


    def parse_srt_file(self, srt_filename):
        lyrics_info = {
            "lyrics": [],
            "lines": [],
        }

        with open(srt_filename, "r", encoding="utf-8") as file:
            lines = file.readlines()

            #? Current line tracker
            current_line = ""
            #? End time tracker of last seen character
            prev_char_end_time = 0

            #? Current block of .srt content tracker
            current_block = {"word": "", "start_time": 0, "end_time": 0, "duration": 0}
            
            #? To be saved in subarr for lines
            subarr_for_lines = {
                "line": "",
                "start_time": 0,
                "end_time": 0,
                "words": [],
            }

            #? looping through lines in .srt file 
            for line in lines:
                line = line.strip()

                # ? Skip index id of .srt lines
                if line.isdigit():
                    continue
                # ? Timestamp getter (start_time, end_time, duration)
                elif re.match(r"\d+:\d+:\d+,\d+ --> \d+:\d+:\d+,\d+", line):
                    start_time, end_time = line.split(" --> ")
                    start_time = float(format(utils.time_to_seconds(start_time), ".3f"))
                    end_time = float(format(utils.time_to_seconds(end_time), ".3f"))
                    current_block["start_time"] = start_time
                    current_block["end_time"] = end_time
                    current_block["duration"] = format(
                        round(end_time - start_time, 3), ".3f"
                    )

                    #? Special case
                    #? First char of srt file - set start_time in init_array
                    if (
                        isinstance(lyrics_info, dict)
                        and "lyrics" in lyrics_info
                        and "lines" in lyrics_info
                    ):
                        if not lyrics_info["lyrics"] and not lyrics_info["lines"]:
                            current_block["start_time"] = start_time

                # ? identifies if the row is a content row
                # ? Only if there's HTML <font> tags in the line
                elif self.is_valid_lyrics(line):
                    # ? Get the text wrapped in html tags
                    line_word_is_in = self.remove_html_tags(line)
                    # ? Handle Special case - full sentence wrapped in <font> tag
                    whole_line_tagged = re.match(
                        r"^<font.*?>(.*?)<\/font>$", line, re.IGNORECASE
                    )
                    if whole_line_tagged:
                        # The whole line is within a font tag, so treat it as a special case
                        line_text = whole_line_tagged.group(1)
                        current_line = line_text
                        lyrics_info["lyrics"].append(current_line)
                        lyrics_info["lines"].append(
                            {
                                "text": current_line,
                                "start_time": current_block["start_time"],
                                "end_time": current_block["end_time"],
                                "words": [
                                    {
                                        "word": current_line,
                                        "start_time": current_block["start_time"],
                                        "end_time": current_block["end_time"],
                                        "duration": current_block["duration"],
                                    }
                                ],
                            }
                        )
                        continue
                     # ? Handle Special case END

                    # ? Gets the marked character
                    tagged_word = re.search(r"<font.*?>(.*?)<\/font>", line)

                    # ? Only proceed if can get character marked by font tags
                    if tagged_word:
                        word = tagged_word.group(1)
                        if word:
                            current_block["word"] = word
                        # ? If there's no word, continue searching the re results
                        else:
                            current_block = {
                                "word": "",
                                "start_time": 0,
                                "end_time": 0,
                                "duration": 0,
                            }
                            continue

                    if current_line == line_word_is_in:
                        
            




    # ? HELPER FUNCTIONS
    def remove_html_tags(self, line):
        # Use regex to remove HTML tags
        clean_line = re.sub(r"<[^>]+>", "", line)
        return clean_line

    def is_valid_lyrics(self, line):
        # Check if the line contains HTML tags
        if re.search(r"<[^>]+>", line):
            return True
        else:
            return False