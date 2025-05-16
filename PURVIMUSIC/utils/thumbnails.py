import asyncio
import os
import re
from io import BytesIO
import aiofiles.os
import httpx
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from aiofiles.os import path as aiopath
from youtubesearchpython.__future__ import VideosSearch

from PURVIMUSIC import LOGGER

# Load fonts with error handling
def load_fonts():
    """
    Loads font files with fallback to default fonts if loading fails.
    """
    try:
        return {
            "cfont": ImageFont.truetype("PURVIMUSIC/assets/cfont.ttf", 24),  # Channel/artist font, reduced size
            "tfont": ImageFont.truetype("PURVIMUSIC/assets/font.ttf", 30),   # Title font, reduced size
        }
    except Exception as e:
        LOGGER.error("Font loading error: %s, using default fonts", e)
        return {
            "cfont": ImageFont.load_default(),
            "tfont": ImageFont.load_default(),
        }

FONTS = load_fonts()

# Fallback image path and YouTube default thumbnail
FALLBACK_IMAGE_PATH = "PURVIMUSIC/assets/controller.png"
YOUTUBE_IMG_URL = "https://i.ytimg.com/vi/default.jpg"

async def resize_youtube_thumbnail(img: Image.Image) -> Image.Image:
    """
    Resize a YouTube thumbnail to 1280x720, preserving aspect ratio and cropping if needed.
    """
    target_width, target_height = 1280, 720
    aspect_ratio = img.width / img.height
    target_ratio = target_width / target_height

    if aspect_ratio > target_ratio:
        new_height = target_height
        new_width = int(new_height * aspect_ratio)
    else:
        new_width = target_width
        new_height = int(new_width / aspect_ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    img = img.crop((left, top, right, bottom))
    enhanced = ImageEnhance.Sharpness(img).enhance(1.5)
    img.close()
    return enhanced

async def fetch_image(url: str) -> Image.Image:
    """
    Fetches an image from a URL and resizes it for YouTube thumbnails.
    Falls back to a placeholder image if fetching fails.
    """
    async with httpx.AsyncClient() as client:
        try:
            if not url:
                raise ValueError("No thumbnail URL provided")
            response = await client.get(url, timeout=5)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            if url.startswith("https://i.ytimg.com"):
                img = await resize_youtube_thumbnail(img)
            else:
                img.close()
                img = Image.new("RGBA", (1280, 720), (255, 255, 255, 255))
            return img
        except Exception as e:
            LOGGER.error("Image loading error for URL %s: %s", url, e)
            try:
                response = await client.get(YOUTUBE_IMG_URL, timeout=5)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                img = await resize_youtube_thumbnail(img)
                return img
            except Exception as e:
                LOGGER.error("YouTube fallback image error: %s", e)
                try:
                    async with aiofiles.open(FALLBACK_IMAGE_PATH, mode="rb") as f:
                        img = Image.open(BytesIO(await f.read())).convert("RGBA")
                    img = await resize_youtube_thumbnail(img)
                    return img
                except Exception as e:
                    LOGGER.error("Local fallback image error: %s", e)
                    return Image.new("RGBA", (1280, 720), (255, 255, 255, 255))

def clean_text(text: str, limit: int = 25) -> str:
    """
    Sanitizes and truncates text to fit within the limit.
    """
    if not text:
        return "Unknown"
    text = text.strip()
    return f"{text[:limit - 3]}..." if len(text) > limit else text

async def add_controls(img: Image.Image) -> Image.Image:
    """
    Adds a subtle blurred background and enhanced playback controls overlay in the transparent UI, centered.
    """
    # Apply a light Gaussian blur to the background
    img = img.filter(ImageFilter.GaussianBlur(radius=10))
    box = (305, 125, 975, 595)  # 670x470 UI player, centered horizontally and vertically

    region = img.crop(box)
    try:
        # Load and enhance controls.png
        controls = Image.open("PURVIMUSIC/assets/controls.png").convert("RGBA")
        
        # Upscale to 1200x320 for better quality (2x target size)
        controls = controls.resize((1200, 320), Image.Resampling.LANCZOS)
        
        # Apply sharpening
        controls = ImageEnhance.Sharpness(controls).enhance(2.0)
        
        # Enhance contrast for better visibility
        controls = ImageEnhance.Contrast(controls).enhance(1.3)
        
        # Resize to final size (600x160) with high-quality resampling
        controls = controls.resize((600, 160), Image.Resampling.LANCZOS)
        
        controls_x = 305 + (670 - 600) // 2  # Center horizontally: (670-600)/2 + 305 = 335
        controls_y = 415  # Positioned at y=415 as per original
    except Exception as e:
        LOGGER.error("Controls image loading error: %s", e)
        # Fallback to a blank transparent image
        controls = Image.new("RGBA", (600, 160), (0, 0, 0, 0))
        controls_x, controls_y = 335, 415

    # Create a darker region for the UI background
    dark_region = ImageEnhance.Brightness(region).enhance(0.4)
    mask = Image.new("L", dark_region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, box[2] - box[0], box[3] - box[1]), radius=20, fill=255
    )

    # Paste the darkened region and controls
    img.paste(dark_region, box, mask)
    img.paste(controls, (controls_x, controls_y), controls)
    
    # Clean up
    region.close()
    controls.close()
    return img

