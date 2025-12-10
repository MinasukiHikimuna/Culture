"use client";

import { useEffect, useCallback, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useGlobalPerformersStore } from "@/stores/global-performers";
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

export default function GlobalPerformersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initializedRef = useRef(false);

  const {
    performers,
    loading,
    error,
    searchTerm,
    currentPage,
    totalPages,
    totalPerformers,
    setSearchTerm,
    setCurrentPage,
    fetchPerformers,
  } = useGlobalPerformersStore();

  // Update URL when state changes
  const updateUrl = useCallback(
    (params: { page?: number; search?: string }) => {
      const newParams = new URLSearchParams(searchParams.toString());

      if (params.page !== undefined) {
        if (params.page > 1) newParams.set("page", params.page.toString());
        else newParams.delete("page");
      }
      if (params.search !== undefined) {
        if (params.search) newParams.set("search", params.search);
        else newParams.delete("search");
      }

      const newUrl = newParams.toString()
        ? `?${newParams.toString()}`
        : "/global-performers";
      router.replace(newUrl, { scroll: false });
    },
    [searchParams, router]
  );

  // Initialize state from URL params on mount
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const pageParam = searchParams.get("page");
    const searchParam = searchParams.get("search");

    if (pageParam) {
      const page = parseInt(pageParam, 10);
      if (!isNaN(page) && page > 0) {
        useGlobalPerformersStore.setState({ currentPage: page });
      }
    }
    if (searchParam) {
      useGlobalPerformersStore.setState({ searchTerm: searchParam });
    }

    fetchPerformers();
  }, [searchParams, fetchPerformers]);

  // Fetch performers when search or page changes (after initialization)
  useEffect(() => {
    if (initializedRef.current) {
      fetchPerformers();
    }
  }, [searchTerm, currentPage, fetchPerformers]);

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
        <h1 className="text-2xl font-bold">Global Performers</h1>
        <p className="text-muted-foreground">
          View performers across all sites, grouped by StashDB/Stashapp ID
        </p>
      </div>

      <div className="mb-4 flex gap-4 flex-wrap">
        <Input
          placeholder="Search performers..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            updateUrl({ search: e.target.value, page: 1 });
          }}
          className="max-w-sm"
        />
      </div>

      {loading ? (
        <div className="text-muted-foreground">Loading...</div>
      ) : (
        <>
          <div className="text-sm text-muted-foreground mb-2">
            Showing {performers.length} of {totalPerformers} global performers
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Grouping</TableHead>
                <TableHead>Sites</TableHead>
                <TableHead>Releases</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {performers.map((performer) => (
                <TableRow key={performer.grouping_id}>
                  <TableCell className="font-medium">
                    {performer.display_name || "-"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        performer.grouping_type === "stashdb"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {performer.grouping_type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="text-muted-foreground">
                      {performer.site_performers
                        .map((sp) => sp.site_name)
                        .join(", ")}
                    </span>
                    <Badge variant="outline" className="ml-2">
                      {performer.site_count}{" "}
                      {performer.site_count === 1 ? "site" : "sites"}
                    </Badge>
                  </TableCell>
                  <TableCell>{performer.total_release_count}</TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" asChild>
                      <a
                        href={`/global-performers/${encodeURIComponent(performer.grouping_id)}`}
                      >
                        View
                      </a>
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
                    No global performers found
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
