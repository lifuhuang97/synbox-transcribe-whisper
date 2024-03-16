import re
import stable_whisper
import os
from pytube import YouTube, Channel, request
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

class TranscribeService:
  def __init__(self):
    cache_dir = os.path.expanduser("~/.cache/whisper")
    self.model = stable_whisper.load_model('medium')

  def transcribev3(self, video_url):
    language ="ja"

    video_id = self.extract_video_id(video_url)
    
    request._DEFAULT_TIMEOUT = 600

    audio_filename = video_id + ".mp4"
    transcript_filename = video_id + ".srt"

    if not os.path.exists(audio_filename):
      audio_file = YouTube(video_url).streams.filter(only_audio=True).first().download(filename=audio_filename)
    else:
      audio_file = audio_filename

    
    if os.path.exists(transcript_filename):
      parsed_srt = self.parse_srt_file(transcript_filename)
      print("This is line in lyrics: ")
      for line in parsed_srt["lyrics"]:
        print(line)
      
      print("This is line in lines:")
      for line in parsed_srt["lines"]:
         print(line)

      # print("This is each line item: ")
      # for line in parsed_srt["lines"]:
      #   print("Lyric Row: ", line["text"])
      #   print("Start Time: ", line["start_time"])
      #   print("End Time: ", line["end_time"])
        
      #   print("This is each word item: ")
      #   for word in line["words"]:
      #     print("Word: ", word["word"])
      #     print("Start Time: ", word["start_time"])
      #     print("End Time: ", word["end_time"])
      #     print("Duration: ", word["duration"])

      print("This is length of lyrics: ", len(parsed_srt["lyrics"]))
      print("This is length of lines: ", len(parsed_srt["lines"]))

      

    else:
      result = self.model.transcribe(audio_file, language=language, word_timestamps=True, beam_size=5, vad=True)
      result.to_srt_vtt(transcript_filename)

  #! Process AI generated srt file for frontend
  def parse_srt_file(self, srt_filename):
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
            start_time = float(format(self.time_to_seconds(start_time), '.3f'))
            end_time = float(format(self.time_to_seconds(end_time), '.3f'))
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
        elif self.is_valid_lyrics(line):
          #? Gets text of lyrics without <font> tag
          line_word_is_in = self.remove_html_tags(line)

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
            print("This is subarray for lines: ", sub_array_for_lines)
            sub_array_for_lines = {
              "text": current_line,
              "start_time": current_block["start_time"],
              "end_time": 0,
              "words": [current_block.copy()]
            }
      if sub_array_for_lines['words'] and sub_array_for_lines["text"] != '':
        sub_array_for_lines['end_time'] = sub_array_for_lines['words'][-1]['end_time']
        lyrics_info["lines"].append(sub_array_for_lines.copy())
      return lyrics_info

  # ? HELPER FUNCTIONS
  def time_to_seconds(self, time_str):
      # Convert timestamp from HH:MM:SS,mmm to seconds with milliseconds
      parts = time_str.split(":")
      hours = int(parts[0])
      minutes = int(parts[1])
      seconds, milliseconds = map(int, parts[2].split(","))
      total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
      return total_seconds

  def extract_video_id(self, youtube_url):
      # Regular expression for finding a YouTube video ID
      video_id_pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11})'
      
      match = re.search(video_id_pattern, youtube_url)
      if match:
          return match.group(1)
      else:
          return None

  def remove_html_tags(self, line):
      # Use regex to remove HTML tags
      clean_line = re.sub(r'<[^>]+>', '', line)
      return clean_line

  #? Line is valid if there's <font> tag
  def is_valid_lyrics(self, line):
      # Check if the line contains HTML tags
      if re.search(r'<[^>]+>', line):
          return True
      else:
          return False

transcribe_service = TranscribeService()
transcribe_service.transcribev3("https://www.youtube.com/watch?v=x90-vUMKdx0")