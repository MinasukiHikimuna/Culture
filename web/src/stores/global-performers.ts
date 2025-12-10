import { create } from "zustand";
import {
  api,
  type GlobalPerformer,
  type GlobalPerformerDetail,
} from "@/lib/api";

interface GlobalPerformersState {
  performers: GlobalPerformer[];
  currentPerformer: GlobalPerformerDetail | null;
  loading: boolean;
  error: string | null;
  searchTerm: string;

  // Pagination state
  currentPage: number;
  totalPages: number;
  totalPerformers: number;
  pageSize: number;

  setSearchTerm: (term: string) => void;
  setCurrentPage: (page: number) => void;
  fetchPerformers: () => Promise<void>;
  fetchPerformer: (externalId: string) => Promise<void>;
}

export const useGlobalPerformersStore = create<GlobalPerformersState>((set, get) => ({
  performers: [],
  currentPerformer: null,
  loading: true,
  error: null,
  searchTerm: "",

  // Pagination state
  currentPage: 1,
  totalPages: 0,
  totalPerformers: 0,
  pageSize: 50,

  setSearchTerm: (term) => set({ searchTerm: term, currentPage: 1 }),
  setCurrentPage: (page) => {
    set({ currentPage: page });
    get().fetchPerformers();
  },

  fetchPerformers: async () => {
    const { searchTerm, currentPage, pageSize } = get();

    set({ loading: true, error: null });
    try {
      const data = await api.globalPerformers.list({
        name: searchTerm || undefined,
        page: currentPage,
        page_size: pageSize,
      });
      set({
        performers: data.items,
        totalPages: data.total_pages,
        totalPerformers: data.total,
        loading: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load global performers",
        loading: false,
      });
    }
  },

  fetchPerformer: async (externalId) => {
    set({ loading: true, error: null, currentPerformer: null });
    try {
      const data = await api.globalPerformers.get(externalId);
      set({ currentPerformer: data, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load performer",
        loading: false,
      });
    }
  },
}));
