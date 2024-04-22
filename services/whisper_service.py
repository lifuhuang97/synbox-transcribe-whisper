import re
import stable_whisper
import os
from pytube import YouTube, Channel, request
import pandas as pd
import threading

from functools import partial
from utils import utils

class WhisperService:


  def __init__(self, redis_service=None):
    # cache_dir = os.path.expanduser("~/.cache/whisper")
    # model = AutoModel.from_pretrained("Tanrei/GPTSAN-japanese")
    # converted_model = convert_hf_whisper("Tanrei/GPTSAN-japanese", "./models/whisperGPTSAN.pt")
    # self.model = stable_whisper.load_model(converted_model)
    self.redis_service = redis_service
    #? Local development only
    self.model = stable_whisper.load_model('medium')
    

#   def get_progress_by_video_id(self, video_id):
    # progress_data = self.ssh_tunnel.hgetall(video_id)
    # if progress_data:
        # Convert byte strings to appropriate data types
        # progress = {
            # "transcribed_seconds": float(progress_data.get(b"transcribed_seconds", 0)),
            # "total_seconds": float(progress_data.get(b"total_seconds", 1)),
            # "progress": float(progress_data.get(b"progress", 0))
        # }
        # return progress
    # else:
        # Handle the case where the key doesn't exist
        # return None

  # progress_callback : Callable, optional
  #     A function that will be called when transcription progress is updated.
  #     The callback need two parameters.
  #     The first parameter is a float for seconds of the audio that has been transcribed.
  #     The second parameter is a float for total duration of audio in seconds.
  def update_progress(self, videoId, *args, **kwargs):
      #? Get the keyword arguments
      transcribed_seconds = kwargs.get('seek', 0)
      total_seconds = kwargs.get('total', 1)  # Avoid division by zero
      # seek = kwargs.get('seek', None)
      # if seek is not None:
      #   print(f"Seek duration: {seek}")

      # if args:
      #     print(f"Additional positional arguments: {args}")
      # if kwargs:
      #     print(f"Additional keyword arguments: {kwargs}")

      progress_percentage = (transcribed_seconds / total_seconds) * 100
      print("Wew my progress update function")
      print(f"Transcribed: {transcribed_seconds:.2f}s / {total_seconds:.2f}s ({progress_percentage:.2f}%)")

    #   self.ssh_tunnel.hmset(videoId, {
    #       "transcribed_seconds": transcribed_seconds,
    #       "total_seconds": total_seconds,
    #       "progress": progress_percentage
    #   })

  def get_available_models(self):
    return stable_whisper.available_models()


  def transcribev3(self, video_url):
    video_id = video_url
    language ="ja"
    update_progress_callback = partial(self.update_progress, video_id)

    root_dir = os.getcwd()  # Get the current working directory (root)
    audio_track_dir = os.path.join(root_dir, 'output/track')
    lyrics_dir = os.path.join(root_dir, 'output/lyrics')

    audio_filename = video_id + ".mp4"
    lyrics_filename = os.path.join(lyrics_dir, video_id + ".srt")

    print("Finding lyrics file... ")

    #? Check if lyrics already exists
    if os.path.exists(lyrics_filename):
      # If .srt already exists, return it immediately
       print("Lyrics already exist for this videoId, returning lyrics")
       return lyrics_filename


    print("Lyrics doesn't exist, finding audio file...")
    #? Check if audio already exists
    audio_filename = os.path.join(audio_track_dir, video_id + ".mp4") 

    if not os.path.exists(audio_filename):
      full_vid_url = "https://www.youtube.com/watch?v=" + video_id
      audio_source =  audio_file = YouTube(full_vid_url)
      audio_duration = audio_source.length
      print("Audio_duration is: ", audio_duration)

      if(audio_duration > 480):
         print("Audio source is too long, cancelling request...")
         return None
      
      else:
        print("Audio file not found, downloading audio file...")
        audio_file = audio_source.streams.filter(only_audio=True).first().download(filename=audio_filename)
        audio_file_downloaded = True
    else:
      print("Audio already exists, using existing audio file...")
      audio_file = audio_filename

    print("Transcribing audio file...")
    result = self.model.transcribe(audio_file, language=language, word_timestamps=True, beam_size=5,no_speech_threshold=0.38, vad=True, progress_callback=update_progress_callback).split_by_length(max_chars=20)
    
    result.to_srt_vtt(lyrics_filename)
    # tag: tuple of (str, str), default None, meaning ('<font color="#00ff00">', '</font>') if SRT else ('<u>', '</u>')     Tag used to change the properties a word at its timestamp.
    print("Transcription complete, returning lyrics file...")


    os.remove(audio_file)
    return lyrics_filename
    

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
            start_time = float(format(utils.time_to_seconds(start_time), '.3f'))
            end_time = float(format(utils.time_to_seconds(end_time), '.3f'))
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

      # print("This is check for whether lines and lyrics are same length")
      # for key, value in lyrics_info.items():
      #    if isinstance(value, list):
      #       print(f"Length of '{key}': {len(value)}")

      return lyrics_info



  # ? HELPER FUNCTIONS
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


