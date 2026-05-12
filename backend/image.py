import requests
from utils.schema import SharedState
from dotenv import load_dotenv
import os
from pathlib import Path
import uuid
load_dotenv()

CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY")
CLOUDFLARE_WORKER_URL = os.getenv("CLOUDFLARE_WORKER_URL")
IMAGES_DIR = Path(__file__).resolve().parents[1] / "images"


def _image_extension(content_type: str, response_content: bytes) -> str:
    if content_type.startswith("image/"):
        subtype = content_type.split("/", 1)[1].split(";", 1)[0].strip().lower()
        if subtype in {"jpeg", "jpg"}:
            return ".jpg"
        if subtype in {"png", "gif", "webp", "bmp", "tiff"}:
            return f".{subtype}"

    if response_content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if response_content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if response_content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"

    return ".img"

def generate_image(state: SharedState) -> SharedState:

    if state.prepared_prompts is None:
        raise ValueError("Error accessing prepared prompts:")

    prompt = state.prepared_prompts

    url = CLOUDFLARE_WORKER_URL

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt
    }

    response = requests.post(url, headers=headers, json=payload)

    print(response.status_code)
    content_type = response.headers.get("content-type", "")
    is_image = content_type.startswith("image/") or response.content.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a"))
    is_html = content_type.startswith("text/html") or "html" in content_type

    print(content_type)
    print(response.text[:200])

    if response.ok:
        print(f"Request successful: {response.status_code}")
        print(f"Response content type: {content_type}")
        print(f"Response bytes: {len(response.content)}")

    print(f"Response contains image: {'yes' if is_image else 'no'}")
    print(f"Response contains html: {'yes' if is_html else 'no'}")

    image_path = None

    if is_image:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        image_filename = f"generated_{uuid.uuid4().hex}{_image_extension(content_type, response.content)}"
        image_path = IMAGES_DIR / image_filename

        with open(image_path, "wb") as f:
            f.write(response.content)

        print(f"Image saved as {image_path}")
    elif is_html:
        with open("response.html", "wb") as f:
            f.write(response.content)

        print("HTML saved as response.html")
    else:
        print("Response did not contain an image or html, so nothing was saved.")

    state.generated_image_path = str(image_path) if image_path else None
    return state

