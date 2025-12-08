import type { components } from "@/types/api";

export type Site = components["schemas"]["Site"];
export type SiteWithLinkStatus = components["schemas"]["SiteWithLinkStatus"];
export type SiteDetail = components["schemas"]["SiteDetail"];
export type LinkSiteRequest = components["schemas"]["LinkSiteRequest"];

// Release types - manually defined until OpenAPI types are regenerated
export interface Release {
  ce_site_uuid: string;
  ce_site_name: string;
  ce_release_uuid: string;
  ce_release_date: string | null;
  ce_release_short_name: string;
  ce_release_name: string;
  ce_release_url: string;
  ce_release_description: string | null;
  ce_release_created: string;
  ce_release_last_updated: string;
  ce_release_available_files: string | null;
  ce_release_json_document: string | null;
}

export interface ReleaseExternalIds {
  stashapp: string | null;
  stashdb: string | null;
}

export interface ReleasePerformer {
  ce_performers_uuid: string;
  ce_performers_short_name: string;
  ce_performers_name: string;
  ce_performers_url: string | null;
  ce_performers_stashapp_id: string | null;
  ce_performers_stashdb_id: string | null;
}

export interface ReleaseTag {
  ce_tags_uuid: string;
  ce_tags_short_name: string;
  ce_tags_name: string;
  ce_tags_url: string | null;
}

export interface ReleaseDownload {
  ce_downloads_uuid: string;
  ce_downloads_downloaded_at: string;
  ce_downloads_file_type: string;
  ce_downloads_content_type: string;
  ce_downloads_variant: string | null;
  ce_downloads_saved_filename: string | null;
}

export interface ReleaseDetail extends Release {
  external_ids: ReleaseExternalIds;
  performers: ReleasePerformer[];
  tags: ReleaseTag[];
  downloads: ReleaseDownload[];
}

export interface LinkReleaseRequest {
  target: string;
  external_id: string;
}

// Performer types
export interface Performer {
  ce_performers_uuid: string;
  ce_performers_short_name: string | null;
  ce_performers_name: string;
  ce_performers_url: string | null;
}

export interface PerformerWithLinkStatus extends Performer {
  ce_site_uuid: string | null;
  ce_site_name: string | null;
  has_stashapp_link: boolean;
  has_stashdb_link: boolean;
}

export interface PerformerExternalIds {
  stashapp: string | null;
  stashdb: string | null;
}

export interface PerformerDetail extends Performer {
  ce_sites_short_name: string | null;
  ce_sites_name: string | null;
  external_ids: PerformerExternalIds;
}

export interface LinkPerformerRequest {
  target: string;
  external_id: string;
}

export type LinkFilter = "all" | "linked" | "unlinked" | "unlinked_stashdb" | "unlinked_stashapp";

// Face matching types
export interface NameMatchResult {
  match_type: string;
  matched_name: string | null;
  score: number;
}

export interface EnrichedMatch {
  name: string;
  confidence: number;
  stashdb_id: string;
  stashdb_image_url: string | null;
  aliases: string[];
  country: string | null;
  stashapp_id: number | null;
  stashapp_exists: boolean;
  name_match: NameMatchResult;
}

export interface PerformerMatchResult {
  performer_uuid: string;
  performer_name: string;
  performer_image_available: boolean;
  bin: "easy" | "difficult" | "no_match" | "no_image";
  matches: EnrichedMatch[];
}

export interface MatchingJob {
  job_id: string;
  site_uuid: string;
  site_name: string;
  status: "pending" | "running" | "completed" | "cancelled" | "failed";
  total_performers: number;
  processed_count: number;
  error: string | null;
}

export interface MatchingJobDetail extends MatchingJob {
  results: Record<string, PerformerMatchResult>;
}

export interface StartJobRequest {
  site: string;
}

export interface StartJobResponse {
  job_id: string;
  message: string;
}

export interface BatchLinkItem {
  performer_uuid: string;
  stashapp_id?: string | null;
  stashdb_id?: string | null;
}

export interface BatchLinkRequest {
  links: BatchLinkItem[];
}

export interface BatchLinkResult {
  performer_uuid: string;
  success: boolean;
  error: string | null;
}

export interface BatchLinkResponse {
  results: BatchLinkResult[];
  successful: number;
  failed: number;
}

export interface StashDBSearchResult {
  id: string;
  name: string;
  disambiguation: string | null;
  aliases: string[];
  country: string | null;
  image_url: string | null;
}

