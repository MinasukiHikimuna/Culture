"""Core sync engine for synchronizing data between systems."""

import base64
import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libraries.client_culture_extractor import ClientCultureExtractor
from libraries.client_stashapp import StashAppClient


@dataclass
class FieldDiff:
    """Represents a difference in a single field."""

    field_name: str
    action: str  # "no_change" | "update" | "add" | "warning"
    current_value: Any
    new_value: Any
    message: str


@dataclass
class PerformerDiff:
    """Represents a performer matching status."""

    ce_uuid: str
    ce_name: str
    status: str  # "matched" | "not_found"
    stashapp_id: int | None
    stashapp_name: str | None
    message: str


@dataclass
class SyncPlan:
    """Complete synchronization plan for a scene."""

    ce_uuid: str
    stashapp_id: int
    ce_release_name: str
    stashapp_title: str
    field_diffs: list[FieldDiff]
    performer_diffs: list[PerformerDiff]

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes to apply."""
        return any(diff.action in ["update", "add"] for diff in self.field_diffs) or any(
            diff.status == "matched" for diff in self.performer_diffs
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(diff.status == "not_found" for diff in self.performer_diffs)


@dataclass
class SyncResult:
    """Result after applying sync."""

    success: bool
    message: str
    fields_updated: list[str]
    performers_linked: int
    errors: list[str]


class SyncEngine:
    """Engine for synchronizing data between Culture Extractor and Stashapp."""

    def __init__(
        self,
        ce_client: ClientCultureExtractor,
        stash_client: StashAppClient,
        metadata_base_path: str | Path | None = None,
    ):
        """Initialize the sync engine.

        Args:
            ce_client: Culture Extractor client
            stash_client: Stashapp client
            metadata_base_path: Base path where downloaded files are stored (optional)
        """
        self.ce_client = ce_client
        self.stash_client = stash_client
        self.metadata_base_path = Path(metadata_base_path) if metadata_base_path else None

    def fetch_ce_data(self, ce_uuid: str) -> dict:
        """Fetch release and performer data from Culture Extractor.

        Args:
            ce_uuid: Culture Extractor release UUID

        Returns:
            Dictionary containing release and performer data
        """
        # Get release data
        release_df = self.ce_client.get_release_by_uuid(ce_uuid)
        if release_df.shape[0] == 0:
            raise ValueError(f"Release with UUID '{ce_uuid}' not found in Culture Extractor")

        release = release_df.to_dicts()[0]

        # Get performers for this release
        performers_df = self.ce_client.get_release_performers(ce_uuid)
        performers = performers_df.to_dicts() if performers_df.shape[0] > 0 else []

        # Get cover image if available
        downloads_df = self.ce_client.get_release_downloads(ce_uuid)
        cover_image_path = None

        if downloads_df.shape[0] > 0:
            # Filter for cover images
            covers = downloads_df.filter(
                (downloads_df["ce_downloads_file_type"] == "image")
                & (downloads_df["ce_downloads_content_type"] == "cover")
            )
            if covers.shape[0] > 0:
                saved_filename = covers["ce_downloads_saved_filename"][0]

                # Construct full path if metadata_base_path is provided
                if self.metadata_base_path and saved_filename:
                    # Path structure: {base_path}/{site_name}/Metadata/{release_uuid}/{filename}
                    site_name = release.get("ce_site_name", "")
                    full_path = (
                        self.metadata_base_path / site_name / "Metadata" / ce_uuid / saved_filename
                    )
                    cover_image_path = str(full_path)
                else:
                    # Just use the filename if no base path configured
                    cover_image_path = saved_filename

        return {
            "release": release,
            "performers": performers,
            "cover_image_path": cover_image_path,
        }

    def fetch_stashapp_data(self, stashapp_id: int) -> dict:
        """Fetch scene and performer data from Stashapp.

        Args:
            stashapp_id: Stashapp scene ID

        Returns:
            Dictionary containing scene and performer data
        """
        fragment = """
            id
            title
            date
            details
            urls
            performers {
                id
                name
                stash_ids {
                    endpoint
                    stash_id
                }
            }
            stash_ids {
                endpoint
                stash_id
            }
        """

        scene = self.stash_client.stash.find_scene(stashapp_id, fragment=fragment)
        if not scene:
            raise ValueError(f"Scene with ID '{stashapp_id}' not found in Stashapp")

        return scene

    def compute_diff(self, ce_data: dict, stash_data: dict) -> SyncPlan:
        """Compute differences between CE and Stashapp data.

        Args:
            ce_data: Culture Extractor data
            stash_data: Stashapp data

        Returns:
            SyncPlan with all differences
        """
        ce_release = ce_data["release"]
        ce_performers = ce_data["performers"]

        field_diffs = []

        # Compare title
        ce_title = ce_release.get("ce_release_name") or ""
        stash_title = stash_data.get("title") or ""
        field_diffs.append(
            self._create_field_diff(
                "title",
                stash_title,
                ce_title,
                lambda action, curr, new: {
                    "add": f'Add title: "{new}"',
                    "update": f'Update title: "{curr}" → "{new}"',
                    "no_change": f'Title unchanged: "{curr}"',
                }[action],
            )
        )

        # Compare date
        ce_date = str(ce_release.get("ce_release_date")) if ce_release.get("ce_release_date") else ""
        stash_date = stash_data.get("date") or ""
        field_diffs.append(self._create_field_diff("date", stash_date, ce_date))

        # Compare description/details
        ce_details = ce_release.get("ce_release_description") or ""
        stash_details = stash_data.get("details") or ""
        field_diffs.append(
            self._create_field_diff(
                "details",
                stash_details,
                ce_details,
                lambda action, _curr, new: {
                    "add": f'Add details: "{new[:50]}{"..." if len(new) > 50 else ""}"',
                    "update": f'Update details: "{new[:50]}{"..." if len(new) > 50 else ""}"',
                    "no_change": "Details unchanged",
                }[action],
            )
        )

        # Compare URL
        ce_url = ce_release.get("ce_release_url") or ""
        stash_urls = stash_data.get("urls") or []
        if ce_url and ce_url not in stash_urls:
            field_diffs.append(
                FieldDiff(
                    field_name="url",
                    action="add",
                    current_value=stash_urls,
                    new_value=ce_url,
                    message=f"Add URL: {ce_url}",
                )
            )
        else:
            field_diffs.append(
                FieldDiff(
                    field_name="url",
                    action="no_change",
                    current_value=stash_urls,
                    new_value=ce_url,
                    message="URL already present" if ce_url else "No URL to add",
                )
            )

        # Compare cover image
        cover_image_path = ce_data.get("cover_image_path")
        if cover_image_path:
            field_diffs.append(
                FieldDiff(
                    field_name="cover_image",
                    action="update",
                    current_value=None,
                    new_value=cover_image_path,
                    message=f"Update cover image from: {cover_image_path}",
                )
            )
        else:
            field_diffs.append(
                FieldDiff(
                    field_name="cover_image",
                    action="no_change",
                    current_value=None,
                    new_value=None,
                    message="No cover image available",
                )
            )

        # Match performers
        performer_diffs = self._match_performers(ce_performers)

        return SyncPlan(
            ce_uuid=ce_release["ce_release_uuid"],
            stashapp_id=int(stash_data["id"]),
            ce_release_name=ce_title,
            stashapp_title=stash_title,
            field_diffs=field_diffs,
            performer_diffs=performer_diffs,
        )

    def _create_field_diff(
        self,
        field_name: str,
        current_value: Any,
        new_value: Any,
        format_message: Callable | None = None,
    ) -> FieldDiff:
        """Create a FieldDiff for a single field comparison.

        Args:
            field_name: Name of the field being compared
            current_value: Current value in Stashapp
            new_value: New value from CE
            format_message: Optional function to format the message

        Returns:
            FieldDiff object
        """
        if new_value != current_value:
            if not current_value:
                action = "add"
                message = (
                    f"Add {field_name}: {new_value}"
                    if not format_message
                    else format_message("add", current_value, new_value)
                )
            else:
                action = "update"
                message = (
                    f"Update {field_name}: {current_value} → {new_value}"
                    if not format_message
                    else format_message("update", current_value, new_value)
                )
        else:
            action = "no_change"
            message = (
                f"{field_name.capitalize()} unchanged: {current_value}"
                if not format_message
                else format_message("no_change", current_value, new_value)
            )

        return FieldDiff(
            field_name=field_name,
            action=action,
            current_value=current_value,
            new_value=new_value,
            message=message,
        )

    def _match_performers(self, ce_performers: list[dict]) -> list[PerformerDiff]:
        """Match CE performers with Stashapp performers.

        Args:
            ce_performers: List of CE performers

        Returns:
            List of PerformerDiff objects
        """
        performer_diffs = []

        for ce_performer in ce_performers:
            ce_uuid = ce_performer["ce_performers_uuid"]
            ce_name = ce_performer["ce_performers_name"]
            ce_stashapp_id = ce_performer.get("ce_performers_stashapp_id")

            # Check if CE already has a Stashapp ID for this performer
            if ce_stashapp_id:
                # CE already has the performer linked - use that ID
                performer_diffs.append(
                    PerformerDiff(
                        ce_uuid=ce_uuid,
                        ce_name=ce_name,
                        status="matched",
                        stashapp_id=int(ce_stashapp_id),
                        stashapp_name=ce_name,  # We'll use the CE name since we trust the ID is correct
                        message=f"Matched to Stashapp performer #{ce_stashapp_id} (via CE link)",
                    )
                )
            else:
                # No Stashapp ID in CE - performer not linked yet
                performer_diffs.append(
                    PerformerDiff(
                        ce_uuid=ce_uuid,
                        ce_name=ce_name,
                        status="not_found",
                        stashapp_id=None,
                        stashapp_name=None,
                        message=f"Performer '{ce_name}' not linked to Stashapp yet (CE UUID: {ce_uuid})",
                    )
                )

        return performer_diffs

    def _process_cover_image(self, cover_path: Path) -> tuple[str | None, list[str]]:
        """Process cover image file and return base64 encoded data.

        Args:
            cover_path: Path to the cover image file

        Returns:
            Tuple of (base64_encoded_image, errors_list)
        """
        errors = []

        if not cover_path.exists():
            errors.append(f"Cover image file not found: {cover_path}")
            return None, errors

        try:
            # Read and encode the image
            with cover_path.open("rb") as img_file:
                image_data = img_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")

            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(str(cover_path))
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/jpeg"  # Default fallback

            cover_image_base64 = f"data:{mime_type};base64,{base64_image}"
            return cover_image_base64, errors

        except OSError as e:
            errors.append(f"Failed to read cover image: {e}")
            return None, errors
        except Exception as e:
            errors.append(f"Failed to process cover image: {e}")
            return None, errors

    def apply_sync(self, plan: SyncPlan) -> SyncResult:
        """Apply the synchronization plan.

        Args:
            plan: SyncPlan to apply

        Returns:
            SyncResult with operation results
        """
        fields_updated = []
        errors = []

        try:
            # Build update payload
            update_data = {"id": plan.stashapp_id}

            # Update title if changed
            title_diff = next((d for d in plan.field_diffs if d.field_name == "title"), None)
            if title_diff and title_diff.action in ["update", "add"]:
                update_data["title"] = title_diff.new_value
                fields_updated.append("title")

            # Update date if changed
            date_diff = next((d for d in plan.field_diffs if d.field_name == "date"), None)
            if date_diff and date_diff.action in ["update", "add"]:
                update_data["date"] = date_diff.new_value
                fields_updated.append("date")

            # Update details if changed
            details_diff = next((d for d in plan.field_diffs if d.field_name == "details"), None)
            if details_diff and details_diff.action in ["update", "add"]:
                update_data["details"] = details_diff.new_value
                fields_updated.append("details")

            # Add URL if new
            url_diff = next((d for d in plan.field_diffs if d.field_name == "url"), None)
            if url_diff and url_diff.action == "add":
                current_urls = url_diff.current_value if isinstance(url_diff.current_value, list) else []
                new_urls = [*current_urls, url_diff.new_value]
                update_data["urls"] = new_urls
                fields_updated.append("url")

            # Update cover image if available
            cover_diff = next((d for d in plan.field_diffs if d.field_name == "cover_image"), None)
            if cover_diff and cover_diff.action in ["update", "add"] and cover_diff.new_value:
                cover_path = Path(cover_diff.new_value)
                cover_image_base64, cover_errors = self._process_cover_image(cover_path)
                errors.extend(cover_errors)

                if cover_image_base64:
                    update_data["cover_image"] = cover_image_base64
                    fields_updated.append("cover_image")

            # Update performer IDs
            matched_performer_ids = [
                p.stashapp_id for p in plan.performer_diffs if p.status == "matched" and p.stashapp_id
            ]
            if matched_performer_ids:
                update_data["performer_ids"] = matched_performer_ids
                fields_updated.append("performers")

            # Add CE external ID to Stashapp scene stash_ids
            update_data["stash_ids"] = [
                {"endpoint": "https://culture.extractor/graphql", "stash_id": plan.ce_uuid}
            ]

            # Apply update to Stashapp
            if fields_updated:  # Only update if there are actual changes
                self.stash_client.stash.update_scene(update_data)

            # Update CE database with Stashapp external ID
            self.ce_client.set_release_external_id(plan.ce_uuid, "stashapp", str(plan.stashapp_id))

            return SyncResult(
                success=True,
                message="Sync completed successfully",
                fields_updated=fields_updated,
                performers_linked=len(matched_performer_ids),
                errors=errors,
            )

        except Exception as e:
            errors.append(str(e))
            return SyncResult(
                success=False,
                message=f"Sync failed: {e}",
                fields_updated=fields_updated,
                performers_linked=0,
                errors=errors,
            )
