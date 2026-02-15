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
class TagDiff:
    """Represents a tag matching status."""

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
    tag_diffs: list[TagDiff]
    existing_stashapp_performer_ids: list[int]
    existing_stashapp_tag_ids: list[int]
    existing_stashapp_stash_ids: list[dict]

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes to apply."""
        return (
            any(diff.action in ["update", "add"] for diff in self.field_diffs)
            or any(diff.status == "matched" for diff in self.performer_diffs)
            or any(diff.status == "matched" for diff in self.tag_diffs)
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(diff.status == "not_found" for diff in self.performer_diffs) or any(
            diff.status == "not_found" for diff in self.tag_diffs
        )


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

        # Get tags for this release
        tags_df = self.ce_client.get_release_tags(ce_uuid)
        tags = []
        if tags_df.shape[0] > 0:
            for tag_dict in tags_df.to_dicts():
                tag_uuid = tag_dict["ce_tags_uuid"]
                # Get external IDs for this tag
                external_ids = self.ce_client.get_tag_external_ids(tag_uuid)
                tag_dict["ce_tags_stashapp_id"] = external_ids.get("stashapp")
                tags.append(tag_dict)

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
            "tags": tags,
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
            studio {
                id
                name
            }
            performers {
                id
                name
                stash_ids {
                    endpoint
                    stash_id
                }
            }
            tags {
                id
                name
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

        # Compare studio
        ce_site_uuid = ce_release.get("ce_site_uuid")
        stash_studio = stash_data.get("studio")
        stash_studio_id = stash_studio.get("id") if stash_studio else None
        stash_studio_name = stash_studio.get("name") if stash_studio else None

        # Get CE site's Stashapp ID mapping if it exists
        ce_studio_stashapp_id = None
        if ce_site_uuid:
            site_external_ids = self.ce_client.get_site_external_ids(ce_site_uuid)
            ce_studio_stashapp_id = site_external_ids.get("stashapp")
            if ce_studio_stashapp_id:
                ce_studio_stashapp_id = int(ce_studio_stashapp_id)

        if ce_studio_stashapp_id:
            if stash_studio_id != ce_studio_stashapp_id:
                field_diffs.append(
                    FieldDiff(
                        field_name="studio",
                        action="update" if stash_studio_id else "add",
                        current_value=stash_studio_id,
                        new_value=ce_studio_stashapp_id,
                        message=f"{'Update' if stash_studio_id else 'Add'} studio: "
                        f"{stash_studio_name or 'None'} (ID: {stash_studio_id}) → "
                        f"Studio ID: {ce_studio_stashapp_id}",
                    )
                )
            else:
                field_diffs.append(
                    FieldDiff(
                        field_name="studio",
                        action="no_change",
                        current_value=stash_studio_id,
                        new_value=ce_studio_stashapp_id,
                        message=f"Studio unchanged: {stash_studio_name} (ID: {stash_studio_id})",
                    )
                )
        else:
            # No studio mapping available
            field_diffs.append(
                FieldDiff(
                    field_name="studio",
                    action="warning" if not stash_studio_id else "no_change",
                    current_value=stash_studio_id,
                    new_value=None,
                    message="No studio mapping available in CE (link site to Stashapp studio first)"
                    if not stash_studio_id
                    else f"Studio in Stashapp: {stash_studio_name} (ID: {stash_studio_id}), but no CE mapping",
                )
            )

        # Match performers
        performer_diffs = self._match_performers(ce_performers)

        # Match tags
        ce_tags = ce_data.get("tags", [])
        tag_diffs = self._match_tags(ce_tags)

        # Extract existing Stashapp data for merging
        existing_performers = stash_data.get("performers", [])
        existing_stashapp_performer_ids = [p["id"] for p in existing_performers]

        existing_tags = stash_data.get("tags", [])
        existing_stashapp_tag_ids = [t["id"] for t in existing_tags]

        existing_stashapp_stash_ids = stash_data.get("stash_ids", [])

        return SyncPlan(
            ce_uuid=ce_release["ce_release_uuid"],
            stashapp_id=int(stash_data["id"]),
            ce_release_name=ce_title,
            stashapp_title=stash_title,
            field_diffs=field_diffs,
            performer_diffs=performer_diffs,
            tag_diffs=tag_diffs,
            existing_stashapp_performer_ids=existing_stashapp_performer_ids,
            existing_stashapp_tag_ids=existing_stashapp_tag_ids,
            existing_stashapp_stash_ids=existing_stashapp_stash_ids,
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

    def _match_tags(self, ce_tags: list[dict]) -> list[TagDiff]:
        """Match CE tags with Stashapp tags.

        Args:
            ce_tags: List of CE tags with external IDs

        Returns:
            List of TagDiff objects
        """
        tag_diffs = []

        for ce_tag in ce_tags:
            ce_uuid = ce_tag["ce_tags_uuid"]
            ce_name = ce_tag["ce_tags_name"]
            ce_stashapp_id = ce_tag.get("ce_tags_stashapp_id")

            # Check if CE already has a Stashapp ID for this tag
            if ce_stashapp_id:
                # CE already has the tag linked - use that ID
                tag_diffs.append(
                    TagDiff(
                        ce_uuid=ce_uuid,
                        ce_name=ce_name,
                        status="matched",
                        stashapp_id=int(ce_stashapp_id),
                        stashapp_name=ce_name,  # We'll use the CE name since we trust the ID is correct
                        message=f"Matched to Stashapp tag #{ce_stashapp_id} (via CE link)",
                    )
                )
            else:
                # No Stashapp ID in CE - tag not linked yet
                tag_diffs.append(
                    TagDiff(
                        ce_uuid=ce_uuid,
                        ce_name=ce_name,
                        status="not_found",
                        stashapp_id=None,
                        stashapp_name=None,
                        message=f"Tag '{ce_name}' not linked to Stashapp yet (CE UUID: {ce_uuid})",
                    )
                )

        return tag_diffs

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

    def apply_sync(self, plan: SyncPlan, overwrite: bool = False) -> SyncResult:
        """Apply the synchronization plan.

        Args:
            plan: SyncPlan to apply
            overwrite: If True, overwrite existing values. If False (default), merge with existing values

        Returns:
            SyncResult with operation results
        """
        fields_updated = []
        errors = []

        try:
            # Build update payload
            update_data = {"id": plan.stashapp_id}

            # Update basic fields
            self._apply_basic_field_updates(plan, update_data, fields_updated)

            # Update cover image
            self._apply_cover_image_update(plan, update_data, fields_updated, errors)

            # Update performers and tags
            matched_performer_ids = self._apply_performer_updates(
                plan, update_data, fields_updated, overwrite
            )
            self._apply_tag_updates(plan, update_data, fields_updated, overwrite)

            # Update stash_ids
            self._apply_stash_ids_update(plan, update_data, overwrite)

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

    def _apply_basic_field_updates(
        self, plan: SyncPlan, update_data: dict, fields_updated: list[str]
    ) -> None:
        """Apply basic field updates (title, date, details, url, studio)."""
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

        # Update studio if changed
        studio_diff = next((d for d in plan.field_diffs if d.field_name == "studio"), None)
        if studio_diff and studio_diff.action in ["update", "add"]:
            update_data["studio_id"] = studio_diff.new_value
            fields_updated.append("studio")

    def _apply_cover_image_update(
        self, plan: SyncPlan, update_data: dict, fields_updated: list[str], errors: list[str]
    ) -> None:
        """Apply cover image update."""
        cover_diff = next((d for d in plan.field_diffs if d.field_name == "cover_image"), None)
        if cover_diff and cover_diff.action in ["update", "add"] and cover_diff.new_value:
            cover_path = Path(cover_diff.new_value)
            cover_image_base64, cover_errors = self._process_cover_image(cover_path)
            errors.extend(cover_errors)

            if cover_image_base64:
                update_data["cover_image"] = cover_image_base64
                fields_updated.append("cover_image")

    def _apply_performer_updates(
        self, plan: SyncPlan, update_data: dict, fields_updated: list[str], overwrite: bool
    ) -> list[int]:
        """Apply performer updates and return matched performer IDs."""
        matched_performer_ids = [
            p.stashapp_id for p in plan.performer_diffs if p.status == "matched" and p.stashapp_id
        ]

        if matched_performer_ids or overwrite:
            if overwrite:
                final_performer_ids = matched_performer_ids
            else:
                final_performer_ids = list(
                    set(plan.existing_stashapp_performer_ids + matched_performer_ids)
                )

            if final_performer_ids:
                update_data["performer_ids"] = final_performer_ids
                fields_updated.append("performers")

        return matched_performer_ids

    def _apply_tag_updates(
        self, plan: SyncPlan, update_data: dict, fields_updated: list[str], overwrite: bool
    ) -> None:
        """Apply tag updates."""
        matched_tag_ids = [
            t.stashapp_id for t in plan.tag_diffs if t.status == "matched" and t.stashapp_id
        ]

        if matched_tag_ids or overwrite:
            final_tag_ids = matched_tag_ids if overwrite else list(set(plan.existing_stashapp_tag_ids + matched_tag_ids))

            if final_tag_ids:
                update_data["tag_ids"] = final_tag_ids
                fields_updated.append("tags")

    def _apply_stash_ids_update(self, plan: SyncPlan, update_data: dict, overwrite: bool) -> None:
        """Apply stash_ids update."""
        ce_stash_id = {"endpoint": "https://culture.extractor/graphql", "stash_id": plan.ce_uuid}

        if overwrite:
            update_data["stash_ids"] = [ce_stash_id]
        else:
            existing_stash_ids = [
                sid
                for sid in plan.existing_stashapp_stash_ids
                if not (
                    sid.get("endpoint") == ce_stash_id["endpoint"]
                    and sid.get("stash_id") == ce_stash_id["stash_id"]
                )
            ]
            update_data["stash_ids"] = [*existing_stash_ids, ce_stash_id]
