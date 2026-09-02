from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/images/icon.png"

TARGETS = {
    ROOT / "assets/images/icon.png": 512,
    ROOT / "assets/images/splash-icon.png": 512,
    ROOT / "assets/images/favicon.png": 192,
    ROOT / "assets/images/android-icon-foreground.png": 512,
    ROOT / "browser-extension/icons/icon.png": 256,
}

with Image.open(SOURCE) as raw:
    base = raw.convert("RGBA")
    for path, size in TARGETS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        image = base.resize((size, size), Image.Resampling.LANCZOS)
        image.save(path, "PNG", optimize=True, compress_level=9)
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size} bytes")
