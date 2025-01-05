import psycopg
import polars as pl
import json


class ClientCultureExtractor:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.connection = psycopg.connect(connection_string)

    def __del__(self):
        if hasattr(self, "connection") and not self.connection.closed:
            self.connection.close()

    def get_sites(self) -> pl.DataFrame:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    uuid AS ce_sites_uuid,
                    short_name AS ce_sites_short_name,
                    name AS ce_sites_name,
                    url AS ce_sites_url
                FROM sites
                ORDER BY name
                """
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
        
    def get_sub_sites(self) -> pl.DataFrame:
        with self.connection.cursor() as cursor:
            cursor.execute("""
                           SELECT
                                sites.uuid AS ce_sites_uuid,
                                sites.short_name AS ce_sites_short_name,
                                sites.name AS ce_sites_name,
                                sites.url AS ce_sites_url,
                                sub_sites.uuid AS ce_sub_sites_uuid,
                                sub_sites.short_name AS ce_sub_sites_short_name,
                                sub_sites.name AS ce_sub_sites_name
                                FROM sub_sites
                                JOIN sites ON sub_sites.site_uuid = sites.uuid
                                ORDER BY sites.name, sub_sites.name
                           """)
            sub_sites_rows = cursor.fetchall()
            
            sub_sites = [
                {
                    "ce_sites_uuid": str(row[0]),
                    "ce_sites_short_name": row[1],
                    "ce_sites_name": row[2],
                    "ce_sites_url": row[3],
                    "ce_sub_sites_uuid": str(row[4]),
                    "ce_sub_sites_short_name": row[5],
                    "ce_sub_sites_name": row[6],
                }
                for row in sub_sites_rows
            ]
            
            schema = {
                "ce_sites_uuid": pl.Utf8,
                "ce_sites_short_name": pl.Utf8,
                "ce_sites_name": pl.Utf8,
                "ce_sites_url": pl.Utf8,
                "ce_sub_sites_uuid": pl.Utf8,
                "ce_sub_sites_short_name": pl.Utf8,
                "ce_sub_sites_name": pl.Utf8,
            }
            
            return pl.DataFrame(sub_sites, schema=schema)

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
                    "ce_downloads_release_available_files": row[10],
                    "ce_downloads_release_json_document": row[11],
                    "ce_downloads_uuid": str(row[12]),
                    "ce_downloads_downloaded_at": row[13],
                    "ce_downloads_file_type": row[14],
                    "ce_downloads_content_type": row[15],
                    "ce_downloads_variant": row[16],
                    "ce_downloads_available_file": row[17],
                    "ce_downloads_original_filename": row[18],
                    "ce_downloads_saved_filename": row[19],
                    "ce_downloads_file_metadata": row[20],
                    "ce_downloads_performers": [
                        {
                            "uuid": p["uuid"],
                            "short_name": p["short_name"],
                            "name": p["name"],
                            "url": p["url"]
                        }
                        for p in row[21]
                    ],
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
                "ce_downloads_release_available_files": pl.Utf8,
                "ce_downloads_release_json_document": pl.Utf8,
                "ce_downloads_uuid": pl.Utf8,
                "ce_downloads_downloaded_at": pl.Datetime,
                "ce_downloads_file_type": pl.Utf8,
                "ce_downloads_content_type": pl.Utf8,
                "ce_downloads_variant": pl.Utf8,
                "ce_downloads_available_file": pl.Utf8,
                "ce_downloads_original_filename": pl.Utf8,
                "ce_downloads_saved_filename": pl.Utf8,
                "ce_downloads_file_metadata": pl.Utf8,
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