def make_rounded_rectangle(image: Image.Image, size: tuple = (184, 184)) -> Image.Image:
    """
    Crops an image into a rounded rectangle (184x184 for new layout).
    """
    width, height = image.size
    side_length = min(width, height)
    crop = image.crop(
        (
            (width - side_length) // 2,
            (height - side_length) // 2,
            (width + side_length) // 2,
            (height + side_length) // 2,
        )
    )
    resize = crop.resize(size, Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *size), radius=20, fill=255)

    rounded = ImageOps.fit(resize, size)
    rounded.putalpha(mask)
    crop.close()
    resize.close()
    return rounded

async def get_thumb(videoid: str) -> str:
    """
    Generates and saves a high-quality YouTube thumbnail (1280x720) with centered UI layout.
    """
    # Validate videoid
    if not videoid or not re.match(r"^[a-zA-Z0-9_-]{11}$", videoid):
        LOGGER.error("Invalid YouTube video ID: %s", videoid)
        return ""

    save_dir = f"database/photos/{videoid}.png"

    # Create directory if it doesn't exist
    try:
        save_dir_parent = "database/photos"
        if not await aiopath.exists(save_dir_parent):
            await asyncio.to_thread(os.makedirs, save_dir_parent)
    except Exception as e:
        LOGGER.error("Failed to create directory %s: %s", save_dir_parent, e)
        return ""

    # Fetch YouTube metadata
    try:
        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        result = (await results.next())["result"][0]
        title = clean_text(result.get("title", "Unknown Title"), limit=25)
        artist = clean_text(result.get("channel", {}).get("name", "Unknown Artist"), limit=28)
        thumbnail_url = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
    except Exception as e:
        LOGGER.error("YouTube metadata fetch error for video %s: %s", videoid, e)
        title, artist = "Unknown Title", "Unknown Artist"
        thumbnail_url = YOUTUBE_IMG_URL

    # Process thumbnail
    thumb = await fetch_image(thumbnail_url)
    bg = await add_controls(thumb)
    image = make_rounded_rectangle(thumb, size=(184, 184))

    # Paste rounded thumbnail inside the transparent UI (top-left, slightly down)
    paste_x, paste_y = 325, 155  # y=125+30 padding
    bg.paste(image, (paste_x, paste_y), image)

    # Draw text inside the transparent UI, aligned vertically to the right of the thumbnail
    draw = ImageDraw.Draw(bg)
    draw.text((540, 155), title, (255, 255, 255), font=FONTS["tfont"])  # Title, aligned with thumbnail
    draw.text((540, 200), artist, (255, 255, 255), font=FONTS["cfont"])  # Artist, below title

    # Enhance image quality
    bg = ImageEnhance.Contrast(bg).enhance(1.1)
    bg = ImageEnhance.Color(bg).enhance(1.2)

    # Save thumbnail
    try:
        await asyncio.to_thread(bg.save, save_dir, format="PNG", quality=95, optimize=True)
        if await aiopath.exists(save_dir):
            thumb.close()
            image.close()
            bg.close()
            return save_dir
        LOGGER.error("Failed to save thumbnail at %s", save_dir)
    except Exception as e:
        LOGGER.error("Thumbnail save error for %s: %s", save_dir, e)

    thumb.close()
    image.close()
    bg.close()
    return ""

# Copyright (c) 2025 AshokShau & TgMusicBot Contributors
# Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
