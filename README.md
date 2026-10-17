# ⚡ CBX-Stream Universal Social Media Downloader Backend

> **Production-Grade, High-Performance Media Streaming, DASH Transcoding & Universal Social Downloader Engine**  
> Built with **FastAPI**, **yt-dlp**, **gallery-dl**, **FFmpeg**, **Mutagen**, and **WebSockets**.  
> Specially crafted to integrate seamlessly with `CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Frontend`.

---

## 🌟 Key Features

- **Deep Metadata & Multi-Tier Format Extraction**:
  - Automatically analyzes URLs from **YouTube (including 4K, 8K, 60fps, Shorts)**, **TikTok (No-Watermark HD)**, **Instagram (Reels, Posts, Stories, Multi-Photo Carousels)**, **Facebook (Watch, Reels)**, **Twitter/X**, **Reddit**, **Pinterest**, **SoundCloud**, **Vimeo**, **Twitch**, and 1,000+ streaming websites.
  - Groups raw formats into categorized tiers: `4K Ultra HD`, `2K Quad HD`, `1080p Full HD`, `720p HD`, and `HQ Audio (320kbps MP3 / M4A / FLAC)`.
  
- **Chameleon Glass UI Color Palette Generation**:
  - Automatically identifies the host platform and injects modern **Chameleon Glass UI tokens** (primary color, secondary color, accent color, backdrop blur gradient, and glowing shadows) into the API response for instant frontend styling.

- **Non-Blocking Async Architecture**:
  - All heavy extraction, downloading, and FFmpeg operations run in `asyncio.to_thread` or non-blocking async subprocesses (`asyncio.create_subprocess_exec`). The FastAPI event loop stays 100% responsive.

- **4K DASH Video + Audio Stream Merger**:
  - High-resolution adaptive DASH streams (such as YouTube 4K/1080p video-only streams) are merged with pristine audio tracks via FFmpeg with zero quality degradation.

- **Precision Timestamp Trimming**:
  - Keyframe-accurate clipping using `-ss` and `-to` timestamp parameters directly from a URL or an already downloaded file.

- **High-Fidelity Audio Transcoding & ID3 Cover Art Embedding**:
  - Extracts and converts media to MP3 (up to 320kbps), M4A, FLAC, WAV, and Opus.
  - Automatically embeds ID3v2 metadata (artist, title, album) and high-resolution cover art into audio files using Mutagen.

- **Multi-Photo/Video Carousel ZIP Bundler**:
  - Extracts Instagram carousels, Pinterest boards, and Reddit albums.
  - Concurrently downloads all slides and packages them into a clean `.zip` archive on the fly.

- **Reverse Media Proxy (CORS Bypass)**:
  - Streams hotlink-protected or CORS-restricted CDN media (Instagram/TikTok CDNs) directly through the backend.

- **Real-Time WebSocket Progress Hooks**:
  - Real-time download percentage, download speed (MB/s), downloaded bytes, total bytes, and ETA are broadcasted via WebSockets (`/ws/progress/{task_id}`).
  - Built-in event state caching guarantees clients receive the latest state even upon reconnecting.

- **Automated TTL Garbage Collector**:
  - Background async service automatically purges completed media files and temporary working folders older than 1 hour.

---

## 🏗️ Architecture & Modular Structure

```text
CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI entry point, CORS, Lifespan, Global Exception Handlers
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # BaseSettings: temp_dir, max_concurrent_tasks, cleanup_ttl_seconds
│   │   ├── exceptions.py            # Custom exceptions (MediaExtractionError, FFmpegProcessError, etc.)
│   │   └── logger.py                # Structured console & rotating file logger
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── media_schemas.py         # All Pydantic v2 Request & Response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── extractor_service.py     # yt-dlp + gallery-dl deep metadata & format analyzer
│   │   ├── downloader_service.py    # Async media downloader with WebSocket progress hooks
│   │   ├── ffmpeg_service.py        # 4K DASH merger, precision timestamp trimmer, MP3 ID3 cover art embedder
│   │   ├── carousel_service.py      # Multi-photo/video gallery extractor & async ZIP bundler
│   │   ├── batch_service.py         # Concurrent playlist & multi-link queue analyzer
│   │   ├── ws_manager.py            # Real-time WebSocket connection & task state broadcaster
│   │   └── cleanup_service.py       # Background worker to purge expired files in temp_downloads/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py                # Master APIRouter aggregating all v1 routes
│   │   ├── routes_analyze.py        # POST /api/v1/analyze & POST /api/v1/batch-analyze
│   │   ├── routes_download.py       # POST /api/v1/download & GET /api/v1/stream/{task_id}
│   │   ├── routes_trim.py           # POST /api/v1/trim
│   │   ├── routes_carousel.py       # POST /api/v1/carousel/zip & GET /api/v1/proxy-media
│   │   ├── routes_system.py         # GET /api/v1/health
│   │   └── routes_ws.py             # WS /ws/progress/{task_id}
│   └── utils/
│       ├── __init__.py
│       ├── platform_detector.py     # URL regex matcher + Chameleon Glass UI color palette generator
│       ├── format_parser.py         # Cleans and groups raw yt-dlp formats into 4K/2K/1080p/720p/Audio
│       └── file_helpers.py          # Safe filename sanitizer, timestamp parser & byte formatter
├── temp_downloads/                  # Auto-created temporary directory for active media jobs
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.11+** installed
- **FFmpeg** installed (System PATH, or auto-resolved via bundled `imageio-ffmpeg`)

### 2. Installation
Clone the repository and install dependencies:
```bash
# Clone the repository
git clone https://github.com/your-username/CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend.git
cd CBX-Stream-All-In-One-Universal-Social-Media-Downloader-Backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Run Locally
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation will be available at:  
👉 **http://localhost:8000/docs**

