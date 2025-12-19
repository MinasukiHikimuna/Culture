"""Delta Lake client for StashDB data storage with time-travel support."""

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from deltalake import DeltaTable, write_deltalake


class StashDbLake:
    """Client for reading/writing StashDB data to Delta Lake tables."""

    def __init__(self, base_path: str = "data/stashdb"):
        self.base_path = Path(base_path)
        self.scenes_path = self.base_path / "scenes"
        self.performers_path = self.base_path / "performers"
        self.studios_path = self.base_path / "studios"
        self.tags_path = self.base_path / "tags"

    def _ensure_dirs(self) -> None:
        """Create base directories if they don't exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _table_exists(self, path: Path) -> bool:
        """Check if a Delta table exists at the given path."""
        return (path / "_delta_log").exists()

    # -------------------------------------------------------------------------
    # Scenes
    # -------------------------------------------------------------------------

    def upsert_scenes(self, scenes: list[dict]) -> None:
        """Merge scenes into Delta table with current timestamp."""
        if not scenes:
            return

        self._ensure_dirs()
        scraped_at = datetime.now(UTC)

        rows = []
        for scene in scenes:
            studio = scene.get("studio") or {}
            parent_studio = studio.get("parent") or {}

            rows.append({
                "id": scene["id"],
                "scraped_at": scraped_at,
                "title": scene.get("title"),
                "release_date": scene.get("release_date"),
                "duration": scene.get("duration"),
                "studio_id": studio.get("id"),
                "parent_studio_id": parent_studio.get("id"),
                "performer_ids": [p["performer"]["id"] for p in scene.get("performers", [])],
                "tag_ids": [t["id"] for t in scene.get("tags", [])],
                "fingerprints": json.dumps(scene.get("fingerprints", [])),
                "json_document": json.dumps(scene),
            })

        df = pl.DataFrame(rows).with_columns([
            pl.col("release_date").str.to_date("%Y-%m-%d", strict=False),
        ])

        self._write_or_merge(df, self.scenes_path, "id")

    def get_scenes(
        self,
        as_of: datetime | None = None,
        scene_ids: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query scenes, optionally at a specific point in time."""
        if not self._table_exists(self.scenes_path):
            return pl.DataFrame()

        if as_of:
            dt = DeltaTable(str(self.scenes_path))
            # Find version at the given timestamp
            version = self._get_version_at_timestamp(dt, as_of)
            if version is not None:
                dt.load_as_version(version)
            df = pl.read_delta(str(self.scenes_path), version=version)
        else:
            df = pl.read_delta(str(self.scenes_path))

        if scene_ids:
            df = df.filter(pl.col("id").is_in(scene_ids))

        return df

    def get_scene_history(self, scene_id: str) -> pl.DataFrame:
        """Get all versions of a scene over time."""
        if not self._table_exists(self.scenes_path):
            return pl.DataFrame()

        dt = DeltaTable(str(self.scenes_path))
        history = dt.history()

        versions = []
        for entry in history:
            version = entry["version"]
            try:
                df = pl.read_delta(str(self.scenes_path), version=version)
                scene_df = df.filter(pl.col("id") == scene_id)
                if len(scene_df) > 0:
                    scene_df = scene_df.with_columns(pl.lit(version).alias("_version"))
                    versions.append(scene_df)
            except Exception:
                continue

        if not versions:
            return pl.DataFrame()

        return pl.concat(versions).sort("scraped_at", descending=True)

    # -------------------------------------------------------------------------
    # Performers
    # -------------------------------------------------------------------------

    def upsert_performers(self, performers: list[dict]) -> None:
        """Merge performers into Delta table with current timestamp."""
        if not performers:
            return

        self._ensure_dirs()
        scraped_at = datetime.now(UTC)

        rows = []
        for perf in performers:
            rows.append({
                "id": perf["id"],
                "scraped_at": scraped_at,
                "name": perf.get("name"),
                "disambiguation": perf.get("disambiguation"),
                "gender": perf.get("gender"),
                "birth_date": perf.get("birth_date"),
                "country": perf.get("country"),
                "ethnicity": perf.get("ethnicity"),
                "json_document": json.dumps(perf),
            })

        df = pl.DataFrame(rows).with_columns([
            pl.col("birth_date").str.to_date("%Y-%m-%d", strict=False),
        ])

        self._write_or_merge(df, self.performers_path, "id")

    def get_performers(
        self,
        as_of: datetime | None = None,
        performer_ids: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query performers, optionally at a specific point in time."""
        if not self._table_exists(self.performers_path):
            return pl.DataFrame()

        if as_of:
            version = self._get_version_at_timestamp(
                DeltaTable(str(self.performers_path)), as_of
            )
            df = pl.read_delta(str(self.performers_path), version=version)
        else:
            df = pl.read_delta(str(self.performers_path))

        if performer_ids:
            df = df.filter(pl.col("id").is_in(performer_ids))

        return df

    # -------------------------------------------------------------------------
    # Studios
    # -------------------------------------------------------------------------

    def upsert_studios(self, studios: list[dict]) -> None:
        """Merge studios into Delta table with current timestamp."""
        if not studios:
            return

        self._ensure_dirs()
        scraped_at = datetime.now(UTC)

        rows = []
        for studio in studios:
            parent = studio.get("parent") or {}
            rows.append({
                "id": studio["id"],
                "scraped_at": scraped_at,
                "name": studio.get("name"),
                "parent_id": parent.get("id"),
                "json_document": json.dumps(studio),
            })

        df = pl.DataFrame(rows)
        self._write_or_merge(df, self.studios_path, "id")

    def get_studios(
        self,
        as_of: datetime | None = None,
        studio_ids: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query studios, optionally at a specific point in time."""
        if not self._table_exists(self.studios_path):
            return pl.DataFrame()

        if as_of:
            version = self._get_version_at_timestamp(
                DeltaTable(str(self.studios_path)), as_of
            )
            df = pl.read_delta(str(self.studios_path), version=version)
        else:
            df = pl.read_delta(str(self.studios_path))

        if studio_ids:
            df = df.filter(pl.col("id").is_in(studio_ids))

        return df

    # -------------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------------

    def upsert_tags(self, tags: list[dict]) -> None:
        """Merge tags into Delta table with current timestamp."""
        if not tags:
            return

        self._ensure_dirs()
        scraped_at = datetime.now(UTC)

        rows = []
        for tag in tags:
            category = tag.get("category") or {}
            rows.append({
                "id": tag["id"],
                "scraped_at": scraped_at,
                "name": tag.get("name"),
                "description": tag.get("description"),
                "category": category.get("name"),
                "json_document": json.dumps(tag),
            })

        df = pl.DataFrame(rows)
        self._write_or_merge(df, self.tags_path, "id")

    def get_tags(
        self,
        as_of: datetime | None = None,
        tag_ids: list[str] | None = None,
    ) -> pl.DataFrame:
        """Query tags, optionally at a specific point in time."""
        if not self._table_exists(self.tags_path):
            return pl.DataFrame()

        if as_of:
            version = self._get_version_at_timestamp(
                DeltaTable(str(self.tags_path)), as_of
            )
            df = pl.read_delta(str(self.tags_path), version=version)
        else:
            df = pl.read_delta(str(self.tags_path))

        if tag_ids:
            df = df.filter(pl.col("id").is_in(tag_ids))

        return df

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _write_or_merge(self, df: pl.DataFrame, path: Path, merge_key: str) -> None:
        """Write new table or merge into existing one."""
        if not self._table_exists(path):
            write_deltalake(str(path), df.to_arrow(), mode="overwrite")
        else:
            dt = DeltaTable(str(path))
            dt.merge(
                source=df.to_arrow(),
                predicate=f"target.{merge_key} = source.{merge_key}",
                source_alias="source",
                target_alias="target",
            ).when_matched_update_all().when_not_matched_insert_all().execute()

    def _get_version_at_timestamp(
        self, dt: DeltaTable, timestamp: datetime
    ) -> int | None:
        """Find the Delta table version at a specific timestamp."""
        history = dt.history()
        for entry in history:
            entry_time = datetime.fromisoformat(
                entry["timestamp"].replace("Z", "+00:00")
            )
            if entry_time <= timestamp:
                return entry["version"]
        return None
