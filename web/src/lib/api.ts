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
};
