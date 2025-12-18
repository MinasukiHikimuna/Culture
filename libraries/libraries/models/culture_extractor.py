"""SQLAlchemy models for Culture Extractor database.

These models match the schema defined in the EF Core migrations.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


# Junction table for releases and performers
release_performer = Table(
    "release_entity_site_performer_entity",
    Base.metadata,
    Column("performers_uuid", PG_UUID(as_uuid=True), nullable=False),
    Column("releases_uuid", PG_UUID(as_uuid=True), nullable=False),
    PrimaryKeyConstraint(
        "performers_uuid", "releases_uuid", name="pk_release_entity_site_performer_entity"
    ),
    ForeignKeyConstraint(
        ["performers_uuid"],
        ["performers.uuid"],
        name="fk_release_entity_site_performer_entity_performers_performers_",
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["releases_uuid"],
        ["releases.uuid"],
        name="fk_release_entity_site_performer_entity_releases_releases_uuid",
        ondelete="CASCADE",
    ),
    Index("ix_release_entity_site_performer_entity_releases_uuid", "releases_uuid"),
)

# Junction table for releases and tags
release_tag = Table(
    "release_entity_site_tag_entity",
    Base.metadata,
    Column("releases_uuid", PG_UUID(as_uuid=True), nullable=False),
    Column("tags_uuid", PG_UUID(as_uuid=True), nullable=False),
    PrimaryKeyConstraint(
        "releases_uuid", "tags_uuid", name="pk_release_entity_site_tag_entity"
    ),
    ForeignKeyConstraint(
        ["releases_uuid"],
        ["releases.uuid"],
        name="fk_release_entity_site_tag_entity_releases_releases_uuid",
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["tags_uuid"],
        ["tags.uuid"],
        name="fk_release_entity_site_tag_entity_tags_tags_uuid",
        ondelete="CASCADE",
    ),
    Index("ix_release_entity_site_tag_entity_tags_uuid", "tags_uuid"),
)


class Site(Base):
    """Represents a content source site."""

    __tablename__ = "sites"
    __table_args__ = (PrimaryKeyConstraint("uuid", name="pk_sites"),)

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    releases: Mapped[list[Release]] = relationship(back_populates="site")
    sub_sites: Mapped[list[SubSite]] = relationship(back_populates="site")
    performers: Mapped[list[Performer]] = relationship(back_populates="site")
    tags: Mapped[list[Tag]] = relationship(back_populates="site")
    storage_state: Mapped[StorageState | None] = relationship(back_populates="site")
    external_ids: Mapped[list[SiteExternalId]] = relationship(back_populates="site")


class SubSite(Base):
    """Represents a sub-category within a site."""

    __tablename__ = "sub_sites"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_sub_sites"),
        ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_sub_sites_sites_site_uuid",
            ondelete="CASCADE",
        ),
        Index("ix_sub_sites_site_uuid", "site_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    json_document: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    site_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Relationships
    site: Mapped[Site] = relationship(back_populates="sub_sites")
    releases: Mapped[list[Release]] = relationship(back_populates="sub_site")
    external_ids: Mapped[list[SubSiteExternalId]] = relationship(
        back_populates="sub_site"
    )


class Release(Base):
    """Represents a content release."""

    __tablename__ = "releases"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_releases"),
        ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_releases_sites_site_temp_id1",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["sub_site_uuid"],
            ["sub_sites.uuid"],
            name="fk_releases_sub_sites_sub_site_temp_id",
        ),
        Index("ix_releases_site_uuid", "site_uuid"),
        Index("ix_releases_sub_site_uuid", "sub_site_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    available_files: Mapped[dict] = mapped_column(JSON, nullable=False)
    json_document: Mapped[dict] = mapped_column(JSON, nullable=False)
    site_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sub_site_uuid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # Relationships
    site: Mapped[Site] = relationship(back_populates="releases")
    sub_site: Mapped[SubSite | None] = relationship(back_populates="releases")
    downloads: Mapped[list[Download]] = relationship(back_populates="release")
    performers: Mapped[list[Performer]] = relationship(
        secondary=release_performer, back_populates="releases"
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=release_tag, back_populates="releases"
    )
    external_ids: Mapped[list[ReleaseExternalId]] = relationship(
        back_populates="release"
    )


class Performer(Base):
    """Represents a content performer."""

    __tablename__ = "performers"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_performers"),
        ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_performers_sites_site_temp_id",
            ondelete="CASCADE",
        ),
        Index("ix_performers_site_uuid", "site_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_document: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    site_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Relationships
    site: Mapped[Site] = relationship(back_populates="performers")
    releases: Mapped[list[Release]] = relationship(
        secondary=release_performer, back_populates="performers"
    )
    external_ids: Mapped[list[PerformerExternalId]] = relationship(
        back_populates="performer"
    )


class Tag(Base):
    """Represents a content tag."""

    __tablename__ = "tags"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_tags"),
        ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_tags_sites_site_uuid",
            ondelete="CASCADE",
        ),
        Index("ix_tags_site_uuid", "site_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Relationships
    site: Mapped[Site] = relationship(back_populates="tags")
    releases: Mapped[list[Release]] = relationship(
        secondary=release_tag, back_populates="tags"
    )
    external_ids: Mapped[list[TagExternalId]] = relationship(back_populates="tag")


class Download(Base):
    """Represents a downloaded file."""

    __tablename__ = "downloads"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_downloads"),
        ForeignKeyConstraint(
            ["release_uuid"],
            ["releases.uuid"],
            name="fk_downloads_releases_release_temp_id",
            ondelete="CASCADE",
        ),
        Index("ix_downloads_release_uuid", "release_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    variant: Mapped[str] = mapped_column(Text, nullable=False)
    available_file: Mapped[dict] = mapped_column(JSON, nullable=False)
    file_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Relationships
    release: Mapped[Release] = relationship(back_populates="downloads")


class StorageState(Base):
    """Stores browser storage state for a site."""

    __tablename__ = "storage_states"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_storage_states"),
        ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_storage_states_sites_site_uuid",
            ondelete="CASCADE",
        ),
        Index("ix_storage_states_site_uuid", "site_uuid", unique=True),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    storage_state: Mapped[str] = mapped_column(Text, nullable=False)
    site_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Relationships
    site: Mapped[Site] = relationship(back_populates="storage_state")


class TargetSystem(Base):
    """Represents an external system for ID mapping (e.g., StashApp, StashDB)."""

    __tablename__ = "target_systems"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_target_systems"),
        Index("ix_target_systems_name", "name", unique=True),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SiteExternalId(Base):
    """Maps a site to an external system ID."""

    __tablename__ = "site_external_ids"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_site_external_ids"),
        ForeignKeyConstraint(
            ["site_uuid"],
            ["sites.uuid"],
            name="fk_site_external_ids_sites_site_temp_id2",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_site_external_ids_target_systems_target_system_temp_id2",
            ondelete="CASCADE",
        ),
        Index(
            "ix_site_external_ids_site_uuid_target_system_uuid",
            "site_uuid",
            "target_system_uuid",
            unique=True,
        ),
        Index("ix_site_external_ids_target_system_uuid", "target_system_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    site_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_system_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )

    # Relationships
    site: Mapped[Site] = relationship(back_populates="external_ids")
    target_system: Mapped[TargetSystem] = relationship()


class SubSiteExternalId(Base):
    """Maps a sub-site to an external system ID."""

    __tablename__ = "sub_site_external_ids"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_sub_site_external_ids"),
        ForeignKeyConstraint(
            ["sub_site_uuid"],
            ["sub_sites.uuid"],
            name="fk_sub_site_external_ids_sub_sites_sub_site_temp_id1",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_sub_site_external_ids_target_systems_target_system_temp_id3",
            ondelete="CASCADE",
        ),
        Index(
            "ix_sub_site_external_ids_sub_site_uuid_target_system_uuid",
            "sub_site_uuid",
            "target_system_uuid",
            unique=True,
        ),
        Index("ix_sub_site_external_ids_target_system_uuid", "target_system_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sub_site_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_system_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )

    # Relationships
    sub_site: Mapped[SubSite] = relationship(back_populates="external_ids")
    target_system: Mapped[TargetSystem] = relationship()


class ReleaseExternalId(Base):
    """Maps a release to an external system ID."""

    __tablename__ = "release_external_ids"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_release_external_ids"),
        ForeignKeyConstraint(
            ["release_uuid"],
            ["releases.uuid"],
            name="fk_release_external_ids_releases_release_temp_id1",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_release_external_ids_target_systems_target_system_temp_id1",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["download_uuid"],
            ["downloads.uuid"],
            name="fk_release_external_ids_downloads_download_uuid",
            ondelete="CASCADE",
        ),
        Index(
            "ix_release_external_ids_release_uuid_target_system_uuid_downlo",
            "release_uuid",
            "target_system_uuid",
            "download_uuid",
            unique=True,
        ),
        Index("ix_release_external_ids_target_system_uuid", "target_system_uuid"),
        Index("ix_release_external_ids_download_uuid", "download_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    release_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_system_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    download_uuid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # Relationships
    release: Mapped[Release] = relationship(back_populates="external_ids")
    target_system: Mapped[TargetSystem] = relationship()
    download: Mapped[Download | None] = relationship()


class PerformerExternalId(Base):
    """Maps a performer to an external system ID."""

    __tablename__ = "performer_external_ids"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_performer_external_ids"),
        ForeignKeyConstraint(
            ["performer_uuid"],
            ["performers.uuid"],
            name="fk_performer_external_ids_performers_performer_temp_id",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_performer_external_ids_target_systems_target_system_temp_id",
            ondelete="CASCADE",
        ),
        Index(
            "ix_performer_external_ids_performer_uuid_target_system_uuid",
            "performer_uuid",
            "target_system_uuid",
            unique=True,
        ),
        Index("ix_performer_external_ids_target_system_uuid", "target_system_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    performer_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_system_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )

    # Relationships
    performer: Mapped[Performer] = relationship(back_populates="external_ids")
    target_system: Mapped[TargetSystem] = relationship()


class TagExternalId(Base):
    """Maps a tag to an external system ID."""

    __tablename__ = "tag_external_ids"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", name="pk_tag_external_ids"),
        ForeignKeyConstraint(
            ["tag_uuid"],
            ["tags.uuid"],
            name="fk_tag_external_ids_tags_tag_temp_id",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_system_uuid"],
            ["target_systems.uuid"],
            name="fk_tag_external_ids_target_systems_target_system_temp_id4",
            ondelete="CASCADE",
        ),
        Index(
            "ix_tag_external_ids_tag_uuid_target_system_uuid",
            "tag_uuid",
            "target_system_uuid",
            unique=True,
        ),
        Index("ix_tag_external_ids_target_system_uuid", "target_system_uuid"),
    )

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    tag_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_system_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )

    # Relationships
    tag: Mapped[Tag] = relationship(back_populates="external_ids")
    target_system: Mapped[TargetSystem] = relationship()
