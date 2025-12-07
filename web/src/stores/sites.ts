import { create } from "zustand";
import { api, type SiteWithLinkStatus, type SiteDetail } from "@/lib/api";

interface SitesState {
  sites: SiteWithLinkStatus[];
  currentSite: SiteDetail | null;
  loading: boolean;
  error: string | null;
  searchTerm: string;
  linkFilter: "all" | "linked" | "unlinked";

  setSearchTerm: (term: string) => void;
  setLinkFilter: (filter: "all" | "linked" | "unlinked") => void;
  fetchSites: () => Promise<void>;
  fetchSite: (uuid: string) => Promise<void>;
  linkSite: (uuid: string, target: string, externalId: string) => Promise<void>;

  filteredSites: () => SiteWithLinkStatus[];
}

export const useSitesStore = create<SitesState>((set, get) => ({
  sites: [],
  currentSite: null,
  loading: false,
  error: null,
  searchTerm: "",
  linkFilter: "all",

  setSearchTerm: (term) => set({ searchTerm: term }),
  setLinkFilter: (filter) => set({ linkFilter: filter }),

  fetchSites: async () => {
    set({ loading: true, error: null });
    try {
      const { linkFilter } = get();
      const linked = linkFilter === "all" ? null : linkFilter === "linked";
      const data = await api.sites.list(linked);
      set({ sites: data as SiteWithLinkStatus[], loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load sites",
        loading: false,
      });
    }
  },

  fetchSite: async (uuid) => {
    set({ loading: true, error: null, currentSite: null });
    try {
      const data = await api.sites.get(uuid);
      set({ currentSite: data, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load site",
        loading: false,
      });
    }
  },

  linkSite: async (uuid, target, externalId) => {
    await api.sites.link(uuid, { target, external_id: externalId });
    await get().fetchSite(uuid);
  },

  filteredSites: () => {
    const { sites, searchTerm } = get();
    const term = searchTerm.toLowerCase();
    return sites.filter(
      (site) =>
        site.ce_sites_name.toLowerCase().includes(term) ||
        site.ce_sites_short_name.toLowerCase().includes(term) ||
        site.ce_sites_url.toLowerCase().includes(term)
    );
  },
}));
