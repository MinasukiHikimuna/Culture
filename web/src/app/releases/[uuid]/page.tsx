"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useReleasesStore } from "@/stores/releases";
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

export default function ReleaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const uuid = params.uuid as string;

  const { currentRelease, loading, error, fetchRelease, linkRelease } =
    useReleasesStore();

  const [linkTarget, setLinkTarget] = useState<string>("stashapp");
  const [externalId, setExternalId] = useState("");
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchRelease(uuid);
  }, [fetchRelease, uuid]);

  async function handleLink() {
    if (!externalId.trim()) {
      setLinkError("External ID is required");
      return;
    }

    setLinking(true);
    setLinkError(null);
    setLinkSuccess(null);

    try {
      await linkRelease(uuid, linkTarget, externalId.trim());
      setLinkSuccess(`Successfully linked to ${linkTarget}`);
      setExternalId("");
    } catch (err) {
      setLinkError(
        err instanceof Error ? err.message : "Failed to link release"
      );
    } finally {
      setLinking(false);
    }
  }

  if (loading) {
    return <div className="p-8 text-muted-foreground">Loading...</div>;
  }

  if (error || !currentRelease) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error || "Release not found"}
        </div>
        <Button variant="outline" className="mt-4" onClick={() => router.back()}>
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <Button variant="outline" size="sm" onClick={() => router.back()}>
          &larr; Back to Releases
        </Button>
      </div>

      <div className="mb-8">
        <h1 className="text-2xl font-bold">{currentRelease.ce_release_name}</h1>
        <p className="text-muted-foreground">
          {currentRelease.ce_release_short_name}
        </p>
        <div className="mt-2 flex items-center gap-4 text-sm">
          <span>
            <strong>Site:</strong> {currentRelease.ce_site_name}
          </span>
          <span>
            <strong>Date:</strong> {currentRelease.ce_release_date || "N/A"}
          </span>
        </div>
        {currentRelease.ce_release_url && (
          <a
            href={currentRelease.ce_release_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline text-sm"
          >
            {currentRelease.ce_release_url}
          </a>
        )}
      </div>

      {/* External Links */}
      <div className="mb-8 rounded-lg border p-6">
        <h2 className="mb-4 text-lg font-semibold">External Links</h2>
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <span className="w-24 font-medium">Stashapp:</span>
            {currentRelease.external_ids.stashapp ? (
              <Badge variant="default">
                {currentRelease.external_ids.stashapp}
              </Badge>
            ) : (
              <Badge variant="secondary">Not linked</Badge>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="w-24 font-medium">StashDB:</span>
            {currentRelease.external_ids.stashdb ? (
              <Badge variant="default">
                {currentRelease.external_ids.stashdb}
              </Badge>
            ) : (
              <Badge variant="secondary">Not linked</Badge>
            )}
          </div>
        </div>
      </div>

      {/* Performers */}
      {currentRelease.performers.length > 0 && (
        <div className="mb-8 rounded-lg border p-6">
          <h2 className="mb-4 text-lg font-semibold">Performers</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Stashapp</TableHead>
                <TableHead>StashDB</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {currentRelease.performers.map((performer) => (
                <TableRow key={performer.ce_performers_uuid}>
                  <TableCell className="font-medium">
                    {performer.ce_performers_name}
                  </TableCell>
                  <TableCell>
                    {performer.ce_performers_stashapp_id ? (
                      <Badge variant="default">
                        {performer.ce_performers_stashapp_id}
                      </Badge>
                    ) : (
                      <Badge variant="secondary">-</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {performer.ce_performers_stashdb_id ? (
                      <Badge variant="default">
                        {performer.ce_performers_stashdb_id}
                      </Badge>
                    ) : (
                      <Badge variant="secondary">-</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Tags */}
      {currentRelease.tags.length > 0 && (
        <div className="mb-8 rounded-lg border p-6">
          <h2 className="mb-4 text-lg font-semibold">Tags</h2>
          <div className="flex flex-wrap gap-2">
            {currentRelease.tags.map((tag) => (
              <Badge key={tag.ce_tags_uuid} variant="outline">
                {tag.ce_tags_name}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Downloads */}
      {currentRelease.downloads.length > 0 && (
        <div className="mb-8 rounded-lg border p-6">
          <h2 className="mb-4 text-lg font-semibold">Downloads</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File Type</TableHead>
                <TableHead>Content Type</TableHead>
                <TableHead>Variant</TableHead>
                <TableHead>Downloaded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {currentRelease.downloads.map((download) => (
                <TableRow key={download.ce_downloads_uuid}>
                  <TableCell>{download.ce_downloads_file_type}</TableCell>
                  <TableCell>{download.ce_downloads_content_type}</TableCell>
                  <TableCell>{download.ce_downloads_variant || "-"}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(
                      download.ce_downloads_downloaded_at
                    ).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Link Form */}
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
