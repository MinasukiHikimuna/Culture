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

    def get_downloads(self, site_uuid: str) -> pl.DataFrame:
        with self.connection.cursor() as cursor:
            # Get site info
            cursor.execute("""
                SELECT name, uuid 
                FROM sites 
                WHERE sites.uuid = %s
            """, (site_uuid,))
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()
            site_name = site_row[0]

            # Get all releases for the site
            cursor.execute("""
                SELECT 
                    uuid,
                    NULLIF(release_date, '-infinity') as release_date,
                    short_name,
                    name,
                    url,
                    description,
                    NULLIF(created, '-infinity') as created,
                    NULLIF(last_updated, '-infinity') as last_updated,
                    available_files::text,
                    json_document::text,
                    sub_site_uuid
                FROM releases 
                WHERE site_uuid = %s
            """, (site_uuid,))
            releases = {row[0]: row for row in cursor.fetchall()}

            # Get sub_sites info
            sub_site_uuids = {row[10] for row in releases.values() if row[10] is not None}
            sub_sites = {}
            if sub_site_uuids:
                cursor.execute("""
                    SELECT uuid, name 
                    FROM sub_sites 
                    WHERE uuid = ANY(%s)
                """, (list(sub_site_uuids),))
                sub_sites = dict(cursor.fetchall())

            # Get downloads
            cursor.execute("""
                SELECT r.uuid AS release_uuid,
                    d.uuid AS download_uuid,
                    d.downloaded_at,
                    d.file_type,
                    d.content_type,
                    d.variant,
                    d.available_file,
                    d.original_filename,
                    d.saved_filename,
                    d.file_metadata
                FROM downloads d
                JOIN releases r ON r.uuid = d.release_uuid
                WHERE r.site_uuid = %s
                ORDER BY r.uuid
            """, (site_uuid,))
            downloads_rows = cursor.fetchall()

            # Get performers
            cursor.execute("""
                SELECT r.uuid, json_agg(
                    json_build_object(
                        'uuid', p.uuid,
                        'short_name', p.short_name,
                        'name', p.name,
                        'url', p.url
                    )
                )
                FROM performers p
                JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                JOIN releases r ON resp.releases_uuid = r.uuid
                WHERE r.site_uuid = %s
                GROUP BY r.uuid
            """, (site_uuid,))
            performers = dict(cursor.fetchall())

            # Get tags
            cursor.execute("""
                SELECT r.uuid, json_agg(
                    json_build_object(
                        'uuid', t.uuid,
                        'short_name', t.short_name,
                        'name', t.name,
                        'url', t.url
                    )
                )
                FROM tags t
                JOIN release_entity_site_tag_entity rest ON t.uuid = rest.tags_uuid
                JOIN releases r ON rest.releases_uuid = r.uuid
                WHERE r.site_uuid = %s
                GROUP BY r.uuid
            """, (site_uuid,))
            tags = dict(cursor.fetchall())

            def convert_uuids_to_str(obj):
                """Helper function to convert UUIDs to strings in nested structures"""
                if isinstance(obj, dict):
                    return {k: convert_uuids_to_str(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_uuids_to_str(item) for item in obj]
                elif hasattr(obj, 'hex'):  # UUID objects have a hex attribute
                    return str(obj)
                return obj

            # Combine all data
            downloads = []
            for row in downloads_rows:
                release_uuid = row[0]
                release = releases[release_uuid]
                
                # Parse available_file JSON if it's a string
                available_file = row[6]
                if isinstance(available_file, str):
                    try:
                        available_file = json.loads(available_file)
                    except json.JSONDecodeError:
                        available_file = None
                available_file = convert_uuids_to_str(available_file)

                # Parse file_metadata JSON if it's a string
                file_metadata = row[9]
                if isinstance(file_metadata, str):
                    try:
                        file_metadata = json.loads(file_metadata)
                    except json.JSONDecodeError:
                        file_metadata = {}
                file_metadata = convert_uuids_to_str(file_metadata)

                download_data = {
                    "ce_downloads_site_name": site_name,
                    "ce_downloads_sub_site_name": sub_sites.get(release[10]) if release[10] else None,
                    "ce_downloads_release_uuid": str(release_uuid),
                    "ce_downloads_release_date": release[1],
                    "ce_downloads_release_short_name": release[2],
                    "ce_downloads_release_name": release[3],
                    "ce_downloads_release_url": release[4],
                    "ce_downloads_release_description": release[5],
                    "ce_downloads_release_created": release[6],
                    "ce_downloads_release_last_updated": release[7],
                    "ce_downloads_release_available_files": release[8],
                    "ce_downloads_release_json_document": release[9],
                    "ce_downloads_uuid": str(row[1]),
                    "ce_downloads_downloaded_at": row[2],
                    "ce_downloads_file_type": row[3],
                    "ce_downloads_content_type": row[4],
                    "ce_downloads_variant": row[5],
                    "ce_downloads_available_file": json.dumps(available_file) if available_file else None,
                    "ce_downloads_original_filename": row[7],
                    "ce_downloads_saved_filename": row[8],
                    "ce_downloads_file_metadata": json.dumps(file_metadata) if file_metadata else None,
                    "ce_downloads_performers": performers.get(release_uuid, []),
                    "ce_downloads_tags": tags.get(release_uuid, []),
                    "ce_downloads_hash_oshash": file_metadata.get("oshash"),
                    "ce_downloads_hash_phash": file_metadata.get("phash"),
                    "ce_downloads_hash_sha256": file_metadata.get("sha256Sum"),
                }
                downloads.append(download_data)

            # Schema remains the same as before
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

            return pl.DataFrame(downloads, schema=schema)
