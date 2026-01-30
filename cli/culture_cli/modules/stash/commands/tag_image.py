"""Tag image commands for Stashapp."""

import base64
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from libraries.client_stashapp import StashAppClient


console = Console()

TAG_DIR = Path("/Volumes/Culture 1/Tags")


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
    # For landscape: crop height-sized square, anchor controls X position
    # For portrait: crop width-sized square, anchor controls Y position
    vf = (
        f"crop="
        f"'min(iw,ih):min(iw,ih)"
        f":(iw-min(iw,ih))*{anchor}"
        f":(ih-min(iw,ih))*{anchor}'"
    )
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


def write_tag_metadata(
    tag_name: str,
    input_path: Path,
    start: str,
    duration: float,
    bitrate: str,
    resolution: int | None,
    anchor: float,
) -> None:
    """Write metadata JSON for a tag image with version history."""
    new_version = {
        "tag_name": tag_name,
        "source_video": str(input_path.absolute()),
        "start": start,
        "duration": duration,
        "bitrate": bitrate,
        "resolution": resolution,
        "anchor": anchor,
        "created_at": datetime.now(UTC).isoformat(),
    }

    metadata_path = TAG_DIR / f"{tag_name}.json"

    # Read existing metadata if it exists
    if metadata_path.exists():
        existing_data = json.loads(metadata_path.read_text())
        versions = existing_data.get("versions", [])
    else:
        versions = []

    # Prepend new version to history
    versions.insert(0, new_version)

    metadata = {"versions": versions}
    metadata_path.write_text(json.dumps(metadata, indent=2))
    console.print(f"[blue]Metadata saved to {metadata_path}[/blue]")


def create_720p_version(source_path: Path, tag_name: str) -> Path:
    """Create a 720p version of the WebM for uploading to Stashapp."""
    temp_path = Path("/tmp") / f"{tag_name}_720p.webm"

    cmd = [
        "ffmpeg",
        "-i",
        str(source_path),
        "-vf",
        "scale=720:720",
        "-c:v",
        "libvpx-vp9",
        "-b:v",
        "1070k",  # Half of default 2140k
        "-an",
        "-y",
        str(temp_path),
    ]
    console.print(f"[blue]Creating 720p version for upload: {' '.join(cmd)}[/blue]")
    subprocess.run(cmd, check=True, capture_output=True)
    return temp_path


def upload_tag_image(client: StashAppClient, tag_name: str, webm_path: Path) -> None:
    """Upload a WebM file as a tag image in Stashapp."""
    tags = client.stash.find_tags(f={"name": {"value": tag_name, "modifier": "EQUALS"}})
    if not tags:
        console.print(f"[red]Tag '{tag_name}' not found in Stashapp.[/red]")
        sys.exit(1)

    tag_id = tags[0]["id"]

    # Probe the resolution of the source WebM
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width",
            "-of",
            "json",
            str(webm_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    width = int(json.loads(result.stdout)["streams"][0]["width"])

    # Create 720p version if source is larger
    upload_path = webm_path
    cleanup_temp = False
    if width > 720:
        console.print(f"[yellow]Source is {width}x{width}, creating 720p version for upload[/yellow]")
        upload_path = create_720p_version(webm_path, tag_name)
        cleanup_temp = True
    else:
        console.print(f"[blue]Source is {width}x{width}, uploading as-is[/blue]")

    data = upload_path.read_bytes()
    b64 = base64.b64encode(data).decode()
    data_url = f"data:video/webm;base64,{b64}"

    client.stash.call_GQL(
        """mutation TagUpdate($input: TagUpdateInput!) {
            tagUpdate(input: $input) { id }
        }""",
        {"input": {"id": tag_id, "image": data_url}},
    )
    console.print(f"[green]Updated tag '{tag_name}' (id={tag_id}) with image from {upload_path}[/green]")

    # Clean up temp file if created
    if cleanup_temp:
        upload_path.unlink()
        console.print("[blue]Cleaned up temporary 720p file[/blue]")


def set_image(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Source video path")],
    start: Annotated[str, typer.Option("--start", "-ss", help="Start time (HH:MM:SS or seconds)")],
    tag: Annotated[str, typer.Option(help="Stashapp tag name")],
    duration: float = typer.Option(5.4, "--duration", "-t", help="Clip duration in seconds"),
    bitrate: str = typer.Option("2140k", "--bitrate", "-b", help="Target bitrate"),
    resolution: int | None = typer.Option(None, "--resolution", "-r", help="Target square size (e.g. 1080)"),
    anchor: float = typer.Option(
        0.5, "--anchor", "-a", help="Crop anchor (landscape: 0.0=left, 1.0=right; portrait: 0.0=top, 1.0=bottom)"
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

    TAG_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TAG_DIR / f"{tag}.webm"

    if resolution:
        source_height = probe_video_height(input_path)
        if source_height != resolution:
            pixel_ratio = (resolution * resolution) / (source_height * source_height)
            bitrate_value = int(bitrate.rstrip("k")) * pixel_ratio
            bitrate = f"{int(bitrate_value)}k"
            console.print(f"[yellow]Scaled bitrate to {bitrate} for {resolution}x{resolution}[/yellow]")

    encode_square_webm(input_path, output_path, start, duration, bitrate, resolution, anchor)
    console.print(f"[green]WebM saved to {output_path}[/green]")

    write_tag_metadata(tag, input_path, start, duration, bitrate, resolution, anchor)

    client = StashAppClient(prefix=prefix)
    upload_tag_image(client, tag, output_path)
