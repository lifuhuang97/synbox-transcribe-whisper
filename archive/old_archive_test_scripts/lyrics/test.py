import re

def time_to_seconds(time_str):
    hours, minutes, seconds_milliseconds = time_str.split(":")
    seconds, milliseconds = seconds_milliseconds.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000.0

def parse_srt(srt_filename):
    with open(srt_filename, "r", encoding="utf-8") as file:
        lines = file.readlines()
        character_array = []
        full_text = ""
        prev_end_time = 0

        for line in lines:
            line = line.strip()

            if line.isdigit():
                continue

            elif re.match(r"\d+:\d+:\d+,\d+ --> \d+:\d+:\d+,\d+", line):
                start_time, end_time = line.split(" --> ")
                start_time = float(format(time_to_seconds(start_time), ".3f"))
                end_time = float(format(time_to_seconds(end_time), ".3f"))

            elif re.search(r'<font>(.*?)</font>', line):
                character = re.search(r'<font>(.*?)</font>', line).group(1)
                duration = round(end_time - start_time, 3)
                current_block = {
                    "character": character,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": format(duration, ".3f"),
                }
                # Check for gap before adding character
                if prev_end_time and (start_time - prev_end_time) > 0.48:
                    # Ensure duration for blank space is at least 300 ms
                    if (start_time - prev_end_time) >= 0.3:
                        blank_block = {
                            "character": " ",
                            "start_time": prev_end_time,
                            "end_time": start_time,
                            "duration": format(start_time - prev_end_time, ".3f"),
                        }
                        character_array.append(blank_block)
                        full_text += " "
                character_array.append(current_block)
                full_text += character
                prev_end_time = end_time

            elif line:
                duration = round(end_time - start_time, 3)
                if duration >= 0.3:
                    current_block = {
                        "character": " ",
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": format(duration, ".3f"),
                    }
                    character_array.append(current_block)
                    full_text += " "

        return character_array, full_text

# Example usage
srt_filename = "./VyvhvlYvRnc.srt"
character_array, full_text = parse_srt(srt_filename)
print(character_array)
print(full_text)
