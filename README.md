<p align="center">
  <img src="assets/banner.png" alt="CBX-Stream Universal Social Media Downloader" width="100%" />
</p>

<p align="center">
  <img src="assets/logo.png" alt="CBX-Stream Emblem Logo" width="110" />
</p>

<p align="center">
  <a href="https://github.com/chathunga2007/CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend/stargazers"><img src="https://img.shields.io/github/stars/chathunga2007/CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend?color=6366f1&style=for-the-badge&logo=github" alt="Stars" /></a>
  <a href="https://github.com/chathunga2007/CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend/network/members"><img src="https://img.shields.io/github/forks/chathunga2007/CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend?color=ec4899&style=for-the-badge&logo=github" alt="Forks" /></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" /></a>
  <a href="https://ffmpeg.org/"><img src="https://img.shields.io/badge/FFmpeg-7.1-007808?style=for-the-badge&logo=ffmpeg&logoColor=white" alt="FFmpeg" /></a>
  <a href="https://fly.io/"><img src="https://img.shields.io/badge/Fly.io-Live-24185b?style=for-the-badge&logo=flydotio&logoColor=white" alt="Fly.io" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License: MIT" /></a>
</p>

---

# ⚡ CBX-Stream Universal Social Media Downloader Backend

> **Production-Grade, High-Performance Media Streaming, DASH Transcoding & Universal Social Downloader Engine**  
> Built with **FastAPI**, **yt-dlp**, **gallery-dl**, **FFmpeg**, **curl-cffi**, **bgutil PO-Token Server**, **Mutagen**, and **WebSockets**.  
> Specially crafted to integrate seamlessly with the Chameleon Glass UI frontend.

---

## 🌟 Key Features

### 🎬 Universal Media Extraction (1,000+ Platforms)
- **YouTube (4K, 8K, 60fps HDR & Shorts)**: Bypasses modern YouTube botguard using our integrated Node.js challenge solver and local PO-Token daemon.
- **TikTok**: Lossless Full HD video extraction with watermarks completely removed.
- **Instagram**: High-resolution Reels, Video Posts, Stories, and multi-slide Carousels.
- **LinkedIn**: Full support for LinkedIn HD Posts, Feed Updates, and Videos.
- **Facebook**: Watch and Reels videos in 1080p Full HD.
- **X / Twitter**: Multi-tier video and GIF downloads up to 1080p.
- **Reddit, Pinterest, SoundCloud, Twitch, Vimeo, Bilibili**: Clean extraction with zero lossy compression.

### 🎨 Chameleon Glass UI Dynamic Theming
- Automatically identifies the host platform from the URL.
- Injects dynamic **Chameleon Glass design tokens** (`primary_color`, `secondary_color`, `accent_color`, `gradient_css`, `glass_border`, `glass_shadow`, and `glow_color`) directly into the JSON response for dynamic UI morphing.

### 🛡️ Automated YouTube Anti-Bot & PO Token Bypass
- Includes **`bgutil-ytdlp-pot-provider`** and a managed background Node.js PO Token generator server running on port `4416`.
- Solves YouTube InnerTube JavaScript challenges on the fly.
- Supports hot-dropping `cookies.txt` or injecting via secure environment secrets (`COOKIES_CONTENT`) without server restarts.

### 🚀 4K DASH Video + Audio Stream Merger
- Adaptive streaming formats (e.g. YouTube 4K/1080p video-only tracks) are merged with uncompressed audio tracks via high-speed FFmpeg pipes with zero generational quality loss.

### ✂️ Precision Timestamp Trimming
- Keyframe-accurate clipping using `-ss` and `-to` timestamp parameters directly from a stream or downloaded file.

### 🎵 High-Fidelity Audio Transcoding & Cover Art Embedding
- Converts audio to **320kbps MP3**, M4A, FLAC, WAV, and Opus.
- Automatically embeds ID3v2 metadata (Artist, Title, Album) and high-resolution thumbnail artwork into the audio file using Mutagen.

### 📦 Multi-Photo/Video Carousel ZIP Bundler
- Detects multi-image Instagram carousels, Pinterest boards, and Reddit albums.
- Concurrently downloads all items and bundles them into an in-memory `.zip` archive on the fly.

### 📡 Real-Time WebSocket Progress Hooks
- Broadcasts real-time download percentage, download speed (MB/s), downloaded bytes, total bytes, and ETA via WebSockets (`/api/v1/ws/{task_id}`).

### 🧹 Automated TTL Garbage Collector
- Background async daemon automatically purges completed media files and temporary working directories older than 1 hour.

---

## 🏗️ Architecture & Modular Structure

