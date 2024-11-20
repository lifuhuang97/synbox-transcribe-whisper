<p align="center">
  <a href="https://synbox.io" target="_blank">
    <img src="logos/Synbox.svg" alt="Synbox Logo" width="340px" />
  </a>
</p>
<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-Personal_Use-red" alt="License Badge" />
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat-square" alt="Version Badge" />
  </a>
</p>
<p align="center">
  Backend service for Synbox - AI-powered Japanese lyrics transcription and translation platform.
  View the <a href="https://github.com/lifuhh/synbox">frontend repository</a> here
  <br/>
  <br />
  <a href="https://synbox.io"><strong>Visit Website »</strong></a>
  <br />
  <br />
  <a href="https://github.com/lifuhh/synbox-backend">Explore the Docs</a> · 
  <a href="https://github.com/lifuhh/synbox-backend/issues">Report Bug</a> · 
  <a href="https://github.com/lifuhh/synbox-backend/issues">Request Feature</a>
</p>


## Architecture Overview

The Synbox backend is built with Python Flask, providing a robust and scalable service architecture for handling complex AI operations and media processing. It's designed to efficiently process Japanese song lyrics through multiple stages of AI analysis while maintaining high performance and reliability.

### System Design
- **Optimized Web Server**: Gunicorn with thread-based workers optimized for cold starts
- **Streaming Architecture**: Real-time progress updates using Flask's streaming capabilities
- **Efficient Caching**: Two-layer caching with Appwrite for processed content
- **Containerized Deployment**: Docker-based deployment with ffmpeg support
- **Error Recovery**: Comprehensive error handling with automatic retries
- **Rate Management**: Intelligent API request management and quota handling

## Core Technologies

| Technology | Purpose | Description |
|------------|---------|-------------|
| **Flask** | Web Framework | High-performance WSGI web application framework |
| **Gunicorn** | WSGI Server | Production-grade server with thread-based workers |
| **OpenAI API** | AI Processing | Powers Whisper and GPT-4 based processing |
| **Appwrite SDK** | Storage | Cloud storage and caching implementation |
| **FFmpeg** | Media Handling | Audio extraction and processing |

## Key Features

### Video Processing & Validation
- Intelligent YouTube content validation
- Automated Japanese content detection
- Multi-format subtitle support (VTT, SRT, ASS, SSA)
- Smart caching system for processed content

### Transcription Engine
- OpenAI Whisper-based transcription
- Multiple subtitle format support
- Intelligent timing synchronization
- Auto-correction and formatting

### AI Translation & Annotation
- Context-aware translation system
- Parallel processing capabilities
- Streaming progress updates
- Automatic error recovery

## Core Components

### Appwrite
- Manages storage and caching of song info and generated outputs
- Ensures fast retrieval of previously processed songs
- Handles secure file uploads and downloads
- Provides robust backup and recovery mechanisms

### OpenAI
- Powers the AI transcription feature using Whisper
- Handles translations using GPT-4o's ability to understand context and nuance
- Processes Japanese text analysis for accurate annotations
- Delivers real-time updates during processing

### Formatter
- Converts Japanese lyrics to romaji for easier reading
- Adds furigana annotations to help with kanji pronunciation
- Maintains proper spacing and line breaks for readability

## **Contacts**

Feel free to reach out for feedback, issues, or contributions:

**Lifu**: [LinkedIn](https://www.linkedin.com/in/lifuhh)
**GitHub Issues**: [Report issues](https://github.com/lifuhh/synbox/issues)

## **License**

This project is licensed under a **Personal Use License**.  
You may view and explore the codebase for personal learning purposes. Redistribution, modification, or commercial use is prohibited without explicit permission from the author.