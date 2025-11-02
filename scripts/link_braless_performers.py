#!/usr/bin/env python3
"""
Script to link Braless Forever performers to StashDB and Stashapp.

This script processes a lookup table mapping Braless Forever performer IDs
to StashDB IDs, finds the corresponding Stashapp performers, and links them
in the Culture Extractor database.

Usage:
    python scripts/link_braless_performers.py [--dry-run]
"""

import json
import subprocess
import sys
from typing import Optional


# Lookup table: Braless Forever ID -> StashDB ID
LOOKUP_TABLE = {
    "1a28dfbc-70ee-4ff3-875c-0c7b9d1125e6": "fb7a0e15-fa8c-4b3d-9cdf-69c75351d785",
    "1a365cda-e30b-4d1b-b4be-b7d2406c6106": "9aceabeb-8e45-474b-bbb4-793132e5e28f",
    "1ccdcf89-d623-48f8-a632-7422d28379fc": "5b415185-387e-42bb-9699-4dc99a51b2a4",
    "1e448b98-f6cb-4d20-9220-a35d382b34b7": "0f86b8ab-c2f1-4622-b144-160cac9cdb76",
    "1ef72544-124f-4da0-b25f-5b25e7560d4c": "7eeedf72-757a-4d76-8889-abc2490c3a90",
    "2e6926ab-d803-4607-bf42-5d992558b329": "252e5c16-1a18-4986-ae53-55c33beeeba7",
    "3e6ff29b-bda2-442a-b5d6-4de4ae8b816d": "b9239163-8afd-4618-a971-0b25f10122a6",
    "03f56534-983e-4f70-8cb7-73b428c66f2f": "a68a7630-4282-4d60-9734-6f695dea6ab8",
    "5e40833c-c4e8-45cd-af3b-5614485c2232": "3c06e0a7-bb29-41ad-b9b2-13ff14d2cf37",
    "5ed1e1f8-db71-4d3b-a7a4-ef13b8e8601b": "595aeb2b-1c9f-4fc6-a4fa-5c4c6208ba0d",
    "6aedfd99-b1fe-43fd-80e3-979789205b39": "a30d9ca6-ed66-47cc-b9e4-2e0858c2ed0d",
    "7a7f85d0-c472-4862-8a0c-bf638124b4db": "428ad0e3-2abe-41f5-bd95-f2f94f94c2d1",
    "8c4e67dd-82ef-4560-aada-aebf6e84df3d": "8a3e0ebe-79f4-4063-b909-4774b9dac132",
    "8cb53af0-6caa-4299-b7cf-6fc9a0b5edbc": "5b30517d-36e1-420b-88e1-9206fb6f5834",
    "8e839a03-25fc-4b1d-bc84-a87d48eaffb9": "1607e117-523f-455d-9621-0b72c2de1de6",
    "9fb6f59f-1a40-46de-8163-627074386cd7": "90d87c00-220c-480c-80cc-ad06d1f34c23",
    "35bd8c49-d9ea-4489-8e37-4c363f3df293": "84cb1e78-bfb3-40a9-8935-582d645d94b4",
    "47c780e9-0f2b-489f-8fc8-774988762411": "2e802072-4f12-4a20-af15-8d46c447f55b",
    "47fff61d-cc7c-47c5-903c-b469ab4bbbd4": "95e5ead8-7b6d-4cf1-a744-a0456580f2ef",
    "54acf36f-1bba-4e64-a491-58ff61414f67": "c74d01a3-4277-4c4e-bcf8-ee1e7fb01a89",
    "85d9ba1a-16ca-40b4-a944-729a2f2f0d87": "da96670a-18ff-4a33-8764-84075c2e2dc6",
    "92d2f82b-b2d1-4a01-9752-fadb583254ae": "cf60621d-3aaf-4e09-b681-db1ebcbbd007",
    "263e1a1e-eeeb-4112-b97a-4e5962aed0e3": "6d6a068c-08d8-401a-8e39-ff9a896f6d42",
    "705a89a0-0fc6-4cb4-aaba-246c0e9113d7": "bc8e19ff-5d2a-4ea2-940c-84dc3002a170",
    "934fec53-9c76-44c3-97a2-6a4bc1b9bec2": "c2261ee2-80d0-4af4-a411-3513103c15fe",
    "958bb1ec-0404-4dfb-bbf8-bfd5dacef4de": "69b5bb3b-6a55-4fa7-be05-89729be60bcb",
    "2723c18c-2c00-44c2-b383-a9f146ed7e95": "81c09da6-c015-4bda-8b60-215413f7a848",
    "3090fe3d-93d7-472e-be6b-5d3477f2f5d9": "75fa549b-4eb4-4546-866f-54a7ef45510a",
    "4913ceca-da66-461e-846e-47e960d5e095": "d999036d-0ade-4baa-a2ff-4dd0ad66acf2",
    "6386d0f1-cf2c-427e-8319-e735d45a2833": "dfe78942-05d7-47df-a5fd-19db80f0b34d",
    "9b7e8fa6-fc0c-473d-be32-6e2094540d4a": "d0ba0862-f086-4d06-9693-06ae74eadf9a",
    "7092148f-5827-45a9-9694-ee1f68d1e317": "b71cb4b5-e8c5-4da1-872a-42688bd07329",
    "79404954-f100-4444-ac12-04cd8ab0aa2d": "14749fcf-c6da-48bd-9a60-85013fa135e2",
    "86610361-af27-4b67-9593-a5d28226ecca": "466e1eae-ddbf-4807-8f8a-e1da3ce275f7",
    "88603679-7194-448a-b310-2ee1973c4976": "4be40db3-10e4-447e-919f-8336a2224b89",
    "a1da8b99-12eb-44ad-ac80-0c86c1780bad": "6fcba8c2-8789-4650-a41e-eb62b4a28e1b",
    "a56bcc11-1fde-4069-945b-2cfe09caa3e9": "9d206547-4483-450e-8041-a2017e0f5a6b",
    "a641270c-fd68-4243-bed2-5c759493837e": "587e6430-889a-4d40-9f98-f5bebbc02f23",
    "ab9c54d5-2231-482a-9dca-640048847bb6": "bc92c0ac-c404-41eb-bf78-dfd3b52145f9",
    "ae9ad1e1-8bf1-4d0c-b53d-9538b3829d8f": "a0d89267-0e9d-4b19-9873-bf31b0155881",
    "b47a251d-bbfc-4481-9baf-6fdf0d060f0f": "b60d173e-1184-4969-8a05-0d46ad4bfd18",
    "b28796c2-8df5-4ddb-b822-8ae3698627c0": "44bb369a-aae0-428d-bcf7-f67bd795fa04",
    "ba67f1fe-5780-441b-8015-8835a479dd6e": "dad1a60a-fdf2-424e-aae4-e5cb53fc4409",
    "c406ee5d-4059-4563-835b-77ad1f3010fa": "3a6dd251-66ba-44a6-a1e6-c2e78c96c40c",
    "ca796ef8-ddfd-4acf-8e8c-5f3adc9164d1": "3cb2be08-a758-4ead-9d44-f5e3526a1b43",
    "d6e0df83-be1b-4e55-821e-01b8fe6fd042": "04d4eb12-40e3-4870-872a-c6a26ad77100",
    "dce8a666-c772-4961-80a7-f444c67780c0": "db64e768-89a8-4900-9775-d0b743a30d87",
    "e8433d50-6c05-47de-95d0-666731e33482": "ac5c612b-d941-416e-bdf0-f777adddd249",
    "eb7c8f03-52d4-4897-a20b-40d576c6b5eb": "1cd4c3bf-1bcc-4e0d-a313-b591612cec6d",
    "f49e45f2-fc0e-4b64-9a9d-9d4f7abbad62": "7303ab42-4f71-454e-98f5-dfefa82e05c2",
    "f95e01c3-6809-4aac-b51b-f2fd03be0f90": "ed5d6e1d-6231-484a-93c0-33e17a2e968a",
    "fa5115ac-1a2b-4c2c-9235-a6e69d0f3c10": "226c4056-38ea-46ac-aff0-0f9cb7a160db",
}


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def get_ce_performers() -> dict[str, dict]:
    """Fetch all Braless Forever performers from CE."""
    print("📥 Fetching Braless Forever performers from CE database...")
    code, stdout, stderr = run_command(["uv", "run", "ce", "performers", "list", "--site", "bralessforever", "--json"])

    if code != 0:
        print(f"❌ Error fetching CE performers: {stderr}")
        sys.exit(1)

    # Find the JSON array in stdout (skip any non-JSON output before it)
    json_start = stdout.find('[')
    if json_start == -1:
        print(f"❌ No JSON array found in output")
        sys.exit(1)

    performers = json.loads(stdout[json_start:])
    # Create lookup by short_name
    lookup = {p["ce_performers_short_name"]: p for p in performers}
    print(f"✓ Found {len(lookup)} performers in CE")
    return lookup


