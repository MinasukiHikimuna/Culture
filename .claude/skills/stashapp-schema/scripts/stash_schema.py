#!/usr/bin/env python3
"""
Stashapp Schema Introspector - Query Stashapp GraphQL API schema.

Usage:
    python scripts/stash_schema.py --types          # List all types
    python scripts/stash_schema.py --type Scene     # Show type details
    python scripts/stash_schema.py --queries        # List all queries
    python scripts/stash_schema.py --mutations      # List all mutations
    python scripts/stash_schema.py --query findScenes   # Show query details
    python scripts/stash_schema.py --mutation sceneUpdate  # Show mutation details
    python scripts/stash_schema.py --search "performer"    # Search by name
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


# Load .env from monorepo root (Culture/)
monorepo_root = Path(__file__).resolve().parents[4]
load_dotenv(monorepo_root / ".env")


def get_stash_config(instance: str) -> tuple[str | None, str | None]:
    """Get Stashapp URL and API key for the specified instance."""
    if instance == "aural":
        base_url = os.getenv("AURAL_STASHAPP_URL")
        api_key = os.getenv("AURAL_STASHAPP_API_KEY")
    else:  # main
        base_url = os.getenv("STASHAPP_URL")
        api_key = os.getenv("STASHAPP_API_KEY")

    url = f"{base_url}/graphql" if base_url else None
    return (url, api_key)


class StashSchemaIntrospector:
    """Stashapp GraphQL schema introspection client."""

    def __init__(self, url: str, api_key: str):
        self.url = url
        self.headers = {"ApiKey": api_key, "Content-Type": "application/json"}
        self._schema_cache = None

    def query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query."""
        response = requests.post(
            self.url,
            json={"query": query, "variables": variables or {}},
            headers=self.headers,
        )
        response.raise_for_status()
        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")
        return result.get("data", {})

    def get_full_schema(self) -> dict:
        """Get the full GraphQL schema via introspection."""
        if self._schema_cache:
            return self._schema_cache

        query = """
        query IntrospectionQuery {
            __schema {
                types {
                    name
                    kind
                    description
                    fields(includeDeprecated: true) {
                        name
                        description
                        isDeprecated
                        deprecationReason
                        type {
                            ...TypeRef
                        }
                        args {
                            name
                            description
                            type {
                                ...TypeRef
                            }
                            defaultValue
                        }
                    }
                    inputFields {
                        name
                        description
                        type {
                            ...TypeRef
                        }
                        defaultValue
                    }
                    enumValues(includeDeprecated: true) {
                        name
                        description
                        isDeprecated
                        deprecationReason
                    }
                }
                queryType {
                    name
                    fields(includeDeprecated: true) {
                        name
                        description
                        isDeprecated
                        deprecationReason
                        type {
                            ...TypeRef
                        }
                        args {
                            name
                            description
                            type {
                                ...TypeRef
                            }
                            defaultValue
                        }
                    }
                }
                mutationType {
                    name
                    fields(includeDeprecated: true) {
                        name
                        description
                        isDeprecated
                        deprecationReason
                        type {
                            ...TypeRef
                        }
                        args {
                            name
                            description
                            type {
                                ...TypeRef
                            }
                            defaultValue
                        }
                    }
                }
            }
        }

        fragment TypeRef on __Type {
            kind
            name
            ofType {
                kind
                name
                ofType {
                    kind
                    name
                    ofType {
                        kind
                        name
                        ofType {
                            kind
                            name
                        }
                    }
                }
            }
        }
        """
        self._schema_cache = self.query(query)
        return self._schema_cache

    def list_types(self, filter_internal: bool = True) -> list[dict]:
        """List all GraphQL types."""
        schema = self.get_full_schema()
        types = schema.get("__schema", {}).get("types", [])

        if filter_internal:
            # Filter out internal types starting with __
            types = [t for t in types if not t["name"].startswith("__")]

        # Sort by kind then name
        types.sort(key=lambda t: (t["kind"], t["name"]))
        return types

    def get_type_details(self, type_name: str) -> dict | None:
        """Get details of a specific type."""
        schema = self.get_full_schema()
        types = schema.get("__schema", {}).get("types", [])

        for t in types:
            if t["name"].lower() == type_name.lower():
                return t
        return None

    def list_queries(self) -> list[dict]:
        """List all available query operations."""
        schema = self.get_full_schema()
        query_type = schema.get("__schema", {}).get("queryType", {})
        fields = query_type.get("fields", [])
        return sorted(fields, key=lambda f: f["name"])

    def list_mutations(self) -> list[dict]:
        """List all available mutation operations."""
        schema = self.get_full_schema()
        mutation_type = schema.get("__schema", {}).get("mutationType", {})
        if not mutation_type:
            return []
        fields = mutation_type.get("fields", [])
        return sorted(fields, key=lambda f: f["name"])

    def get_operation_details(self, operation_name: str, is_mutation: bool = False) -> dict | None:
        """Get details of a specific query or mutation."""
        operations = self.list_mutations() if is_mutation else self.list_queries()
        for op in operations:
            if op["name"].lower() == operation_name.lower():
                return op
        return None

    def search(self, term: str) -> dict:
        """Search types and operations by name."""
        term_lower = term.lower()
        results = {
            "types": [],
            "queries": [],
            "mutations": [],
        }

        # Search types
        for t in self.list_types():
            if term_lower in t["name"].lower():
                results["types"].append(t)

        # Search queries
        for q in self.list_queries():
            if term_lower in q["name"].lower():
                results["queries"].append(q)

        # Search mutations
        for m in self.list_mutations():
            if term_lower in m["name"].lower():
                results["mutations"].append(m)

        return results


