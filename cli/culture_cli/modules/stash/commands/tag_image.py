"""Tag image commands for Stashapp."""

import base64
import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from libraries.client_stashapp import StashAppClient


console = Console()

TAG_IMAGE_DIR = Path("/tmp/culture/tag-images")


def probe_video_height(input_path: Path) -> int:
    """Get the height of a video file using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "json",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return int(data["streams"][0]["height"])


def encode_square_webm(
    input_path: Path,
    output_path: Path,
    start: str,
    duration: float,
    bitrate: str,
    resolution: int | None,
    anchor: float,
) -> None:
    """Encode a square cropped VP9 WebM clip."""
    vf = f"crop=ih:ih:(iw-ih)*{anchor}:0"
    if resolution:
        vf += f",scale={resolution}:{resolution}"

    cmd = [
        "ffmpeg",
        "-ss",
        start,
        "-i",
        str(input_path),
        "-t",
        str(duration),
        "-vf",
        vf,
        "-c:v",
        "libvpx-vp9",
        "-b:v",
        bitrate,
        "-an",
        "-y",
        str(output_path),
    ]
    console.print(f"[blue]Running: {' '.join(cmd)}[/blue]")
    subprocess.run(cmd, check=True)


def upload_tag_image(client: StashAppClient, tag_name: str, webm_path: Path) -> None:
    """Upload a WebM file as a tag image in Stashapp."""
    tags = client.stash.find_tags(f={"name": {"value": tag_name, "modifier": "EQUALS"}})
    if not tags:
        console.print(f"[red]Tag '{tag_name}' not found in Stashapp.[/red]")
        sys.exit(1)

    tag_id = tags[0]["id"]
    data = webm_path.read_bytes()
    b64 = base64.b64encode(data).decode()
    data_url = f"data:video/webm;base64,{b64}"

    client.stash.call_GQL(
        """mutation TagUpdate($input: TagUpdateInput!) {
            tagUpdate(input: $input) { id }
        }""",
        {"input": {"id": tag_id, "image": data_url}},
    )
    console.print(f"[green]Updated tag '{tag_name}' (id={tag_id}) with image from {webm_path}[/green]")


def set_image(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Source video path")],
    start: Annotated[str, typer.Option("--start", "-ss", help="Start time (HH:MM:SS or seconds)")],
    tag: Annotated[str, typer.Option(help="Stashapp tag name")],
    duration: float = typer.Option(5.4, "--duration", "-t", help="Clip duration in seconds"),
    bitrate: str = typer.Option("2140k", "--bitrate", "-b", help="Target bitrate"),
    resolution: int | None = typer.Option(None, "--resolution", "-r", help="Target square size (e.g. 1080)"),
    anchor: float = typer.Option(
        0.5, "--anchor", "-a", help="Horizontal crop anchor (0.0=left, 0.5=center, 1.0=right)"
    ),
    prefix: str = typer.Option("", "--prefix", "-p", help="Env var prefix for Stashapp connection"),
) -> None:
    """Extract a square clip from a video and set it as a tag image in Stashapp.

    Examples:
        culture stash tags set-image -i video.mp4 -ss 00:01:30 --tag "POV"
        culture stash tags set-image -i video.mp4 -ss 30 --tag "POV" -r 1080 -b 8560k
    """
    if not input_path.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
        sys.exit(1)

    TAG_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TAG_IMAGE_DIR / f"{tag}.webm"

    if resolution:
        source_height = probe_video_height(input_path)
        if source_height != resolution:
            pixel_ratio = (resolution * resolution) / (source_height * source_height)
            bitrate_value = int(bitrate.rstrip("k")) * pixel_ratio
            bitrate = f"{int(bitrate_value)}k"
            console.print(f"[yellow]Scaled bitrate to {bitrate} for {resolution}x{resolution}[/yellow]")

    encode_square_webm(input_path, output_path, start, duration, bitrate, resolution, anchor)
    console.print(f"[green]WebM saved to {output_path}[/green]")

    client = StashAppClient(prefix=prefix)
    upload_tag_image(client, tag, output_path)
