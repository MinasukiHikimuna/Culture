import { create } from "zustand";
import { api, type Release, type ReleaseDetail, type Site } from "@/lib/api";

interface ReleasesState {
  // Site selection
  sites: Site[];
  selectedSiteUuid: string | null;

  // Releases list
  releases: Release[];
  currentRelease: ReleaseDetail | null;
  loading: boolean;
  error: string | null;

  // Filters
  searchTerm: string;
  sortDesc: boolean;
  limit: number | null;

  // Actions
  fetchSites: () => Promise<void>;
  setSelectedSite: (uuid: string | null) => void;
  setSearchTerm: (term: string) => void;
  setSortDesc: (desc: boolean) => void;
  setLimit: (limit: number | null) => void;
  fetchReleases: () => Promise<void>;
  fetchRelease: (uuid: string) => Promise<void>;
  linkRelease: (uuid: string, target: string, externalId: string) => Promise<void>;

  // Computed
  filteredReleases: () => Release[];
}

export const useReleasesStore = create<ReleasesState>((set, get) => ({
  sites: [],
  selectedSiteUuid: null,
  releases: [],
  currentRelease: null,
  loading: true,
  error: null,
  searchTerm: "",
  sortDesc: true,
  limit: 100,

  fetchSites: async () => {
    try {
      const data = await api.sites.list();
      set({ sites: data as Site[] });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load sites",
      });
    }
  },

  setSelectedSite: (uuid) => {
    set({ selectedSiteUuid: uuid, releases: [], currentRelease: null });
    if (uuid) {
      get().fetchReleases();
    }
  },

  setSearchTerm: (term) => set({ searchTerm: term }),
  setSortDesc: (desc) => set({ sortDesc: desc }),
  setLimit: (limit) => set({ limit }),

  fetchReleases: async () => {
    const { selectedSiteUuid, sortDesc, limit } = get();
    if (!selectedSiteUuid) {
      set({ releases: [], loading: false });
      return;
    }

    set({ loading: true, error: null });
    try {
      const data = await api.releases.list({
        site: selectedSiteUuid,
        desc: sortDesc,
        limit: limit ?? undefined,
      });
      set({ releases: data, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load releases",
        loading: false,
      });
    }
  },

  fetchRelease: async (uuid) => {
    set({ loading: true, error: null, currentRelease: null });
    try {
      const data = await api.releases.get(uuid);
      set({ currentRelease: data, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load release",
        loading: false,
      });
    }
  },

  linkRelease: async (uuid, target, externalId) => {
    await api.releases.link(uuid, { target, external_id: externalId });
    await get().fetchRelease(uuid);
  },

  filteredReleases: () => {
    const { releases, searchTerm } = get();
    const term = searchTerm.toLowerCase();
    if (!term) return releases;

    return releases.filter(
      (release) =>
        release.ce_release_name.toLowerCase().includes(term) ||
        release.ce_release_short_name.toLowerCase().includes(term)
    );
  },
}));
