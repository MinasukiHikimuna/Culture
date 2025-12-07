"""Stashface API client for face recognition.

This service wraps the Stashface Gradio API for face recognition
and performer matching.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass
class PerformerMatch:
    """A performer match from face recognition."""

    name: str
    confidence: int
    country: str | None
    performer_url: str
    stashdb_id: str
    image_url: str | None


@dataclass
class FaceResult:
    """Result for a single face in an image."""

    confidence: float
    area: int
    performers: list[PerformerMatch]


@dataclass
class StashfaceResult:
    """Result from Stashface face recognition."""

    success: bool
    error: str | None
    faces: list[FaceResult]


class StashfaceClient:
    """Client for the Stashface face recognition API."""

    def __init__(self, base_url: str = "http://mini.piilukko.fi:7860"):
        """Initialize the client.

        Args:
            base_url: Base URL for the Stashface server
        """
        self.base_url = base_url.rstrip("/")

    async def analyze_image(
        self,
        image_path: str,
        threshold: float = 0.5,
        max_results: int = 5,
    ) -> StashfaceResult:
        """Analyze faces in an image using the Stashface API.

        Args:
            image_path: Path to the image file
            threshold: Confidence threshold for face matching (0.0-1.0)
            max_results: Maximum number of results to return per face

        Returns:
            StashfaceResult with face recognition results
        """
        image_file = Path(image_path)
        if not image_file.exists():
            return StashfaceResult(
                success=False,
                error=f"Image file not found: {image_path}",
                faces=[],
            )

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Upload the image file
            file_ref = await self._upload_file(client, image_path)
            if file_ref is None:
                return StashfaceResult(
                    success=False,
                    error="Failed to upload image",
                    faces=[],
                )

            # Analyze faces
            return await self._analyze_faces(
                client, image_path, file_ref, threshold, max_results
            )

    async def _upload_file(
        self, client: httpx.AsyncClient, file_path: str
    ) -> str | None:
        """Upload a file to the Gradio server.

        Args:
            client: HTTP client
            file_path: Path to the image file

        Returns:
            File reference or None if upload failed
        """
        upload_id = "".join(str(uuid.uuid4()).split("-"))[:15]
        file_path_obj = Path(file_path)

        with file_path_obj.open("rb") as f:
            files = {"files": (file_path_obj.name, f, "image/jpeg")}
            response = await client.post(
                f"{self.base_url}/gradio_api/upload",
                files=files,
                params={"upload_id": upload_id},
            )

        if response.status_code != 200:
            return None

        upload_info = response.json()
        if not upload_info or len(upload_info) == 0:
            return None

        return upload_info[0]

    async def _analyze_faces(
        self,
        client: httpx.AsyncClient,
        image_path: str,
        file_ref: str,
        threshold: float,
        max_results: int,
    ) -> StashfaceResult:
        """Analyze faces using the uploaded file.

        Args:
            client: HTTP client
            image_path: Original image path (for metadata)
            file_ref: Uploaded file reference
            threshold: Confidence threshold
            max_results: Maximum results per face

        Returns:
            StashfaceResult with analysis results
        """
        session_hash = "".join(str(uuid.uuid4()).split("-"))[:11]

        # Format image data for Gradio
        image_data = {
            "path": file_ref,
            "url": None,
            "size": None,
            "orig_name": Path(image_path).name,
            "mime_type": None,
            "is_file": True,
        }

        queue_data = {
            "data": [image_data, threshold, max_results],
            "event_data": None,
            "fn_index": 1,  # JSON API endpoint
            "session_hash": session_hash,
        }

        # Join the processing queue
        response = await client.post(
            f"{self.base_url}/gradio_api/queue/join",
            json=queue_data,
        )

        if response.status_code != 200:
            return StashfaceResult(
                success=False,
                error=f"Failed to join queue: {response.status_code}",
                faces=[],
            )

        # Poll for results
        max_attempts = 60
        for _ in range(max_attempts):
            await self._async_sleep(1)

            response = await client.get(
                f"{self.base_url}/gradio_api/queue/data",
                params={"session_hash": session_hash},
            )

            if response.status_code != 200:
                continue

            result = self._parse_sse_response(response.text)
            if result is not None:
                return result

        return StashfaceResult(
            success=False,
            error="Processing timeout",
            faces=[],
        )

    def _parse_sse_response(self, text: str) -> StashfaceResult | None:
        """Parse server-sent events response.

        Args:
            text: SSE response text

        Returns:
            StashfaceResult if processing completed, None otherwise
        """
        lines = text.strip().split("\n")
        for line in lines:
            if not line.startswith("data: "):
                continue

            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            msg = data.get("msg", "")

            if msg == "process_completed":
                return self._parse_completed_response(data)
            if "error" in msg.lower():
                return StashfaceResult(
                    success=False,
                    error=f"Server error: {msg}",
                    faces=[],
                )

        return None

    def _parse_completed_response(self, data: dict) -> StashfaceResult:
        """Parse a completed processing response.

        Args:
            data: Response data dict

        Returns:
            StashfaceResult with parsed faces
        """
        output_data = data.get("output", {}).get("data", [])

        # Handle nested list structure - Gradio sometimes returns [[data]]
        if (
            output_data
            and isinstance(output_data, list)
            and len(output_data) > 0
            and isinstance(output_data[0], list)
        ):
            output_data = output_data[0]

        if not output_data:
            return StashfaceResult(success=True, error=None, faces=[])

        faces = []
        for face_data in output_data:
            performers = []
            for performer in face_data.get("performers", []):
                # Extract StashDB ID from performer URL
                performer_url = performer.get("performer_url", "")
                stashdb_id = performer_url.split("/")[-1] if performer_url else ""

                performers.append(
                    PerformerMatch(
                        name=performer.get("name", ""),
                        confidence=performer.get("confidence", 0),
                        country=performer.get("country"),
                        performer_url=performer_url,
                        stashdb_id=stashdb_id,
                        image_url=performer.get("image"),
                    )
                )

            faces.append(
                FaceResult(
                    confidence=face_data.get("confidence", 0.0),
                    area=face_data.get("area", 0),
                    performers=performers,
                )
            )

        return StashfaceResult(success=True, error=None, faces=faces)

    async def _async_sleep(self, seconds: float) -> None:
        """Async sleep helper.

        Args:
            seconds: Seconds to sleep
        """
        await asyncio.sleep(seconds)
