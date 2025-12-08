import { create } from "zustand";
import {
  api,
  type PerformerWithLinkStatus,
  type PerformerDetail,
  type SiteWithLinkStatus,
  type MatchingJobDetail,
  type MatchingJob,
  type EnrichedMatch,
  type BatchLinkItem,
  type LinkFilter,
} from "@/lib/api";

// Selection for a performer match
export interface MatchSelection {
  performerUuid: string;
  match: EnrichedMatch;
}

interface PerformersState {
  performers: PerformerWithLinkStatus[];
  currentPerformer: PerformerDetail | null;
  sites: SiteWithLinkStatus[];
  selectedSite: string | null;
  loading: boolean;
  error: string | null;
  searchTerm: string;
  linkFilter: LinkFilter;

  // Pagination state
  currentPage: number;
  totalPages: number;
  totalPerformers: number;
  pageSize: number;

  // Job state
  currentJob: MatchingJobDetail | null;
  recentJobs: MatchingJob[];
  jobPollingInterval: ReturnType<typeof setInterval> | null;

  // Match selections (performer_uuid -> selected match or null for skip)
  selections: Record<string, MatchSelection | null>;

  setSelectedSite: (site: string | null) => void;
  setSearchTerm: (term: string) => void;
  setLinkFilter: (filter: LinkFilter) => void;
  setCurrentPage: (page: number) => void;
  fetchSites: () => Promise<void>;
  fetchPerformers: () => Promise<void>;
  fetchPerformer: (uuid: string) => Promise<void>;
  linkPerformer: (uuid: string, target: string, externalId: string) => Promise<void>;

  // Job actions
  startMatchingJob: (siteUuid: string) => Promise<string>;
  fetchJobStatus: (jobId: string) => Promise<void>;
  cancelJob: (jobId: string) => Promise<void>;
  fetchRecentJobs: () => Promise<void>;
  startPolling: (jobId: string) => void;
  stopPolling: () => void;

  // Selection actions
  setSelection: (performerUuid: string, selection: MatchSelection | null) => void;
  clearSelections: () => void;
  approveSelections: () => Promise<void>;

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
  linkFilter: "all",

  // Pagination state
  currentPage: 1,
  totalPages: 0,
  totalPerformers: 0,
  pageSize: 50,

  // Job state
  currentJob: null,
  recentJobs: [],
  jobPollingInterval: null,
  selections: {},

  setSelectedSite: (site) => set({ selectedSite: site, performers: [], currentPage: 1 }),
  setSearchTerm: (term) => set({ searchTerm: term }),
  setLinkFilter: (filter) => set({ linkFilter: filter, currentPage: 1 }),
  setCurrentPage: (page) => {
    set({ currentPage: page });
    get().fetchPerformers();
  },

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
    const { selectedSite, linkFilter, currentPage, pageSize } = get();
    if (!selectedSite) {
      set({ performers: [], loading: false, totalPages: 0, totalPerformers: 0 });
      return;
    }

    set({ loading: true, error: null });
    try {
      const data = await api.performers.list({
        site: selectedSite,
        link_filter: linkFilter,
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

  // Job actions
  startMatchingJob: async (siteUuid) => {
    const { linkFilter } = get();
    set({ loading: true, error: null });
    try {
      const response = await api.faceMatching.startJob(siteUuid, linkFilter);
      // Start polling for job status
      get().startPolling(response.job_id);
      set({ loading: false });
      return response.job_id;
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to start matching job",
        loading: false,
      });
      throw err;
    }
  },

  fetchJobStatus: async (jobId) => {
    try {
      const job = await api.faceMatching.getJob(jobId);
      set({ currentJob: job });

      // Stop polling if job is completed, cancelled, or failed
      if (["completed", "cancelled", "failed"].includes(job.status)) {
        get().stopPolling();
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to fetch job status",
      });
    }
  },

  cancelJob: async (jobId) => {
    try {
      await api.faceMatching.cancelJob(jobId);
      get().stopPolling();
      await get().fetchJobStatus(jobId);
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to cancel job",
      });
    }
  },

  fetchRecentJobs: async () => {
    try {
      const jobs = await api.faceMatching.listJobs(10);
      set({ recentJobs: jobs });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to fetch recent jobs",
      });
    }
  },

  startPolling: (jobId) => {
    const { stopPolling, fetchJobStatus } = get();
    stopPolling(); // Clear any existing interval

    // Fetch immediately
    fetchJobStatus(jobId);

    // Then poll every 2 seconds
    const interval = setInterval(() => {
      fetchJobStatus(jobId);
    }, 2000);

    set({ jobPollingInterval: interval });
  },

  stopPolling: () => {
    const { jobPollingInterval } = get();
    if (jobPollingInterval) {
      clearInterval(jobPollingInterval);
      set({ jobPollingInterval: null });
    }
  },

  // Selection actions
  setSelection: (performerUuid, selection) => {
    set((state) => ({
      selections: {
        ...state.selections,
        [performerUuid]: selection,
      },
    }));
  },

  clearSelections: () => {
    set({ selections: {} });
  },

  approveSelections: async () => {
    const { selections, currentJob } = get();
    const links: BatchLinkItem[] = [];
    const approvedUuids: string[] = [];

    for (const [performerUuid, selection] of Object.entries(selections)) {
      if (selection) {
        links.push({
          performer_uuid: performerUuid,
          stashdb_id: selection.match.stashdb_id,
          stashapp_id: selection.match.stashapp_id?.toString() ?? null,
        });
        approvedUuids.push(performerUuid);
      }
    }

    if (links.length === 0) return;

    set({ loading: true, error: null });
    try {
      await api.performers.batchLink({ links });

      // Remove approved performers from the job results
      if (currentJob) {
        const updatedResults = { ...currentJob.results };
        for (const uuid of approvedUuids) {
          delete updatedResults[uuid];
        }
        set({
          selections: {},
          loading: false,
          currentJob: { ...currentJob, results: updatedResults },
        });
      } else {
        set({ selections: {}, loading: false });
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to approve selections",
        loading: false,
      });
      throw err;
    }
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