---

## 🐳 Docker Deployment

Run with Docker Compose:
```bash
docker compose up -d --build
```
Or build and run the Docker container directly:
```bash
docker build -t cbx-stream-backend .
docker run -d -p 8000:8000 --name cbx-stream-backend cbx-stream-backend
```

---

## 📡 REST API Reference

### 1. Analyze Media URL
**`POST /api/v1/analyze`**
Analyzes a social media link and returns metadata, video/audio formats, and Chameleon UI tokens.

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "extract_flat": false
}
```

**Response Example:**
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
    "icon": "youtube",
    "badge_text": "YouTube 4K Ultra HDR",
    "primary_color": "#FF0000",
    "secondary_color": "#CC0000",
    "accent_color": "#FF4D4D",
    "gradient_css": "linear-gradient(135deg, rgba(255, 0, 0, 0.85) 0%, rgba(180, 0, 0, 0.65) 100%)",
    "glass_border": "1px solid rgba(255, 0, 0, 0.35)",
    "glass_shadow": "0 8px 32px 0 rgba(255, 0, 0, 0.25)",
    "glow_color": "rgba(255, 0, 0, 0.5)",
    "text_color": "#FFFFFF"
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
      "quality_label": "Lossless / HQ Audio (128 kbps)",
      "filesize_formatted": "3.35 MB"
    }
  ],
  "is_carousel": false,
  "carousel_items": []
}
```

---

### 2. Initiate Download Task
**`POST /api/v1/download`**

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format_id": "137+bestaudio/best",
  "extract_audio": false,
  "audio_format": "mp3",
  "audio_quality": "320",
  "embed_metadata": true,
  "embed_thumbnail": true
}
```

**Response:**
```json
{
  "task_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "queued",
  "message": "Media download queued successfully.",
  "ws_url": "/ws/progress/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

---

### 3. Stream or Download Completed File
**`GET /api/v1/stream/{task_id}`**
- `?inline=true`: Serves for browser video/audio player preview.
- `?inline=false` (default): Triggers file attachment download with original filename.

---

### 4. Precision Media Trimmer
**`POST /api/v1/trim`**

**Request:**
```json
{
  "task_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "start_time": "00:15",
  "end_time": "01:05",
  "extract_audio": false
}
```

---

### 5. Multi-Item Carousel ZIP Bundler
**`POST /api/v1/carousel/zip`**

**Request:**
```json
{
  "media_urls": [
    "https://example.com/slide1.jpg",
    "https://example.com/slide2.mp4"
  ],
  "custom_filename": "instagram_holiday_reel"
}
```

---

### 6. Reverse Media Proxy (CORS Bypass)
**`GET /api/v1/proxy-media?url=<remote_url>`**
Streams remote media through the backend to circumvent CORS restrictions and referer blockers.

---

### 7. System Health & Hardware Diagnostics
**`GET /api/v1/health`**

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 1245.5,
  "active_tasks": 0,
  "disk_free_gb": 128.45,
  "disk_total_gb": 476.21,
  "ffmpeg_available": true,
  "ffmpeg_path": "ffmpeg",
  "python_version": "3.11.9"
}
```

---

## ⚡ Real-Time WebSocket Progress Protocol

Connect to the WebSocket at:  
`ws://localhost:8000/ws/progress/{task_id}`

### Progress Event Payload Example:
```json
{
  "task_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "downloading",
  "progress_percent": 68.4,
  "downloaded_bytes": 14200000,
  "total_bytes": 20760000,
  "downloaded_formatted": "13.54 MB",
  "total_formatted": "19.80 MB",
  "speed": "4.20 MB/s",
  "eta": "00:02",
  "filename": null,
  "stream_url": null,
  "error": null
}
```

When completed:
```json
{
  "task_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "completed",
  "progress_percent": 100.0,
  "downloaded_bytes": 20760000,
  "total_bytes": 20760000,
  "downloaded_formatted": "19.80 MB",
  "total_formatted": "19.80 MB",
  "filename": "Rick_Astley_Never_Gonna_Give_You_Up.mp4",
  "stream_url": "/api/v1/stream/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

---

## 🛡️ License
Released under the MIT License. Developed for seamless integration with the CBX-Stream frontend ecosystem.
