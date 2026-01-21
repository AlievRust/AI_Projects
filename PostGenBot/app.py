import os
import io
import time
import uuid
import base64
from typing import Dict, Any, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from PIL import Image, ImageDraw, ImageFont

# Новый SDK OpenAI (openai>=1.x)
from openai import OpenAI


# ---------------------------
# Config
# ---------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")  # <-- добавляем

# TTL на хранение картинок в памяти (секунды)
IMAGE_TTL_SECONDS = int(os.getenv("IMAGE_TTL_SECONDS", "1800"))  # 30 минут по умолчанию

# Шрифт с кириллицей. На большинстве Linux образов есть DejaVuSans.
DEFAULT_FONT_PATHS = [
    os.getenv("FONT_PATH", "").strip(),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

def pick_font_path() -> Optional[str]:
    for p in DEFAULT_FONT_PATHS:
        if p and os.path.exists(p):
            return p
    return None


if not OPENAI_API_KEY or not CURRENTS_API_KEY or not STABILITY_API_KEY:
    raise ValueError("Нужны переменные окружения: OPENAI_API_KEY, CURRENTS_API_KEY, STABILITY_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Post+Image Generator API")

# Простейшее in-memory хранилище для картинок
# image_id -> {"bytes": b"...", "created_at": float, "content_type": "image/jpeg"}
IMAGE_STORE: Dict[str, Dict[str, Any]] = {}


# ---------------------------
# Models
# ---------------------------
class Topic(BaseModel):
    topic: str


# ---------------------------
# Helpers: cleanup
# ---------------------------
def cleanup_images() -> None:
    """Удаляем протухшие картинки из памяти."""
    now = time.time()
    expired = [k for k, v in IMAGE_STORE.items() if now - v["created_at"] > IMAGE_TTL_SECONDS]
    for k in expired:
        IMAGE_STORE.pop(k, None)


# ---------------------------
# News
# ---------------------------
def get_recent_news(topic: str) -> str:
    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "language": "en",
        "keywords": topic,
        "apiKey": CURRENTS_API_KEY,
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка CurrentsAPI: {r.text}")

    news_data = r.json().get("news", [])
    if not news_data:
        return "Свежих новостей не найдено."

    return "\n".join([article.get("title", "").strip() for article in news_data[:5] if article.get("title")])


# ---------------------------
# OpenAI: content generation
# ---------------------------
def oai_text(model: str, prompt: str, max_tokens: int, temperature: float = 0.7) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def generate_post_bundle(topic: str) -> Dict[str, str]:
    recent_news = get_recent_news(topic)

    title = oai_text(
        model="gpt-4o",
        max_tokens=80,
        temperature=0.5,
        prompt=(
            f"Придумай привлекательный и точный заголовок статьи на русском на тему: '{topic}'.\n"
            f"Учитывай актуальные новости:\n{recent_news}\n"
            f"Ответь только заголовком."
        ),
    )

    meta_description = oai_text(
        model="gpt-4o-mini",
        max_tokens=140,
        temperature=0.5,
        prompt=(
            f"Напиши мета-описание (на русском) для статьи с заголовком: '{title}'. "
            f"Должно быть информативно и включать ключевые слова. "
            f"Ответь одним абзацем."
        ),
    )

    post_content = oai_text(
        model="gpt-4o",
        max_tokens=1800,
        temperature=0.5,
        prompt=(
            f"Напиши подробную статью для поста в Telegram на тему '{topic}' на русском языке, "
            f"используя последние новости:\n{recent_news}\n\n"
            f"Требования:\n"
            f"1) Не менее 1500 символов\n"
            f"2) Чёткая структура с подзаголовками\n"
            f"3) Вступление, основная часть, заключение\n"
            f"4) Анализ текущих трендов + примеры из новостей\n"
            f"5) Каждый абзац 3-4 предложения\n"
            f"6) Используй форматирование HTML\n"
            f"Выдай только текст статьи."
        ),
    )

    image_prompt = oai_text(
        model="gpt-4o",
        max_tokens=250,
        temperature=0.8,
        prompt=(
            f"Подготовь промпт на английском языке для генерации изображения в Stability.ai "
            f"к посту по ключевым словам:\n{meta_description}\n\n"
            f"Требования: изображение должно отражать смысл, быть понятным, без текста на самой картинке. "
            f"Ответь только промптом."
        ),
    )

    image_overlay_text = oai_text(
        model="gpt-4o",
        max_tokens=80,
        temperature=0.8,
        prompt=(
            f"На основе ключевых слов:\n{meta_description}\n\n"
            f"и промпта для изображения:\n{image_prompt}\n\n"
            f"Сгенерируй вдохновляющую короткую фразу-цитату для оверлея на изображение. "
            f"До 20 слов, на русском, без кавычек."
        ),
    )

    return {
        "title": title,
        "meta_description": meta_description,
        "post_content": post_content,
        "image_prompt": image_prompt,
        "image_overlay_text": image_overlay_text,
    }


# ---------------------------
# Stability: image generation
# ---------------------------
def stability_generate_jpeg(prompt: str) -> bytes:
    url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
    headers = {
        "authorization": f"Bearer {STABILITY_API_KEY}",
        "accept": "image/*",
    }
    # "files={'none': ''}" — как у тебя в примере :contentReference[oaicite:5]{index=5}
    data = {
        "prompt": prompt,
        "output_format": "jpeg",
    }
    r = requests.post(url, headers=headers, files={"none": ""}, data=data, timeout=120)
    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise HTTPException(status_code=500, detail=f"Stability error: {detail}")
    return r.content


def crop_to_story_9_16(img: Image.Image) -> Image.Image:
    width, height = img.size
    target_aspect = 9 / 16
    current_aspect = width / height

    if current_aspect > target_aspect:
        new_width = int(height * target_aspect)
        left = (width - new_width) // 2
        right = left + new_width
        return img.crop((left, 0, right, height))
    elif current_aspect < target_aspect:
        new_height = int(width / target_aspect)
        top = (height - new_height) // 2
        bottom = top + new_height
        return img.crop((0, top, width, bottom))
    return img


def add_text_overlay(img: Image.Image, text: str) -> Image.Image:
    """
    Оверлей-плашка + текст. По мотивам твоего imagegen :contentReference[oaicite:6]{index=6},
    но безопаснее для продакшена (фонт-фоллбек, авторазметка, без хардкода Colab путей).
    """
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_path = pick_font_path()
    if not font_path:
        # Фоллбек: встроенный шрифт PIL может плохо поддерживать кириллицу,
        # но пусть сервис не падает.
        font = ImageFont.load_default()
        font_size = None
    else:
        # Размер шрифта под story-формат
        font_size = 52
        font = ImageFont.truetype(font_path, font_size)

    W, H = img.size
    margin_x = int(W * 0.08)
    margin_y = int(H * 0.08)
    max_width = W - 2 * margin_x

    # перенос строк
    words = text.split()
    lines = []
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        try:
            tw = draw.textlength(test, font=font)
        except Exception:
            tw = len(test) * 10  # грубый фоллбек
        if tw <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)

    # размеры блока
    ascent, descent = font.getmetrics() if hasattr(font, "getmetrics") else (18, 6)
    line_h = ascent + descent + 6
    block_h = line_h * len(lines)

    # позиция: верхняя часть, как в твоём примере (x=100, y=100) :contentReference[oaicite:7]{index=7}
    x = margin_x
    y = margin_y

    # ширина блока по самой длинной строке
    widths = []
    for ln in lines:
        try:
            widths.append(draw.textlength(ln, font=font))
        except Exception:
            widths.append(len(ln) * 10)
    block_w = int(max(widths) if widths else max_width)

    # плашка
    overlay = Image.new("RGBA", (block_w + 40, block_h + 30), (0, 0, 128, 180))
    img.paste(overlay, (x - 20, y - 15), mask=overlay)

    # текст
    ty = y
    for ln in lines:
        draw.text((x, ty), ln, font=font, fill=(255, 255, 255, 255))
        ty += line_h

    return img.convert("RGB")


