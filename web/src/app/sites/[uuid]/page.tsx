"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSitesStore } from "@/stores/sites";
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

export default function SiteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const uuid = params.uuid as string;

  const { currentSite, loading, error, fetchSite, linkSite } = useSitesStore();

  const [linkTarget, setLinkTarget] = useState<string>("stashapp");
  const [externalId, setExternalId] = useState("");
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchSite(uuid);
  }, [fetchSite, uuid]);

  async function handleLink() {
    if (!externalId.trim()) {
      setLinkError("External ID is required");
      return;
    }

    setLinking(true);
    setLinkError(null);
    setLinkSuccess(null);

    try {
      await linkSite(uuid, linkTarget, externalId.trim());
      setLinkSuccess(`Successfully linked to ${linkTarget}`);
      setExternalId("");
    } catch (err) {
      setLinkError(err instanceof Error ? err.message : "Failed to link site");
    } finally {
      setLinking(false);
    }
  }

  if (loading) {
    return <div className="p-8 text-muted-foreground">Loading...</div>;
  }

  if (error || !currentSite) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error || "Site not found"}
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
          &larr; Back to Sites
        </Button>
      </div>

      <div className="mb-8">
        <h1 className="text-2xl font-bold">{currentSite.ce_sites_name}</h1>
        <p className="text-muted-foreground">{currentSite.ce_sites_short_name}</p>
        <a
          href={currentSite.ce_sites_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline"
        >
          {currentSite.ce_sites_url}
        </a>
      </div>

      <div className="mb-8 rounded-lg border p-6">
        <h2 className="mb-4 text-lg font-semibold">External Links</h2>
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <span className="w-24 font-medium">Stashapp:</span>
            {currentSite.external_ids.stashapp ? (
              <Badge variant="default">{currentSite.external_ids.stashapp}</Badge>
            ) : (
              <Badge variant="secondary">Not linked</Badge>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="w-24 font-medium">StashDB:</span>
            {currentSite.external_ids.stashdb ? (
              <Badge variant="default">{currentSite.external_ids.stashdb}</Badge>
            ) : (
              <Badge variant="secondary">Not linked</Badge>
            )}
          </div>
        </div>
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
