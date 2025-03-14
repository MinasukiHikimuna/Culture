from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    create_engine,
    Column,
    String,
    Integer,
    UUID,
    JSON,
    Table,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from dotenv import load_dotenv
import os
from cultureextractorscrapy.items import (
    SiteItem,
    SitePerformerItem,
    SiteTagItem,
)  # Make sure to import SiteItem
import newnewid
from sqlalchemy.orm.exc import NoResultFound
import json

load_dotenv()

Base = declarative_base()

# Junction table for releases and performers
release_performer = Table(
    "release_entity_site_performer_entity",
    Base.metadata,
    Column("releases_uuid", String(36), ForeignKey("releases.uuid")),
    Column("performers_uuid", String(36), ForeignKey("performers.uuid")),
)

# Junction table for releases and tags
release_tag = Table(
    "release_entity_site_tag_entity",
    Base.metadata,
    Column("releases_uuid", String(36), ForeignKey("releases.uuid")),
    Column("tags_uuid", String(36), ForeignKey("tags.uuid")),
)


class Site(Base):
    __tablename__ = "sites"
    uuid = Column(String(36), primary_key=True)
    short_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    releases = relationship("Release", back_populates="site")


class Release(Base):
    __tablename__ = "releases"
    uuid = Column(String(36), primary_key=True)
    release_date = Column(Date, nullable=False)
    short_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    description = Column(String, nullable=False)
    duration = Column(Float, nullable=False)
    created = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, nullable=False)
    available_files = Column(String, nullable=False)
    json_document = Column(String, nullable=False)
    site_uuid = Column(String(36), ForeignKey("sites.uuid"), nullable=False)
    site = relationship("Site", back_populates="releases")
    downloads = relationship("DownloadedFile", back_populates="release")
    performers = relationship(
        "Performer", secondary=release_performer, back_populates="releases"
    )
    tags = relationship("Tag", secondary=release_tag, back_populates="releases")


class Performer(Base):
    __tablename__ = "performers"
    uuid = Column(String(36), primary_key=True)
    short_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    site_uuid = Column(String(36), ForeignKey("sites.uuid"), nullable=False)
    releases = relationship(
        "Release",
        secondary=release_performer,
        back_populates="performers",
        overlaps="performers",
    )


class Tag(Base):
    __tablename__ = "tags"
    uuid = Column(String(36), primary_key=True)
    short_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    site_uuid = Column(String(36), ForeignKey("sites.uuid"), nullable=False)
    releases = relationship(
        "Release", secondary=release_tag, back_populates="tags", overlaps="tags"
    )


class DownloadedFile(Base):
    __tablename__ = "downloads"

    uuid = Column(UUID, primary_key=True)
    downloaded_at = Column(DateTime, nullable=False)
    file_type = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    variant = Column(String, nullable=False)
    available_file = Column(JSON, nullable=False)
    original_filename = Column(String)
    saved_filename = Column(String)
    release_uuid = Column(UUID, ForeignKey("releases.uuid"), nullable=False)
    file_metadata = Column(JSON, nullable=False, default="{}")

    release = relationship("Release", back_populates="downloads")


def get_engine():
    db_url = os.getenv("CONNECTION_STRING")
    return create_engine(db_url)


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def get_sites():
    session = get_session()
    sites = session.query(Site).all()
    session.close()
    return sites


def save_release(release):
    session = get_session()
    session.add(release)
    session.commit()
    session.close()


def get_existing_release_short_names(site_uuid):
    session = get_session()
    releases = (
        session.query(Release.short_name, Release.uuid)
        .filter(Release.site_uuid == site_uuid)
        .all()
    )
    result = {r.short_name: r.uuid for r in releases}
    session.close()
    return result


def get_site_item(site_short_name):
    session = get_session()
    site = session.query(Site).filter_by(short_name=site_short_name).first()
    session.close()
    if site:
        return SiteItem(
            id=site.uuid, short_name=site.short_name, name=site.name, url=site.url
        )
    return None


def get_or_create_performer(site_uuid, short_name, name, url):
    session = get_session()
    try:
        performer = (
            session.query(Performer)
            .filter_by(site_uuid=site_uuid, short_name=short_name)
            .one()
        )
    except NoResultFound:
        performer = Performer(
            uuid=newnewid.uuid7(),
            site_uuid=site_uuid,
            short_name=short_name,
            name=name,
            url=url,
        )
        session.add(performer)
        session.commit()
    finally:
        site_performer_item = SitePerformerItem(
            id=performer.uuid,
            short_name=performer.short_name,
            name=performer.name,
            url=performer.url,
            site_uuid=performer.site_uuid,
        )
        session.close()
        return site_performer_item


def get_or_create_tag(site_uuid, short_name, name, url):
    session = get_session()
    try:
        tag = (
            session.query(Tag)
            .filter_by(site_uuid=site_uuid, short_name=short_name)
            .one()
        )
    except NoResultFound:
        tag = Tag(
            uuid=newnewid.uuid7(),
            site_uuid=site_uuid,
            short_name=short_name,
            name=name,
            url=url,
        )
        session.add(tag)
        session.commit()
    finally:
        site_tag_item = SiteTagItem(
            id=tag.uuid,
            short_name=tag.short_name,
            name=tag.name,
            url=tag.url,
            site_uuid=tag.site_uuid,
        )
        session.close()
        return site_tag_item


def get_existing_releases_with_status(site_uuid):
    session = get_session()
    releases = (
        session.query(
            Release.short_name,
            Release.uuid,
            Release.available_files,
            DownloadedFile.file_type,
            DownloadedFile.content_type,
            DownloadedFile.variant,
        )
        .outerjoin(DownloadedFile)
        .filter(Release.site_uuid == site_uuid)
        .all()
    )

    result = {}
    for r in releases:
        if r.short_name not in result:
            if isinstance(r.available_files, str):
                available_files = json.loads(r.available_files)
            else:
                available_files = r.available_files or []

            result[r.short_name] = {
                "uuid": r.uuid,
                "available_files": available_files,
                "downloaded_files": set(),
            }

        if r.file_type and r.content_type and r.variant:
            result[r.short_name]["downloaded_files"].add(
                (r.file_type, r.content_type, r.variant)
            )

    session.close()
    return result
