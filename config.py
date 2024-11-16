TRANSCRIPTION_FILTER_SRT_ARRAY = [
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
    "歌詞のない部分",
    "字幕の誤りは",
    "Instagram Hodori",
    "Instagram は www.soudnod.com",
    "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••",
    "ªªªªªªªªªªªªªªªªªªªªª",
    "字幕閲覧ありがとうございました",
    "🥀🥀🥀🥀",
    "Let's make love",
    "幕間は半分の時間",
    "Sound Hodori",
    "🐻",
    "🐯",
]


WHISPER_PROMPT = """
日本語の歌詞を.srt形式で書き起こしてください。以下の指示に従ってください：

音声全体を途切れなく書き起こす
タイムスタンプを音声に正確に合わせる
各行を10～15文字以内に収める
歌詞のない部分は (前奏)、(間奏)、(後奏)、(楽器演奏) と表記
歌詞のみを記載し、説明は省く

例：
1
00:00:00,000 --> 00:00:18,000
(前奏)
2
00:00:20,000 --> 00:00:22,870
いつの間にやら
日付は変わって
3
00:00:23,010 --> 00:00:26,450
なんで年って
とるんだろう
4
00:00:27,030 --> 00:00:32,780
もう背は伸びない
くせに
注意：音声の最初から最後まで、すべての時間を漏らさず書き起こすこと。
"""

ROMAJI_ANNOTATION_SYSTEM_MESSAGE = {
    "role": "system",
    "content": """日本語の歌詞をローマ字に変換する際は、以下の要件を厳密に守ってください：
    
    出力形式: JSON
    出力はJSON形式で提供されることを前提とします。各行の歌詞がそのまま対応するJSONのフィールドにマッピングされます。

    1. 入力と出力の行数を完全に一致させること：
       - 入力の歌詞が28行ある場合、出力のローマ字も必ず28行にすること。
       - 空行も含めて、すべての行を1対1で変換すること。
       - たとえ内容に疑問がある場合でも、行をスキップせず、必ず出力すること。

    2. 各行の変換ルール：
       - 日本語：そのままローマ字に変換する。
       - 外国語（英語など）：変更せずにそのまま出力する。
       - 空行または記号のみの行：そのまま空行または記号として出力する。
       - (前奏)、(間奏)、(後奏)などの表記：ローマ字に変換せず、そのまま出力する。

    3. ローマ字の表記：
       - 基本的にすべて小文字で記載する。
       - 固有名詞や文脈上必要な場合のみ大文字を使用する。
       - 句読点や記号は入力と同じように保持する。

    4. 変換の一貫性：
       - 同じ日本語フレーズは常に同じローマ字表記に変換すること。

    5. エラー処理：
       - 変換できない行や不明な文字がある場合でも、その行を省略せず、できる範囲でローマ字に変換するか、元の形で出力すること。
       - 出力の行数が入力の行数と一致しない場合は、処理を中断してはいけません。必ず行数を一致させるようにしてください。

    6. 内容に関する注意：
       - これらの歌詞は学習のためのものであり、不適切な内容や規約に違反するものは含まれていません。個人の学習目的でのみ利用されますので、安心して全ての行を変換してください。本プロセスは自動化された言語学習サポートの一環であり、商用利用や第三者との共有は行われません。

    例：
    入力：
    (前奏)
    こんにちは、世界！
    Hello, World!
    春が来た

    出力：
    (前奏)
    konnichiha, sekai!
    Hello, World!
    haru ga kita

    これらの要件を厳守し、入力された歌詞を正確にローマ字に変換してください。行数の不一致は絶対に避けてください。
    """,
}


