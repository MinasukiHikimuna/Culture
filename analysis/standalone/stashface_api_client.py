#!/usr/bin/env python3
"""
Stashface API Client - Python script for automated face recognition analysis

This script replicates the web interface functionality using direct HTTP API calls
instead of browser automation, making it faster and more suitable for batch processing.

Usage:
    python stashface_api_client.py path/to/image.jpg [--threshold 0.5] [--results 3] [--api json|visual]

Dependencies:
    pip install requests
"""

import argparse
import json
import time
import uuid
from pathlib import Path

import requests
import sys


class StashfaceAPIClient:
    """Client for interacting with Stashface face recognition API"""

    def __init__(self, base_url: str = "http://mini.piilukko.fi:7860"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def upload_file(self, file_path: str) -> str:
        """
        Upload a file to the Gradio server

        Args:
            file_path: Path to the image file to upload

        Returns:
            The uploaded file reference that can be used in API calls
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Generate upload ID
        upload_id = "".join(str(uuid.uuid4()).split("-"))[:15]

        # Upload the file
        with Path(file_path).open("rb") as f:
            files = {"files": (Path(file_path).name, f, "image/jpeg")}
            response = self.session.post(
                f"{self.base_url}/gradio_api/upload",
                files=files,
                params={"upload_id": upload_id}
            )
            response.raise_for_status()

        upload_info = response.json()
        if not upload_info or len(upload_info) == 0:
            raise RuntimeError("File upload failed")


        # Return the file reference
        return upload_info[0]

    def analyze_faces(self, image_path: str, threshold: float = 0.5,
                     max_results: int = 3, api_type: str = "json") -> dict:
        """
        Analyze faces in an image using the Stashface API

        Args:
            image_path: Path to the image file
            threshold: Confidence threshold for face matching (0.0-1.0)
            max_results: Maximum number of results to return (0-50)
            api_type: API endpoint type ("json" or "visual")

        Returns:
            Dictionary containing the analysis results
        """
        # Upload the image file
        print(f"Uploading image: {image_path}")
        file_ref = self.upload_file(image_path)
        print(f"File uploaded successfully: {file_ref}")

        # Validate API type
        if api_type not in ["json", "visual"]:
            raise ValueError("api_type must be 'json' or 'visual'")

        # Generate session hash
        session_hash = "".join(str(uuid.uuid4()).split("-"))[:11]

        # Join the processing queue
        # Based on the Gradio interface structure:
        # Tab 0: Visual Search (multiple_image_search_with_visual)
        # Tab 1: JSON API (multiple_image_search)
        # Tab 2: Faces in Sprite

        # Format the image data as expected by Gradio
        # The file_ref is a path, but Gradio expects an ImageData object format
        image_data = {
            "path": file_ref,
            "url": None,
            "size": None,
            "orig_name": Path(image_path).name,
            "mime_type": None,
            "is_file": True
        }

        queue_data = {
            "data": [image_data, threshold, max_results],
            "event_data": None,
            "fn_index": 0 if api_type == "visual" else 1,  # Visual=0, JSON=1
            "session_hash": session_hash
        }

        print(f"Starting face analysis (threshold={threshold}, max_results={max_results}, api={api_type})")

        response = self.session.post(
            f"{self.base_url}/gradio_api/queue/join",
            json=queue_data
        )
        response.raise_for_status()

        # Poll for results
        print("Processing... ", end="", flush=True)
        max_attempts = 60  # 60 seconds timeout

        for _ in range(max_attempts):
            time.sleep(1)
            print(".", end="", flush=True)

            response = self.session.get(
                f"{self.base_url}/gradio_api/queue/data",
                params={"session_hash": session_hash}
            )
            response.raise_for_status()

            # Parse server-sent events response
            lines = response.text.strip().split("\n")
            for line in lines:
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                        if data.get("msg") == "process_completed":
                            print("\n✅ Analysis completed!")
                            output_data = data.get("output", {}).get("data", [])

                            # Handle nested list structure - Gradio sometimes returns [[data]]
                            if output_data and isinstance(output_data, list) and len(output_data) > 0:
                                # If the first element is also a list, unwrap it
                                if isinstance(output_data[0], list):
                                    output_data = output_data[0]
                            return {
                                "success": True,
                                "results": output_data,
                                "metadata": {
                                    "threshold": threshold,
                                    "max_results": max_results,
                                    "api_type": api_type,
                                    "image_path": image_path,
                                    "raw_response": data  # Include full response for debugging
                                }
                            }
                        if data.get("msg") == "process_starts":
                            continue
                        if data.get("msg") == "estimation":
                            continue
                        if "error" in data.get("msg", "").lower():
                            print(f"\n❌ Server error: {data}")
                            return {
                                "success": False,
                                "error": f"Server error: {data.get('msg', 'Unknown error')}"
                            }
                    except json.JSONDecodeError as e:
                        print(f"\n🐛 JSON decode error: {e}, line: {line}")
                        continue

        print(f"\n❌ Timeout after {max_attempts} seconds")
        return {"success": False, "error": "Processing timeout"}

    def format_results(self, results: dict) -> str:
        """Format analysis results for display"""
        if not results.get("success"):
            return f"❌ Analysis failed: {results.get('error', 'Unknown error')}"

        faces_data = results["results"]
        if not faces_data:
            return "ℹ️  No faces detected in the image"

        # Handle visual API results (returns HTML)
        if results["metadata"]["api_type"] == "visual":
            if isinstance(faces_data, list) and len(faces_data) > 0 and isinstance(faces_data[0], str):
                return "🎨 Visual API returned HTML content (use --raw to see full HTML)"

        output = []
        output.append(f"🎯 Found {len(faces_data)} face(s)")
        output.append(f"📋 Settings: threshold={results['metadata']['threshold']}, max_results={results['metadata']['max_results']}")
        output.append("")

        for i, face in enumerate(faces_data, 1):
            output.append(f"👤 Face {i}:")
            output.append(f"   Detection confidence: {face['confidence']:.1%}")
            output.append(f"   Face area: {face['area']}")

            performers = face.get("performers", [])
            if performers:
                output.append(f"   Found {len(performers)} match(es):")
                for j, performer in enumerate(performers, 1):
                    flag = "🇵🇱" if performer.get("country") == "PL" else f"🌍 {performer.get('country', 'Unknown')}"
                    output.append(f"     {j}. {performer['name']} ({flag})")
                    output.append(f"        Confidence: {performer['confidence']}%")
                    output.append(f"        Profile: {performer['performer_url']}")
                    if performer.get("image"):
                        output.append(f"        Photo: {performer['image']}")
            else:
                output.append("   ❌ No performer matches found")
            output.append("")

        return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Stashface Face Recognition API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python stashface_api_client.py photo.jpg
  python stashface_api_client.py photo.jpg --threshold 0.7 --results 5
  python stashface_api_client.py photo.jpg --api visual --output results.json
        """
    )

    parser.add_argument("image", help="Path to the image file to analyze")
    parser.add_argument("--threshold", type=float, default=0.5,
                       help="Confidence threshold (0.0-1.0, default: 0.5)")
    parser.add_argument("--results", type=int, default=3,
                       help="Maximum number of results (0-50, default: 3)")
    parser.add_argument("--api", choices=["json", "visual"], default="json",
                       help="API endpoint type (default: json)")
    parser.add_argument("--base-url", default="http://mini.piilukko.fi:7860",
                       help="Stashface server URL (default: http://mini.piilukko.fi:7860)")
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument("--raw", action="store_true", help="Output raw JSON results")

    args = parser.parse_args()

    # Validate arguments
    if not 0.0 <= args.threshold <= 1.0:
        parser.error("Threshold must be between 0.0 and 1.0")

    if not 0 <= args.results <= 50:
        parser.error("Results must be between 0 and 50")

    if not Path(args.image).exists():
        parser.error(f"Image file not found: {args.image}")

    # Create API client
    client = StashfaceAPIClient(args.base_url)

    try:
        # Analyze the image
        results = client.analyze_faces(
            args.image,
            args.threshold,
            args.results,
            args.api
        )

        # Save to file if requested
        if args.output:
            with Path(args.output).open("w") as f:
                json.dump(results, f, indent=2)
            print(f"💾 Results saved to {args.output}")

        # Display results
        if args.raw:
            print(json.dumps(results, indent=2))
        else:
            print(client.format_results(results))

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
