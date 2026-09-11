#!/usr/bin/env python3
"""Build transparent NaiWaPet runtime assets from the licensed source video.

The source has a near-white background.  We remove only near-neutral pixels that
are connected to the image border, which preserves the cream belly and white
teeth inside the character.  Every decoded foreground frame keeps the source
video's timing and is packed into PNG atlases for decoder-free WPF playback.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageFilter


ATLAS_COLUMNS = 8
ATLAS_ROWS = 8
FRAMES_PER_ATLAS = ATLAS_COLUMNS * ATLAS_ROWS
MASK_MAGIC = b"NWMK"
MASK_VERSION = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connected_background(candidate: np.ndarray) -> np.ndarray:
    """Return candidate pixels reachable from an image border."""

    height, width = candidate.shape
    flat = candidate.reshape(-1)
    connected = np.zeros(flat.shape, dtype=np.uint8)
    pending: deque[int] = deque()

    def add(index: int) -> None:
        if flat[index] and not connected[index]:
            connected[index] = 1
            pending.append(index)

    for x in range(width):
        add(x)
        add((height - 1) * width + x)
    for y in range(height):
        add(y * width)
        add(y * width + width - 1)

    while pending:
        index = pending.popleft()
        x = index % width
        if x:
            add(index - 1)
        if x + 1 < width:
            add(index + 1)
        if index >= width:
            add(index - width)
        if index + width < flat.size:
            add(index + width)

    return connected.reshape((height, width)).astype(bool)


def largest_component(mask: np.ndarray) -> np.ndarray:
    """Keep the character and discard disconnected floor-shadow fragments."""

    height, width = mask.shape
    visited = np.zeros(mask.shape, dtype=np.uint8)
    largest: list[int] = []

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue

            component: list[int] = []
            pending: deque[int] = deque([y * width + x])
            visited[y, x] = 1
            while pending:
                index = pending.popleft()
                component.append(index)
                current_x = index % width
                current_y = index // width
                for neighbour_x, neighbour_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if (
                        0 <= neighbour_x < width
                        and 0 <= neighbour_y < height
                        and mask[neighbour_y, neighbour_x]
                        and not visited[neighbour_y, neighbour_x]
                    ):
                        visited[neighbour_y, neighbour_x] = 1
                        pending.append(neighbour_y * width + neighbour_x)

            if len(component) > len(largest):
                largest = component

    result = np.zeros(mask.shape, dtype=np.uint8)
    if largest:
        flat = result.reshape(-1)
        flat[np.asarray(largest, dtype=np.int64)] = 255
    return result


def remove_background(rgb: np.ndarray) -> np.ndarray:
    """Create an RGBA frame while preserving border-disconnected light areas."""

    height, width, _ = rgb.shape
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    background = np.median(border, axis=0).astype(np.int16)
    values = rgb.astype(np.int16)
    maximum = values.max(axis=2)
    minimum = values.min(axis=2)
    luminance = values.mean(axis=2)
    chroma = maximum - minimum
    distance = np.abs(values - background).max(axis=2)

    # Start only with pixels that are confidently background.  A previous
    # implementation flood-filled a much looser threshold and could leak through
    # anti-aliased arm edges into the cream belly on a handful of frames.
    certain = ((luminance >= 236) & (chroma <= 52)) | (
        (distance <= 36) & (luminance >= 215) & (chroma <= 58)
    )
    connected = connected_background(certain)

    # Absorb a few pixels of anti-aliasing and the soft floor shadow without
    # recursively walking through a large, light-colored foreground region.
    fringe = ((luminance >= 185) & (chroma <= 48)) | (
        (distance <= 66) & (luminance >= 175) & (chroma <= 62)
    )
    for _ in range(5):
        adjacent = np.zeros_like(connected)
        adjacent[1:, :] |= connected[:-1, :]
        adjacent[:-1, :] |= connected[1:, :]
        adjacent[:, 1:] |= connected[:, :-1]
        adjacent[:, :-1] |= connected[:, 1:]
        connected |= fringe & adjacent

    # The source video includes a pale floor shadow.  Remove its connected
    # neutral region only in the lower third; dark feet/hands remain outside the
    # luminance range, and the enclosed cream belly remains disconnected.
    ground_candidate = (luminance >= 48) & (chroma <= 60)
    ground_candidate[: int(height * 0.67), :] = False
    connected |= connected_background(ground_candidate)
    foreground = largest_component(~connected)

    # A small feather avoids a hard edge.  Keep the decoded source color in
    # partially transparent pixels; aggressive matte decontamination can turn a
    # misclassified pale foreground edge black.
    alpha = np.asarray(
        Image.fromarray(foreground, mode="L").filter(ImageFilter.GaussianBlur(0.72)),
        dtype=np.uint8,
    ).copy()
    alpha[alpha < 4] = 0
    alpha[alpha > 251] = 255

    output_rgb = rgb.copy()
    output_rgb[alpha == 0] = 0

    return np.dstack((output_rgb, alpha))


def save_atlas(atlas: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(destination, format="PNG", compress_level=9, optimize=False)


def build_icon(frame: Image.Image, png_path: Path, ico_path: Path) -> None:
    alpha = frame.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise RuntimeError("first frame has no visible foreground")
    cropped = frame.crop(bounds)
    side = max(cropped.width, cropped.height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    icon = square.resize((256, 256), Image.Resampling.LANCZOS)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    icon.save(png_path, format="PNG")
    icon.save(ico_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def extract_audio(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "22050",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    subprocess.run(command, check=True)


def build(source: Path, project_root: Path, target_height: int, fps: int) -> None:
    try:
        source_file = source.relative_to(project_root).as_posix()
    except ValueError as error:
        raise ValueError("source video must be located inside the project directory") from error

    animation_dir = project_root / "src/NaiWaPet/Assets/Animation"
    app_asset_dir = project_root / "src/NaiWaPet/Assets/App"
    audio_dir = project_root / "src/NaiWaPet/Assets/Audio"
    docs_dir = project_root / "docs"

    if animation_dir.exists():
        for old in animation_dir.glob("laugh-*.png"):
            old.unlink()

    reader = imageio_ffmpeg.read_frames(
        str(source),
        pix_fmt="rgb24",
        output_params=[
            "-vf",
            f"fps={fps},scale=-2:{target_height}:flags=lanczos",
            "-vsync",
            "0",
        ],
    )
    metadata = next(reader)
    frame_width, frame_height = metadata["size"]
    if frame_height != target_height:
        raise RuntimeError(f"unexpected decoded height: {frame_height}")

    atlas = Image.new(
        "RGBA",
        (frame_width * ATLAS_COLUMNS, frame_height * ATLAS_ROWS),
        (0, 0, 0, 0),
    )
    atlas_index = 0
    atlas_frame_count = 0
    frame_count = 0
    atlas_entries: list[dict[str, int | str]] = []
    preview_frames: list[Image.Image] = []
    first_frame: Image.Image | None = None

    animation_dir.mkdir(parents=True, exist_ok=True)
    mask_path = animation_dir / "hitmask.bin"
    bytes_per_mask = (frame_width * frame_height + 7) // 8
    with mask_path.open("wb+") as masks:
        masks.write(b"\0" * 24)
        for raw_frame in reader:
            rgb = np.frombuffer(raw_frame, dtype=np.uint8).reshape((frame_height, frame_width, 3))
            rgba = remove_background(rgb)
            frame = Image.fromarray(rgba, mode="RGBA")

            if first_frame is None:
                first_frame = frame.copy()
            if frame_count % 4 == 0:
                preview_frames.append(frame.copy())

            local = frame_count % FRAMES_PER_ATLAS
            column = local % ATLAS_COLUMNS
            row = local // ATLAS_COLUMNS
            atlas.alpha_composite(frame, (column * frame_width, row * frame_height))
            atlas_frame_count += 1

            opaque = rgba[:, :, 3] >= 12
            packed = np.packbits(opaque.reshape(-1), bitorder="little").tobytes()
            if len(packed) != bytes_per_mask:
                raise RuntimeError("unexpected hit-mask size")
            masks.write(packed)
            frame_count += 1

            if atlas_frame_count == FRAMES_PER_ATLAS:
                filename = f"laugh-{atlas_index:02d}.png"
                save_atlas(atlas, animation_dir / filename)
                atlas_entries.append(
                    {
                        "file": filename,
                        "firstFrame": frame_count - atlas_frame_count,
                        "frameCount": atlas_frame_count,
                    }
                )
                atlas_index += 1
                atlas_frame_count = 0
                atlas = Image.new(
                    "RGBA",
                    (frame_width * ATLAS_COLUMNS, frame_height * ATLAS_ROWS),
                    (0, 0, 0, 0),
                )

        if atlas_frame_count:
            filename = f"laugh-{atlas_index:02d}.png"
            save_atlas(atlas, animation_dir / filename)
            atlas_entries.append(
                {
                    "file": filename,
                    "firstFrame": frame_count - atlas_frame_count,
                    "frameCount": atlas_frame_count,
                }
            )

        masks.seek(0)
        masks.write(
            struct.pack(
                "<4sIIIII",
                MASK_MAGIC,
                MASK_VERSION,
                frame_width,
                frame_height,
                frame_count,
                bytes_per_mask,
            )
        )

    if frame_count == 0 or first_frame is None:
        raise RuntimeError("no video frames were decoded")

    manifest = {
        "schemaVersion": 1,
        "frameWidth": frame_width,
        "frameHeight": frame_height,
        "framesPerSecond": fps,
        "totalFrames": frame_count,
        "columns": ATLAS_COLUMNS,
        "rows": ATLAS_ROWS,
        "idleFrame": 0,
        "hitMaskFile": "hitmask.bin",
        "atlases": atlas_entries,
        "source": {
            "file": source_file,
            "sha256": sha256(source),
        },
    }
    (animation_dir / "animation.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    build_icon(first_frame, app_asset_dir / "naiwa.png", app_asset_dir / "naiwa.ico")
    extract_audio(source, audio_dir / "laugh.wav")

    docs_dir.mkdir(parents=True, exist_ok=True)
    preview_frames[0].save(
        docs_dir / "preview.png",
        format="PNG",
        save_all=True,
        append_images=preview_frames[1:],
        duration=round(4000 / fps),
        loop=0,
        optimize=True,
        disposal=0,
        blend=0,
    )

    (docs_dir / "preview.webp").unlink(missing_ok=True)

    print(
        f"built {frame_count} frames at {frame_width}x{frame_height} into "
        f"{len(atlas_entries)} atlases"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("assets/source/Naiwa.mp4"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--height", type=int, default=400)
    parser.add_argument("--fps", type=int, default=30)
    arguments = parser.parse_args()

    if arguments.height <= 0:
        parser.error("--height must be greater than zero")
    if not 1 <= arguments.fps <= 120:
        parser.error("--fps must be between 1 and 120")

    source = arguments.source.resolve()
    if not source.is_file():
        print(f"source video not found: {source}", file=sys.stderr)
        return 2
    build(source, arguments.project_root.resolve(), arguments.height, arguments.fps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
