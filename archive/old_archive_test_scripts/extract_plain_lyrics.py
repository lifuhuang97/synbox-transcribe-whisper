def extract_lyrics_from_srt(srt_file_path, output_text_file_path):
    # Open the .srt file and read its contents
    with open(srt_file_path, 'r', encoding='utf-8') as srt_file:
        lines = srt_file.readlines()

    # Initialize an empty list to store the lyrics lines
    lyrics_lines = []

    # Iterate through the lines of the .srt file
    for line in lines:
        # Skip empty lines and lines with timestamps
        if line.strip() and not line.strip().isdigit() and '-->' not in line:
            lyrics_lines.append(line.strip())

    # Write the extracted lyrics lines to the output text file
    with open(output_text_file_path, 'w', encoding='utf-8') as text_file:
        for line in lyrics_lines:
            text_file.write(line + '\n')

    print(f"Lyrics extracted and saved to {output_text_file_path}")

# Example usage
song_id="VyvhvlYvRnc"
srt_file_path = './' + song_id + ".srt"
output_text_file_path = './' + song_id + ".txt"
extract_lyrics_from_srt(srt_file_path, output_text_file_path)
