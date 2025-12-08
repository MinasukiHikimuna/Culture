"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { usePerformersStore } from "@/stores/performers";
import { api, PerformerRelease } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PerformerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const uuid = params.uuid as string;

  const { currentPerformer, loading, error, fetchPerformer, linkPerformer } =
    usePerformersStore();

  const [linkTarget, setLinkTarget] = useState<string>("stashapp");
  const [externalId, setExternalId] = useState("");
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);
  const [releases, setReleases] = useState<PerformerRelease[]>([]);
  const [releasesLoading, setReleasesLoading] = useState(false);

  useEffect(() => {
    setImageError(false);
    fetchPerformer(uuid);

    async function fetchReleases() {
      setReleasesLoading(true);
      try {
        const data = await api.performers.getReleases(uuid);
        setReleases(data);
      } catch {
        setReleases([]);
      } finally {
        setReleasesLoading(false);
      }
    }
    fetchReleases();
  }, [fetchPerformer, uuid]);

  async function handleLink() {
    if (!externalId.trim()) {
      setLinkError("External ID is required");
      return;
    }

    setLinking(true);
    setLinkError(null);
    setLinkSuccess(null);

    try {
      await linkPerformer(uuid, linkTarget, externalId.trim());
      setLinkSuccess(`Successfully linked to ${linkTarget}`);
      setExternalId("");
    } catch (err) {
      setLinkError(err instanceof Error ? err.message : "Failed to link performer");
    } finally {
      setLinking(false);
    }
  }

  if (loading) {
    return <div className="p-8 text-muted-foreground">Loading...</div>;
  }

  if (error || !currentPerformer) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error || "Performer not found"}
        </div>
        <Button variant="outline" className="mt-4" onClick={() => router.back()}>
          Go Back
        </Button>
      </div>
    );
  }

  const imageUrl = `${API_BASE_URL}/performers/${uuid}/image`;

  return (
    <div className="p-8">
      <div className="mb-6">
        <Button variant="outline" size="sm" onClick={() => router.back()}>
          &larr; Back to Performers
        </Button>
      </div>

      <div className="mb-8 flex gap-8">
        {/* Performer Info */}
        <div className="flex-grow">
          <h1 className="text-2xl font-bold">{currentPerformer.ce_performers_name}</h1>
          <p className="text-muted-foreground">
            {currentPerformer.ce_performers_short_name || "No short name"}
          </p>
          {currentPerformer.ce_performers_url && (
            <p className="mt-2 text-sm text-muted-foreground">
              URL: {currentPerformer.ce_performers_url}
            </p>
          )}
          {currentPerformer.ce_sites_name && (
            <p className="text-sm text-muted-foreground">
              Site: {currentPerformer.ce_sites_name}
            </p>
          )}
        </div>

        {/* Performer Image - right side */}
        {!imageError && (
          <div className="flex-shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl}
              alt={currentPerformer.ce_performers_name}
              width={300}
              height={450}
              className="rounded-lg object-cover shadow-lg"
              onError={() => setImageError(true)}
            />
          </div>
        )}
      </div>

      <div className="mb-8 rounded-lg border p-6">
        <h2 className="mb-4 text-lg font-semibold">External Links</h2>
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <span className="w-24 font-medium">Stashapp:</span>
            {currentPerformer.external_ids.stashapp ? (
              <Badge variant="default">{currentPerformer.external_ids.stashapp}</Badge>
            ) : (
              <Badge variant="secondary">Not linked</Badge>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="w-24 font-medium">StashDB:</span>
            {currentPerformer.external_ids.stashdb ? (
              <Badge variant="default">{currentPerformer.external_ids.stashdb}</Badge>
            ) : (
              <Badge variant="secondary">Not linked</Badge>
            )}
          </div>
        </div>
      </div>

      {/* Releases */}
      <div className="mb-8 rounded-lg border p-6">
        <h2 className="mb-4 text-lg font-semibold">
          Releases {!releasesLoading && `(${releases.length})`}
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
          <p className="text-muted-foreground">No releases found for this performer.</p>
        )}
      </div>

      <div className="rounded-lg border p-6">
        <h2 className="mb-4 text-lg font-semibold">Link to External System</h2>

        {linkError && (
          <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {linkError}
          </div>
        )}

        {linkSuccess && (
          <div className="mb-4 rounded-md bg-green-100 p-3 text-sm text-green-800 dark:bg-green-900/20 dark:text-green-400">
            {linkSuccess}
          </div>
        )}

        <div className="flex gap-4">
          <Select value={linkTarget} onValueChange={setLinkTarget}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="stashapp">Stashapp</SelectItem>
              <SelectItem value="stashdb">StashDB</SelectItem>
            </SelectContent>
          </Select>

          <Input
            placeholder="External ID"
            value={externalId}
            onChange={(e) => setExternalId(e.target.value)}
            className="max-w-xs"
          />

          <Button onClick={handleLink} disabled={linking}>
            {linking ? "Linking..." : "Link"}
          </Button>
        </div>
      </div>
    </div>
  );
}
