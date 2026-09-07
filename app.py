"""
خدمة إنتاج فيديوهات كرتونية للأطفال - تُستدعى مرة واحدة من Make عبر webhook
وترجع رابط تحميل الفيديو النهائي (جاهز لرفعه على Google Drive من Make).

الخط: Gemini (سكربت) -> Pollinations.ai (صور كرتونية) -> edge-tts (تعليق صوتي عربي)
      -> ffmpeg (تحريك الصور + دمج الصوت والموسيقى) -> ملف mp4 نهائي
"""

import os
import json
import uuid
import shutil
import asyncio
import subprocess
import urllib.parse
import urllib.request

from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
ARABIC_VOICE = os.environ.get("ARABIC_VOICE", "ar-EG-SalmaNeural")
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
WORK_ROOT = "/tmp/kids_video_jobs"
BG_MUSIC_PATH = os.path.join(os.path.dirname(__file__), "assets", "bg_music.mp3")

os.makedirs(WORK_ROOT, exist_ok=True)


def generate_script(topic_hint: str | None = None) -> dict:
    prompt = f"""
أنت كاتب قصص أطفال محترف. اكتب قصة قصيرة جدًا ومناسبة تمامًا للأطفال (بدون أي عنف أو خوف حقيقي)،
بلغة عربية بسيطة وواضحة (ليست فصحى ثقيلة، لكن ليست عامية محلية ضيقة - لغة وسطى يفهمها كل طفل عربي).
مدة الفيديو النهائي حوالي 40-55 ثانية، لذلك اجعل القصة مكوّنة من 5 إلى 6 مشاهد فقط، كل مشهد جملة أو جملتين قصيرتين.
{"الموضوع المقترح: " + topic_hint if topic_hint else "اختر موضوعًا تعليميًا أو أخلاقيًا لطيفًا بنفسك (صداقة، مشاركة، شجاعة، حب الطبيعة...)."}

أعد النتيجة بصيغة JSON فقط، بدون أي نص إضافي قبله أو بعده، وبالضبط بهذا الشكل:
{{
  "title": "عنوان قصير جذاب",
  "scenes": [
    {{
      "narration": "جملة السرد بالعربية لهذا المشهد",
      "image_prompt": "English description of a cute cartoon scene for kids, describing characters, colors, setting - no text in image"
    }}
  ]
}}
""".strip()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/mod