```text
CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI entry point, CORS, Lifespan, Global Exception Handlers
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # BaseSettings, FFmpeg resolution, env cookies & proxy config
│   │   ├── exceptions.py            # Custom exceptions (MediaExtractionError, FFmpegProcessError, etc.)
│   │   └── logger.py                # Structured console & rotating file logger
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── media_schemas.py         # Pydantic v2 Request & Response schemas with byte casting
│   ├── services/
│   │   ├── __init__.py
│   │   ├── extractor_service.py     # yt-dlp + gallery-dl deep metadata & format analyzer
│   │   ├── downloader_service.py    # Async media downloader with WebSocket progress hooks
│   │   ├── pot_service.py           # Background PO Token daemon lifecycle manager (Port 4416)
│   │   ├── ffmpeg_service.py        # 4K DASH merger, precision trimmer & MP3 ID3 embedder
│   │   ├── carousel_service.py      # Multi-photo/video gallery extractor & async ZIP bundler
│   │   ├── batch_service.py         # Concurrent playlist & multi-link queue analyzer
│   │   ├── ws_manager.py            # Real-time WebSocket connection & task state broadcaster
│   │   └── cleanup_service.py       # Background worker purging expired files in temp_downloads/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py                # Master APIRouter aggregating all v1 routes
│   │   ├── routes_analyze.py        # POST /api/v1/analyze & POST /api/v1/batch-analyze
│   │   ├── routes_download.py       # POST /api/v1/download & GET /api/v1/stream/{task_id}
│   │   ├── routes_trim.py           # POST /api/v1/trim
│   │   ├── routes_carousel.py       # POST /api/v1/carousel/zip & GET /api/v1/proxy-media
│   │   ├── routes_system.py         # GET /api/v1/health
│   │   └── routes_ws.py             # WS /api/v1/ws/{task_id}
│   └── utils/
│       ├── __init__.py
│       ├── platform_detector.py     # Platform regex matcher & Chameleon Glass theme generator
│       ├── format_parser.py         # Groups raw formats into 4K/2K/1080p/720p/Audio tiers
│       └── file_helpers.py          # Safe filename sanitizer, timestamp parser & byte formatter
├── assets/
│   └── banner.png                   # High-resolution splash banner
├── temp_downloads/                  # Auto-created temporary storage for active media jobs
├── requirements.txt
├── .env.example
├── Dockerfile                       # Multi-stage production Dockerfile with Node.js & POT server
├── fly.toml                         # Fly.io cloud deployment specification
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.11+** installed
- **Node.js 18+** installed (for YouTube JavaScript challenge solver)
- **FFmpeg 7.0+** installed (or auto-resolved via bundled `imageio-ffmpeg`)

### 2. Local Installation
```bash
# Clone the repository
git clone https://github.com/chathunga2007/CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend.git
cd CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend

# Create and activate virtual environment
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Run the Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation will be available at:  
👉 **http://localhost:8000/docs**

---

## ☁️ Cloud Deployment (Fly.io)

This backend is pre-configured for **Fly.io** with 1GB RAM, Singapore (`sin`) region, and automatic scaling.

```bash
# 1. Install Fly CLI (Windows PowerShell)
iwr https://fly.io/install.ps1 -useb | iex

# 2. Login to Fly.io
fly auth login

# 3. Launch and deploy
fly launch

# 4. (Optional) Inject YouTube cookies securely without pushing to Git
fly secrets set COOKIES_CONTENT="$(Get-Content cookies.txt -Raw)"
```

Live Production Endpoint:  
👉 **https://cbx-stream-backend.fly.dev**

---

## 📡 REST API Reference

### 1. Analyze Media URL
**`POST /api/v1/analyze`**

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "extract_flat": false
}
```

**Response:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "uploader": "Rick Astley",
  "duration": 213,
  "duration_formatted": "03:33",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "platform": {
    "id": "youtube",
    "name": "YouTube",
    "badge_text": "YouTube 4K Ultra HDR",
    "primary_color": "#FF0000",
    "secondary_color": "#CC0000",
    "accent_color": "#FF4D4D",
    "gradient_css": "linear-gradient(135deg, rgba(255, 0, 0, 0.85) 0%, rgba(180, 0, 0, 0.65) 100%)"
  },
  "video_formats": [
    {
      "format_id": "137+bestaudio/best",
      "ext": "mp4",
      "resolution": "1920x1080",
      "quality_label": "1080p Full HD",
      "height": 1080,
      "fps": 30,
      "filesize_formatted": "42.50 MB"
    }
  ],
  "audio_formats": [
    {
      "format_id": "140",
      "ext": "m4a",
      "resolution": "Audio Only",
      "quality_label": "HQ Audio (128k)",
      "filesize_formatted": "3.40 MB"
    }
  ]
}
```

### 2. Start Media Download
**`POST /api/v1/download`**

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format_id": "137+bestaudio/best",
  "extract_audio": false
}
```

**Response:**
```json
{
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "queued",
  "progress_percent": 0.0,
  "ws_url": "/api/v1/ws/3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "message": "Download task queued successfully."
}
```

### 3. Stream Completed File
**`GET /api/v1/stream/{task_id}`**  
Streams the completed media directly to the browser with `Content-Disposition: attachment` headers.

### 4. Health Check
**`GET /api/v1/health`**  
Returns server uptime, active tasks, disk space, and FFmpeg readiness.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

<p align="center">
  Crafted with ❤️ by <b>Chathunga Bimsara</b> for high-performance media archiving.
</p>
