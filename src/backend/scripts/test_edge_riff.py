"""Quick check: Edge TTS riff-24khz-16bit-mono-pcm output."""
import asyncio

import aiohttp

from edge_tts.communicate import (
    WSS_URL,
    WSS_HEADERS,
    _SSL_CTX,
    connect_id,
    date_to_string,
    get_headers_and_data,
    mkssml,
    ssml_headers_plus_data,
)
from edge_tts.data_classes import TTSConfig
from edge_tts.constants import SEC_MS_GEC_VERSION
from edge_tts.drm import DRM

OUTPUT = "riff-24khz-16bit-mono-pcm"


async def main() -> None:
    cfg = TTSConfig("es-MX-DaliaNeural", "+0%", "+0%", "+0Hz", "SentenceBoundary")
    text = b"Hola"
    async with aiohttp.ClientSession() as session:
        url = (
            f"{WSS_URL}&ConnectionId={connect_id()}"
            f"&Sec-MS-GEC={DRM.generate_sec_ms_gec()}"
            f"&Sec-MS-GEC-Version={SEC_MS_GEC_VERSION}"
        )
        async with session.ws_connect(
            url,
            compress=15,
            headers=DRM.headers_with_muid(WSS_HEADERS),
            ssl=_SSL_CTX,
        ) as ws:
            await ws.send_str(
                f"X-Timestamp:{date_to_string()}\r\n"
                "Content-Type:application/json; charset=utf-8\r\n"
                "Path:speech.config\r\n\r\n"
                '{"context":{"synthesis":{"audio":{"metadataoptions":{'
                '"sentenceBoundaryEnabled":"true","wordBoundaryEnabled":"false"'
                "},"
                f'"outputFormat":"{OUTPUT}"'
                "}}}}}\r\n"
            )
            await ws.send_str(
                ssml_headers_plus_data(connect_id(), date_to_string(), mkssml(cfg, text))
            )
            audio = bytearray()
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.CLOSED:
                    print("closed", msg.data)
                    break
                if msg.type == aiohttp.WSMsgType.ERROR:
                    print("error", msg.data)
                    break
                if msg.type == aiohttp.WSMsgType.BINARY:
                    hl = int.from_bytes(msg.data[:2], "big")
                    params, data = get_headers_and_data(msg.data, hl)
                    ct = params.get(b"Content-Type")
                    if params.get(b"Path") == b"audio" and data:
                        print("chunk", len(data), "ct", ct)
                        audio.extend(data)
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    enc = msg.data.encode("utf-8")
                    sep = enc.find(b"\r\n\r\n")
                    params, body = get_headers_and_data(enc, sep)
                    path = params.get(b"Path")
                    if path == b"turn.end":
                        break
                    if path not in (b"response", b"turn.start", b"audio.metadata"):
                        print("text path", path, body[:200])
    print("total", len(audio), "magic", bytes(audio[:4]))


if __name__ == "__main__":
    asyncio.run(main())
