"""baseline

Revision ID: 0001
Revises:
Create Date: 2025-12-18 16:08:41.655590

This migration creates the full database schema. It matches the schema
created by the EF Core migrations. For existing databases, stamp with
this revision to mark it as applied without running the migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the full database schema."""
    # === SITES ===
    op.create_table(
        "sites",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("uuid", name="pk_sites"),
    )

    # === TARGET SYSTEMS ===
    op.create_table(
        "target_systems",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("uuid", name="pk_target_systems"),
    )
    op.create_index("ix_target_systems_name", "target_systems", ["name"], unique=True)

    # === SUB SITES ===
    op.create_table(
        "sub_sites",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("site_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "json_document",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="'{}'",
        ),
        sa.ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_sub_sites_sites_site_uuid",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_sub_sites"),
    )
    op.create_index("ix_sub_sites_site_uuid", "sub_sites", ["site_uuid"])

    # === PERFORMERS ===
    op.create_table(
        "performers",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("site_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "json_document",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="'{}'",
        ),
        sa.ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_performers_sites_site_temp_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_performers"),
    )
    op.create_index("ix_performers_site_uuid", "performers", ["site_uuid"])

    # === TAGS ===
    op.create_table(
        "tags",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("site_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_tags_sites_site_uuid",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_tags"),
    )
    op.create_index("ix_tags_site_uuid", "tags", ["site_uuid"])

    # === RELEASES ===
    op.create_table(
        "releases",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column(
            "available_files", postgresql.JSON(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("json_document", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("site_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_site_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_releases_sites_site_temp_id1",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sub_site_uuid"],
            ["sub_sites.uuid"],
            name="fk_releases_sub_sites_sub_site_temp_id",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_releases"),
    )
    op.create_index("ix_releases_site_uuid", "releases", ["site_uuid"])
    op.create_index("ix_releases_sub_site_uuid", "releases", ["sub_site_uuid"])

    # === DOWNLOADS ===
    op.create_table(
        "downloads",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column(
            "available_file", postgresql.JSON(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("saved_filename", sa.Text(), nullable=True),
        sa.Column("release_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "file_metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="'{}'",
        ),
        sa.ForeignKeyConstraint(
            ["release_uuid"],
            ["releases.uuid"],
            name="fk_downloads_releases_release_temp_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_downloads"),
    )
    op.create_index("ix_downloads_release_uuid", "downloads", ["release_uuid"])

    # === STORAGE STATES ===
    op.create_table(
        "storage_states",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_state", sa.Text(), nullable=False),
        sa.Column("site_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_storage_states_sites_site_uuid",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_storage_states"),
    )
    op.create_index(
        "ix_storage_states_site_uuid", "storage_states", ["site_uuid"], unique=True
    )

    # === JUNCTION TABLE: RELEASES <-> PERFORMERS ===
    op.create_table(
        "release_entity_site_performer_entity",
        sa.Column("performers_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("releases_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["performers_uuid"],
            ["performers.uuid"],
            name="fk_release_entity_site_performer_entity_performers_performers_",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["releases_uuid"],
            ["releases.uuid"],
            name="fk_release_entity_site_performer_entity_releases_releases_uuid",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "performers_uuid", "releases_uuid", name="pk_release_entity_site_performer_entity"
        ),
    )
    op.create_index(
        "ix_release_entity_site_performer_entity_releases_uuid",
        "release_entity_site_performer_entity",
        ["releases_uuid"],
    )

    # === JUNCTION TABLE: RELEASES <-> TAGS ===
    op.create_table(
        "release_entity_site_tag_entity",
        sa.Column("releases_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tags_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["releases_uuid"],
            ["releases.uuid"],
            name="fk_release_entity_site_tag_entity_releases_releases_uuid",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tags_uuid"],
            ["tags.uuid"],
            name="fk_release_entity_site_tag_entity_tags_tags_uuid",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "releases_uuid", "tags_uuid", name="pk_release_entity_site_tag_entity"
        ),
    )
    op.create_index(
        "ix_release_entity_site_tag_entity_tags_uuid",
        "release_entity_site_tag_entity",
        ["tags_uuid"],
    )

    # === SITE EXTERNAL IDS ===
    op.create_table(
        "site_external_ids",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column("site_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_system_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_site_external_ids_sites_site_temp_id2",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_site_external_ids_target_systems_target_system_temp_id2",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_site_external_ids"),
    )
    op.create_index(
        "ix_site_external_ids_site_uuid_target_system_uuid",
        "site_external_ids",
        ["site_uuid", "target_system_uuid"],
        unique=True,
    )
    op.create_index(
        "ix_site_external_ids_target_system_uuid",
        "site_external_ids",
        ["target_system_uuid"],
    )

    # === SUB SITE EXTERNAL IDS ===
    op.create_table(
        "sub_site_external_ids",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column("sub_site_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_system_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sub_site_uuid"],
            ["sub_sites.uuid"],
            name="fk_sub_site_external_ids_sub_sites_sub_site_temp_id1",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_sub_site_external_ids_target_systems_target_system_temp_id3",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_sub_site_external_ids"),
    )
    op.create_index(
        "ix_sub_site_external_ids_sub_site_uuid_target_system_uuid",
        "sub_site_external_ids",
        ["sub_site_uuid", "target_system_uuid"],
        unique=True,
    )
    op.create_index(
        "ix_sub_site_external_ids_target_system_uuid",
        "sub_site_external_ids",
        ["target_system_uuid"],
    )

    # === RELEASE EXTERNAL IDS ===
    op.create_table(
        "release_external_ids",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column("release_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_system_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("download_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["release_uuid"],
            ["releases.uuid"],
            name="fk_release_external_ids_releases_release_temp_id1",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_release_external_ids_target_systems_target_system_temp_id1",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["download_uuid"],
            ["downloads.uuid"],
            name="fk_release_external_ids_downloads_download_uuid",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_release_external_ids"),
    )
    op.create_index(
        "ix_release_external_ids_release_uuid_target_system_uuid_downlo",
        "release_external_ids",
        ["release_uuid", "target_system_uuid", "download_uuid"],
        unique=True,
    )
    op.create_index(
        "ix_release_external_ids_target_system_uuid",
        "release_external_ids",
        ["target_system_uuid"],
    )
    op.create_index(
        "ix_release_external_ids_download_uuid",
        "release_external_ids",
        ["download_uuid"],
    )

    # === PERFORMER EXTERNAL IDS ===
    op.create_table(
        "performer_external_ids",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column("performer_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_system_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["performer_uuid"],
            ["performers.uuid"],
            name="fk_performer_external_ids_performers_performer_temp_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_performer_external_ids_target_systems_target_system_temp_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_performer_external_ids"),
    )
    op.create_index(
        "ix_performer_external_ids_performer_uuid_target_system_uuid",
        "performer_external_ids",
        ["performer_uuid", "target_system_uuid"],
        unique=True,
    )
    op.create_index(
        "ix_performer_external_ids_target_system_uuid",
        "performer_external_ids",
        ["target_system_uuid"],
    )

    # === TAG EXTERNAL IDS ===
    op.create_table(
        "tag_external_ids",
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.Column("tag_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_system_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tag_uuid"],
            ["tags.uuid"],
            name="fk_tag_external_ids_tags_tag_temp_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_tag_external_ids_target_systems_target_system_temp_id4",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_tag_external_ids"),
    )
    op.create_index(
        "ix_tag_external_ids_tag_uuid_target_system_uuid",
        "tag_external_ids",
        ["tag_uuid", "target_system_uuid"],
        unique=True,
    )
    op.create_index(
        "ix_tag_external_ids_target_system_uuid",
        "tag_external_ids",
        ["target_system_uuid"],
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table("tag_external_ids")
    op.drop_table("performer_external_ids")
    op.drop_table("release_external_ids")
    op.drop_table("sub_site_external_ids")
    op.drop_table("site_external_ids")
    op.drop_table("release_entity_site_tag_entity")
    op.drop_table("release_entity_site_performer_entity")
    op.drop_table("storage_states")
    op.drop_table("downloads")
    op.drop_table("releases")
    op.drop_table("tags")
    op.drop_table("performers")
    op.drop_table("sub_sites")
    op.drop_table("target_systems")
    op.drop_table("sites")
