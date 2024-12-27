import pandas as pd
import psycopg
import polars as pl
import json


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

            # Convert UUID objects to strings
            sites_rows = [(str(row[0]), row[1], row[2], row[3]) for row in sites_rows]

            schema = {
                "ce_sites_uuid": pl.Utf8,
                "ce_sites_short_name": pl.Utf8,
                "ce_sites_name": pl.Utf8,
                "ce_sites_url": pl.Utf8,
            }

            df_sites = pl.DataFrame(
                sites_rows,
                schema=schema,
            )

            return df_sites


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
                    COALESCE(NULLIF(releases.release_date, '-infinity'), '1970-01-01'::date) as release_date,
                    releases.short_name AS release_short_name, 
                    releases.name AS release_name, 
                    releases.url AS release_url,
                    releases.description AS release_description,
                    releases.created AS release_created,
                    releases.last_updated AS release_last_updated,
                    releases.available_files::text AS release_available_files,
                    releases.json_document::text AS release_json_document,
                    downloads.uuid AS downloads_uuid,
                    downloads.downloaded_at AS downloads_downloaded_at,
                    downloads.file_type,
                    downloads.content_type,
                    downloads.variant AS downloads_variant,
                    downloads.available_file::text AS downloads_available_file,
                    downloads.original_filename AS downloads_original_filename,
                    downloads.saved_filename AS downloads_saved_filename,
                    downloads.file_metadata::text AS downloads_file_metadata,
                    -- Aggregate performers into a JSON array of objects
                    json_agg(
                        DISTINCT jsonb_build_object(
                            'uuid', performers.uuid,
                            'short_name', performers.short_name,
                            'name', performers.name,
                            'url', performers.url
                        ) 
                    ) FILTER (WHERE performers.uuid IS NOT NULL) as performers,
                    -- Aggregate tags into an array  
                    array_agg(DISTINCT jsonb_build_object(
                        'uuid', tags.uuid,
                        'short_name', tags.short_name,
                        'name', tags.name,
                        'url', tags.url
                    )) FILTER (WHERE tags.name IS NOT NULL) as tags
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