def get_stashapp_performer(stashdb_id: str) -> Optional[dict]:
    """Find Stashapp performer by StashDB ID."""
    code, stdout, stderr = run_command([
        "uv", "run", "stash-cli", "performers", "list",
        "--stashdb-id", stashdb_id, "--json"
    ])

    if code != 0:
        return None

    # Find the JSON array in stdout (skip any non-JSON output before it)
    json_start = stdout.find('[')
    if json_start == -1:
        return None

    performers = json.loads(stdout[json_start:])
    return performers[0] if performers else None


def link_performer(ce_uuid: str, stashapp_id: int, stashdb_id: str, dry_run: bool = False) -> bool:
    """Link CE performer to Stashapp and StashDB."""
    if dry_run:
        print(f"  [DRY RUN] Would link {ce_uuid} → Stashapp:{stashapp_id}, StashDB:{stashdb_id}")
        return True

    code, stdout, stderr = run_command([
        "uv", "run", "ce", "performers", "link", ce_uuid,
        "--stashapp-id", str(stashapp_id),
        "--stashdb-id", stashdb_id
    ])

    return code == 0


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    else:
        print("🚀 Starting performer linking process\n")

    # Step 1: Get all CE performers
    ce_performers = get_ce_performers()
    print()

    # Step 2: Process each entry in lookup table
    total = len(LOOKUP_TABLE)
    success = 0
    skipped = 0
    failed = 0
    skipped_details = []

    for idx, (bf_id, stashdb_id) in enumerate(LOOKUP_TABLE.items(), 1):
        print(f"[{idx}/{total}] Processing {bf_id[:8]}...")

        # Find CE performer
        ce_performer = ce_performers.get(bf_id)
        if not ce_performer:
            print(f"  ⚠️  Not found in CE database - skipping")
            skipped += 1
            skipped_details.append({
                "bf_id": bf_id,
                "stashdb_id": stashdb_id,
                "reason": "Not found in CE database"
            })
            continue

        ce_uuid = ce_performer["ce_performers_uuid"]
        ce_name = ce_performer["ce_performers_name"]
        print(f"  Found in CE: {ce_name} ({ce_uuid})")

        # Find Stashapp performer
        stashapp_performer = get_stashapp_performer(stashdb_id)
        if not stashapp_performer:
            print(f"  ⚠️  StashDB ID not found in Stashapp - skipping")
            skipped += 1
            skipped_details.append({
                "bf_id": bf_id,
                "ce_name": ce_name,
                "ce_uuid": ce_uuid,
                "stashdb_id": stashdb_id,
                "reason": "StashDB ID not found in Stashapp"
            })
            continue

        stashapp_id = stashapp_performer["stashapp_id"]
        stashapp_name = stashapp_performer["stashapp_name"]
        print(f"  Found in Stashapp: {stashapp_name} (ID: {stashapp_id})")

        # Link them
        if link_performer(ce_uuid, stashapp_id, stashdb_id, dry_run):
            print(f"  ✓ Linked successfully")
            success += 1
        else:
            print(f"  ❌ Failed to link")
            failed += 1

        print()

    # Summary
    print("=" * 60)
    print("📊 Summary")
    print("=" * 60)
    print(f"Total entries:     {total}")
    print(f"✓ Linked:          {success}")
    print(f"⚠️  Skipped:        {skipped}")
    print(f"❌ Failed:         {failed}")

    # Show skipped details
    if skipped_details:
        print("\n" + "=" * 60)
        print("⚠️  Skipped Performers Details")
        print("=" * 60)
        for detail in skipped_details:
            print(f"\nPerformer: {detail.get('ce_name', 'Unknown')}")
            if 'ce_uuid' in detail:
                print(f"  CE UUID: {detail['ce_uuid']}")
            print(f"  Braless Forever ID: {detail['bf_id']}")
            print(f"  StashDB ID: {detail['stashdb_id']}")
            print(f"  Reason: {detail['reason']}")

        # Export StashDB IDs to file for easy reference
        stashdb_ids = [d['stashdb_id'] for d in skipped_details]
        print(f"\n📝 StashDB IDs not found in Stashapp ({len(stashdb_ids)}):")
        for stashdb_id in stashdb_ids:
            print(f"  {stashdb_id}")

    if dry_run:
        print("\n💡 Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()