def format_type_ref(type_ref: dict) -> str:
    """Format a GraphQL type reference to a readable string."""
    if not type_ref:
        return "Unknown"

    kind = type_ref.get("kind")
    name = type_ref.get("name")
    of_type = type_ref.get("ofType")

    if kind == "NON_NULL":
        return f"{format_type_ref(of_type)}!"
    if kind == "LIST":
        return f"[{format_type_ref(of_type)}]"
    if name:
        return name
    return "Unknown"


def print_types(types: list[dict], verbose: bool = False):
    """Print type list."""
    print(f"\nTypes ({len(types)}):")
    for t in types:
        kind = t["kind"]
        name = t["name"]
        print(f"  {kind:<14} {name}")
        if verbose and t.get("description"):
            desc = t["description"][:80].replace("\n", " ")
            print(f"                 {desc}")


def print_type_details(t: dict, verbose: bool = False):
    """Print type details."""
    print(f"\nType: {t['name']} ({t['kind']})")

    if verbose and t.get("description"):
        print(f"Description: {t['description']}")

    # Handle different type kinds
    if t["kind"] == "OBJECT" or t["kind"] == "INTERFACE":
        fields = t.get("fields", [])
        if fields:
            print(f"\nFields ({len(fields)}):")
            for f in sorted(fields, key=lambda x: x["name"]):
                type_str = format_type_ref(f.get("type"))
                deprecated = " [DEPRECATED]" if f.get("isDeprecated") else ""
                args = f.get("args", [])

                if args:
                    arg_strs = [f"{a['name']}: {format_type_ref(a.get('type'))}" for a in args]
                    print(f"  {f['name']}({', '.join(arg_strs)}): {type_str}{deprecated}")
                else:
                    print(f"  {f['name']}: {type_str}{deprecated}")

                if verbose:
                    if f.get("description"):
                        desc = f["description"][:100].replace("\n", " ")
                        print(f"      {desc}")
                    if f.get("deprecationReason"):
                        print(f"      Deprecation: {f['deprecationReason']}")

    elif t["kind"] == "INPUT_OBJECT":
        input_fields = t.get("inputFields", [])
        if input_fields:
            print(f"\nInput Fields ({len(input_fields)}):")
            for f in sorted(input_fields, key=lambda x: x["name"]):
                type_str = format_type_ref(f.get("type"))
                default = f" = {f['defaultValue']}" if f.get("defaultValue") else ""
                print(f"  {f['name']}: {type_str}{default}")
                if verbose and f.get("description"):
                    desc = f["description"][:100].replace("\n", " ")
                    print(f"      {desc}")

    elif t["kind"] == "ENUM":
        enum_values = t.get("enumValues", [])
        if enum_values:
            print(f"\nEnum Values ({len(enum_values)}):")
            for v in enum_values:
                deprecated = " [DEPRECATED]" if v.get("isDeprecated") else ""
                print(f"  {v['name']}{deprecated}")
                if verbose and v.get("description"):
                    print(f"      {v['description']}")

    elif t["kind"] == "SCALAR":
        print("  (Scalar type)")

    elif t["kind"] == "UNION":
        print("  (Union type - use --verbose for possible types)")


def print_operations(operations: list[dict], op_type: str, verbose: bool = False):
    """Print query/mutation list."""
    print(f"\n{op_type} ({len(operations)}):")
    for op in operations:
        deprecated = " [DEPRECATED]" if op.get("isDeprecated") else ""
        return_type = format_type_ref(op.get("type"))
        print(f"  {op['name']}: {return_type}{deprecated}")
        if verbose and op.get("description"):
            desc = op["description"][:80].replace("\n", " ")
            print(f"      {desc}")


