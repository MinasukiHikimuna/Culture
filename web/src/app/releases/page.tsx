"use client";

import { useEffect, useCallback, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useReleasesStore } from "@/stores/releases";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function ReleasesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initializedRef = useRef(false);

  const {
    sites,
    selectedSiteUuid,
    loading,
    error,
    searchTerm,
    sortDesc,
    limit,
    setSelectedSite,
    setSearchTerm,
    setSortDesc,
    setLimit,
    fetchSites,
    fetchReleases,
    filteredReleases,
  } = useReleasesStore();

  // Update URL when state changes
  const updateUrl = useCallback((params: { site?: string | null; sort?: string; limit?: string; search?: string }) => {
    const newParams = new URLSearchParams(searchParams.toString());

    if (params.site !== undefined) {
      if (params.site) newParams.set("site", params.site);
      else newParams.delete("site");
    }
    if (params.sort !== undefined) {
      if (params.sort === "oldest") newParams.set("sort", "oldest");
      else newParams.delete("sort");
    }
    if (params.limit !== undefined) {
      if (params.limit && params.limit !== "100") newParams.set("limit", params.limit);
      else newParams.delete("limit");
    }
    if (params.search !== undefined) {
      if (params.search) newParams.set("search", params.search);
      else newParams.delete("search");
    }

    const newUrl = newParams.toString() ? `?${newParams.toString()}` : "/releases";
    router.replace(newUrl, { scroll: false });
  }, [searchParams, router]);

  // Initialize state from URL params on mount
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const siteParam = searchParams.get("site");
    const sortParam = searchParams.get("sort");
    const limitParam = searchParams.get("limit");
    const searchParam = searchParams.get("search");

    if (siteParam) setSelectedSite(siteParam);
    if (sortParam === "oldest") setSortDesc(false);
    if (limitParam) {
      const limitVal = limitParam === "all" ? null : parseInt(limitParam, 10);
      if (limitParam === "all" || (!isNaN(limitVal!) && limitVal! > 0)) {
        setLimit(limitVal);
      }
    }
    if (searchParam) setSearchTerm(searchParam);
  }, [searchParams, setSelectedSite, setSortDesc, setLimit, setSearchTerm]);

  useEffect(() => {
    fetchSites();
  }, [fetchSites]);

  useEffect(() => {
    if (initializedRef.current && selectedSiteUuid) {
      fetchReleases();
    }
  }, [selectedSiteUuid, sortDesc, limit, fetchReleases]);

  const releases = filteredReleases();

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Releases</h1>
        <p className="text-muted-foreground">
          Browse and manage releases from your sites
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-4">
        <Select
          value={selectedSiteUuid || ""}
          onValueChange={(value) => {
            setSelectedSite(value || null);
            updateUrl({ site: value || null });
          }}
        >
          <SelectTrigger className="w-[250px]">
            <SelectValue placeholder="Select a site..." />
          </SelectTrigger>
          <SelectContent>
            {sites.map((site) => (
              <SelectItem key={site.ce_sites_uuid} value={site.ce_sites_uuid}>
                {site.ce_sites_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          placeholder="Search releases..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            updateUrl({ search: e.target.value });
          }}
          className="max-w-sm"
          disabled={!selectedSiteUuid}
        />

        <Select
          value={sortDesc ? "newest" : "oldest"}
          onValueChange={(value) => {
            setSortDesc(value === "newest");
            updateUrl({ sort: value });
          }}
          disabled={!selectedSiteUuid}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="newest">Newest First</SelectItem>
            <SelectItem value="oldest">Oldest First</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={limit?.toString() || "all"}
          onValueChange={(value) => {
            setLimit(value === "all" ? null : parseInt(value, 10));
            updateUrl({ limit: value });
          }}
          disabled={!selectedSiteUuid}
        >
          <SelectTrigger className="w-[120px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="50">50</SelectItem>
            <SelectItem value="100">100</SelectItem>
            <SelectItem value="250">250</SelectItem>
            <SelectItem value="all">All</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!selectedSiteUuid ? (
        <div className="text-muted-foreground">
          Select a site to view releases
        </div>
      ) : loading ? (
        <div className="text-muted-foreground">Loading...</div>
      ) : (
        <>
          <div className="mb-2 text-sm text-muted-foreground">
            {releases.length} release{releases.length !== 1 ? "s" : ""}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Short Name</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {releases.map((release) => (
                <TableRow key={release.ce_release_uuid}>
                  <TableCell className="font-mono text-sm">
                    {release.ce_release_date || "-"}
                  </TableCell>
                  <TableCell className="font-medium">
                    {release.ce_release_name}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {release.ce_release_short_name}
                  </TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" asChild>
                      <a href={`/releases/${release.ce_release_uuid}`}>View</a>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {releases.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-center text-muted-foreground"
                  >
                    No releases found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}
