import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import polars as pl
import requests
import stashapi.log as logger

from .scene_matcher import SceneMatcher


class StashboxClient(ABC):
    @abstractmethod
    def query_performer_image(self, performer_stash_id):
        pass

    @abstractmethod
    def query_studio_image(self, performer_stash_id):
        pass

    @abstractmethod
    def query_scenes(self, performer_stash_id):
        pass


class StashDbClient(StashboxClient):
    def __init__(self, endpoint, api_key):
        self.endpoint = endpoint
        self.api_key = api_key
        self.scene_matcher = SceneMatcher()

    def query_performer_image(self, performer_stash_id):
        query = """
            query FindPerformer($id: ID!) {
                findPerformer(id: $id) {
                    id
                    images {
                        id
                        url
                    }
                }
            }
        """
        result = self._gql_query(query, {"id": performer_stash_id})
        if result:
            performer_data = result["data"]["findPerformer"]
            if (
                performer_data
                and performer_data["images"]
                and len(performer_data["images"]) > 0
            ):
                return performer_data["images"][0]["url"]
            else:
                logger.error(
                    f"No image found for performer with Stash ID {performer_stash_id}."
                )
                return None

        logger.error(f"Failed to query performer with Stash ID {performer_stash_id}.")
        return None

    def query_performer_images(self, performer_stash_id):
        query = """
            query FindPerformer($id: ID!) {
                findPerformer(id: $id) {
                    id
                    images {
                        id
                        url
                    }
                }
            }
        """
        result = self._gql_query(query, {"id": performer_stash_id})
        if result:
            performer_data = result["data"]["findPerformer"]
            if (
                performer_data
                and performer_data["images"]
                and len(performer_data["images"]) > 0
            ):
                return [image["url"] for image in performer_data["images"]]
            else:
                logger.error(
                    f"No images found for performer with Stash ID {performer_stash_id}."
                )
                return None

        logger.error(f"Failed to query performer with Stash ID {performer_stash_id}.")
        return None

    def query_studio_image(self, performer_stash_id):
        query = """
            query FindStudio($id: ID!) {
                findStudio(id: $id) {
                    id
                    images {
                        id
                        url
                    }
                }
            }
        """
        result = self._gql_query(query, {"id": performer_stash_id})
        if result:
            performer_data = result["data"]["findStudio"]
            if (
                performer_data
                and performer_data["images"]
                and len(performer_data["images"]) > 0
            ):
                return performer_data["images"][0]["url"]
            else:
                logger.error(
                    f"No image found for studio with Stash ID {performer_stash_id}."
                )
                return None

        logger.error(f"Failed to query studio with Stash ID {performer_stash_id}.")
        return None

    def query_scenes_by_performer(self, performer_stash_id):
        query = """
            query QueryScenes($stash_ids: [ID!]!, $page: Int!) {
                queryScenes(
                    input: {
                        performers: {
                            value: $stash_ids,
                            modifier: INCLUDES
                        },
                        per_page: 25,
                        page: $page
                    }
                ) {
                    scenes {
                        id
                        title
                        details
                        release_date
                        urls {
                            url
                            site {
                                name
                                url
                            }
                        }
                        studio {
                            id
                            name
                            parent {
                                id
                                name
                            }
                        }
                        images {
                            id
                            url
                        }
                        performers {
                            performer {
                                id
                                name
                                gender
                                aliases
                                birth_date
                                breast_type
                                cup_size
                                ethnicity
                                country
                                hair_color
                                eye_color
                                images {
                                    id
                                    url
                                }
                            }
                        }
                        duration
                        code
                        tags {
                            id
                            name
                        }
                    }
                    count
                }
            }
        """
        scenes = []
        page = 1
        total_scenes = None
        while True:
            result = self._gql_query(
                query, {"stash_ids": performer_stash_id, "page": page}
            )
            if result:
                scenes_data = result["data"]["queryScenes"]
                scenes.extend(scenes_data["scenes"])
                total_scenes = total_scenes or scenes_data["count"]
                if len(scenes) >= total_scenes or len(scenes_data["scenes"]) < 25:
                    break
                page += 1
            else:
                break

        return scenes

    def query_scenes_by_studio(self, studio_stash_id):
        query = """
            query QueryScenes($studio_ids: [ID!]!, $page: Int!) {
                queryScenes(
                    input: {
                        studios: {
                            value: $studio_ids,
                            modifier: INCLUDES
                        },
                        per_page: 25,
                        page: $page
                    }
                ) {
                    scenes {
                        id
                        title
                        details
                        release_date
                        urls {
                            url
                            site {
                                name
                                url
                            }
                        }
                        studio {
                            id
                            name
                            parent {
                                id
                                name
                            }
                        }
                        images {
                            id
                            url
                        }
                        performers {
                            performer {
                                id
                                name
                                gender
                                aliases
                                birth_date
                                breast_type
                                cup_size
                                ethnicity
                                country
                                hair_color
                                eye_color
                                images {
                                    id
                                    url
                                }
                            }
                        }
                        duration
                        code
                        tags {
                            id
                            name
                        }
                    }
                    count
                }
            }
        """
        scenes = []
        page = 1
        total_scenes = None
        while True:
            result = self._gql_query(
                query, {"studio_ids": studio_stash_id, "page": page}
            )
            if result:
                scenes_data = result["data"]["queryScenes"]
                scenes.extend(scenes_data["scenes"])
                total_scenes = total_scenes or scenes_data["count"]
                if len(scenes) >= total_scenes or len(scenes_data["scenes"]) < 25:
                    break
                page += 1
            else:
                break

        return scenes

    def query_scenes_by_phash(self, scenes: List[Dict]) -> pl.DataFrame:
        """Legacy method for querying scenes by phash"""
        phashes = [scene["phash"] for scene in scenes]
        scene_ids = [scene["stashdb_id"] for scene in scenes if scene.get("stashdb_id")]
        return self.query_scenes(scene_ids=scene_ids, phashes=phashes)

    def query_scenes_by_phash_optimized(self, scenes: List[Dict]) -> pl.DataFrame:
        """Optimized method for querying scenes by phash"""
        # Validate that all scenes have StashDB IDs
        scenes_without_ids = [scene for scene in scenes if not scene.get("stashdb_id")]
        if scenes_without_ids:
            raise ValueError(f"All scenes must have StashDB IDs. Found {len(scenes_without_ids)} scenes without IDs.")

        scene_ids = [scene["stashdb_id"] for scene in scenes]
        return self.query_scenes(scene_ids=scene_ids)

    def query_tag(self, tag_id: str) -> dict | None:
        """
        Query a single tag by ID, including deleted status.

        Args:
            tag_id: The StashDB tag ID

        Returns:
            dict with tag data including 'deleted' field, or None if not found
        """
        query = """
            query Tag($id: ID!) {
                findTag(id: $id) {
                    id
                    name
                    description
                    aliases
                    deleted
                    category {
                        id
                        name
                        group
                        description
                    }
                }
            }
        """
        result = self._gql_query(query, {"id": tag_id})
        if result and "data" in result and "findTag" in result["data"]:
            return result["data"]["findTag"]
        return None

    def query_tags(self):
        query = """
            query QueryTags($page: Int!, $per_page: Int!) {
                queryTags(input: {
                    page: $page
                    per_page: $per_page
                }) {
                    count
                    tags {
                        id
                        name
                        description
                        aliases
                        created
                        updated
                        category {
                            id
                            name
                            group
                            description
                        }
                    }
                }
            }
        """
        per_page = 25
        page = 1
        all_tags = []
        total_count = None

        while True:
            result = self._gql_query(query, {"page": page, "per_page": per_page})
            if result is None or "data" not in result or "queryTags" not in result["data"]:
                break

            tags_data = result["data"]["queryTags"]
            all_tags.extend(tags_data["tags"])

            if total_count is None:
                total_count = tags_data["count"]

            if len(all_tags) >= total_count:
                break

            page += 1

        return all_tags

    def submit_scene_draft(self, draft_input: dict) -> dict:
        """
        Submit a scene draft with just the title field.

        Args:
            draft_input: The draft input to submit

        Returns:
            dict: The response from the server containing the draft submission status
        """
        query = """
        mutation SubmitSceneDraft($input: SceneDraftInput!) {
            submitSceneDraft(input: $input) {
                id
            }
        }
        """

        variables = {
            "input": draft_input
        }

        return self._gql_query(query, variables)

    def _gql_query(self, query, variables=None):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Apikey"] = self.api_key
        response = requests.post(
            self.endpoint,
            json={"query": query, "variables": variables},
            headers=headers,
        )
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(
                f"Query failed with status code {response.status_code}: {response.text}"
            )
            return None

    def _get_scene_fragment(self):
        """Returns the GraphQL fragment for querying scene data"""
        return """
            id
            title
            code
            details
            director
            duration
            date
            urls {
                url
                type
            }
            images {
                id
                url
                width
                height
            }
            studio {
                id
                name
                urls {
                    url
                    type
                }
                images {
                    id
                    url
                    width
                    height
                }
                parent {
                    id
                    name
                    urls {
                        url
                        type
                    }
                    images {
                        id
                        url
                        width
                        height
                    }
                }
            }
            tags {
                name
                id
            }
            performers {
                as
                performer {
                    id
                    name
                    disambiguation
                    aliases
                    gender
                    merged_ids
                    urls {
                        url
                        type
                    }
                    images {
                        id
                        url
                        width
                        height
                    }
                    birth_date
                    ethnicity
                    country
                    eye_color
                    hair_color
                    height
                    measurements {
                        band_size
                        cup_size
                        waist
                        hip
                    }
                    breast_type
                    career_start_year
                    career_end_year
                    tattoos {
                        location
                        description
                    }
                    piercings {
                        location
                        description
                    }
                }
            }
            fingerprints {
                algorithm
                hash
                duration
            }
        """

    def _transform_scene_data(self, scene_data: dict, queried_phash: Optional[str] = None) -> dict:
        """Transform raw GraphQL scene data into standardized format"""
        if not scene_data:
            return {"queried_phash": queried_phash} if queried_phash else {}

        return {
            **({"queried_phash": queried_phash} if queried_phash else {}),
            "id": scene_data["id"],
            "title": scene_data["title"],
            "code": scene_data["code"],
            "duration": scene_data["duration"] * 1000 if scene_data["duration"] else None,
            "date": (
                datetime.strptime(scene_data.get("date", ""), "%Y-%m-%d").date()
                if scene_data.get("date")
                else None
            ),
            "urls": [
                {"url": url["url"], "type": url["type"]}
                for url in scene_data.get("urls", [])
            ],
            "images": [
                {
                    "id": image["id"],
                    "url": image["url"],
                    "width": image["width"],
                    "height": image["height"],
                }
                for image in scene_data.get("images", [])
            ],
            "studio": {
                "id": scene_data["studio"]["id"],
                "name": scene_data["studio"]["name"],
                "urls": [
                    {"url": url["url"], "type": url["type"]}
                    for url in scene_data["studio"].get("urls", [])
                ],
                "images": [
                    {
                        "id": image["id"],
                        "url": image["url"],
                        "width": image["width"],
                        "height": image["height"],
                    }
                    for image in scene_data["studio"].get("images", [])
                ],
                "parent": (
                    {
                        "id": scene_data["studio"]["parent"]["id"],
                        "name": scene_data["studio"]["parent"]["name"],
                        "urls": [
                            {"url": url["url"], "type": url["type"]}
                            for url in scene_data["studio"]["parent"].get("urls", [])
                        ],
                        "images": [
                            {
                                "id": image["id"],
                                "url": image["url"],
                                "width": image["width"],
                                "height": image["height"],
                            }
                            for image in scene_data["studio"]["parent"].get("images", [])
                        ],
                    }
                    if scene_data["studio"].get("parent")
                    else None
                ),
            },
            "tags": [
                {"name": tag["name"], "id": tag["id"]}
                for tag in scene_data.get("tags", [])
            ],
            "performers": [
                {
                    "as": performer["as"],
                    "performer": {
                        "id": performer["performer"]["id"],
                        "name": performer["performer"]["name"],
                        "disambiguation": performer["performer"]["disambiguation"],
                        "aliases": performer["performer"]["aliases"],
                        "gender": performer["performer"]["gender"],
                        "merged_ids": performer["performer"]["merged_ids"],
                        "urls": [
                            {"url": url["url"], "type": url["type"]}
                            for url in performer["performer"].get("urls", [])
                        ],
                        "images": [
                            {
                                "id": image["id"],
                                "url": image["url"],
                                "width": image["width"],
                                "height": image["height"],
                            }
                            for image in performer["performer"].get("images", [])
                        ],
                        "birth_date": performer["performer"]["birth_date"],
                        "ethnicity": performer["performer"]["ethnicity"],
                        "country": performer["performer"]["country"],
                        "eye_color": performer["performer"]["eye_color"],
                        "hair_color": performer["performer"]["hair_color"],
                        "height": performer["performer"]["height"],
                        "measurements": {
                            "band_size": performer["performer"]["measurements"]["band_size"],
                            "cup_size": performer["performer"]["measurements"]["cup_size"],
                            "waist": performer["performer"]["measurements"]["waist"],
                            "hip": performer["performer"]["measurements"]["hip"],
                        },
                        "breast_type": performer["performer"]["breast_type"],
                        "career_start_year": performer["performer"]["career_start_year"],
                        "career_end_year": performer["performer"]["career_end_year"],
                        "tattoos": [
                            {
                                "location": tattoo.get("location"),
                                "description": tattoo.get("description"),
                            }
                            for tattoo in performer["performer"].get("tattoos") or []
                        ],
                        "piercings": [
                            {
                                "location": piercing["location"],
                                "description": piercing["description"],
                            }
                            for piercing in performer["performer"].get("piercings") or []
                        ],
                    },
                }
                for performer in scene_data.get("performers", [])
            ],
            "fingerprints": [
                {
                    "algorithm": fingerprint["algorithm"],
                    "hash": fingerprint["hash"],
                    "duration": fingerprint["duration"],
                }
                for fingerprint in scene_data.get("fingerprints") or []
            ],
            "stashdb_data": json.dumps(scene_data)
        }

    def query_scenes(self, scene_ids: Optional[List[str]] = None, phashes: Optional[List[str]] = None) -> pl.DataFrame:
        """
        Query scenes by either their StashDB IDs or phash values.

        Args:
            scene_ids: Optional list of StashDB scene IDs
            phashes: Optional list of phash values

        Returns:
            pl.DataFrame: DataFrame containing the scene data
        """
        if not scene_ids and not phashes:
            raise ValueError("Must provide either scene_ids or phashes")

        fragment = self._get_scene_fragment()

        # Query scenes by ID
        scenes_by_id = {}
        if scene_ids:
            find_scene_query = f"""
                query FindScene($id: ID!) {{
                    findScene(id: $id) {{
                        {fragment}
                    }}
                }}
            """

            for scene_id in scene_ids:
                result = self._gql_query(find_scene_query, {"id": scene_id})
                if result and "data" in result and "findScene" in result["data"]:
                    scenes_by_id[scene_id] = result["data"]["findScene"]

        # Query scenes by phash
        scenes_by_phash = {}
        if phashes:
            find_scenes_query = f"""
                query FindScenesByFullFingerprints($fingerprints: [FingerprintQueryInput!]!) {{
                    findScenesByFullFingerprints(fingerprints: $fingerprints) {{
                        {fragment}
                    }}
                }}
            """

            variables = {
                "fingerprints": [{"algorithm": "PHASH", "hash": phash} for phash in phashes]
            }

            result = self._gql_query(find_scenes_query, variables)
            if result and "data" in result and "findScenesByFullFingerprints" in result["data"]:
                stashdb_scenes = result["data"]["findScenesByFullFingerprints"]
                scenes_by_phash = self.scene_matcher.match_scenes(
                    [{"phash": phash} for phash in phashes],
                    stashdb_scenes
                )

        # Transform results
        transformed_scenes = []

        for scene_id, scene_data in scenes_by_id.items():
            transformed_scenes.append(self._transform_scene_data(scene_data))

        for phash, scene_data in scenes_by_phash.items():
            transformed_scenes.append(self._transform_scene_data(scene_data, phash))

        # Create DataFrame with schema
        schema = {
            "queried_phash": pl.Utf8,
            "id": pl.Utf8,
            "title": pl.Utf8,
            "code": pl.Utf8,
            "duration": pl.Duration(time_unit="ms"),
            "date": pl.Date,
            "urls": pl.List(pl.Struct({"url": pl.Utf8, "type": pl.Utf8})),
            "images": pl.List(
                pl.Struct(
                    {
                        "id": pl.Utf8,
                        "url": pl.Utf8,
                        "width": pl.Int64,
                        "height": pl.Int64,
                    }
                )
            ),
            "studio": pl.Struct(
                {
                    "id": pl.Utf8,
                    "name": pl.Utf8,
                    "urls": pl.List(pl.Struct({"url": pl.Utf8, "type": pl.Utf8})),
                    "images": pl.List(
                        pl.Struct(
                            {
                                "id": pl.Utf8,
                                "url": pl.Utf8,
                                "width": pl.Int64,
                                "height": pl.Int64,
                            }
                        )
                    ),
                    "parent": pl.Struct(
                        {
                            "id": pl.Utf8,
                            "name": pl.Utf8,
                            "urls": pl.List(
                                pl.Struct({"url": pl.Utf8, "type": pl.Utf8})
                            ),
                        }
                    ),
                }
            ),
            "tags": pl.List(pl.Struct({"name": pl.Utf8, "id": pl.Utf8})),
            "performers": pl.List(
                pl.Struct(
                    {
                        "as": pl.Utf8,
                        "performer": pl.Struct(
                            {
                                "id": pl.Utf8,
                                "name": pl.Utf8,
                                "disambiguation": pl.Utf8,
                                "aliases": pl.List(pl.Utf8),
                                "gender": pl.Utf8,
                                "merged_ids": pl.List(pl.Utf8),
                                "urls": pl.List(
                                    pl.Struct({"url": pl.Utf8, "type": pl.Utf8})
                                ),
                                "images": pl.List(
                                    pl.Struct(
                                        {
                                            "id": pl.Utf8,
                                            "url": pl.Utf8,
                                            "width": pl.Int64,
                                            "height": pl.Int64,
                                        }
                                    )
                                ),
                                "birth_date": pl.Date,
                                "ethnicity": pl.Utf8,
                                "country": pl.Utf8,
                                "eye_color": pl.Utf8,
                                "hair_color": pl.Utf8,
                                "height": pl.Int64,
                                "measurements": pl.Struct(
                                    {
                                        "band_size": pl.Utf8,
                                        "cup_size": pl.Utf8,
                                        "waist": pl.Utf8,
                                        "hip": pl.Utf8,
                                    }
                                ),
                                "breast_type": pl.Utf8,
                                "career_start_year": pl.Int64,
                                "career_end_year": pl.Int64,
                                "tattoos": pl.List(
                                    pl.Struct(
                                        {"location": pl.Utf8, "description": pl.Utf8}
                                    )
                                ),
                                "piercings": pl.List(
                                    pl.Struct(
                                        {"location": pl.Utf8, "description": pl.Utf8}
                                    )
                                ),
                            }
                        ),
                    }
                )
            ),
            "fingerprints": pl.List(
                pl.Struct(
                    {"algorithm": pl.Utf8, "hash": pl.Utf8, "duration": pl.Int64}
                )
            ),
            "stashdb_data": pl.Utf8,
        }

        return pl.DataFrame(transformed_scenes, schema=schema)
