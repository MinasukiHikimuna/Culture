from typing import List
import numpy as np
import pandas as pd
import stashapi.log as log
from stashapi.stashapp import StashInterface
from datetime import datetime
from dotenv import load_dotenv
import os
import polars as pl

# Load the .env file
load_dotenv()


def get_stashapp_client(prefix=""):
    # Use the provided prefix to get environment variables
    scheme = os.getenv(f"{prefix}STASHAPP_SCHEME")
    host = os.getenv(f"{prefix}STASHAPP_HOST")
    port = os.getenv(f"{prefix}STASHAPP_PORT")
    api_key = os.getenv(f"{prefix}STASHAPP_API_KEY")

    stash = StashInterface(
        {
            "scheme": scheme,
            "host": host,
            "port": port,
            "logger": log,
            "ApiKey": api_key,
        }
    )
    return stash


class StashAppClient:
    def __init__(self, prefix=""):
        self.stash = get_stashapp_client(prefix)

    def get_studios(self) -> pl.DataFrame:
        fragment = """
        id
        name
        url
        stash_ids {
            endpoint
            stash_id
            updated_at
        }
        parent_studio {
            id
            name
            url
            stash_ids {
                endpoint
                stash_id
                updated_at
            }
        }
        """

        stashapp_studios = self.stash.find_studios(fragment=fragment)

        studios = []
        for studio in stashapp_studios:
            studio_data = {
                "stash_studios_id": int(studio.get("id")),
                "stash_studios_name": studio.get("name"),
                "stash_studios_url": studio.get("url"),
                **self._get_stash_ids(studio.get("stash_ids", [])),
            }
            parent_studio = studio.get("parent_studio")
            if parent_studio:
                studio_data["stash_studios_parent_studio_id"] = int(
                    parent_studio.get("id")
                )
                studio_data["stash_studios_parent_studio_name"] = parent_studio.get(
                    "name"
                )
                studio_data["stash_studios_parent_studio_url"] = parent_studio.get(
                    "url"
                )
                parent_stash_ids = self._get_stash_ids(
                    parent_studio.get("stash_ids", [])
                )
                studio_data["stash_studios_parent_studio_stashdb_id"] = (
                    parent_stash_ids["stash_studios_stashdb_id"]
                )
                studio_data["stash_studios_parent_studio_tpdb_id"] = parent_stash_ids[
                    "stash_studios_tpdb_id"
                ]
            else:
                studio_data["stash_studios_parent_studio_id"] = None
                studio_data["stash_studios_parent_studio_name"] = None
                studio_data["stash_studios_parent_studio_url"] = None
                studio_data["stash_studios_parent_studio_stashdb_id"] = None
                studio_data["stash_studios_parent_studio_tpdb_id"] = None
            studios.append(studio_data)

        schema = {
            "stash_studios_id": pl.Int64,
            "stash_studios_name": pl.Utf8,
            "stash_studios_url": pl.Utf8,
            "stash_studios_stashdb_id": pl.Utf8,
            "stash_studios_tpdb_id": pl.Utf8,
            "stash_studios_parent_studio_id": pl.Int64,
            "stash_studios_parent_studio_name": pl.Utf8,
            "stash_studios_parent_studio_url": pl.Utf8,
            "stash_studios_parent_studio_stashdb_id": pl.Utf8,
            "stash_studios_parent_studio_tpdb_id": pl.Utf8,
        }

        df_studios = pl.DataFrame(studios, schema=schema)
        return df_studios

    def _get_stash_ids(self, stash_ids):
        """Extract StashDB and TPDB IDs from stash_ids list."""
        result = {"stash_studios_stashdb_id": None, "stash_studios_tpdb_id": None}
        if stash_ids:
            for stash_id in stash_ids:
                if stash_id["endpoint"] == "https://stashdb.org/graphql":
                    result["stash_studios_stashdb_id"] = stash_id["stash_id"]
                elif stash_id["endpoint"] == "https://theporndb.net/graphql":
                    result["stash_studios_tpdb_id"] = stash_id["stash_id"]
        return result

    def find_scenes_by_oshash(self, oshashes: List[str]) -> pl.DataFrame:
        fragment = """
        id
        title
        details
        date
        urls
        created_at
        updated_at
        organized
        interactive
        play_duration
        play_count
        o_counter
        performers {
            id
            name
            disambiguation
            alias_list
            gender
        }
        studio {
            id
            name
            url
            parent_studio {
                id
                name
                url
            }
        }
        files {
            id
            path
            size
            duration
            fingerprints {
                type
                value
            }
        }
        tags {
            id
            name
        }
        """

        scenes = []
        for oshash in oshashes:
            stash_scene = self.stash.find_scene_by_hash({"oshash": oshash}, fragment)
            if stash_scene:
                # Extract fields according to our schema
                scene_data = {
                    "stashapp_id": int(stash_scene.get("id")),
                    "stashapp_title": stash_scene.get("title", ""),
                    "stashapp_details": stash_scene.get("details", ""),
                    "stashapp_date": (
                        datetime.strptime(
                            stash_scene.get("date", ""), "%Y-%m-%d"
                        ).date()
                        if stash_scene.get("date")
                        else None
                    ),
                    "stashapp_urls": stash_scene.get("urls", []),
                    "stashapp_created_at": (
                        datetime.fromisoformat(
                            stash_scene.get("created_at").replace("Z", "+00:00")
                        )
                        if stash_scene.get("created_at")
                        else None
                    ),
                    "stashapp_updated_at": (
                        datetime.fromisoformat(
                            stash_scene.get("updated_at").replace("Z", "+00:00")
                        )
                        if stash_scene.get("updated_at")
                        else None
                    ),
                    "stashapp_performers": stash_scene.get("performers", []),
                    "stashapp_studio": stash_scene.get("studio", {}),
                    "stashapp_files": [
                        {
                            "id": int(f.get("id")),
                            "path": f.get("path", ""),
                            "size": int(f.get("size", 0)),
                            "duration": int(
                                f.get("duration", 0) * 1000
                            ),  # Convert seconds to milliseconds
                            "fingerprints": [
                                {
                                    "type": fp.get("type", ""),
                                    "value": fp.get("value", ""),
                                }
                                for fp in f.get("fingerprints", [])
                            ],
                        }
                        for f in stash_scene.get("files", [])
                    ],
                    "stashapp_primary_file_path": stash_scene.get("files", [])[0].get("path", ""),
                    "stashapp_primary_file_oshash": next((fp['value'] for fp in stash_scene.get("files", [])[0].get("fingerprints", []) if fp['type'] == 'oshash'), None),
                    "stashapp_primary_file_phash": next((fp['value'] for fp in stash_scene.get("files", [])[0].get("fingerprints", []) if fp['type'] == 'phash'), None),
                    "stashapp_primary_file_xxhash": next((fp['value'] for fp in stash_scene.get("files", [])[0].get("fingerprints", []) if fp['type'] == 'xxhash'), None),
                    "stashapp_primary_file_duration": stash_scene.get("files", [])[0].get("duration", 0) * 1000,
                    "stashapp_tags": stash_scene.get("tags", []),
                    "stashapp_organized": stash_scene.get("organized", False),
                    "stashapp_interactive": stash_scene.get("interactive", False),
                    "stashapp_play_duration": stash_scene.get("play_duration", 0),
                    "stashapp_play_count": stash_scene.get("play_count", 0),
                    "stashapp_o_counter": stash_scene.get("o_counter", 0),
                }
                scenes.append(scene_data)

        schema = {
            "stashapp_id": pl.Int64,
            "stashapp_title": pl.Utf8,
            "stashapp_details": pl.Utf8,
            "stashapp_date": pl.Date,
            "stashapp_urls": pl.List(pl.Utf8),
            "stashapp_created_at": pl.Datetime,
            "stashapp_updated_at": pl.Datetime,
            "stashapp_performers": pl.List(
                pl.Struct(
                    {
                        "id": pl.Int64,
                        "name": pl.Utf8,
                        "disambiguation": pl.Utf8,
                        "alias_list": pl.List(pl.Utf8),
                        "gender": pl.Enum(
                            [
                                "MALE",
                                "FEMALE",
                                "TRANSGENDER_MALE",
                                "TRANSGENDER_FEMALE",
                                "NON_BINARY",
                            ]
                        ),
                    }
                )
            ),
            "stashapp_studio": pl.Struct(
                {
                    "id": pl.Int64,
                    "name": pl.Utf8,
                    "url": pl.Utf8,
                    "parent_studio": pl.Struct(
                        {"id": pl.Int64, "name": pl.Utf8, "url": pl.Utf8}
                    ),
                }
            ),
            "stashapp_files": pl.List(
                pl.Struct(
                    {
                        "id": pl.Int64,
                        "path": pl.Utf8,
                        "size": pl.Int64,
                        "duration": pl.Duration(time_unit="ms"),
                        "fingerprints": pl.List(
                            pl.Struct(
                                {
                                    "type": pl.Utf8,
                                    "value": pl.Utf8,
                                }
                            )
                        ),
                    }
                )
            ),
            "stashapp_primary_file_path": pl.Utf8,
            "stashapp_primary_file_oshash": pl.Utf8,
            "stashapp_primary_file_phash": pl.Utf8,
            "stashapp_primary_file_xxhash": pl.Utf8,
            "stashapp_primary_file_duration": pl.Duration(time_unit="ms"),
            "stashapp_tags": pl.List(pl.Struct({"id": pl.Int64, "name": pl.Utf8})),
            "stashapp_organized": pl.Boolean,
            "stashapp_interactive": pl.Boolean,
            "stashapp_play_duration": pl.Int64,
            "stashapp_play_count": pl.Int64,
            "stashapp_o_counter": pl.Int64,
        }

        df_scenes = pl.DataFrame(scenes, schema=schema)

        return df_scenes

    def set_studio_stash_id_for_endpoint(
        self, studio_id: int, endpoint: str, stash_id: str
    ):
        refreshed_studio = self.stash.find_studio(
            studio_id,
            fragment="""
            id
            name
            url
            stash_ids {
                endpoint
                stash_id
                updated_at
            }
            """,
        )

        existing_stash_ids = refreshed_studio.get("stash_ids", [])
        existing_entry = next(
            (x for x in existing_stash_ids if x["endpoint"] == endpoint), None
        )

        if existing_entry and existing_entry["stash_id"] == stash_id:
            return

        if existing_entry:
            new_stash_ids = [
                {
                    "endpoint": x["endpoint"],
                    "stash_id": (
                        stash_id if x["endpoint"] == endpoint else x["stash_id"]
                    ),
                }
                for x in existing_stash_ids
            ]
        else:
            new_stash_ids = [
                *[
                    {
                        "endpoint": x["endpoint"],
                        "stash_id": x["stash_id"],
                    }
                    for x in existing_stash_ids
                ],
                {"endpoint": endpoint, "stash_id": stash_id},
            ]

        self.stash.update_studio({"id": studio_id, "stash_ids": new_stash_ids})
