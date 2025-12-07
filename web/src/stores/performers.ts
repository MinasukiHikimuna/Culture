import { create } from "zustand";
import {
  api,
  type PerformerWithLinkStatus,
  type PerformerDetail,
  type SiteWithLinkStatus,
} from "@/lib/api";

interface PerformersState {
  performers: PerformerWithLinkStatus[];
  currentPerformer: PerformerDetail | null;
  sites: SiteWithLinkStatus[];
  selectedSite: string | null;
  loading: boolean;
  error: string | null;
  searchTerm: string;
  unmappedOnly: boolean;

  setSelectedSite: (site: string | null) => void;
  setSearchTerm: (term: string) => void;
  setUnmappedOnly: (value: boolean) => void;
  fetchSites: () => Promise<void>;
  fetchPerformers: () => Promise<void>;
  fetchPerformer: (uuid: string) => Promise<void>;
  linkPerformer: (uuid: string, target: string, externalId: string) => Promise<void>;

  filteredPerformers: () => PerformerWithLinkStatus[];
}

export const usePerformersStore = create<PerformersState>((set, get) => ({
  performers: [],
  currentPerformer: null,
  sites: [],
  selectedSite: null,
  loading: true,
  error: null,
  searchTerm: "",
  unmappedOnly: false,

  setSelectedSite: (site) => set({ selectedSite: site, performers: [] }),
  setSearchTerm: (term) => set({ searchTerm: term }),
  setUnmappedOnly: (value) => set({ unmappedOnly: value }),

  fetchSites: async () => {
    try {
      const data = await api.sites.list();
      set({ sites: data as SiteWithLinkStatus[] });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load sites",
      });
    }
  },

  fetchPerformers: async () => {
    const { selectedSite, unmappedOnly } = get();
    if (!selectedSite) {
      set({ performers: [], loading: false });
      return;
    }

    set({ loading: true, error: null });
    try {
      const data = await api.performers.list({
        site: selectedSite,
        unmapped_only: unmappedOnly,
      });
      set({ performers: data, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load performers",
        loading: false,
      });
    }
  },

  fetchPerformer: async (uuid) => {
    set({ loading: true, error: null, currentPerformer: null });
    try {
      const data = await api.performers.get(uuid);
      set({ currentPerformer: data, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load performer",
        loading: false,
      });
    }
  },

  linkPerformer: async (uuid, target, externalId) => {
    await api.performers.link(uuid, { target, external_id: externalId });
    await get().fetchPerformer(uuid);
  },

  filteredPerformers: () => {
    const { performers, searchTerm } = get();
    const term = searchTerm.toLowerCase();
    if (!term) return performers;
    return performers.filter(
      (performer) =>
        performer.ce_performers_name.toLowerCase().includes(term) ||
        (performer.ce_performers_short_name?.toLowerCase().includes(term) ?? false)
    );
  },
}));
