"""List Edge TTS voices. Usage: uv run python scripts/list_edge_voices.py [locale_prefix]"""
import asyncio
import sys

import edge_tts


async def main() -> None:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "en-US"
    voices = await edge_tts.list_voices()
    filtered = [v for v in voices if v["Locale"].startswith(prefix)]
    for v in sorted(filtered, key=lambda x: x["ShortName"]):
        print(
            f"{v['ShortName']:32} {v.get('Gender', '?'):8} {v.get('FriendlyName', '')}"
        )
    print(f"\n{len(filtered)} voices matching {prefix!r}")


if __name__ == "__main__":
    asyncio.run(main())
