"""
Builder pattern for creating Stash data quality checks with a fluent API.
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field


def create_tag_resolver(stash):
    """Create a tag resolver function that maps tag names to TagReference objects"""

    def resolve_tag(tag_name: str) -> "TagReference":
        tag_dict = stash.find_tag(tag_name)
        if not tag_dict:
            raise ValueError(f"Tag '{tag_name}' not found")
        return TagReference.from_dict(tag_dict)

    return resolve_tag


def create_studio_resolver(stash):
    """Create a studio resolver function that maps studio names to StudioReference objects"""

    def resolve_studio(studio_name: str) -> "StudioReference":
        studio_dict = stash.find_studio(studio_name)
        if not studio_dict:
            raise ValueError(f"Studio '{studio_name}' not found")
        return StudioReference.from_dict(studio_dict)

    return resolve_studio


@dataclass
class TagReference:
    """Represents a tag with ID and name"""

    id: str
    name: str

    @classmethod
    def from_dict(cls, tag_dict: Dict[str, Any]) -> "TagReference":
        return cls(id=tag_dict["id"], name=tag_dict["name"])


@dataclass
class StudioReference:
    """Represents a studio with ID and name"""

    id: str
    name: str

    @classmethod
    def from_dict(cls, studio_dict: Dict[str, Any]) -> "StudioReference":
        return cls(id=studio_dict["id"], name=studio_dict["name"])


@dataclass
class FixAction:
    """Represents a fix action with tags to add or remove"""

    name: str
    add_tags: List[TagReference] = field(default_factory=list)
    remove_tags: List[TagReference] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "addTags": [{"id": tag.id, "name": tag.name} for tag in self.add_tags],
            "removeTags": [
                {"id": tag.id, "name": tag.name} for tag in self.remove_tags
            ],
        }


class QueryTagsBuilder:
    """Builder for tag-based query filters"""

    def __init__(self):
        self._included_tags: List[TagReference] = []
        self._excluded_tags: List[TagReference] = []
        self._modifier = "INCLUDES"
        self._depth = 0

    def include(self, *tags: Union[str, TagReference]) -> "QueryTagsBuilder":
        """Include tags in the query"""
        for tag in tags:
            if isinstance(tag, str):
                # Will need to be resolved later
                self._included_tags.append(TagReference(id="", name=tag))
            else:
                self._included_tags.append(tag)
        return self

    def exclude(self, *tags: Union[str, TagReference]) -> "QueryTagsBuilder":
        """Exclude tags from the query"""
        for tag in tags:
            if isinstance(tag, str):
                # Will need to be resolved later
                self._excluded_tags.append(TagReference(id="", name=tag))
            else:
                self._excluded_tags.append(tag)
        return self

    def modifier(self, modifier: str) -> "QueryTagsBuilder":
        """Set the modifier (INCLUDES, INCLUDES_ALL, etc.)"""
        self._modifier = modifier
        return self

    def depth(self, depth: int) -> "QueryTagsBuilder":
        """Set the depth for hierarchical tags"""
        self._depth = depth
        return self

    def build(self, tag_resolver) -> Dict[str, Any]:
        """Build the query filter"""
        # Resolve tag names to IDs
        resolved_included = []
        resolved_excluded = []

        for tag in self._included_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_included.append(resolved_tag)
            else:
                resolved_included.append(tag)

        for tag in self._excluded_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_excluded.append(resolved_tag)
            else:
                resolved_excluded.append(tag)

        return {
            "value": [tag.id for tag in resolved_included],
            "modifier": self._modifier,
            "excludes": [tag.id for tag in resolved_excluded],
            "depth": self._depth,
        }

    def build_url_query(self, tag_resolver) -> Dict[str, Any]:
        """Build URL query format"""
        # Resolve tag names to IDs first
        resolved_included = []
        resolved_excluded = []

        for tag in self._included_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_included.append(resolved_tag)
            else:
                resolved_included.append(tag)

        for tag in self._excluded_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_excluded.append(resolved_tag)
            else:
                resolved_excluded.append(tag)

        return {
            "type": "tags",
            "modifier": self._modifier,
            "value": {
                "items": [
                    {"id": tag.id, "label": tag.name} for tag in resolved_included
                ],
                "excluded": [
                    {"id": tag.id, "label": tag.name} for tag in resolved_excluded
                ],
                "depth": self._depth,
            },
        }


class QueryPerformerTagsBuilder:
    """Builder for performer tag-based query filters"""

    def __init__(self):
        self._included_tags: List[TagReference] = []
        self._excluded_tags: List[TagReference] = []
        self._modifier = "INCLUDES"
        self._depth = 0

    def include(self, *tags: Union[str, TagReference]) -> "QueryPerformerTagsBuilder":
        """Include performer tags in the query"""
        for tag in tags:
            if isinstance(tag, str):
                self._included_tags.append(TagReference(id="", name=tag))
            else:
                self._included_tags.append(tag)
        return self

    def exclude(self, *tags: Union[str, TagReference]) -> "QueryPerformerTagsBuilder":
        """Exclude performer tags from the query"""
        for tag in tags:
            if isinstance(tag, str):
                self._excluded_tags.append(TagReference(id="", name=tag))
            else:
                self._excluded_tags.append(tag)
        return self

    def modifier(self, modifier: str) -> "QueryPerformerTagsBuilder":
        """Set the modifier (INCLUDES, INCLUDES_ALL, etc.)"""
        self._modifier = modifier
        return self

    def depth(self, depth: int) -> "QueryPerformerTagsBuilder":
        """Set the depth for hierarchical tags"""
        self._depth = depth
        return self

    def build(self, tag_resolver) -> Dict[str, Any]:
        """Build the query filter"""
        # Resolve tag names to IDs
        resolved_included = []
        resolved_excluded = []

        for tag in self._included_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_included.append(resolved_tag)
            else:
                resolved_included.append(tag)

        for tag in self._excluded_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_excluded.append(resolved_tag)
            else:
                resolved_excluded.append(tag)

        return {
            "value": [tag.id for tag in resolved_included],
            "modifier": self._modifier,
            "excludes": [tag.id for tag in resolved_excluded],
            "depth": self._depth,
        }

    def build_url_query(self, tag_resolver) -> Dict[str, Any]:
        """Build URL query format"""
        # Resolve tag names to IDs first
        resolved_included = []
        resolved_excluded = []

        for tag in self._included_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_included.append(resolved_tag)
            else:
                resolved_included.append(tag)

        for tag in self._excluded_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_excluded.append(resolved_tag)
            else:
                resolved_excluded.append(tag)

        return {
            "type": "performer_tags",
            "modifier": self._modifier,
            "value": {
                "items": [
                    {"id": tag.id, "label": tag.name} for tag in resolved_included
                ],
                "excluded": [
                    {"id": tag.id, "label": tag.name} for tag in resolved_excluded
                ],
                "depth": self._depth,
            },
        }


class QueryStudiosBuilder:
    """Builder for studio-based query filters"""

    def __init__(self):
        self._included_studios: List[StudioReference] = []
        self._excluded_studios: List[StudioReference] = []
        self._modifier = "INCLUDES"
        self._depth = 0

    def include(self, *studios: Union[str, StudioReference]) -> "QueryStudiosBuilder":
        """Include studios in the query"""
        for studio in studios:
            if isinstance(studio, str):
                self._included_studios.append(StudioReference(id="", name=studio))
            else:
                self._included_studios.append(studio)
        return self

    def exclude(self, *studios: Union[str, StudioReference]) -> "QueryStudiosBuilder":
        """Exclude studios from the query"""
        for studio in studios:
            if isinstance(studio, str):
                self._excluded_studios.append(StudioReference(id="", name=studio))
            else:
                self._excluded_studios.append(studio)
        return self

    def modifier(self, modifier: str) -> "QueryStudiosBuilder":
        """Set the modifier (INCLUDES, INCLUDES_ALL, etc.)"""
        self._modifier = modifier
        return self

    def depth(self, depth: int) -> "QueryStudiosBuilder":
        """Set the depth for hierarchical studios"""
        self._depth = depth
        return self

    def build(self, studio_resolver) -> Dict[str, Any]:
        """Build the query filter"""
        # Resolve studio names to IDs
        resolved_included = []
        resolved_excluded = []

        for studio in self._included_studios:
            if not studio.id:  # Need to resolve
                resolved_studio = studio_resolver(studio.name)
                resolved_included.append(resolved_studio)
            else:
                resolved_included.append(studio)

        for studio in self._excluded_studios:
            if not studio.id:  # Need to resolve
                resolved_studio = studio_resolver(studio.name)
                resolved_excluded.append(resolved_studio)
            else:
                resolved_excluded.append(studio)

        return {
            "value": [studio.id for studio in resolved_included],
            "modifier": self._modifier,
            "excludes": [studio.id for studio in resolved_excluded],
            "depth": self._depth,
        }

    def build_url_query(self, studio_resolver) -> Dict[str, Any]:
        """Build URL query format"""
        # Resolve studio names to IDs first
        resolved_included = []
        resolved_excluded = []

        for studio in self._included_studios:
            if not studio.id:  # Need to resolve
                resolved_studio = studio_resolver(studio.name)
                resolved_included.append(resolved_studio)
            else:
                resolved_included.append(studio)

        for studio in self._excluded_studios:
            if not studio.id:  # Need to resolve
                resolved_studio = studio_resolver(studio.name)
                resolved_excluded.append(resolved_studio)
            else:
                resolved_excluded.append(studio)

        return {
            "type": "studios",
            "modifier": self._modifier,
            "value": {
                "items": [
                    {"id": studio.id, "label": studio.name}
                    for studio in resolved_included
                ],
                "excluded": [
                    {"id": studio.id, "label": studio.name}
                    for studio in resolved_excluded
                ],
                "depth": self._depth,
            },
        }


class QueryBuilder:
    """Builder for constructing GraphQL queries"""

    def __init__(self):
        self._tags_builder: Optional[QueryTagsBuilder] = None
        self._performer_tags_builder: Optional[QueryPerformerTagsBuilder] = None
        self._studios_builder: Optional[QueryStudiosBuilder] = None
        self._performer_count: Optional[Dict[str, Any]] = None

    def tags(self, tags_builder: QueryTagsBuilder) -> "QueryBuilder":
        """Add tag-based filters"""
        self._tags_builder = tags_builder
        return self

    def performer_tags(
        self, performer_tags_builder: QueryPerformerTagsBuilder
    ) -> "QueryBuilder":
        """Add performer tag-based filters"""
        self._performer_tags_builder = performer_tags_builder
        return self

    def studios(self, studios_builder: QueryStudiosBuilder) -> "QueryBuilder":
        """Add studio-based filters"""
        self._studios_builder = studios_builder
        return self

    def performer_count(self, modifier: str, value: int) -> "QueryBuilder":
        """Add performer count filter"""
        self._performer_count = {"modifier": modifier, "value": value}
        return self

    def build(self, stash) -> Dict[str, Any]:
        """Build the complete query"""
        query = {}

        if self._tags_builder:
            tag_resolver = create_tag_resolver(stash)
            query["tags"] = self._tags_builder.build(tag_resolver)

        if self._performer_tags_builder:
            tag_resolver = create_tag_resolver(stash)
            query["performer_tags"] = self._performer_tags_builder.build(tag_resolver)

        if self._studios_builder:
            studio_resolver = create_studio_resolver(stash)
            query["studios"] = self._studios_builder.build(studio_resolver)

        if self._performer_count:
            query["performer_count"] = self._performer_count

        return query

    def build_url_query(self, stash) -> List[Dict[str, Any]]:
        """Build URL query format"""
        url_query = []

        if self._performer_count:
            url_query.append(
                {
                    "type": "performer_count",
                    "modifier": self._performer_count["modifier"],
                    "value": self._performer_count["value"],
                }
            )

        if self._tags_builder:
            tag_resolver = create_tag_resolver(stash)
            url_query.append(self._tags_builder.build_url_query(tag_resolver))

        if self._performer_tags_builder:
            tag_resolver = create_tag_resolver(stash)
            url_query.append(self._performer_tags_builder.build_url_query(tag_resolver))

        if self._studios_builder:
            studio_resolver = create_studio_resolver(stash)
            url_query.append(self._studios_builder.build_url_query(studio_resolver))

        return url_query


class FixBuilder:
    """Builder for fix actions"""

    def __init__(self, name: str):
        self._name = name
        self._add_tags: List[TagReference] = []
        self._remove_tags: List[TagReference] = []

    def add_tags(self, *tags: Union[str, TagReference]) -> "FixBuilder":
        """Add tags to be added in the fix"""
        for tag in tags:
            if isinstance(tag, str):
                self._add_tags.append(TagReference(id="", name=tag))
            else:
                self._add_tags.append(tag)
        return self

    def remove_tags(self, *tags: Union[str, TagReference]) -> "FixBuilder":
        """Add tags to be removed in the fix"""
        for tag in tags:
            if isinstance(tag, str):
                self._remove_tags.append(TagReference(id="", name=tag))
            else:
                self._remove_tags.append(tag)
        return self

    def build(self, stash) -> FixAction:
        """Build the fix action"""
        # Resolve tag names to IDs
        resolved_add_tags = []
        resolved_remove_tags = []

        tag_resolver = create_tag_resolver(stash)

        for tag in self._add_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_add_tags.append(resolved_tag)
            else:
                resolved_add_tags.append(tag)

        for tag in self._remove_tags:
            if not tag.id:  # Need to resolve
                resolved_tag = tag_resolver(tag.name)
                resolved_remove_tags.append(resolved_tag)
            else:
                resolved_remove_tags.append(tag)

        return FixAction(
            name=self._name,
            add_tags=resolved_add_tags,
            remove_tags=resolved_remove_tags,
        )


class StashCheckBuilder:
    """Main builder for Stash data quality checks"""

    def __init__(self):
        self._name: str = ""
        self._query_builder: Optional[QueryBuilder] = None
        self._fragment: str = "id title date tags { id name }"
        self._fix_builders: List[FixBuilder] = []

    def name(self, name: str) -> "StashCheckBuilder":
        """Set the name of the check"""
        self._name = name
        return self

    def query(self, query_builder: QueryBuilder) -> "StashCheckBuilder":
        """Set the query builder"""
        self._query_builder = query_builder
        return self

    def fragment(self, fragment: str) -> "StashCheckBuilder":
        """Set the GraphQL fragment"""
        self._fragment = fragment
        return self

    def fix(self, fix_builder: FixBuilder) -> "StashCheckBuilder":
        """Add a fix action"""
        self._fix_builders.append(fix_builder)
        return self

    def build(self, stash) -> Dict[str, Any]:
        """Build the complete check"""
        if not self._query_builder:
            raise ValueError("Query builder is required")

        query = self._query_builder.build(stash)
        url_query = self._query_builder.build_url_query(stash)

        fixes = []
        for fix_builder in self._fix_builders:
            fix_action = fix_builder.build(stash)
            fixes.append(fix_action.to_dict())

        return {
            "name": self._name,
            "query": query,
            "fragment": self._fragment,
            "url_query": url_query,
            "fixes": fixes,
        }


# Convenience functions for common patterns
def tags() -> QueryTagsBuilder:
    """Create a new tags builder"""
    return QueryTagsBuilder()


def performer_tags() -> QueryPerformerTagsBuilder:
    """Create a new performer tags builder"""
    return QueryPerformerTagsBuilder()


def studios() -> QueryStudiosBuilder:
    """Create a new studios builder"""
    return QueryStudiosBuilder()


def query() -> QueryBuilder:
    """Create a new query builder"""
    return QueryBuilder()


def fix(name: str) -> FixBuilder:
    """Create a new fix builder"""
    return FixBuilder(name)


def create_check() -> StashCheckBuilder:
    """Create a new check builder"""
    return StashCheckBuilder()
