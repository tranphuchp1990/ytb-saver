from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import re

app = FastAPI(title="YouTube HD Downloader API")

# Cho phép Blogspot (và mọi website) gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Hoặc chỉ định domain Blogspot của bạn
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    url: str
    quality: str = "1080"   # "720", "1080", hoặc "highest"

class DownloadResponse(BaseModel):
    success: bool
    title: str
    download_url: str
    quality: str
    duration: int | None = None
    filesize: str | None = None

def clean_filename(title: str) -> str:
    # Làm sạch tên file
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title[:150]  # Giới hạn độ dài

@app.post("/download", response_model=DownloadResponse)
async def get_download_link(request: DownloadRequest):
    if not request.url or ("youtube.com" not in request.url and "youtu.be" not in request.url):
        raise HTTPException(status_code=400, detail="Vui lòng nhập link YouTube hợp lệ")

    try:
        # Cấu hình yt-dlp - chỉ lấy thông tin, không tải
        ydl_opts = {
            'format': f'bestvideo[height<={request.quality}]+bestaudio/best[height<={request.quality}]' 
                      if request.quality != "highest" 
                      else 'bestvideo+bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)

            title = info.get('title', 'video')
            safe_title = clean_filename(title)
            duration = info.get('duration')

            # Lấy direct download link tốt nhất
            direct_url = None

            # Ưu tiên format đã merge sẵn (mp4)
            if info.get('url') and info.get('ext') in ['mp4', 'mkv', 'webm']:
                direct_url = info['url']
            else:
                # Tìm format tốt nhất có cả video + audio
                formats = info.get('formats', [])
                for f in reversed(formats):  # Ưu tiên chất lượng cao
                    if (f.get('vcodec') != 'none' and 
                        f.get('acodec') != 'none' and 
                        f.get('url')):
                        direct_url = f['url']
                        break

            if not direct_url:
                raise HTTPException(status_code=503, detail="Không lấy được link tải. Video có thể bị hạn chế.")

            # Ước lượng kích thước (nếu có)
            filesize = None
            if info.get('filesize_approx'):
                filesize = f"{info['filesize_approx'] / (1024*1024):.1f} MB"

            return DownloadResponse(
                success=True,
                title=f"{safe_title}.mp4",
                download_url=direct_url,
                quality=f"{request.quality}p" if request.quality != "highest" else "Highest",
                duration=duration,
                filesize=filesize
            )

    except Exception as e:
        error_msg = str(e)
        if "Sign in" in error_msg or "login" in error_msg.lower():
            error_msg = "Video yêu cầu đăng nhập (age-restricted hoặc private)."
        raise HTTPException(status_code=500, detail=f"Lỗi: {error_msg}")

# Route test đơn giản
@app.get("/")
async def root():
    return {"message": "YouTube HD Downloader API đang chạy! POST /download để sử dụng."}