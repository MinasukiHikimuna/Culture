import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from the correct path
# Don't touch this! This works! You will break it!
load_dotenv("H:\Git\scrapytickling\scrapy\cultureextractorscrapy\spiders\.env")

# Get connection string from environment variable
connection_string = os.getenv("CONNECTION_STRING")
if not connection_string:
    print("Error: CONNECTION_STRING not found in environment variables")
    exit(1)

# Create database engine
engine = create_engine(connection_string)

with engine.connect() as conn:
    # First, let's check what tables exist
    print("\nAvailable Tables:")
    table_query = text(
        """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """
    )
    tables = conn.execute(table_query)
    for table in tables:
        print(f"- {table[0]}")

    print("\nLezKiss Site Info:")
    site_query = text(
        """
        SELECT uuid, short_name, name 
        FROM sites 
        WHERE short_name = 'lezkiss'
    """
    )
    site_result = conn.execute(site_query).fetchone()
    if not site_result:
        print("Error: LezKiss site not found")
        exit(1)

    site_uuid = site_result[0]
    print(f"UUID: {site_uuid}, Short name: {site_result[1]}, Name: {site_result[2]}")

    print("\nLezKiss Releases:")
    releases_query = text(
        """
        SELECT uuid, short_name, name, release_date 
        FROM releases 
        WHERE site_uuid = :site_uuid
        LIMIT 5
    """
    )
    releases = conn.execute(releases_query, {"site_uuid": site_uuid})
    for release in releases:
        print(
            f"UUID: {release[0]}, Short name: {release[1]}, Name: {release[2]}, Date: {release[3]}"
        )

    print("\nChecking for junction tables:")
    junction_query = text(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'release_entity_site_performer_entity'
        ) as has_performers,
        EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'release_entity_site_tag_entity'
        ) as has_tags
        """
    )
    junction_result = conn.execute(junction_query).fetchone()
    print(f"release_entity_site_performer_entity table exists: {junction_result[0]}")
    print(f"release_entity_site_tag_entity table exists: {junction_result[1]}")

    # Check performers table content
    print("\nPerformers in database:")
    performers_query = text(
        """
        SELECT p.uuid, p.short_name, p.name, p.url
        FROM performers p
        WHERE p.site_uuid = :site_uuid
        LIMIT 5
        """
    )
    performers = conn.execute(performers_query, {"site_uuid": site_uuid})
    for performer in performers:
        print(f"UUID: {performer[0]}, Short name: {performer[1]}, Name: {performer[2]}")

    # Check tags table content
    print("\nTags in database:")
    tags_query = text(
        """
        SELECT t.uuid, t.short_name, t.name, t.url
        FROM tags t
        WHERE t.site_uuid = :site_uuid
        LIMIT 5
        """
    )
    tags = conn.execute(tags_query, {"site_uuid": site_uuid})
    for tag in tags:
        print(f"UUID: {tag[0]}, Short name: {tag[1]}, Name: {tag[2]}")

    # Let's check the structure of the junction tables
    print("\nJunction table structures:")
    structure_query = text(
        """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'release_entity_site_performer_entity'
        """
    )
    print("\nrelease_entity_site_performer_entity columns:")
    structure = conn.execute(structure_query)
    for col in structure:
        print(f"- {col[0]}: {col[1]}")

    structure_query = text(
        """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'release_entity_site_tag_entity'
        """
    )
    print("\nrelease_entity_site_tag_entity columns:")
    structure = conn.execute(structure_query)
    for col in structure:
        print(f"- {col[0]}: {col[1]}")

    # Now check the relationships with the correct column names
    print("\nRelease-Performer relationships:")
    rel_perf_query = text(
        """
        SELECT DISTINCT r.name as release_name, p.name as performer_name
        FROM releases r
        JOIN release_entity_site_performer_entity rp ON r.uuid = rp.releases_uuid
        JOIN performers p ON p.uuid = rp.performers_uuid
        WHERE r.site_uuid = :site_uuid
        LIMIT 5
        """
    )
    try:
        rel_perfs = conn.execute(rel_perf_query, {"site_uuid": site_uuid})
        for rel_perf in rel_perfs:
            print(f"Release: {rel_perf[0]}, Performer: {rel_perf[1]}")
    except Exception as e:
        print(f"Error querying release_entity_site_performer_entity: {str(e)}")

    print("\nRelease-Tag relationships:")
    rel_tag_query = text(
        """
        SELECT DISTINCT r.name as release_name, t.name as tag_name
        FROM releases r
        JOIN release_entity_site_tag_entity rt ON r.uuid = rt.releases_uuid
        JOIN tags t ON t.uuid = rt.tags_uuid
        WHERE r.site_uuid = :site_uuid
        LIMIT 5
        """
    )
    try:
        rel_tags = conn.execute(rel_tag_query, {"site_uuid": site_uuid})
        for rel_tag in rel_tags:
            print(f"Release: {rel_tag[0]}, Tag: {rel_tag[1]}")
    except Exception as e:
        print(f"Error querying release_entity_site_tag_entity: {str(e)}")

    print("\nLezKiss Downloads:")
    downloads_query = text(
        """
        SELECT d.uuid, d.saved_filename, d.content_type, d.variant, r.name as release_name
        FROM downloads d
        JOIN releases r ON d.release_uuid = r.uuid
        WHERE r.site_uuid = :site_uuid
        LIMIT 5
        """
    )
    downloads = conn.execute(downloads_query, {"site_uuid": site_uuid})
    for download in downloads:
        print(
            f"UUID: {download[0]}, File: {download[1]}, Type: {download[2]}, Variant: {download[3]}, Release: {download[4]}"
        )

    # Get the site UUID for lezkiss
    site_result = conn.execute(
        text("SELECT uuid, short_name, name FROM sites WHERE short_name = 'lezkiss'")
    )
    site = site_result.fetchone()

    if site:
        print(f"\nSite Info:")
        print(f"UUID: {site.uuid}")
        print(f"Name: {site.name}")

        # Get the specific release we just created
        release_uuid = "0195882c-cb47-7479-9492-81870e0ef7a4"
        release_result = conn.execute(
            text(
                "SELECT uuid, short_name, name, created FROM releases WHERE uuid = :uuid"
            ),
            {"uuid": release_uuid},
        )
        release = release_result.fetchone()

        if release:
            print(f"\nRelease Info:")
            print(f"UUID: {release.uuid}")
            print(f"Name: {release.name}")
            print(f"Created: {release.created}")

            # Get all downloads associated with this release
            downloads_result = conn.execute(
                text(
                    """
                    SELECT uuid, saved_filename, file_type, content_type, variant, 
                           downloaded_at, file_metadata
                    FROM downloads 
                    WHERE release_uuid = :release_uuid
                    ORDER BY downloaded_at
                """
                ),
                {"release_uuid": release_uuid},
            )

            print("\nDownloads:")
            for download in downloads_result:
                print(f"\n- File: {download.saved_filename}")
                print(f"  UUID: {download.uuid}")
                print(f"  Type: {download.file_type}")
                print(f"  Content: {download.content_type}")
                print(f"  Variant: {download.variant}")
                print(f"  Downloaded: {download.downloaded_at}")
                print(f"  Metadata: {download.file_metadata}")
        else:
            print(f"No release found with UUID {release_uuid}")
    else:
        print("LezKiss site not found in database")
