import os
import json
from openai import OpenAI
import yt_dlp
from tenacity import retry, wait_random_exponential, stop_after_attempt
from utils import utils
from termcolor import colored

translation_setup_system_message = {
    "role": "system",
    "content": """You are an expert translator with a deep understanding of Japanese lyrics, tasked with translating song lyrics into English and Chinese and return them in JSON. The translations must be tonally consistent with the original song and capture the full context and emotion of the lyrics.
    
Requirements:
1. The translated lyrics should form a complete and coherent narrative, connecting each verse smoothly, and capture the essence of the original lyrics, conveying the same emotions and meaning accurately.
2. The output must be an array with the exact same length as the input array. For instance, if the input array has 30 lines, the output should also have 30 lines.
3. Ensure each translated line corresponds to the same position in the array as the original, maintaining the same number of lines.
4. If it is unavoidable to combine two lines into one, duplicate the resulting line to maintain the original number of lines.
5. You should not provide any additional responses that are unrelated to the task of translating lyrics.

Example:
Input: ["今、静かな夜の中で","無計画に車を走らせた","左隣、あなたの","横顔を月が照らした","ただ、思い出を探る様に","辿る様に言葉を繋ぎ合わせれば","どうしようもなく溢れてくる","日々の記憶","あなたのそばで生きると決めたその日から","少しずつ変わり始めた世界","強く在るように弱さを隠すように","演じてきた日々に","ある日突然現れたその眼差しが","知らなかったこと教えてくれた","守るべきものがあればそれだけで","こんなにも強くなれるんだ","深い深い暗闇の中で","出会い、共に過ごしてきた","類の無い日々","心地よかった","いや、幸せだった","確かにほら","救われたんだよ","あなたに","わずかな光を捉えて輝いたのは","まるで流れ星のような涙","不器用な命から流れて零れ落ちた","美しい涙","強く大きな体に秘めた優しさも","どこか苦しげなその顔も","愛しく思うんだ","姿形じゃないんだ","やっと気付いたんだ","無情に響く銃声が夜を引き裂く","別れの息吹が襲いかかる","刹那に輝いた無慈悲な流れ星","祈りはただ届かずに消えた","この、手の中で燃え尽きた","金色の優しい彗星を","美しいたてがみを","暗闇の中握り締めた"]
Output: {
    "english_lyrics": ["Now, in the quiet night","I drove the car aimlessly","To my left, you","Your profile illuminated by the moon","Just like searching for memories","If I piece together words","Uncontrollably overflowing","Memories of the days","Since the day I decided to live by your side","The world began to change little by little","Hiding my weakness to be strong","In the days I pretended","One day, suddenly, those eyes appeared","Taught me things I didn't know","As long as I have something to protect","I can become this strong","In the deep, deep darkness","We met and spent time together","Days unlike any other","They were comfortable","No, they were happy","Indeed, look","I was saved","By you","The faint light captured and shined","Like a shooting star, tears","Fell from a clumsy life","Beautiful tears","The kindness hidden in a strong, large body","And that slightly pained face","I find them dear","It's not about appearance","I finally realized","The merciless gunshot tears the night","The breath of farewell attacks","A merciless shooting star shining in an instant","The prayer just disappeared without reaching","In my hands, it burned out","The gentle golden comet","Its beautiful mane","I held tight in the darkness"
],
    "chinese_lyrics": ["现在，在宁静的夜晚","我毫无计划地开车","在我的左边，你","你的侧脸被月光照亮","就像在寻找回忆","如果我把话语拼凑起来","不受控制地涌现出来","那些日子的记忆","从我决定在你身边生活的那一天起","世界开始一点一点地改变","隐藏我的软弱来变得坚强","在我假装的日子里","有一天，突然，那双眼睛出现了","教会了我不知道的事情","只要有需要保护的东西","我就能变得这么强大","在深深的黑暗中","我们相遇并一起度过了","无与伦比的日子","那些日子很舒服","不，那些日子很幸福","确实，你看","我被你拯救了","我被你拯救了","那微弱的光被捕捉并闪耀着","像流星一样的眼泪","从笨拙的生命中流淌下来的","美丽的眼泪","隐藏在强大身体里的温柔","和那略带痛苦的脸","我觉得它们很可爱","这不是关于外表的","我终于意识到了","无情的枪声撕裂了夜晚","告别的气息袭来","刹那间闪耀的无情流星","祈祷没有传达就消失了","在我手中燃尽","温柔的金色彗星","它美丽的鬃毛","在黑暗中紧紧握住",
],
}
    """,
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "translate_lyrics",
            "description": "Please translate the given array of Japanese lyrics into both English and Chinese versions of the original lyrics, maintaining the same array length and capturing the context and tone of the original song accurately, and return a JSON object",
            "parameters": {
                "type": "object",
                "properties": {
                    "english_lyrics": {
                        "type": "array",
                        "description": "The translated English lyrics array, with the same length as the input array",
                        "items": {"type": "string"},
                    },
                    "chinese_lyrics": {
                        "type": "array",
                        "description": "The translated Chinese lyrics array, with the same length as the input array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["english_lyrics", "chinese_lyrics"],
            },
        },
    },
]


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_KEY"),
        )
        self.MODEL = "gpt-4o"

    def get_eng_translation(self, lyrics_arr, video_id):

        messages = [
            translation_setup_system_message,
            {"role": "user", "content": json.dumps(lyrics_arr)},
        ]

        gpt_response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=messages,
            tools=tools,
            temperature=0.9,
            response_format={"type": "json_object"},
            tool_choice={"type": "function", "function": {"name": "translate_lyrics"}},
        )

        print("This is response message in ENG translation")
        print(gpt_response.choices[0])

        if (
            gpt_response.choices[0].message
            and gpt_response.choices[0].message.tool_calls
        ):
            tool_call = gpt_response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "translate_lyrics":
                function_response = tool_call.function.arguments
                lyrics_response = json.loads(function_response)
                english_lyrics = lyrics_response.get("english_lyrics", "")
                chinese_lyrics = lyrics_response.get("chinese_lyrics", "")
            else:
                raise ValueError("Unexpected function call in GPT response")
        else:
            raise ValueError("No function call found in GPT response")

        # Ensure the output directory exists
        os.makedirs("./output/response_4o_translate/", exist_ok=True)

        # Define the output file paths
        eng_output_file_path = f"./output/response_4o_translate/{video_id}_eng.json"
        chi_output_file_path = f"./output/response_4o_translate/{video_id}_chi.json"

        # Save the English lyrics to a JSON file
        with open(eng_output_file_path, "w", encoding="utf-8") as eng_file:
            json.dump(
                {"english_lyrics": english_lyrics},
                eng_file,
                ensure_ascii=False,
                indent=4,
            )

        # Save the Chinese lyrics to a JSON file
        with open(chi_output_file_path, "w", encoding="utf-8") as chi_file:
            json.dump(
                {"chinese_lyrics": chinese_lyrics},
                chi_file,
                ensure_ascii=False,
                indent=4,
            )

        print(f"English lyrics saved successfully to {eng_output_file_path}")
        print(f"Chinese lyrics saved successfully to {chi_output_file_path}")

        return english_lyrics, chinese_lyrics

    def get_transcription(self, video_id):

        ydl_opts = {
            "match_filter": self.longer_than_five_mins,
            "format": "m4a/bestaudio/best",
            "postprocessors": [
                {  # Extract audio using ffmpeg
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
            "outtmpl": "./output/track/%(id)s.%(ext)s",
        }

        #TODO: Clean up, only validate URL once across the process
        full_vid_url = "https://www.youtube.com/watch?v=" + video_id

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download(full_vid_url)
            print(
                "Audio download failed"
                if error_code
                else "Audio successfully downloaded"
            )

        audio_file_path = "./output/track/" + video_id + ".m4a"

        with open(audio_file_path, "rb") as audio_file:
            
            #TODO: Check whether this can guarantee good results, if not convert to function call
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ja",
                #TODO: Rewrite prompt
                prompt="日本語の歌を文章に書き起こしてください。歌詞を意味のある場所で改行し、各行は5~7秒以内にしてください。タイムスタンプは常に曲の範囲内である必要があります。可能な限り正しい漢字を推測して使用してください",
                response_format="srt",
                timestamp_granularities=["segment"],
            )

            srt_save_path = f"./output/response_srt/{video_id}.srt"
            with open(srt_save_path, "w", encoding="utf-8") as output_file:
                output_file.write(transcription)

        tbr_output = self.process_gpt_transcription(transcription)

        print("GPT Transcription generated, processed, and saved successfully")

        if tbr_output:

            return tbr_output
        else:
            return "Failed to get transcription"

    #! Helper Functions
    def longer_than_five_mins(self, info):
        """Download only videos shorter than 5mins"""
        duration = info.get("duration")
        if duration and duration > 300:
            return "The video is too long"

    def process_gpt_transcription(self, gpt_output):
        # Process the transcription response from OpenAI
        lyrics = []
        timestamped_lyrics = []

        srt_blocks = gpt_output.strip().split("\n\n")
        for block in srt_blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                timestamp = lines[1]
                lyric = " ".join(lines[2:])

                lyrics.append(lyric)

                start_time_str, end_time_str = timestamp.split(" --> ")
                start_time = utils.convert_time_to_seconds(start_time_str)
                end_time = utils.convert_time_to_seconds(end_time_str)
                duration = round(end_time - start_time, 3)

                timestamped_lyrics.append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration,
                        "lyric": lyric,
                    }
                )

        return {"lyrics": lyrics, "timestamped_lyrics": timestamped_lyrics}

    @retry(
        wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3)
    )
    def chat_completion_request(
        self, messages, tools=None, tool_choice=None, model="gpt-4o"
    ):
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            return response
        except Exception as e:
            print("Unable to generate ChatCompletion response")
            print(f"Exception: {e}")
            return e

    def pretty_print_conversation(self, messages):
        role_to_color = {
            "system": "red",
            "user": "green",
            "assistant": "blue",
            "function": "magenta",
        }

        for message in messages:
            if message["role"] == "system":
                print(
                    colored(
                        f"system: {message['content']}\n",
                        role_to_color[message["role"]],
                    )
                )
            elif message["role"] == "user":
                print(
                    colored(
                        f"user: {message['content']}\n", role_to_color[message["role"]]
                    )
                )
            elif message["role"] == "assistant" and message.get("function_call"):
                print(
                    colored(
                        f"assistant: {message['function_call']}\n",
                        role_to_color[message["role"]],
                    )
                )
            elif message["role"] == "assistant" and not message.get("function_call"):
                print(
                    colored(
                        f"assistant: {message['content']}\n",
                        role_to_color[message["role"]],
                    )
                )
            elif message["role"] == "function":
                print(
                    colored(
                        f"function ({message['name']}): {message['content']}\n",
                        role_to_color[message["role"]],
                    )
                )
