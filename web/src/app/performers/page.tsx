"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { usePerformersStore } from "@/stores/performers";
import type { LinkFilter } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const LINK_FILTER_OPTIONS: { value: LinkFilter; label: string }[] = [
  { value: "all", label: "All performers" },
  { value: "linked", label: "Linked" },
  { value: "unlinked", label: "Unlinked (all)" },
  { value: "unlinked_stashdb", label: "Unlinked to StashDB" },
  { value: "unlinked_stashapp", label: "Unlinked to Stashapp" },
];

const VALID_LINK_FILTERS: LinkFilter[] = ["all", "linked", "unlinked", "unlinked_stashdb", "unlinked_stashapp"];

export default function PerformersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [startingJob, setStartingJob] = useState(false);
  const initializedRef = useRef(false);

  const {
    sites,
    selectedSite,
    loading,
    error,
    searchTerm,
    linkFilter,
    currentPage,
    totalPages,
    totalPerformers,
    setSelectedSite,
    setSearchTerm,
    setLinkFilter,
    setCurrentPage,
    fetchSites,
    fetchPerformers,
    filteredPerformers,
    startMatchingJob,
  } = usePerformersStore();

  // Update URL when state changes
  const updateUrl = useCallback((params: { site?: string | null; filter?: string; page?: number; search?: string }) => {
    const newParams = new URLSearchParams(searchParams.toString());

    if (params.site !== undefined) {
      if (params.site) newParams.set("site", params.site);
      else newParams.delete("site");
    }
    if (params.filter !== undefined) {
      if (params.filter && params.filter !== "all") newParams.set("filter", params.filter);
      else newParams.delete("filter");
    }
    if (params.page !== undefined) {
      if (params.page > 1) newParams.set("page", params.page.toString());
      else newParams.delete("page");
    }
    if (params.search !== undefined) {
      if (params.search) newParams.set("search", params.search);
      else newParams.delete("search");
    }

    const newUrl = newParams.toString() ? `?${newParams.toString()}` : "/performers";
    router.replace(newUrl, { scroll: false });
  }, [searchParams, router]);

  // Initialize state from URL params on mount
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const siteParam = searchParams.get("site");
    const filterParam = searchParams.get("filter") as LinkFilter | null;
    const pageParam = searchParams.get("page");
    const searchParam = searchParams.get("search");

    if (siteParam) setSelectedSite(siteParam);
    if (filterParam && VALID_LINK_FILTERS.includes(filterParam)) setLinkFilter(filterParam);
    if (pageParam) {
      const page = parseInt(pageParam, 10);
      if (!isNaN(page) && page > 0) setCurrentPage(page);
    }
    if (searchParam) setSearchTerm(searchParam);
  }, [searchParams, setSelectedSite, setLinkFilter, setCurrentPage, setSearchTerm]);

  useEffect(() => {
    fetchSites();
  }, [fetchSites]);

  useEffect(() => {
    if (initializedRef.current && selectedSite) {
      fetchPerformers();
    }
  }, [selectedSite, linkFilter, currentPage, fetchPerformers]);

  const performers = filteredPerformers();

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
        <h1 className="text-2xl font-bold">Performers</h1>
        <p className="text-muted-foreground">
          View performers by site and manage their links
        </p>
      </div>

      <div className="mb-4 flex gap-4 flex-wrap">
        <Select
          value={selectedSite || ""}
          onValueChange={(value) => {
            setSelectedSite(value || null);
            updateUrl({ site: value || null, page: 1 });
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
          placeholder="Search performers..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            updateUrl({ search: e.target.value });
          }}
          className="max-w-sm"
          disabled={!selectedSite}
        />

        <Select
          value={linkFilter}
          onValueChange={(value) => {
            setLinkFilter(value as LinkFilter);
            updateUrl({ filter: value, page: 1 });
          }}
          disabled={!selectedSite}
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Filter by link status" />
          </SelectTrigger>
          <SelectContent>
            {LINK_FILTER_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="default"
          disabled={!selectedSite || startingJob}
          onClick={async () => {
            if (!selectedSite) return;
            setStartingJob(true);
            try {
              const jobId = await startMatchingJob(selectedSite);
              router.push(`/performers/match/${jobId}`);
            } catch {
              // Error is handled in the store
            } finally {
              setStartingJob(false);
            }
          }}
        >
          {startingJob ? "Starting..." : "Start Face Matching"}
        </Button>
      </div>

      {!selectedSite ? (
        <div className="text-muted-foreground">
          Select a site to view performers
        </div>
      ) : loading ? (
        <div className="text-muted-foreground">Loading...</div>
      ) : (
        <>
          <div className="text-sm text-muted-foreground mb-2">
            Showing {performers.length} of {totalPerformers} performers
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Short Name</TableHead>
                <TableHead>Stashapp</TableHead>
                <TableHead>StashDB</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {performers.map((performer) => (
                <TableRow key={performer.ce_performers_uuid}>
                  <TableCell className="font-medium">
                    {performer.ce_performers_name || "-"}
                  </TableCell>
                  <TableCell>{performer.ce_performers_short_name || "-"}</TableCell>
                  <TableCell>
                    <Badge
                      variant={performer.has_stashapp_link ? "default" : "secondary"}
                    >
                      {performer.has_stashapp_link ? "Linked" : "Not linked"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={performer.has_stashdb_link ? "default" : "secondary"}
                    >
                      {performer.has_stashdb_link ? "Linked" : "Not linked"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" asChild>
                      <a href={`/performers/${performer.ce_performers_uuid}`}>View</a>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {performers.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-center text-muted-foreground"
                  >
                    No performers found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCurrentPage(1);
                    updateUrl({ page: 1 });
                  }}
                  disabled={currentPage === 1}
                >
                  First
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCurrentPage(currentPage - 1);
                    updateUrl({ page: currentPage - 1 });
                  }}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCurrentPage(currentPage + 1);
                    updateUrl({ page: currentPage + 1 });
                  }}
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCurrentPage(totalPages);
                    updateUrl({ page: totalPages });
                  }}
                  disabled={currentPage === totalPages}
                >
                  Last
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
