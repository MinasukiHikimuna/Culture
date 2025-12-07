"use client";

import { useEffect } from "react";
import { usePerformersStore } from "@/stores/performers";
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

export default function PerformersPage() {
  const {
    sites,
    selectedSite,
    loading,
    error,
    searchTerm,
    unmappedOnly,
    setSelectedSite,
    setSearchTerm,
    setUnmappedOnly,
    fetchSites,
    fetchPerformers,
    filteredPerformers,
  } = usePerformersStore();

  useEffect(() => {
    fetchSites();
  }, [fetchSites]);

  useEffect(() => {
    if (selectedSite) {
      fetchPerformers();
    }
  }, [selectedSite, unmappedOnly, fetchPerformers]);

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
          onValueChange={(value) => setSelectedSite(value || null)}
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
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-sm"
          disabled={!selectedSite}
        />

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={unmappedOnly}
            onChange={(e) => setUnmappedOnly(e.target.checked)}
            disabled={!selectedSite}
            className="rounded border-gray-300"
          />
          Unmapped only
        </label>
      </div>

      {!selectedSite ? (
        <div className="text-muted-foreground">
          Select a site to view performers
        </div>
      ) : loading ? (
        <div className="text-muted-foreground">Loading...</div>
      ) : (
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
      )}
    </div>
  );
}
