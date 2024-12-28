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
                **self._get_stash_ids(studio.get("stash_ids", []))
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
                parent_stash_ids = self._get_stash_ids(parent_studio.get("stash_ids", []))
                studio_data["stash_studios_parent_studio_stashdb_id"] = parent_stash_ids["stash_studios_stashdb_id"]
                studio_data["stash_studios_parent_studio_tpdb_id"] = parent_stash_ids["stash_studios_tpdb_id"]
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
            "stash_studios_parent_studio_tpdb_id": pl.Utf8
        }

        df_studios = pl.DataFrame(studios, schema=schema)
        return df_studios

    def _get_stash_ids(self, stash_ids):
        """Extract StashDB and TPDB IDs from stash_ids list."""
        result = {
            "stash_studios_stashdb_id": None,
            "stash_studios_tpdb_id": None
        }
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
                    "id": int(stash_scene.get("id")),
                    "title": stash_scene.get("title", ""),
                    "details": stash_scene.get("details", ""),
                    "date": (
                        datetime.strptime(
                            stash_scene.get("date", ""), "%Y-%m-%d"
                        ).date()
                        if stash_scene.get("date")
                        else None
                    ),
                    "urls": stash_scene.get("urls", []),
                    "created_at": (
                        datetime.fromisoformat(
                            stash_scene.get("created_at").replace("Z", "+00:00")
                        )
                        if stash_scene.get("created_at")
                        else None
                    ),
                    "updated_at": (
                        datetime.fromisoformat(
                            stash_scene.get("updated_at").replace("Z", "+00:00")
                        )
                        if stash_scene.get("updated_at")
                        else None
                    ),
                    "performers": stash_scene.get("performers", []),
                    "studio": stash_scene.get("studio", {}),
                    "files": [
                        {
                            "id": int(f.get("id")),
                            "path": f.get("path", ""),
                            "size": int(f.get("size", 0)),
                            "duration": int(
                                f.get("duration", 0) * 1000
                            ),  # Convert seconds to milliseconds
                        }
                        for f in stash_scene.get("files", [])
                    ],
                    "tags": stash_scene.get("tags", []),
                    "organized": stash_scene.get("organized", False),
                    "interactive": stash_scene.get("interactive", False),
                    "play_duration": stash_scene.get("play_duration", 0),
                    "play_count": stash_scene.get("play_count", 0),
                    "o_counter": stash_scene.get("o_counter", 0),
                }
                scenes.append(scene_data)

        schema = {
            "id": pl.Int64,
            "title": pl.Utf8,
            "details": pl.Utf8,
            "date": pl.Date,
            "urls": pl.List(pl.Utf8),
            "created_at": pl.Datetime,
            "updated_at": pl.Datetime,
            "performers": pl.List(
                pl.Struct(
                    {
                        "id": pl.Int64,
                        "name": pl.Utf8,
                        "disambiguation": pl.Utf8,
                        "alias_list": pl.List(pl.Utf8),
                        "gender": pl.Enum(["MALE", "FEMALE", "TRANSGENDER_MALE", "TRANSGENDER_FEMALE", "NON_BINARY"]),
                    }
                )
            ),
            "studio": pl.Struct(
                {
                    "id": pl.Int64,
                    "name": pl.Utf8,
                    "url": pl.Utf8,
                    "parent_studio": pl.Struct(
                        {"id": pl.Int64, "name": pl.Utf8, "url": pl.Utf8}
                    ),
                }
            ),
            "files": pl.List(
                pl.Struct(
                    {
                        "id": pl.Int64,
                        "path": pl.Utf8,
                        "size": pl.Int64,
                        "duration": pl.Duration(time_unit="ms"),
                    }
                )
            ),
            "tags": pl.List(pl.Struct({"id": pl.Int64, "name": pl.Utf8})),
            "organized": pl.Boolean,
            "interactive": pl.Boolean,
            "play_duration": pl.Int64,
            "play_count": pl.Int64,
            "o_counter": pl.Int64,
        }

        df_scenes = pl.DataFrame(scenes, schema=schema)
        return df_scenes
