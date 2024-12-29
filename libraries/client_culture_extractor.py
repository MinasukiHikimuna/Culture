import pandas as pd
import psycopg
import polars as pl
import json
from datetime import datetime


class ClientCultureExtractorPolars:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.connection = psycopg.connect(connection_string)

    def __del__(self):
        if hasattr(self, "connection") and not self.connection.closed:
            self.connection.close()

    def get_sites(self) -> pl.DataFrame:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT uuid AS ce_sites_uuid, short_name AS ce_sites_short_name, name AS ce_sites_name, url AS ce_sites_url FROM sites"
            )

            sites_rows = cursor.fetchall()

            sites = [
                {
                    "ce_sites_uuid": str(row[0]),
                    "ce_sites_short_name": row[1],
                    "ce_sites_name": row[2],
                    "ce_sites_url": row[3],
                }
                for row in sites_rows
            ]

            schema = {
                "ce_sites_uuid": pl.Utf8,
                "ce_sites_short_name": pl.Utf8,
                "ce_sites_name": pl.Utf8,
                "ce_sites_url": pl.Utf8,
            }

            df_sites = pl.DataFrame(sites, schema=schema)
            return df_sites

    def get_downloads(self, site_name: str) -> pl.DataFrame:
        with self.connection.cursor() as cursor:
            query = """
                SELECT 
                    sites.name AS site_name,
                    sub_sites.name AS sub_site_name,
                    releases.uuid AS release_uuid,
                    NULLIF(releases.release_date, '-infinity') as release_date,
                    releases.short_name AS release_short_name, 
                    releases.name AS release_name, 
                    releases.url AS release_url,
                    releases.description AS release_description,
                    NULLIF(releases.created, '-infinity') as created,
                    NULLIF(releases.last_updated, '-infinity') as last_updated,
                    releases.available_files::text AS release_available_files,
                    releases.json_document::text AS release_json_document,
                    downloads.uuid AS downloads_uuid,
                    NULLIF(downloads.downloaded_at, '-infinity') as downloaded_at,
                    downloads.file_type,
                    downloads.content_type,
                    downloads.variant AS downloads_variant,
                    downloads.available_file::text AS downloads_available_file,
                    downloads.original_filename AS downloads_original_filename,
                    downloads.saved_filename AS downloads_saved_filename,
                    downloads.file_metadata::text AS downloads_file_metadata,
                    -- Aggregate performers into a JSON array of objects
                    COALESCE(json_agg(
                        DISTINCT jsonb_build_object(
                            'uuid', performers.uuid,
                            'short_name', performers.short_name,
                            'name', performers.name,
                            'url', performers.url
                        ) 
                    ) FILTER (WHERE performers.uuid IS NOT NULL), '[]') as performers,
                    -- Aggregate tags into an array  
                    COALESCE(json_agg(DISTINCT jsonb_build_object(
                        'uuid', tags.uuid,
                        'short_name', tags.short_name,
                        'name', tags.name,
                        'url', tags.url
                    )) FILTER (WHERE tags.name IS NOT NULL), '[]') as tags
                FROM releases
                JOIN sites ON releases.site_uuid = sites.uuid
                JOIN downloads ON releases.uuid = downloads.release_uuid
                LEFT JOIN sub_sites ON releases.sub_site_uuid = sub_sites.uuid
                -- Left join performers through junction table
                LEFT JOIN release_entity_site_performer_entity rep ON releases.uuid = rep.releases_uuid
                LEFT JOIN performers ON rep.performers_uuid = performers.uuid
                -- Left join tags through junction table
                LEFT JOIN release_entity_site_tag_entity ret ON releases.uuid = ret.releases_uuid
                LEFT JOIN tags ON ret.tags_uuid = tags.uuid
                WHERE sites.name = %s
                GROUP BY
                    sites.name,
                    sub_sites.name,
                    releases.uuid,
                    releases.release_date,
                    releases.short_name,
                    releases.name,
                    releases.url,
                    releases.description,
                    releases.created,
                    releases.last_updated,
                    releases.available_files::text,
                    releases.json_document::text,
                    downloads.uuid,
                    downloads.downloaded_at,
                    downloads.file_type,
                    downloads.content_type,
                    downloads.variant,
                    downloads.available_file::text,
                    downloads.original_filename,
                    downloads.saved_filename,
                    downloads.file_metadata::text
            """
            cursor.execute(query, (site_name,))
            downloads_rows = cursor.fetchall()

            if not downloads_rows:
                return pl.DataFrame(schema=schema)

            downloads = [
                {
                    "ce_downloads_site_name": row[0],
                    "ce_downloads_sub_site_name": row[1],
                    "ce_downloads_release_uuid": str(row[2]),
                    "ce_downloads_release_date": row[3],
                    "ce_downloads_release_short_name": row[4],
                    "ce_downloads_release_name": row[5],
                    "ce_downloads_release_url": row[6],
                    "ce_downloads_release_description": row[7],
                    "ce_downloads_release_created": row[8],
                    "ce_downloads_release_last_updated": row[9],
                    "ce_downloads_release_available_files": (
                        json.loads(row[10]) if isinstance(row[10], str) else None
                    ),
                    "ce_downloads_release_json_document": (
                        json.loads(row[11]) if isinstance(row[11], str) else None
                    ),
                    "ce_downloads_uuid": str(row[12]),
                    "ce_downloads_downloaded_at": row[13],
                    "ce_downloads_file_type": row[14],
                    "ce_downloads_content_type": row[15],
                    "ce_downloads_variant": row[16],
                    "ce_downloads_available_file": (
                        json.loads(row[17]) if isinstance(row[17], str) else None
                    ),
                    "ce_downloads_original_filename": row[18],
                    "ce_downloads_saved_filename": row[19],
                    "ce_downloads_file_metadata": (
                        json.loads(row[20]) if isinstance(row[20], str) else None
                    ),
                    "ce_downloads_performers": row[21],
                    "ce_downloads_tags": row[22],
                    "ce_downloads_hash_oshash": (
                        json.loads(row[20]).get("oshash")
                        if isinstance(row[20], str)
                        else None
                    ),
                    "ce_downloads_hash_phash": (
                        json.loads(row[20]).get("phash")
                        if isinstance(row[20], str)
                        else None
                    ),
                    "ce_downloads_hash_sha256": (
                        json.loads(row[20]).get("sha256Sum")
                        if isinstance(row[20], str)
                        else None
                    ),
                }
                for row in downloads_rows
            ]

            schema = {
                "ce_downloads_site_name": pl.Utf8,
                "ce_downloads_sub_site_name": pl.Utf8,
                "ce_downloads_release_uuid": pl.Utf8,
                "ce_downloads_release_date": pl.Date,
                "ce_downloads_release_short_name": pl.Utf8,
                "ce_downloads_release_name": pl.Utf8,
                "ce_downloads_release_url": pl.Utf8,
                "ce_downloads_release_description": pl.Utf8,
                "ce_downloads_release_created": pl.Datetime,
                "ce_downloads_release_last_updated": pl.Datetime,
                "ce_downloads_release_downloaded_at": pl.Datetime,
                "ce_downloads_release_available_files": pl.List,
                "ce_downloads_release_json_document": pl.Object,
                "ce_downloads_uuid": pl.Utf8,
                "ce_downloads_downloaded_at": pl.Datetime,
                "ce_downloads_file_type": pl.Utf8,
                "ce_downloads_content_type": pl.Utf8,
                "ce_downloads_variant": pl.Utf8,
                "ce_downloads_available_file": pl.Object,
                "ce_downloads_original_filename": pl.Utf8,
                "ce_downloads_saved_filename": pl.Utf8,
                "ce_downloads_file_metadata": pl.Object,
                "ce_downloads_performers": pl.List(
                    pl.Struct(
                        {
                            "uuid": pl.Utf8,
                            "short_name": pl.Utf8,
                            "name": pl.Utf8,
                            "url": pl.Utf8,
                        }
                    )
                ),
                "ce_downloads_tags": pl.List(
                    pl.Struct(
                        {
                            "uuid": pl.Utf8,
                            "short_name": pl.Utf8,
                            "name": pl.Utf8,
                            "url": pl.Utf8,
                        }
                    )
                ),
                "ce_downloads_hash_oshash": pl.Utf8,
                "ce_downloads_hash_phash": pl.Utf8,
                "ce_downloads_hash_sha256": pl.Utf8,
            }

            df_downloads = pl.DataFrame(downloads, schema=schema)
            return df_downloads