def print_operation_details(op: dict, is_mutation: bool = False, verbose: bool = False):
    """Print query/mutation details."""
    op_type = "Mutation" if is_mutation else "Query"
    print(f"\n{op_type}: {op['name']}")

    if verbose and op.get("description"):
        print(f"Description: {op['description']}")

    if op.get("isDeprecated"):
        print(f"DEPRECATED: {op.get('deprecationReason', 'No reason given')}")

    args = op.get("args", [])
    if args:
        print(f"\nArguments ({len(args)}):")
        for a in args:
            type_str = format_type_ref(a.get("type"))
            default = f" = {a['defaultValue']}" if a.get("defaultValue") else ""
            print(f"  {a['name']}: {type_str}{default}")
            if verbose and a.get("description"):
                desc = a["description"][:100].replace("\n", " ")
                print(f"      {desc}")
    else:
        print("\nArguments: None")

    return_type = format_type_ref(op.get("type"))
    print(f"\nReturns: {return_type}")


def print_search_results(results: dict, verbose: bool = False):
    """Print search results."""
    total = len(results["types"]) + len(results["queries"]) + len(results["mutations"])

    if total == 0:
        print("\nNo matches found.")
        return

    print(f"\nSearch Results ({total} matches):")

    if results["types"]:
        print(f"\n  Types ({len(results['types'])}):")
        for t in results["types"]:
            print(f"    {t['kind']:<14} {t['name']}")

    if results["queries"]:
        print(f"\n  Queries ({len(results['queries'])}):")
        for q in results["queries"]:
            return_type = format_type_ref(q.get("type"))
            print(f"    {q['name']}: {return_type}")

    if results["mutations"]:
        print(f"\n  Mutations ({len(results['mutations'])}):")
        for m in results["mutations"]:
            return_type = format_type_ref(m.get("type"))
            print(f"    {m['name']}: {return_type}")


def main():
    parser = argparse.ArgumentParser(
        description="Introspect Stashapp GraphQL API schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Type operations
    parser.add_argument("--types", action="store_true", help="List all GraphQL types")
    parser.add_argument("--type", metavar="NAME", help="Show details of a specific type")

    # Query/mutation operations
    parser.add_argument("--queries", action="store_true", help="List all query operations")
    parser.add_argument("--mutations", action="store_true", help="List all mutation operations")
    parser.add_argument("--query", metavar="NAME", help="Show details of a specific query")
    parser.add_argument("--mutation", metavar="NAME", help="Show details of a specific mutation")

    # Search
    parser.add_argument("--search", metavar="TERM", help="Search types and operations by name")

    # Output options
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Instance selection
    parser.add_argument(
        "--instance",
        choices=["aural", "main"],
        default="aural",
        help="Stashapp instance to query (default: aural)",
    )

    args = parser.parse_args()

    # Check that at least one action is specified
    actions = [args.types, args.type, args.queries, args.mutations, args.query, args.mutation, args.search]
    if not any(actions):
        parser.print_help()
        sys.exit(1)

    # Get configuration for selected instance
    stash_url, stash_api_key = get_stash_config(args.instance)

    # Validate required environment variables
    if not stash_url or not stash_api_key:
        prefix = "AURAL_STASHAPP" if args.instance == "aural" else "STASHAPP"
        print(f"Error: Missing required environment variables for '{args.instance}' instance.")
        print(f"Please set {prefix}_URL and {prefix}_API_KEY in your .env file.")
        sys.exit(1)

    # Initialize client
    client = StashSchemaIntrospector(stash_url, stash_api_key)

    try:
        if args.types:
            types = client.list_types()
            if args.json:
                print(json.dumps(types, indent=2))
            else:
                print_types(types, verbose=args.verbose)

        elif args.type:
            t = client.get_type_details(args.type)
            if t:
                if args.json:
                    print(json.dumps(t, indent=2))
                else:
                    print_type_details(t, verbose=args.verbose)
            else:
                print(f"Type '{args.type}' not found.")
                sys.exit(1)

        elif args.queries:
            queries = client.list_queries()
            if args.json:
                print(json.dumps(queries, indent=2))
            else:
                print_operations(queries, "Queries", verbose=args.verbose)

        elif args.mutations:
            mutations = client.list_mutations()
            if args.json:
                print(json.dumps(mutations, indent=2))
            else:
                print_operations(mutations, "Mutations", verbose=args.verbose)

        elif args.query:
            op = client.get_operation_details(args.query, is_mutation=False)
            if op:
                if args.json:
                    print(json.dumps(op, indent=2))
                else:
                    print_operation_details(op, is_mutation=False, verbose=args.verbose)
            else:
                print(f"Query '{args.query}' not found.")
                sys.exit(1)

        elif args.mutation:
            op = client.get_operation_details(args.mutation, is_mutation=True)
            if op:
                if args.json:
                    print(json.dumps(op, indent=2))
                else:
                    print_operation_details(op, is_mutation=True, verbose=args.verbose)
            else:
                print(f"Mutation '{args.mutation}' not found.")
                sys.exit(1)

        elif args.search:
            results = client.search(args.search)
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print_search_results(results, verbose=args.verbose)

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Stashapp: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
