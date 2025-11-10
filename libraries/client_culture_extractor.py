import json
import uuid

import polars as pl
import psycopg


class ClientCultureExtractor:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.connection = psycopg.connect(connection_string)

    def __del__(self):
        if hasattr(self, "connection") and not self.connection.closed:
            self.connection.close()

    def get_database_schema(self) -> pl.DataFrame:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    table_name,
                    column_name,
                    data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, column_name
            """
            )
            schema_rows = cursor.fetchall()

            schema = {
                "table_name": pl.Utf8,
                "column_name": pl.Utf8,
                "data_type": pl.Utf8,
            }

            return pl.DataFrame(schema_rows, schema=schema, orient="row")

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
            cursor.execute(
                """
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
                           """
            )
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

    def get_releases(
        self,
        site_uuid: str,
        tag_uuid: str | None = None,
        performer_uuid: str | None = None,
    ) -> pl.DataFrame:
        """Get all releases for a given site UUID, optionally filtered by tag and/or performer.

        Args:
            site_uuid: UUID of the site to get releases for
            tag_uuid: Optional tag UUID to filter releases by
            performer_uuid: Optional performer UUID to filter releases by

        Returns:
            DataFrame containing all releases for the site
        """
        with self.connection.cursor() as cursor:
            # Get site info
            cursor.execute(
                """
                SELECT name, uuid
                FROM sites
                WHERE sites.uuid = %s
            """,
                (site_uuid,),
            )
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()
            site_name = site_row[0]

            # Build WHERE clause based on filters
            if tag_uuid and performer_uuid:
                # Filter by both tag and performer
                return self._get_releases_by_query(
                    cursor,
                    """WHERE site_uuid = %s
                       AND uuid IN (
                           SELECT releases_uuid
                           FROM release_entity_site_tag_entity
                           WHERE tags_uuid = %s
                       )
                       AND uuid IN (
                           SELECT releases_uuid
                           FROM release_entity_site_performer_entity
                           WHERE performers_uuid = %s
                       )""",
                    (site_uuid, tag_uuid, performer_uuid),
                    site_name=site_name,
                    site_uuid=site_uuid,
                )

            if tag_uuid:
                # Filter releases by tag only
                return self._get_releases_by_query(
                    cursor,
                    """WHERE site_uuid = %s
                       AND uuid IN (
                           SELECT releases_uuid
                           FROM release_entity_site_tag_entity
                           WHERE tags_uuid = %s
                       )""",
                    (site_uuid, tag_uuid),
                    site_name=site_name,
                    site_uuid=site_uuid,
                )

            if performer_uuid:
                # Filter releases by performer only
                return self._get_releases_by_query(
                    cursor,
                    """WHERE site_uuid = %s
                       AND uuid IN (
                           SELECT releases_uuid
                           FROM release_entity_site_performer_entity
                           WHERE performers_uuid = %s
                       )""",
                    (site_uuid, performer_uuid),
                    site_name=site_name,
                    site_uuid=site_uuid,
                )

            return self._get_releases_by_query(
                cursor,
                "WHERE site_uuid = %s",
                (site_uuid,),
                site_name=site_name,
                site_uuid=site_uuid,
            )

    def get_release_by_uuid(self, release_uuid: str) -> pl.DataFrame:
        """Get a specific release by its UUID.

        Args:
            release_uuid: UUID of the release to get

        Returns:
            DataFrame containing the release data
        """
        with self.connection.cursor() as cursor:
            # First get the site info for this release
            cursor.execute(
                """
                SELECT s.name, s.uuid
                FROM sites s
                JOIN releases r ON r.site_uuid = s.uuid
                WHERE r.uuid = %s
                """,
                (release_uuid,),
            )
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()
            site_name = site_row[0]
            site_uuid = site_row[1]

            return self._get_releases_by_query(
                cursor,
                "WHERE uuid = %s",
                (release_uuid,),
                site_name=site_name,
                site_uuid=site_uuid,
            )

    def _get_releases_by_query(
        self, cursor, where_clause: str, params: tuple, site_name: str, site_uuid: str
    ) -> pl.DataFrame:
        """Internal method to get releases based on a WHERE clause.

        Args:
            cursor: Database cursor
            where_clause: SQL WHERE clause to filter releases
            params: Parameters for the WHERE clause
            site_name: Name of the site
            site_uuid: UUID of the site

        Returns:
            DataFrame containing the matching releases
        """
        cursor.execute(
            f"""
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
                site_uuid
            FROM releases
            {where_clause}
        """,
            params,
        )
        releases_rows = cursor.fetchall()

        # Combine all data
        releases = []
        for row in releases_rows:
            release_uuid = row[0]

            # Parse available_file JSON if it's a string
            available_files = row[8]
            if isinstance(available_files, str):
                try:
                    available_files = json.loads(available_files)
                except json.JSONDecodeError:
                    available_files = None

            # Parse file_metadata JSON if it's a string
            file_metadata = row[9]
            if isinstance(file_metadata, str):
                try:
                    file_metadata = json.loads(file_metadata)
                except json.JSONDecodeError:
                    file_metadata = {}

            release_data = {
                "ce_site_uuid": str(site_uuid),
                "ce_site_name": site_name,
                "ce_release_uuid": str(release_uuid),
                "ce_release_date": row[1],
                "ce_release_short_name": row[2],
                "ce_release_name": row[3],
                "ce_release_url": row[4],
                "ce_release_description": row[5],
                "ce_release_created": row[6],
                "ce_release_last_updated": row[7],
                "ce_release_available_files": row[8],
                "ce_release_json_document": row[9],
            }
            releases.append(release_data)

        schema = {
            "ce_site_uuid": pl.Utf8,
            "ce_site_name": pl.Utf8,
            "ce_release_uuid": pl.Utf8,
            "ce_release_date": pl.Date,
            "ce_release_short_name": pl.Utf8,
            "ce_release_name": pl.Utf8,
            "ce_release_url": pl.Utf8,
            "ce_release_description": pl.Utf8,
            "ce_release_created": pl.Datetime,
            "ce_release_last_updated": pl.Datetime,
            "ce_release_available_files": pl.Utf8,
            "ce_release_json_document": pl.Utf8,
        }

        return pl.DataFrame(releases, schema=schema)

    def get_downloads(self, site_uuid: str, sub_site_uuid: str | None = None) -> pl.DataFrame:
        with self.connection.cursor() as cursor:
            # Get site info
            cursor.execute(
                """
                SELECT name, uuid
                FROM sites
                WHERE sites.uuid = %s
            """,
                (site_uuid,),
            )
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()
            site_name = site_row[0]

            # Get sub_site info conditionally
            if sub_site_uuid:
                cursor.execute(
                    """
                    SELECT name, uuid
                    FROM sub_sites
                    WHERE uuid = %s
                """,
                    (sub_site_uuid,),
                )
                sub_site_row = cursor.fetchone()
                if not sub_site_row:
                    return pl.DataFrame()
                sub_site_row[0]

            # Get all releases for the site
            if not sub_site_uuid:
                cursor.execute(
                    """
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
                """,
                    (site_uuid,),
                )
            else:
                cursor.execute(
                    """
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
                    WHERE site_uuid = %s AND sub_site_uuid = %s
                """,
                    (site_uuid, sub_site_uuid),
                )

            releases = {row[0]: row for row in cursor.fetchall()}

            # Get sub_sites info
            sub_site_uuids = {
                row[10] for row in releases.values() if row[10] is not None
            }
            sub_sites = {}
            if sub_site_uuids:
                cursor.execute(
                    """
                    SELECT uuid, name
                    FROM sub_sites
                    WHERE uuid = ANY(%s)
                """,
                    (list(sub_site_uuids),),
                )
                sub_sites = dict(cursor.fetchall())

            # Get downloads
            cursor.execute(
                """
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
                WHERE r.site_uuid = %s {}
                ORDER BY r.uuid
            """.format(
                    "AND r.sub_site_uuid = %s" if sub_site_uuid else ""
                ),
                (site_uuid, sub_site_uuid) if sub_site_uuid else (site_uuid,),
            )
            downloads_rows = cursor.fetchall()

            # Get performers
            cursor.execute(
                """
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
            """,
                (site_uuid,),
            )
            performers = dict(cursor.fetchall())

            # Get tags
            cursor.execute(
                """
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
            """,
                (site_uuid,),
            )
            tags = dict(cursor.fetchall())

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

                # Parse file_metadata JSON if it's a string
                file_metadata = row[9]
                if isinstance(file_metadata, str):
                    try:
                        file_metadata = json.loads(file_metadata)
                    except json.JSONDecodeError:
                        file_metadata = {}

                download_data = {
                    "ce_downloads_site_uuid": site_uuid,
                    "ce_downloads_site_name": site_name,
                    "ce_downloads_sub_site_name": (
                        sub_sites.get(release[10]) if release[10] else None
                    ),
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
                    "ce_downloads_available_file": (
                        json.dumps(available_file) if available_file else None
                    ),
                    "ce_downloads_original_filename": row[7],
                    "ce_downloads_saved_filename": row[8],
                    "ce_downloads_file_metadata": (
                        json.dumps(file_metadata) if file_metadata else None
                    ),
                    "ce_downloads_performers": performers.get(release_uuid, []),
                    "ce_downloads_tags": tags.get(release_uuid, []),
                    "ce_downloads_hash_oshash": (
                        file_metadata.get("oshash") if file_metadata else None
                    ),
                    "ce_downloads_hash_phash": (
                        file_metadata.get("phash") if file_metadata else None
                    ),
                    "ce_downloads_hash_sha256": (
                        file_metadata.get("sha256Sum") if file_metadata else None
                    ),
                }
                downloads.append(download_data)

            # Schema remains the same as before
            schema = {
                "ce_downloads_site_uuid": pl.Utf8,
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

    def create_site(
        self,
        short_name: str,
        name: str,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> str:
        """Create a new site in the database.

        Args:
            short_name: A short identifier for the site
            name: The full name of the site
            url: The base URL of the site
            username: Optional username for site authentication
            password: Optional password for site authentication

        Returns:
            str: The UUID of the created site
        """
        with self.connection.cursor() as cursor:
            site_uuid = str(uuid.uuid7())
            cursor.execute(
                """
                INSERT INTO sites (uuid, short_name, name, url, username, password)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING uuid
            """,
                (site_uuid, short_name, name, url, username, password),
            )
            self.connection.commit()
            return site_uuid

    def create_sub_site(
        self, site_uuid: str, short_name: str, name: str, json_document: dict | None = None
    ) -> str:
        """Create a new sub-site in the database.

        Args:
            site_uuid: The UUID of the parent site
            short_name: A short identifier for the sub-site
            name: The full name of the sub-site
            json_document: Optional JSON metadata for the sub-site, defaults to empty dict if None

        Returns:
            str: The UUID of the created sub-site
        """
        with self.connection.cursor() as cursor:
            # First verify the site exists
            cursor.execute("SELECT uuid FROM sites WHERE uuid = %s", (site_uuid,))
            if not cursor.fetchone():
                raise ValueError(f"Site with UUID {site_uuid} does not exist")

            sub_site_uuid = str(uuid.uuid7())
            # Ensure json_document is never None
            json_doc = {} if json_document is None else json_document
            cursor.execute(
                """
                INSERT INTO sub_sites (uuid, site_uuid, short_name, name, json_document)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING uuid
            """,
                (
                    sub_site_uuid,
                    site_uuid,
                    short_name,
                    name,
                    json.dumps(json_doc),  # Always serialize a dictionary
                ),
            )
            self.connection.commit()
            return sub_site_uuid

    def get_site_by_uuid(self, site_uuid: str) -> pl.DataFrame:
        """Get a specific site by its UUID.

        Args:
            site_uuid: UUID of the site to get

        Returns:
            DataFrame containing the site data
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    uuid AS ce_sites_uuid,
                    short_name AS ce_sites_short_name,
                    name AS ce_sites_name,
                    url AS ce_sites_url
                FROM sites
                WHERE uuid = %s
            """,
                (site_uuid,),
            )
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()

            site_data = {
                "ce_sites_uuid": str(site_row[0]),
                "ce_sites_short_name": site_row[1],
                "ce_sites_name": site_row[2],
                "ce_sites_url": site_row[3],
            }

            schema = {
                "ce_sites_uuid": pl.Utf8,
                "ce_sites_short_name": pl.Utf8,
                "ce_sites_name": pl.Utf8,
                "ce_sites_url": pl.Utf8,
            }

            return pl.DataFrame([site_data], schema=schema)

    def get_site_external_ids(self, site_uuid: str) -> dict:
        """Get external IDs for a site from the site_external_ids table.

        Args:
            site_uuid: UUID of the site

        Returns:
            Dictionary containing external IDs by target system name
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ts.name, sei.external_id
                FROM site_external_ids sei
                JOIN target_systems ts ON sei.target_system_uuid = ts.uuid
                WHERE sei.site_uuid = %s
            """,
                (site_uuid,),
            )
            results = cursor.fetchall()

            # Return as dictionary with target system name as key
            return {row[0]: row[1] for row in results}

    def set_site_external_id(
        self, site_uuid: str, target_system_name: str, external_id: str
    ) -> None:
        """Set an external ID for a site in the site_external_ids table.

        Args:
            site_uuid: UUID of the site
            target_system_name: Name of the target system (e.g., 'stashapp', 'stashdb')
            external_id: The external ID value (as string)
        """
        with self.connection.cursor() as cursor:
            # Verify site exists
            cursor.execute(
                "SELECT uuid FROM sites WHERE uuid = %s", (site_uuid,)
            )
            if not cursor.fetchone():
                raise ValueError(f"Site with UUID {site_uuid} does not exist")

            # Get or create target system
            cursor.execute(
                "SELECT uuid FROM target_systems WHERE name = %s",
                (target_system_name,),
            )
            target_system_row = cursor.fetchone()

            if target_system_row:
                target_system_uuid = target_system_row[0]
            else:
                # Create new target system
                target_system_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO target_systems (uuid, name, description, created, last_updated)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """,
                    (target_system_uuid, target_system_name, f"External system: {target_system_name}"),
                )

            # Check if external ID already exists for this site and target system
            cursor.execute(
                """
                SELECT uuid FROM site_external_ids
                WHERE site_uuid = %s AND target_system_uuid = %s
            """,
                (site_uuid, target_system_uuid),
            )
            existing_row = cursor.fetchone()

            if existing_row:
                # Update existing
                cursor.execute(
                    """
                    UPDATE site_external_ids
                    SET external_id = %s, last_updated = NOW()
                    WHERE uuid = %s
                """,
                    (external_id, existing_row[0]),
                )
            else:
                # Insert new
                external_id_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO site_external_ids
                    (uuid, site_uuid, target_system_uuid, external_id, created, last_updated)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                    (external_id_uuid, site_uuid, target_system_uuid, external_id),
                )

            self.connection.commit()

    def get_tags(self, site_uuid: str, name_filter: str | None = None) -> pl.DataFrame:
        """Get all tags for a given site UUID, with optional name filtering.

        Args:
            site_uuid: UUID of the site to get tags for
            name_filter: Optional case-insensitive substring to filter tag names

        Returns:
            DataFrame containing all tags for the site
        """
        with self.connection.cursor() as cursor:
            # Get site info to verify it exists
            cursor.execute(
                """
                SELECT name, uuid
                FROM sites
                WHERE sites.uuid = %s
            """,
                (site_uuid,),
            )
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()
            site_name = site_row[0]

            # Build query with optional name filter
            if name_filter:
                query = """
                    SELECT DISTINCT
                        t.uuid AS ce_tags_uuid,
                        t.short_name AS ce_tags_short_name,
                        t.name AS ce_tags_name,
                        t.url AS ce_tags_url
                    FROM tags t
                    JOIN release_entity_site_tag_entity rest ON t.uuid = rest.tags_uuid
                    JOIN releases r ON rest.releases_uuid = r.uuid
                    WHERE r.site_uuid = %s
                      AND (t.name ILIKE %s OR t.short_name ILIKE %s)
                    ORDER BY t.name
                """
                params = (site_uuid, f"%{name_filter}%", f"%{name_filter}%")
            else:
                query = """
                    SELECT DISTINCT
                        t.uuid AS ce_tags_uuid,
                        t.short_name AS ce_tags_short_name,
                        t.name AS ce_tags_name,
                        t.url AS ce_tags_url
                    FROM tags t
                    JOIN release_entity_site_tag_entity rest ON t.uuid = rest.tags_uuid
                    JOIN releases r ON rest.releases_uuid = r.uuid
                    WHERE r.site_uuid = %s
                    ORDER BY t.name
                """
                params = (site_uuid,)

            cursor.execute(query, params)
            tags_rows = cursor.fetchall()

            tags = []
            for row in tags_rows:
                tag_uuid = str(row[0])
                # Get external IDs for this tag
                external_ids = self.get_tag_external_ids(tag_uuid)

                tags.append(
                    {
                        "ce_site_uuid": str(site_uuid),
                        "ce_site_name": site_name,
                        "ce_tags_uuid": tag_uuid,
                        "ce_tags_short_name": row[1],
                        "ce_tags_name": row[2],
                        "ce_tags_url": row[3],
                        "ce_tags_stashapp_id": external_ids.get("stashapp"),
                        "ce_tags_stashdb_id": external_ids.get("stashdb"),
                    }
                )

            schema = {
                "ce_site_uuid": pl.Utf8,
                "ce_site_name": pl.Utf8,
                "ce_tags_uuid": pl.Utf8,
                "ce_tags_short_name": pl.Utf8,
                "ce_tags_name": pl.Utf8,
                "ce_tags_url": pl.Utf8,
                "ce_tags_stashapp_id": pl.Utf8,
                "ce_tags_stashdb_id": pl.Utf8,
            }

            return pl.DataFrame(tags, schema=schema)

    def get_tag_by_uuid(self, tag_uuid: str) -> pl.DataFrame:
        """Get a specific tag by its UUID.

        Args:
            tag_uuid: UUID of the tag to get

        Returns:
            DataFrame containing the tag data
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    uuid AS ce_tags_uuid,
                    short_name AS ce_tags_short_name,
                    name AS ce_tags_name,
                    url AS ce_tags_url
                FROM tags
                WHERE uuid = %s
            """,
                (tag_uuid,),
            )
            tag_row = cursor.fetchone()
            if not tag_row:
                return pl.DataFrame()

            tag_data = {
                "ce_tags_uuid": str(tag_row[0]),
                "ce_tags_short_name": tag_row[1],
                "ce_tags_name": tag_row[2],
                "ce_tags_url": tag_row[3],
            }

            schema = {
                "ce_tags_uuid": pl.Utf8,
                "ce_tags_short_name": pl.Utf8,
                "ce_tags_name": pl.Utf8,
                "ce_tags_url": pl.Utf8,
            }

            return pl.DataFrame([tag_data], schema=schema)

    def get_tag_external_ids(self, tag_uuid: str) -> dict:
        """Get external IDs for a tag from the tag_external_ids table.

        Args:
            tag_uuid: UUID of the tag

        Returns:
            Dictionary containing external IDs by target system name
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ts.name, tei.external_id
                FROM tag_external_ids tei
                JOIN target_systems ts ON tei.target_system_uuid = ts.uuid
                WHERE tei.tag_uuid = %s
            """,
                (tag_uuid,),
            )
            results = cursor.fetchall()

            # Return as dictionary with target system name as key
            return {row[0]: row[1] for row in results}

    def set_tag_external_id(
        self, tag_uuid: str, target_system_name: str, external_id: str
    ) -> None:
        """Set an external ID for a tag in the tag_external_ids table.

        Args:
            tag_uuid: UUID of the tag
            target_system_name: Name of the target system (e.g., 'stashapp', 'stashdb')
            external_id: The external ID value (as string)
        """
        with self.connection.cursor() as cursor:
            # Verify tag exists
            cursor.execute(
                "SELECT uuid FROM tags WHERE uuid = %s", (tag_uuid,)
            )
            if not cursor.fetchone():
                raise ValueError(f"Tag with UUID {tag_uuid} does not exist")

            # Get or create target system
            cursor.execute(
                "SELECT uuid FROM target_systems WHERE name = %s",
                (target_system_name,),
            )
            target_system_row = cursor.fetchone()

            if target_system_row:
                target_system_uuid = target_system_row[0]
            else:
                # Create new target system
                target_system_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO target_systems (uuid, name, description, created, last_updated)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """,
                    (target_system_uuid, target_system_name, f"External system: {target_system_name}"),
                )

            # Check if external ID already exists for this tag and target system
            cursor.execute(
                """
                SELECT uuid FROM tag_external_ids
                WHERE tag_uuid = %s AND target_system_uuid = %s
            """,
                (tag_uuid, target_system_uuid),
            )
            existing_row = cursor.fetchone()

            if existing_row:
                # Update existing
                cursor.execute(
                    """
                    UPDATE tag_external_ids
                    SET external_id = %s, last_updated = NOW()
                    WHERE uuid = %s
                """,
                    (external_id, existing_row[0]),
                )
            else:
                # Insert new
                external_id_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO tag_external_ids
                    (uuid, tag_uuid, target_system_uuid, external_id, created, last_updated)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                    (external_id_uuid, tag_uuid, target_system_uuid, external_id),
                )

            self.connection.commit()

    def get_performers_all(self, name_filter: str | None = None) -> pl.DataFrame:
        """Get all performers across all sites, with optional name filtering.

        Args:
            name_filter: Optional case-insensitive substring to filter performer names

        Returns:
            DataFrame containing all performers (optionally filtered)
        """
        with self.connection.cursor() as cursor:
            # Build query with optional name filter
            if name_filter:
                query = """
                    SELECT DISTINCT
                        p.uuid AS ce_performers_uuid,
                        p.short_name AS ce_performers_short_name,
                        p.name AS ce_performers_name,
                        p.url AS ce_performers_url,
                        s.uuid AS ce_site_uuid,
                        s.name AS ce_site_name
                    FROM performers p
                    JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                    JOIN releases r ON resp.releases_uuid = r.uuid
                    JOIN sites s ON r.site_uuid = s.uuid
                    WHERE p.name ILIKE %s OR p.short_name ILIKE %s
                    ORDER BY p.name, s.name
                """
                params = (f"%{name_filter}%", f"%{name_filter}%")
            else:
                query = """
                    SELECT DISTINCT
                        p.uuid AS ce_performers_uuid,
                        p.short_name AS ce_performers_short_name,
                        p.name AS ce_performers_name,
                        p.url AS ce_performers_url,
                        s.uuid AS ce_site_uuid,
                        s.name AS ce_site_name
                    FROM performers p
                    JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                    JOIN releases r ON resp.releases_uuid = r.uuid
                    JOIN sites s ON r.site_uuid = s.uuid
                    ORDER BY p.name, s.name
                """
                params = ()

            cursor.execute(query, params)
            performers_rows = cursor.fetchall()

            performers = [
                {
                    "ce_performers_uuid": str(row[0]),
                    "ce_performers_short_name": row[1],
                    "ce_performers_name": row[2],
                    "ce_performers_url": row[3],
                    "ce_site_uuid": str(row[4]),
                    "ce_site_name": row[5],
                }
                for row in performers_rows
            ]

            schema = {
                "ce_performers_uuid": pl.Utf8,
                "ce_performers_short_name": pl.Utf8,
                "ce_performers_name": pl.Utf8,
                "ce_performers_url": pl.Utf8,
                "ce_site_uuid": pl.Utf8,
                "ce_site_name": pl.Utf8,
            }

            return pl.DataFrame(performers, schema=schema)

    def get_performers(self, site_uuid: str, name_filter: str | None = None) -> pl.DataFrame:
        """Get all performers for a given site UUID, with optional name filtering.

        Args:
            site_uuid: UUID of the site to get performers for
            name_filter: Optional case-insensitive substring to filter performer names

        Returns:
            DataFrame containing all performers for the site
        """
        with self.connection.cursor() as cursor:
            # Get site info to verify it exists
            cursor.execute(
                """
                SELECT name, uuid
                FROM sites
                WHERE sites.uuid = %s
            """,
                (site_uuid,),
            )
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()
            site_name = site_row[0]

            # Build query with optional name filter
            if name_filter:
                query = """
                    SELECT DISTINCT
                        p.uuid AS ce_performers_uuid,
                        p.short_name AS ce_performers_short_name,
                        p.name AS ce_performers_name,
                        p.url AS ce_performers_url
                    FROM performers p
                    JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                    JOIN releases r ON resp.releases_uuid = r.uuid
                    WHERE r.site_uuid = %s
                      AND (p.name ILIKE %s OR p.short_name ILIKE %s)
                    ORDER BY p.name
                """
                params = (site_uuid, f"%{name_filter}%", f"%{name_filter}%")
            else:
                query = """
                    SELECT DISTINCT
                        p.uuid AS ce_performers_uuid,
                        p.short_name AS ce_performers_short_name,
                        p.name AS ce_performers_name,
                        p.url AS ce_performers_url
                    FROM performers p
                    JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                    JOIN releases r ON resp.releases_uuid = r.uuid
                    WHERE r.site_uuid = %s
                    ORDER BY p.name
                """
                params = (site_uuid,)

            cursor.execute(query, params)
            performers_rows = cursor.fetchall()

            performers = [
                {
                    "ce_site_uuid": str(site_uuid),
                    "ce_site_name": site_name,
                    "ce_performers_uuid": str(row[0]),
                    "ce_performers_short_name": row[1],
                    "ce_performers_name": row[2],
                    "ce_performers_url": row[3],
                }
                for row in performers_rows
            ]

            schema = {
                "ce_site_uuid": pl.Utf8,
                "ce_site_name": pl.Utf8,
                "ce_performers_uuid": pl.Utf8,
                "ce_performers_short_name": pl.Utf8,
                "ce_performers_name": pl.Utf8,
                "ce_performers_url": pl.Utf8,
            }

            return pl.DataFrame(performers, schema=schema)

    def get_performers_unmapped(
        self, site_uuid: str, target_system_name: str = "stashapp", name_filter: str | None = None
    ) -> pl.DataFrame:
        """Get performers for a site that don't have mappings to an external system.

        Args:
            site_uuid: UUID of the site to get performers for
            target_system_name: Name of the target system to check (default: 'stashapp')
            name_filter: Optional case-insensitive substring to filter performer names

        Returns:
            DataFrame containing performers without external IDs for the target system
        """
        with self.connection.cursor() as cursor:
            # Get site info to verify it exists
            cursor.execute(
                """
                SELECT name, uuid
                FROM sites
                WHERE sites.uuid = %s
            """,
                (site_uuid,),
            )
            site_row = cursor.fetchone()
            if not site_row:
                return pl.DataFrame()
            site_name = site_row[0]

            # Build query with optional name filter
            if name_filter:
                query = """
                    SELECT DISTINCT
                        p.uuid AS ce_performers_uuid,
                        p.short_name AS ce_performers_short_name,
                        p.name AS ce_performers_name,
                        p.url AS ce_performers_url
                    FROM performers p
                    JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                    JOIN releases r ON resp.releases_uuid = r.uuid
                    WHERE r.site_uuid = %s
                      AND (p.name ILIKE %s OR p.short_name ILIKE %s)
                      AND NOT EXISTS (
                          SELECT 1 FROM performer_external_ids pei
                          JOIN target_systems ts ON pei.target_system_uuid = ts.uuid
                          WHERE pei.performer_uuid = p.uuid AND ts.name = %s
                      )
                    ORDER BY p.name
                """
                params = (site_uuid, f"%{name_filter}%", f"%{name_filter}%", target_system_name)
            else:
                query = """
                    SELECT DISTINCT
                        p.uuid AS ce_performers_uuid,
                        p.short_name AS ce_performers_short_name,
                        p.name AS ce_performers_name,
                        p.url AS ce_performers_url
                    FROM performers p
                    JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                    JOIN releases r ON resp.releases_uuid = r.uuid
                    WHERE r.site_uuid = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM performer_external_ids pei
                          JOIN target_systems ts ON pei.target_system_uuid = ts.uuid
                          WHERE pei.performer_uuid = p.uuid AND ts.name = %s
                      )
                    ORDER BY p.name
                """
                params = (site_uuid, target_system_name)

            cursor.execute(query, params)
            performers_rows = cursor.fetchall()

            performers = [
                {
                    "ce_site_uuid": str(site_uuid),
                    "ce_site_name": site_name,
                    "ce_performers_uuid": str(row[0]),
                    "ce_performers_short_name": row[1],
                    "ce_performers_name": row[2],
                    "ce_performers_url": row[3],
                }
                for row in performers_rows
            ]

            schema = {
                "ce_site_uuid": pl.Utf8,
                "ce_site_name": pl.Utf8,
                "ce_performers_uuid": pl.Utf8,
                "ce_performers_short_name": pl.Utf8,
                "ce_performers_name": pl.Utf8,
                "ce_performers_url": pl.Utf8,
            }

            return pl.DataFrame(performers, schema=schema)

    def get_release_performers(self, release_uuid: str) -> pl.DataFrame:
        """Get all performers for a specific release.

        Args:
            release_uuid: UUID of the release

        Returns:
            DataFrame containing performers for the release with their external IDs
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    p.uuid AS ce_performers_uuid,
                    p.short_name AS ce_performers_short_name,
                    p.name AS ce_performers_name,
                    p.url AS ce_performers_url
                FROM performers p
                JOIN release_entity_site_performer_entity resp ON p.uuid = resp.performers_uuid
                WHERE resp.releases_uuid = %s
                ORDER BY p.name
            """,
                (release_uuid,),
            )
            performers_rows = cursor.fetchall()

            performers = []
            for row in performers_rows:
                performer_uuid = str(row[0])
                # Get external IDs for this performer
                external_ids = self.get_performer_external_ids(performer_uuid)

                performers.append(
                    {
                        "ce_performers_uuid": performer_uuid,
                        "ce_performers_short_name": row[1],
                        "ce_performers_name": row[2],
                        "ce_performers_url": row[3],
                        "ce_performers_stashapp_id": external_ids.get("stashapp"),
                        "ce_performers_stashdb_id": external_ids.get("stashdb"),
                    }
                )

            schema = {
                "ce_performers_uuid": pl.Utf8,
                "ce_performers_short_name": pl.Utf8,
                "ce_performers_name": pl.Utf8,
                "ce_performers_url": pl.Utf8,
                "ce_performers_stashapp_id": pl.Utf8,
                "ce_performers_stashdb_id": pl.Utf8,
            }

            return pl.DataFrame(performers, schema=schema)

    def get_release_tags(self, release_uuid: str) -> pl.DataFrame:
        """Get all tags for a specific release.

        Args:
            release_uuid: UUID of the release

        Returns:
            DataFrame containing tags for the release
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    t.uuid AS ce_tags_uuid,
                    t.short_name AS ce_tags_short_name,
                    t.name AS ce_tags_name,
                    t.url AS ce_tags_url
                FROM tags t
                JOIN release_entity_site_tag_entity rest ON t.uuid = rest.tags_uuid
                WHERE rest.releases_uuid = %s
                ORDER BY t.name
            """,
                (release_uuid,),
            )
            tags_rows = cursor.fetchall()

            tags = [
                {
                    "ce_tags_uuid": str(row[0]),
                    "ce_tags_short_name": row[1],
                    "ce_tags_name": row[2],
                    "ce_tags_url": row[3],
                }
                for row in tags_rows
            ]

            schema = {
                "ce_tags_uuid": pl.Utf8,
                "ce_tags_short_name": pl.Utf8,
                "ce_tags_name": pl.Utf8,
                "ce_tags_url": pl.Utf8,
            }

            return pl.DataFrame(tags, schema=schema)

    def get_performer_by_uuid(self, performer_uuid: str) -> pl.DataFrame:
        """Get a specific performer by its UUID.

        Args:
            performer_uuid: UUID of the performer to get

        Returns:
            DataFrame containing the performer data
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    uuid AS ce_performers_uuid,
                    short_name AS ce_performers_short_name,
                    name AS ce_performers_name,
                    url AS ce_performers_url
                FROM performers
                WHERE uuid = %s
            """,
                (performer_uuid,),
            )
            performer_row = cursor.fetchone()
            if not performer_row:
                return pl.DataFrame()

            performer_data = {
                "ce_performers_uuid": str(performer_row[0]),
                "ce_performers_short_name": performer_row[1],
                "ce_performers_name": performer_row[2],
                "ce_performers_url": performer_row[3],
            }

            schema = {
                "ce_performers_uuid": pl.Utf8,
                "ce_performers_short_name": pl.Utf8,
                "ce_performers_name": pl.Utf8,
                "ce_performers_url": pl.Utf8,
            }

            return pl.DataFrame([performer_data], schema=schema)

    def get_performer_external_ids(self, performer_uuid: str) -> dict:
        """Get external IDs for a performer from the performer_external_ids table.

        Args:
            performer_uuid: UUID of the performer

        Returns:
            Dictionary containing external IDs by target system name
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ts.name, pei.external_id
                FROM performer_external_ids pei
                JOIN target_systems ts ON pei.target_system_uuid = ts.uuid
                WHERE pei.performer_uuid = %s
            """,
                (performer_uuid,),
            )
            results = cursor.fetchall()

            # Return as dictionary with target system name as key
            return {row[0]: row[1] for row in results}

    def set_performer_external_id(
        self, performer_uuid: str, target_system_name: str, external_id: str
    ) -> None:
        """Set an external ID for a performer in the performer_external_ids table.

        Args:
            performer_uuid: UUID of the performer
            target_system_name: Name of the target system (e.g., 'stashapp', 'stashdb')
            external_id: The external ID value (as string)
        """
        with self.connection.cursor() as cursor:
            # Verify performer exists
            cursor.execute(
                "SELECT uuid FROM performers WHERE uuid = %s", (performer_uuid,)
            )
            if not cursor.fetchone():
                raise ValueError(f"Performer with UUID {performer_uuid} does not exist")

            # Get or create target system
            cursor.execute(
                "SELECT uuid FROM target_systems WHERE name = %s",
                (target_system_name,),
            )
            target_system_row = cursor.fetchone()

            if target_system_row:
                target_system_uuid = target_system_row[0]
            else:
                # Create new target system
                target_system_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO target_systems (uuid, name, description, created, last_updated)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """,
                    (target_system_uuid, target_system_name, f"External system: {target_system_name}"),
                )

            # Check if external ID already exists for this performer and target system
            cursor.execute(
                """
                SELECT uuid FROM performer_external_ids
                WHERE performer_uuid = %s AND target_system_uuid = %s
            """,
                (performer_uuid, target_system_uuid),
            )
            existing_row = cursor.fetchone()

            if existing_row:
                # Update existing
                cursor.execute(
                    """
                    UPDATE performer_external_ids
                    SET external_id = %s, last_updated = NOW()
                    WHERE uuid = %s
                """,
                    (external_id, existing_row[0]),
                )
            else:
                # Insert new
                external_id_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO performer_external_ids
                    (uuid, performer_uuid, target_system_uuid, external_id, created, last_updated)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                    (external_id_uuid, performer_uuid, target_system_uuid, external_id),
                )

            self.connection.commit()

    def get_release_downloads(self, release_uuid: str) -> pl.DataFrame:
        """Get all downloads for a specific release.

        Args:
            release_uuid: UUID of the release

        Returns:
            DataFrame containing downloads for the release
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
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
                WHERE d.release_uuid = %s
                ORDER BY d.downloaded_at DESC
            """,
                (release_uuid,),
            )
            downloads_rows = cursor.fetchall()

            downloads = []
            for row in downloads_rows:
                # Parse available_file JSON if it's a string
                available_file = row[5]
                if isinstance(available_file, str):
                    try:
                        available_file = json.loads(available_file)
                    except json.JSONDecodeError:
                        available_file = None

                # Parse file_metadata JSON if it's a string
                file_metadata = row[8]
                if isinstance(file_metadata, str):
                    try:
                        file_metadata = json.loads(file_metadata)
                    except json.JSONDecodeError:
                        file_metadata = {}

                download_data = {
                    "ce_downloads_uuid": str(row[0]),
                    "ce_downloads_downloaded_at": row[1],
                    "ce_downloads_file_type": row[2],
                    "ce_downloads_content_type": row[3],
                    "ce_downloads_variant": row[4],
                    "ce_downloads_available_file": (
                        json.dumps(available_file) if available_file else None
                    ),
                    "ce_downloads_original_filename": row[6],
                    "ce_downloads_saved_filename": row[7],
                    "ce_downloads_file_metadata": (
                        json.dumps(file_metadata) if file_metadata else None
                    ),
                    "ce_downloads_hash_oshash": (
                        file_metadata.get("oshash") if file_metadata else None
                    ),
                    "ce_downloads_hash_phash": (
                        file_metadata.get("phash") if file_metadata else None
                    ),
                    "ce_downloads_hash_sha256": (
                        file_metadata.get("sha256Sum") if file_metadata else None
                    ),
                }
                downloads.append(download_data)

            schema = {
                "ce_downloads_uuid": pl.Utf8,
                "ce_downloads_downloaded_at": pl.Datetime,
                "ce_downloads_file_type": pl.Utf8,
                "ce_downloads_content_type": pl.Utf8,
                "ce_downloads_variant": pl.Utf8,
                "ce_downloads_available_file": pl.Utf8,
                "ce_downloads_original_filename": pl.Utf8,
                "ce_downloads_saved_filename": pl.Utf8,
                "ce_downloads_file_metadata": pl.Utf8,
                "ce_downloads_hash_oshash": pl.Utf8,
                "ce_downloads_hash_phash": pl.Utf8,
                "ce_downloads_hash_sha256": pl.Utf8,
            }

            return pl.DataFrame(downloads, schema=schema)

    def get_release_external_ids(self, release_uuid: str) -> dict:
        """Get external IDs for a release from the release_external_ids table.

        Args:
            release_uuid: UUID of the release

        Returns:
            Dictionary containing external IDs by target system name
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ts.name, rei.external_id
                FROM release_external_ids rei
                JOIN target_systems ts ON rei.target_system_uuid = ts.uuid
                WHERE rei.release_uuid = %s
            """,
                (release_uuid,),
            )
            results = cursor.fetchall()

            # Return as dictionary with target system name as key
            return {row[0]: row[1] for row in results}

    def set_release_external_id(
        self, release_uuid: str, target_system_name: str, external_id: str
    ) -> None:
        """Set an external ID for a release in the release_external_ids table.

        Args:
            release_uuid: UUID of the release
            target_system_name: Name of the target system (e.g., 'stashapp', 'stashdb')
            external_id: The external ID value (as string)
        """
        with self.connection.cursor() as cursor:
            # Verify release exists
            cursor.execute(
                "SELECT uuid FROM releases WHERE uuid = %s", (release_uuid,)
            )
            if not cursor.fetchone():
                raise ValueError(f"Release with UUID {release_uuid} does not exist")

            # Get or create target system
            cursor.execute(
                "SELECT uuid FROM target_systems WHERE name = %s",
                (target_system_name,),
            )
            target_system_row = cursor.fetchone()

            if target_system_row:
                target_system_uuid = target_system_row[0]
            else:
                # Create new target system
                target_system_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO target_systems (uuid, name, description, created, last_updated)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """,
                    (target_system_uuid, target_system_name, f"External system: {target_system_name}"),
                )

            # Check if external ID already exists for this release and target system
            cursor.execute(
                """
                SELECT uuid FROM release_external_ids
                WHERE release_uuid = %s AND target_system_uuid = %s
            """,
                (release_uuid, target_system_uuid),
            )
            existing_row = cursor.fetchone()

            if existing_row:
                # Update existing
                cursor.execute(
                    """
                    UPDATE release_external_ids
                    SET external_id = %s, last_updated = NOW()
                    WHERE uuid = %s
                """,
                    (external_id, existing_row[0]),
                )
            else:
                # Insert new
                external_id_uuid = str(uuid.uuid7())
                cursor.execute(
                    """
                    INSERT INTO release_external_ids
                    (uuid, release_uuid, target_system_uuid, external_id, created, last_updated)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                    (external_id_uuid, release_uuid, target_system_uuid, external_id),
                )

            self.connection.commit()
