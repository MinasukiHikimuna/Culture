from typing import Dict, List, Optional
import polars as pl
import requests
from datetime import datetime
import stashapi.log as logger

from abc import ABC, abstractmethod
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

    def query_scenes(self, performer_stash_id):
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

    def query_scenes_by_phash(self, scenes: List[Dict]) -> pl.DataFrame:
        """
        Query StashDB for multiple scenes using their phash fingerprints in a single request.

        Args:
            scenes (list[dict]): List of scene objects

        Returns:
            pl.DataFrame: DataFrame with phash, id, title, code, duration, date, urls, images, studio, tags, performers
        """
        fragment = """
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
        
        find_scene = f"""
            query FindScene($id: ID!) {{
                findScene(id: $id) {{
                    {fragment}
                }}
            }}
        """
        
        find_scenes_by_full_fingerprints = f"""
            query FindScenesByFullFingerprints($fingerprints: [FingerprintQueryInput!]!) {{
                findScenesByFullFingerprints(fingerprints: $fingerprints) {{
                    {fragment}
                }}
            }}
        """
    
        scenes_with_stashdb_id = [scene for scene in scenes if scene["stashdb_id"]]
        scenes_without_stashdb_id = [scene for scene in scenes if not scene["stashdb_id"]]

        results_with_stashdb_id = {}
        for scene in scenes_with_stashdb_id:
            find_scene_result = self._gql_query(find_scene, {"id": scene["stashdb_id"]})
            if find_scene_result:
                results_with_stashdb_id[scene["phash"]] = find_scene_result["data"]["findScene"]

        find_scenes_by_full_fingerprints_variables = {
            "fingerprints": [
                {"algorithm": "PHASH", "hash": scene["phash"]} for scene in scenes_without_stashdb_id
            ]
        }

        results_without_stashdb_id = self._gql_query(find_scenes_by_full_fingerprints, find_scenes_by_full_fingerprints_variables)

        if (
            not results_without_stashdb_id
            or "data" not in results_without_stashdb_id
            or "findScenesByFullFingerprints" not in results_without_stashdb_id["data"]
        ):
            raise Exception("Failed to query scenes by phash")

        # Save to file for debugging/testing
        # import json
        # time_in_ticks = datetime.now().timestamp()
        # with open(f"phash_to_scene_{time_in_ticks}.json", "w") as f:
        #     f.write(json.dumps({ "input_scenes": scenes, "results": results_without_stashdb_id }, indent=4))

        stashdb_scenes = results_without_stashdb_id["data"]["findScenesByFullFingerprints"]
        matched_scenes = self.scene_matcher.match_scenes(scenes, stashdb_scenes)

        # Combined results
        for phash, scene_data in results_with_stashdb_id.items():
            matched_scenes[phash] = scene_data

        matched_scenes_list = [
            (
                {
                    "queried_phash": phash,
                    "id": scene_data["id"],
                    "title": scene_data["title"],
                    "code": scene_data["code"],
                    "duration": scene_data["duration"] * 1000,
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
                                    for url in scene_data["studio"]["parent"].get(
                                        "urls", []
                                    )
                                ],
                                "images": [
                                    {
                                        "id": image["id"],
                                        "url": image["url"],
                                        "width": image["width"],
                                        "height": image["height"],
                                    }
                                    for image in scene_data["studio"]["parent"].get(
                                        "images", []
                                    )
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
                                "fingerprints": [
                                    {
                                        "algorithm": fingerprint["algorithm"],
                                        "hash": fingerprint["hash"],
                                        "duration": fingerprint["duration"],
                                    }
                                    for fingerprint in performer["performer"].get("fingerprints") or []
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
                }
                if scene_data
                else {"queried_phash": phash}
            )
            for phash, scene_data in matched_scenes.items()
        ]

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
        }

        df_matched_scenes = pl.DataFrame(matched_scenes_list, schema=schema)

        return df_matched_scenes

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
                        deleted
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
            if result is None or 'data' not in result or 'queryTags' not in result['data']:
                break

            tags_data = result['data']['queryTags']
            all_tags.extend(tags_data['tags'])

            if total_count is None:
                total_count = tags_data['count']

            if len(all_tags) >= total_count:
                break

            page += 1

        return all_tags

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
