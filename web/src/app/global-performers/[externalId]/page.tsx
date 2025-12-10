"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useGlobalPerformersStore } from "@/stores/global-performers";
import {
  api,
  STASHAPP_URL,
  STASHDB_URL,
  type PerformerRelease,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function GlobalPerformerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const externalId = decodeURIComponent(params.externalId as string);

  const { currentPerformer, loading, error, fetchPerformer } =
    useGlobalPerformersStore();

  const [releases, setReleases] = useState<PerformerRelease[]>([]);
  const [releasesLoading, setReleasesLoading] = useState(false);

  useEffect(() => {
    fetchPerformer(externalId);
  }, [fetchPerformer, externalId]);

  // Fetch releases for all site performers
  useEffect(() => {
    if (!currentPerformer) return;

    async function fetchAllReleases() {
      setReleasesLoading(true);
      try {
        const allReleases: PerformerRelease[] = [];
        for (const siteRecord of currentPerformer!.site_records) {
          const data = await api.performers.getReleases(siteRecord.performer_uuid);
          allReleases.push(...data);
        }
        // Sort by date descending
        allReleases.sort((a, b) => {
          if (!a.ce_release_date) return 1;
          if (!b.ce_release_date) return -1;
          return b.ce_release_date.localeCompare(a.ce_release_date);
        });
        setReleases(allReleases);
      } catch {
        setReleases([]);
      } finally {
        setReleasesLoading(false);
      }
    }
    fetchAllReleases();
  }, [currentPerformer]);

  if (loading) {
    return <div className="p-8 text-muted-foreground">Loading...</div>;
  }

  if (error || !currentPerformer) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error || "Global performer not found"}
        </div>
        <Button variant="outline" className="mt-4" onClick={() => router.back()}>
          Go Back
        </Button>
      </div>
    );
  }

  const stashdbUrl =
    currentPerformer.grouping_type === "stashdb"
      ? `${STASHDB_URL}/performers/${currentPerformer.grouping_id}`
      : null;
  const stashappUrl =
    currentPerformer.grouping_type === "stashapp"
      ? `${STASHAPP_URL}/performers/${currentPerformer.grouping_id}`
      : null;

  return (
    <div className="p-8">
      <div className="mb-6">
        <Button variant="outline" size="sm" onClick={() => router.back()}>
          &larr; Back to Global Performers
        </Button>
      </div>

      <div className="mb-8">
        <h1 className="text-2xl font-bold">{currentPerformer.display_name}</h1>
        <div className="flex items-center gap-2 mt-2">
          <Badge
            variant={
              currentPerformer.grouping_type === "stashdb" ? "default" : "secondary"
            }
          >
            {currentPerformer.grouping_type}
          </Badge>
          {stashdbUrl && (
            <a
              href={stashdbUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline text-sm"
            >
              View on StashDB
            </a>
          )}
          {stashappUrl && (
            <a
              href={stashappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline text-sm"
            >
              View on Stashapp
            </a>
          )}
        </div>
        <p className="text-muted-foreground mt-2">
          {currentPerformer.total_release_count} releases across{" "}
          {currentPerformer.site_records.length} sites
        </p>
      </div>

      {/* Site Records */}
      <div className="mb-8 rounded-lg border p-6">
        <h2 className="mb-4 text-lg font-semibold">
          Sites ({currentPerformer.site_records.length})
        </h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Site</TableHead>
              <TableHead>Performer Name</TableHead>
              <TableHead>Releases</TableHead>
              <TableHead>StashDB</TableHead>
              <TableHead>Stashapp</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentPerformer.site_records.map((record) => (
              <TableRow key={record.performer_uuid}>
                <TableCell className="font-medium">{record.site_name}</TableCell>
                <TableCell>{record.performer_name}</TableCell>
                <TableCell>{record.release_count}</TableCell>
                <TableCell>
                  {record.stashdb_id ? (
                    <a
                      href={`${STASHDB_URL}/performers/${record.stashdb_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      <Badge variant="default">Linked</Badge>
                    </a>
                  ) : (
                    <Badge variant="secondary">-</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {record.stashapp_id ? (
                    <a
                      href={`${STASHAPP_URL}/performers/${record.stashapp_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      <Badge variant="default">Linked</Badge>
                    </a>
                  ) : (
                    <Badge variant="secondary">-</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/performers/${record.performer_uuid}`}>
                      View Details
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* All Releases */}
      <div className="rounded-lg border p-6">
        <h2 className="mb-4 text-lg font-semibold">
          All Releases {!releasesLoading && `(${releases.length})`}
        </h2>
        {releasesLoading ? (
          <p className="text-muted-foreground">Loading releases...</p>
        ) : releases.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Site</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {releases.map((release) => (
                <TableRow key={release.ce_release_uuid}>
                  <TableCell className="font-medium">
                    <Link
                      href={`/releases/${release.ce_release_uuid}`}
                      className="text-blue-600 hover:underline"
                    >
                      {release.ce_release_name}
                    </Link>
                  </TableCell>
                  <TableCell>{release.ce_release_date || "-"}</TableCell>
                  <TableCell>{release.ce_site_name}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-muted-foreground">
            No releases found for this performer.
          </p>
        )}
      </div>
    </div>
  );
}
