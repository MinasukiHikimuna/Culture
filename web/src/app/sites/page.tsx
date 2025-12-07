"use client";

import { useEffect } from "react";
import { useSitesStore } from "@/stores/sites";
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

export default function SitesPage() {
  const {
    loading,
    error,
    searchTerm,
    linkFilter,
    setSearchTerm,
    setLinkFilter,
    fetchSites,
    filteredSites,
  } = useSitesStore();

  useEffect(() => {
    fetchSites();
  }, [fetchSites, linkFilter]);

  const sites = filteredSites();

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
        <h1 className="text-2xl font-bold">Sites</h1>
        <p className="text-muted-foreground">
          Manage site links to Stashapp and StashDB
        </p>
      </div>

      <div className="mb-4 flex gap-4">
        <Input
          placeholder="Search sites..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-sm"
        />
        <Select
          value={linkFilter}
          onValueChange={(value) =>
            setLinkFilter(value as "all" | "linked" | "unlinked")
          }
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Sites</SelectItem>
            <SelectItem value="linked">Linked</SelectItem>
            <SelectItem value="unlinked">Unlinked</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="text-muted-foreground">Loading...</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Short Name</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>URL</TableHead>
              <TableHead>Stashapp</TableHead>
              <TableHead>StashDB</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sites.map((site) => (
              <TableRow key={site.ce_sites_uuid}>
                <TableCell className="font-medium">
                  {site.ce_sites_short_name}
                </TableCell>
                <TableCell>{site.ce_sites_name}</TableCell>
                <TableCell>
                  <a
                    href={site.ce_sites_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {site.ce_sites_url}
                  </a>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={site.has_stashapp_link ? "default" : "secondary"}
                  >
                    {site.has_stashapp_link ? "Linked" : "Not linked"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={site.has_stashdb_link ? "default" : "secondary"}
                  >
                    {site.has_stashdb_link ? "Linked" : "Not linked"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button variant="outline" size="sm" asChild>
                    <a href={`/sites/${site.ce_sites_uuid}`}>View</a>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {sites.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center text-muted-foreground"
                >
                  No sites found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
