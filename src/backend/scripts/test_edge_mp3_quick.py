import asyncio

import edge_tts


async def main() -> None:
    c = edge_tts.Communicate("Hola", "es-MX-DaliaNeural")
    n = 0
    async for ch in c.stream():
        if ch["type"] == "audio":
            n += len(ch["data"])
    print("mp3", n, "head", end=" ")


asyncio.run(main())
