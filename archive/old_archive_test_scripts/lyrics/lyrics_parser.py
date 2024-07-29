import re
from utils import time_to_seconds

#! Process AI generated srt file for frontend
def parse_srt_file(srt_filename):
    lyrics_info = {
        "lyrics": [],
        "lines": [],
    }

# Open the .srt file and read its contents
    with open(srt_filename, "r") as file:
        lines = file.readlines()

        #? Identifies current line of lyrics 
        current_line = None
        #? Identifies the end time of the last seen character
        previous_character_end_time = 0

        #? To be saved in subarray for lines
        sub_array_for_lines = {
            "text": "",
            "start_time": 0,
            "end_time": 0,
            "words": []
        }
        
        #? Identifies current block of .srt content
        current_block = {
            "word": "",
            "start_time": 0,
            "end_time": 0,
            "duration": 0
        }

        #? Each Line processing
        for line in lines:
            line = line.strip()

            #? If row is a timestamp, get start_time, end_time, and duration
            if re.match(r"\d+:\d+:\d+,\d+ --> \d+:\d+:\d+,\d+", line):
                start_time, end_time = line.split(" --> ")
                start_time = float(format(time_to_seconds(start_time), '.3f'))
                end_time = float(format(time_to_seconds(end_time), '.3f'))
                current_block["start_time"] = start_time
                current_block["end_time"] = end_time
                current_block["duration"] = format(round(end_time - start_time, 3), '.3f')
            
                #? Special case - first character of srt file - need to set start_time in init array
                if isinstance(lyrics_info, dict) and "lyrics" in lyrics_info and "lines" in lyrics_info:
                    if not lyrics_info["lyrics"] and not lyrics_info["lines"]:
                        current_block["start_time"] = start_time
            
            #? ignore index rows of .srt file
            elif line.isdigit():
                continue
            
            #? identifies if the row is a content row
            elif is_valid_lyrics(line):
                #? Gets text of lyrics without <font> tag
                line_word_is_in = remove_html_tags(line)

                #? Handle Special case - full sentence wrapped in <font> tag
                whole_line_tagged = re.match(r'^<font.*?>(.*?)<\/font>$', line, re.IGNORECASE)
                if whole_line_tagged:
                    # The whole line is within a font tag, so treat it as a special case
                    line_text = whole_line_tagged.group(1)
                    current_line = line_text
                    lyrics_info["lyrics"].append(current_line)
                    lyrics_info["lines"].append({
                        "text": current_line,
                        "start_time": current_block["start_time"],
                        "end_time": current_block["end_time"],
                        "words": [{
                            "word": current_line,
                            "start_time": current_block["start_time"],
                            "end_time": current_block["end_time"],
                            "duration": current_block["duration"]
                        }]
                    })
                    continue

                
                #? Gets the marked character
                tagged_word = re.search(r"<font.*?>(.*?)<\/font>", line)
                #? Only do stuff if can get the marked character
                if tagged_word:
                    word = tagged_word.group(1)
                    if word:
                        current_block["word"] = word
                    else:
                        current_block = {
                            "word": "",
                            "start_time": 0,
                            "end_time": 0,
                            "duration": 0
                        }
                        continue

                # ? If we are still on the same line as the previous word:
                if current_line == line_word_is_in:
                    # Add contents of this block to the subarray
                    sub_array_for_lines["words"].append(current_block.copy())
                    previous_character_end_time = current_block["end_time"]
                    current_block = {
                        "word": "",
                        "start_time": 0,
                        "end_time": 0,
                        "duration": 0
                    }
                #? If we moved onto a new line:
                else:
                    #? Add new line to the full lyrics array
                    if current_line is not None and sub_array_for_lines["text"] != '':  # Check if not the first line
                        #? Update end time and add the subarray of all words into tbr
                        if(previous_character_end_time == 0):
                            previous_character_end_time = current_block["end_time"]
                        sub_array_for_lines['end_time'] = previous_character_end_time
                        lyrics_info["lines"].append(sub_array_for_lines.copy())
                    current_line = line_word_is_in
                    lyrics_info["lyrics"].append(current_line)
                    sub_array_for_lines = {
                        "text": current_line,
                        "start_time": current_block["start_time"],
                        "end_time": 0,
                        "words": [current_block.copy()]
                    }
        if sub_array_for_lines['words'] and sub_array_for_lines["text"] != '':
            sub_array_for_lines['end_time'] = sub_array_for_lines['words'][-1]['end_time']
            lyrics_info["lines"].append(sub_array_for_lines.copy())

        # print("This is check for whether lines and lyrics are same length")
        # for key, value in lyrics_info.items():
        #    if isinstance(value, list):
        #       print(f"Length of '{key}': {len(value)}")

        return lyrics_info



# ? HELPER FUNCTIONS
def remove_html_tags(line):
    # Use regex to remove HTML tags
    clean_line = re.sub(r'<[^>]+>', '', line)
    return clean_line

#? Line is valid if there's <font> tag
def is_valid_lyrics(line):
    # Check if the line contains HTML tags
    if re.search(r'<[^>]+>', line):
        return True
    else:
        return False



result = parse_srt_file("./K1Tz2yNmamI.srt")
print(result)