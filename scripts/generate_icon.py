#!/usr/bin/env python3
"""Script to generate app icon for StreamGrab"""

import struct
import zlib
from pathlib import Path


def create_simple_png(width: int, height: int, r: int, g: int, b: int) -> bytes:
    """Create a simple solid color PNG"""

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk_len = struct.pack(">I", len(data))
        chunk_crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return chunk_len + chunk_type + data + chunk_crc

    signature = b"\x89PNG\r\n\x1a\n"

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b"IHDR", ihdr_data)

    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"
        for x in range(width):
            center_x = width // 2
            center_y = height // 2
            radius = min(width, height) // 2 - 4

            dx = x - center_x
            dy = y - center_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < radius:
                if dist > radius - 6:
                    raw_data += bytes([255, 255, 255])
                else:
                    raw_data += bytes([r, g, b])
            else:
                raw_data += bytes([45, 45, 45])

    compressed = zlib.compress(raw_data, 9)
    idat = png_chunk(b"IDAT", compressed)

    iend = png_chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def create_ico_file(output_path: Path):
    """Create ICO file from PNG images"""

    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        png_data = create_simple_png(size, size, 255, 80, 80)
        images.append((size, size, png_data))

    with open(output_path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(images)))

        offset = 6 + len(images) * 16

        for width, height, png_data in images:
            if width >= 256:
                width = 0
            if height >= 256:
                height = 0

            f.write(
                struct.pack(
                    "<BBBBHHII", width, height, 0, 0, 1, 32, len(png_data), offset
                )
            )
            offset += len(png_data)

        for _, _, png_data in images:
            f.write(png_data)


def main():
    resources_dir = Path(__file__).parent.parent / "resources"
    resources_dir.mkdir(exist_ok=True)

    ico_path = resources_dir / "icon.ico"
    create_ico_file(ico_path)
    print(f"Created icon: {ico_path}")

    png_path = resources_dir / "icon.png"
    png_data = create_simple_png(256, 256, 255, 80, 80)
    with open(png_path, "wb") as f:
        f.write(png_data)
    print(f"Created PNG: {png_path}")


if __name__ == "__main__":
    main()