export interface StashappSearchResult {
  id: number;
  name: string;
  disambiguation: string | null;
  aliases: string[];
  stashdb_id: string | null;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export const api = {
  sites: {
    list: async (linked?: boolean | null): Promise<Site[] | SiteWithLinkStatus[]> => {
      const params = new URLSearchParams();
      if (linked !== undefined && linked !== null) {
        params.set("linked", String(linked));
      }
      const query = params.toString();
      return fetchApi(`/sites${query ? `?${query}` : ""}`);
    },

    get: async (uuid: string): Promise<SiteDetail> => {
      return fetchApi(`/sites/${uuid}`);
    },

    link: async (uuid: string, request: LinkSiteRequest): Promise<Record<string, unknown>> => {
      return fetchApi(`/sites/${uuid}/link`, {
        method: "POST",
        body: JSON.stringify(request),
      });
    },
  },

  releases: {
    list: async (params: {
      site: string;
      tag?: string;
      performer?: string;
      limit?: number;
      desc?: boolean;
    }): Promise<Release[]> => {
      const searchParams = new URLSearchParams();
      searchParams.set("site", params.site);
      if (params.tag) searchParams.set("tag", params.tag);
      if (params.performer) searchParams.set("performer", params.performer);
      if (params.limit) searchParams.set("limit", String(params.limit));
      if (params.desc) searchParams.set("desc", "true");
      return fetchApi(`/releases?${searchParams.toString()}`);
    },

    get: async (uuid: string): Promise<ReleaseDetail> => {
      return fetchApi(`/releases/${uuid}`);
    },

    link: async (uuid: string, request: LinkReleaseRequest): Promise<Record<string, unknown>> => {
      return fetchApi(`/releases/${uuid}/link`, {
        method: "POST",
        body: JSON.stringify(request),
      });
    },
  },

  health: async (): Promise<Record<string, unknown>> => {
    return fetchApi("/health");
  },

  performers: {
    list: async (params: {
      site: string;
      name?: string;
      link_filter?: "all" | "linked" | "unlinked" | "unlinked_stashdb" | "unlinked_stashapp";
      limit?: number;
    }): Promise<PerformerWithLinkStatus[]> => {
      const searchParams = new URLSearchParams();
      searchParams.set("site", params.site);
      if (params.name) searchParams.set("name", params.name);
      if (params.link_filter) searchParams.set("link_filter", params.link_filter);
      if (params.limit) searchParams.set("limit", String(params.limit));
      return fetchApi(`/performers?${searchParams.toString()}`);
    },

    get: async (uuid: string): Promise<PerformerDetail> => {
      return fetchApi(`/performers/${uuid}`);
    },

    link: async (uuid: string, request: LinkPerformerRequest): Promise<Record<string, unknown>> => {
      return fetchApi(`/performers/${uuid}/link`, {
        method: "POST",
        body: JSON.stringify(request),
      });
    },

    batchLink: async (request: BatchLinkRequest): Promise<BatchLinkResponse> => {
      return fetchApi(`/performers/batch-link`, {
        method: "POST",
        body: JSON.stringify(request),
      });
    },

    searchStashDB: async (query: string, limit?: number): Promise<StashDBSearchResult[]> => {
      const params = new URLSearchParams({ query });
      if (limit) params.set("limit", String(limit));
      return fetchApi(`/performers/search/stashdb?${params.toString()}`);
    },

    searchStashapp: async (query: string, limit?: number): Promise<StashappSearchResult[]> => {
      const params = new URLSearchParams({ query });
      if (limit) params.set("limit", String(limit));
      return fetchApi(`/performers/search/stashapp?${params.toString()}`);
    },
  },

  faceMatching: {
    startJob: async (site: string): Promise<StartJobResponse> => {
      return fetchApi(`/face-matching/jobs`, {
        method: "POST",
        body: JSON.stringify({ site }),
      });
    },

    listJobs: async (limit?: number): Promise<MatchingJob[]> => {
      const params = limit ? `?limit=${limit}` : "";
      return fetchApi(`/face-matching/jobs${params}`);
    },

    getJob: async (jobId: string): Promise<MatchingJobDetail> => {
      return fetchApi(`/face-matching/jobs/${jobId}`);
    },

    cancelJob: async (jobId: string): Promise<Record<string, unknown>> => {
      return fetchApi(`/face-matching/jobs/${jobId}`, {
        method: "DELETE",
      });
    },
  },
};