class ClientCultureExtractor:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.connection = psycopg.connect(connection_string)

    def __del__(self):
        if hasattr(self, "connection") and not self.connection.closed:
            self.connection.close()

    def get_sites(self) -> pd.DataFrame:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT uuid, short_name, name, url FROM sites")

            sites_rows = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            df_sites = pd.DataFrame(sites_rows, columns=column_names)
            df_sites = df_sites.add_prefix("ce_sites_")

            return df_sites

    def get_downloads(self, site_name: str) -> pd.DataFrame:
        with self.connection.cursor() as cursor:
            query = """
                SELECT 
                    sites.name AS site_name,
                    sub_sites.name AS sub_site_name,
                    releases.uuid AS release_uuid,
                    NULLIF(releases.release_date, '-infinity') as release_date,
                    releases.short_name AS release_short_name, 
                    releases.name AS release_name, 
                    releases.url AS release_url,
                    releases.description AS release_description,
                    NULLIF(releases.created, '-infinity') as created,
                    NULLIF(releases.last_updated, '-infinity') as last_updated,
                    releases.available_files::text AS release_available_files,
                    releases.json_document::text AS release_json_document,
                    downloads.uuid AS downloads_uuid,
                    NULLIF(downloads.downloaded_at, '-infinity') as downloaded_at,
                    downloads.file_type,
                    downloads.content_type,
                    downloads.variant AS downloads_variant,
                    downloads.available_file::text AS downloads_available_file,
                    downloads.original_filename AS downloads_original_filename,
                    downloads.saved_filename AS downloads_saved_filename,
                    downloads.file_metadata::text AS downloads_file_metadata,
                    -- Aggregate performers into a JSON array of objects
                    COALESCE(json_agg(
                        DISTINCT jsonb_build_object(
                            'uuid', performers.uuid,
                            'short_name', performers.short_name,
                            'name', performers.name,
                            'url', performers.url
                        ) 
                    ) FILTER (WHERE performers.uuid IS NOT NULL), '[]') as performers,
                    -- Aggregate tags into an array  
                    COALESCE(json_agg(DISTINCT jsonb_build_object(
                        'uuid', tags.uuid,
                        'short_name', tags.short_name,
                        'name', tags.name,
                        'url', tags.url
                    )) FILTER (WHERE tags.name IS NOT NULL), '[]') as tags
                FROM releases
                JOIN sites ON releases.site_uuid = sites.uuid
                JOIN downloads ON releases.uuid = downloads.release_uuid
                LEFT JOIN sub_sites ON releases.sub_site_uuid = sub_sites.uuid
                -- Left join performers through junction table
                LEFT JOIN release_entity_site_performer_entity rep ON releases.uuid = rep.releases_uuid
                LEFT JOIN performers ON rep.performers_uuid = performers.uuid
                -- Left join tags through junction table
                LEFT JOIN release_entity_site_tag_entity ret ON releases.uuid = ret.releases_uuid
                LEFT JOIN tags ON ret.tags_uuid = tags.uuid
                WHERE sites.name = %s
                GROUP BY
                    sites.name,
                    sub_sites.name,
                    releases.uuid,
                    releases.release_date,
                    releases.short_name,
                    releases.name,
                    releases.url,
                    releases.description,
                    releases.created,
                    releases.last_updated,
                    releases.available_files::text,
                    releases.json_document::text,
                    downloads.uuid,
                    downloads.downloaded_at,
                    downloads.file_type,
                    downloads.content_type,
                    downloads.variant,
                    downloads.available_file::text,
                    downloads.original_filename,
                    downloads.saved_filename,
                    downloads.file_metadata::text
            """
            cursor.execute(query, (site_name,))

            downloads = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            df_downloads = pd.DataFrame(downloads, columns=column_names)

            # Convert date and datetime columns
            df_downloads["release_date"] = pd.to_datetime(df_downloads["release_date"])
            df_downloads["release_created"] = pd.to_datetime(
                df_downloads["release_created"]
            )
            df_downloads["release_last_updated"] = pd.to_datetime(
                df_downloads["release_last_updated"]
            )
            df_downloads["downloads_downloaded_at"] = pd.to_datetime(
                df_downloads["downloads_downloaded_at"]
            )

            # Convert JSON string fields to Python objects
            json_fields = [
                "release_available_files",
                "release_json_document",
                "downloads_available_file",
                "downloads_file_metadata",
                "performers",
                "tags",
            ]
            for field in json_fields:
                df_downloads[field] = df_downloads[field].apply(
                    lambda x: json.loads(x) if isinstance(x, str) else x
                )

            # Extract hash fields from file_metadata
            df_downloads["hash_sha256"] = df_downloads["downloads_file_metadata"].apply(
                lambda x: x.get("sha256Sum") if isinstance(x, dict) else None
            )
            df_downloads["hash_phash"] = df_downloads["downloads_file_metadata"].apply(
                lambda x: x.get("phash") if isinstance(x, dict) else None
            )
            df_downloads["hash_oshash"] = df_downloads["downloads_file_metadata"].apply(
                lambda x: x.get("oshash") if isinstance(x, dict) else None
            )

            df_downloads = df_downloads.add_prefix("ce_downloads_")

            return df_downloads