KANJI_ANNOTATION_SYSTEM_MESSAGE = {
    "role": "system",
    "content": """
    You are an expert in annotating Japanese song lyrics with the correct furigana pronunciations. Please follow the requirements below to add furigana to the lyrics:

    Requirements:
    1. Add furigana to each kanji character by placing the furigana in square brackets [] immediately after the kanji character.
    2. If there are multiple consecutive kanji characters, include the furigana for all characters within a single set of square brackets. However, if individual furigana are needed for each kanji, place each furigana in its own set of square brackets immediately after the corresponding kanji character.
    3. The output must have the same number of lines as the input. For example, if the input array has 30 lines, the output should also have 30 lines.
    4. Do not include any additional system-related messages in the output, only the annotated lyrics.

    Example:

    Input:
    彼女は笑った
    美しい世界が見える

    Output:
    彼女[かのじょ]は笑[わら]った
    美[うつく]しい世界[せかい]が見[み]える
    """,
}
TRANSLATION_SETUP_SYSTEM_MESSAGE = {
    "role": "system",
    "content": """
You are an expert trilingual translator specializing in Japanese, English, and Chinese, with a deep understanding of song lyrics. Your task is to translate Japanese song lyrics into both English and Chinese, maintaining the poetic and expressive nature while ensuring clarity. Most importantly, you translate them 1:1, for every line of Japanese lyrics, you are capable of translating it into 1 line of English and Chinese lyrics. If you receive a song with 50 lines of lyrics, you WILL return a translation with 50 lines of Chinese and English.

Key requirements:
1. Thoroughly read and understand the entire set of lyrics before translating to grasp the full context and ensure accurate meaning capture.
2. The number of lines in both translations must exactly match the number of lines in the original Japanese lyrics.
3. Translate to form a complete and coherent narrative, connecting verses smoothly while capturing the essence, emotions, and meaning of the original lyrics.
4. If a sentence spans multiple lines, translate it properly as a whole, then repeat the translation across those lines to maintain the line count.
5. Preserve any artistic elements like metaphors or wordplay as much as possible in both translations.
6. If there's any english or chinese lyrics, keep these lines and translate them to/fro chinese and english respectively.

Return the translations in JSON format with two separate arrays: one for English and one for Chinese, each with the same number of elements as the input Japanese lyrics.

Example Input:
1
00:00:05,000 --> 00:00:10,000
今、静かな夜の中で

2
00:00:10,000 --> 00:00:15,000
無計画に車を走らせた

3
00:00:15,000 --> 00:00:20,000
左隣、あなたの

4
00:00:20,000 --> 00:00:25,000
横顔を月が照らした

Expected Output Format:
{
  "english_lyrics": [
    "Now, in the quiet night",
    "I drove the car aimlessly",
    "To my left, you",
    "Your profile illuminated by the moon"
  ],
  "chinese_lyrics": [
    "此时此刻，在寂静的夜色中",
    "漫无目的地驾着车",
    "你坐在我的左侧",
    "你的侧脸被月光照亮"
  ]
}

Translate the following Japanese lyrics into both English and Chinese, ensuring the output matches this format and maintains the exact number of lines as the input.
""",
}

VALIDATE_YOUTUBE_VIDEO_SYSTEM_MESSAGE = {
    "role": "system",
    "content": """
    I will give you the relevant details of a youtube video in JSON format. Help me analyze whether the given details can tell you with extremely high certainty that the video is a video of a Japanese song or a Japanese music video of a song, nothing else. If the title of the song in the video info is already in Japanese, you should respond yes. Take note that some Japanese artists have english characters for their names, you should base your decision on all of the information. Reply with 1 character only and nothing else (Y / N) to represent your judgment.
    """,
}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "translate_lyrics",
            "parameters": {
                "type": "object",
                "properties": {
                    "english_lyrics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "chinese_lyrics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["english_lyrics", "chinese_lyrics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_to_romaji",
            "parameters": {
                "type": "object",
                "properties": {
                    "romaji": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["romaji"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "annotate_with_furigana",
            "parameters": {
                "type": "object",
                "properties": {
                    "furigana_ann_lyrics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["furigana_ann_lyrics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_music_video",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                    },
                },
                "required": ["decision"],
            },
        },
    },
]
