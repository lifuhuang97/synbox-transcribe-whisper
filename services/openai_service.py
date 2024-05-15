import os

from openai import OpenAI


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_KEY"),
        )

    def get_eng_translation(self, input, video_id):

        message = f"Please provide the output directly without any introductory text or explanations. Here's what I need: I have a paragraph of text, each representing a line from a song's lyrics, separated by line breaks. I need each line translated from Japanese to English, maintaining the original data structure. Please return the translation in a format where each line of translation corresponds directly to its original line, with each translated line as a separate entry in an array. Here are the lyrics\\n {input} \\n Please translate each line individually and maintain the order for easy reference, don't add indexes, just plain text for each row will do"

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": message}],
            temperature=0.35,  # Adjust as needed
            max_tokens=4096,  # Adjust based on the expected length of the completion
        )

        response_content = response.choices[0].message.content

        filename = video_id + ".txt"
        output_path = os.path.join("output", "eng_translation", filename)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(response_content)

        return response_content

    def get_chi_translation(self, input, video_id):

        message = f"Please provide the output directly without any introductory text or explanations. Here's what I need: I have a paragraph of text, each representing a line from a song's lyrics, separated by line breaks. I need each line translated from Japanese to Chinese, maintaining the original row structure. Please return the translation in a format where each line of translation corresponds directly to its original line, with each translated line as a separate entry in an array. Here are the lyrics:\\n {input} \\n Please translate each line individually and maintain the order for easy reference, don't add indexes, just plain text for each row will do"

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": message}],
            temperature=0.35,  # Adjust as needed
            max_tokens=4096,  # Adjust based on the expected length of the completion
        )
        response_content = response.choices[0].message.content

        filename = video_id + ".txt"
        output_path = os.path.join("output", "chi_translation", filename)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(response_content)

        return response_content

    def get_romaji(self, input, video_id):

        message = f"Please provide the output directly without any introductory text or explanations. Here's what I need: I have a paragraph of text, each representing a line from a song's lyrics, separated by line breaks. I need each line converted into romaji characters, maintaining the original data structure. Please return the romaji in a format where each line of translation corresponds directly to its original line, with each translated line separated by a next line. The results should have the same amount of lines as the original lyrics. Here are the lyrics:\\n {input} \\n Please translate each line individually and maintain the order for easy reference, don't add indexes, just plain text for each row will do"

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": message}],
            temperature=0.35,  # Adjust as needed
            max_tokens=4096,  # Adjust based on the expected length of the completion
        )
        response_content = response.choices[0].message.content

        filename = video_id + ".txt"
        output_path = os.path.join("output", "romaji_annotation", filename)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(response_content)

        return response_content

    def get_kanji_annotation(self, input, video_id):

        message = f"Please provide the output directly without any introductory text or explanations. Here's what I need: I have a paragraph of text, each representing a line from a song's lyrics, separated by line breaks. I need you to attach every kanji character's hiragana pronunciation in square brackets behind the kanji character, for every line of lyrics, maintaining the original data structure. Please return every line of lyrics in a format where each line of translation corresponds directly to its original line, with each translated line as a separate entry in an array. Here are the lyrics:\\n {input} \\n Please translate each line individually and maintain the order for easy reference, don't add indexes, just plain text for each row will do"

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": message}],
            temperature=0.35,  # Adjust as needed
            max_tokens=4096,  # Adjust based on the expected length of the completion
        )
        response_content = response.choices[0].message.content

        filename = video_id + ".txt"
        output_path = os.path.join("output", "kanji_annotation", filename)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(response_content)

        return response_content