def make_story_image(image_prompt: str, overlay_text: str) -> bytes:
    raw = stability_generate_jpeg(image_prompt)
    with Image.open(io.BytesIO(raw)) as im:
        im = crop_to_story_9_16(im)
        im = add_text_overlay(im, overlay_text)

        out = io.BytesIO()
        im.save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()


# ---------------------------
# API
# ---------------------------
@app.get("/")
async def root():
    return {"message": "Service is running"}

@app.get("/heartbeat")
async def heartbeat_api():
    return {"status": "OK"}


@app.post("/generate-post")
async def generate_post_api(topic: Topic):
    # сохранён твой endpoint :contentReference[oaicite:8]{index=8}
    return generate_post_bundle(topic.topic)


@app.post("/generate-post-with-image")
async def generate_post_with_image_api(topic: Topic):
    cleanup_images()

    bundle = generate_post_bundle(topic.topic)
    img_bytes = make_story_image(bundle["image_prompt"], bundle["image_overlay_text"])

    image_id = uuid.uuid4().hex
    IMAGE_STORE[image_id] = {
        "bytes": img_bytes,
        "created_at": time.time(),
        "content_type": "image/jpeg",
    }

    # Render обычно сидит за прокси, поэтому базовый URL удобнее передавать env-ом
    base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    image_url = f"{base_url}/image/{image_id}" if base_url else f"/image/{image_id}"

    return {
        **bundle,
        "image_id": image_id,
        "image_url": image_url,
        "image_expires_at": int(IMAGE_STORE[image_id]["created_at"] + IMAGE_TTL_SECONDS),
    }


@app.get("/image/{image_id}")
async def get_image(image_id: str):
    cleanup_images()
    item = IMAGE_STORE.get(image_id)
    if not item:
        raise HTTPException(status_code=404, detail="Image not found or expired")

    return Response(content=item["bytes"], media_type=item["content_type"])


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
