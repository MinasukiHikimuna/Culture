from sqlalchemy import Date, DateTime, Float, ForeignKey, create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from dotenv import load_dotenv
import os
from cultureextractorscrapy.items import SiteItem, SitePerformerItem  # Make sure to import SiteItem
import newnewid
from sqlalchemy.orm.exc import NoResultFound

load_dotenv()

Base = declarative_base()

class Site(Base):
    __tablename__ = 'sites'
    uuid = Column(String(36), primary_key=True)
    short_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    releases = relationship("Release", back_populates="site")

class Release(Base):
    __tablename__ = 'releases'
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
    site_uuid = Column(String(36), ForeignKey('sites.uuid'), nullable=False)
    site = relationship("Site", back_populates="releases")

class Performer(Base):
    __tablename__ = 'performers'
    uuid = Column(String(36), primary_key=True)
    short_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    site_uuid = Column(String(36), ForeignKey('sites.uuid'), nullable=False)

def get_engine():
    db_url = os.getenv('CONNECTION_STRING')
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
    short_names = set(
        r.short_name for r in session.query(Release.short_name)
        .filter(Release.site_uuid == site_uuid)
        .all()
    )
    session.close()
    return short_names

def get_site_item(site_short_name):
    session = get_session()
    site = session.query(Site).filter_by(short_name=site_short_name).first()
    session.close()
    if site:
        return SiteItem(
            id=site.uuid,
            short_name=site.short_name,
            name=site.name,
            url=site.url
        )
    return None

def get_or_create_performer(site_uuid, short_name, name, url):
    session = get_session()
    try:
        performer = session.query(Performer).filter_by(site_uuid=site_uuid, short_name=short_name).one()
    except NoResultFound:
        performer = Performer(
            uuid=newnewid.uuid7(),
            site_uuid=site_uuid,
            short_name=short_name,
            name=name,
            url=url
        )
        session.add(performer)
        session.commit()
    finally:
        site_performer_item = SitePerformerItem(
            id=performer.uuid,
            short_name=performer.short_name,
            name=performer.name,
            url=performer.url,
            site_uuid=performer.site_uuid
        )
        session.close()
        return site_performer_item
