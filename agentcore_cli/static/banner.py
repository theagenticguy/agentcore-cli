from pathlib import Path

# Get the path to the banner.txt file relative to this module
_banner_path = Path(__file__).parent / "banner.txt"
banner_ascii = _banner_path.read_text(encoding="utf-8")
