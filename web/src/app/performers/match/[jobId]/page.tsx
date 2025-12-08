"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { usePerformersStore, type MatchSelection } from "@/stores/performers";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  api,
  API_BASE_URL,
  type PerformerMatchResult,
  type EnrichedMatch,
  type StashDBSearchResult,
  type StashappSearchResult,
} from "@/lib/api";

export default function MatchResultsPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const {
    currentJob,
    selections,
    error,
    startPolling,
    stopPolling,
    cancelJob,
    setSelection,
    clearSelections,
    approveSelections,
  } = usePerformersStore();

  const [activeTab, setActiveTab] = useState("easy");
  const [approving, setApproving] = useState(false);

  useEffect(() => {
    // Start polling when component mounts
    startPolling(jobId);

    // Cleanup on unmount
    return () => {
      stopPolling();
    };
  }, [jobId, startPolling, stopPolling]);

  // Group results by bin
  const resultsByBin = {
    easy: [] as PerformerMatchResult[],
    difficult: [] as PerformerMatchResult[],
    no_match: [] as PerformerMatchResult[],
    no_image: [] as PerformerMatchResult[],
  };

  if (currentJob?.results) {
    Object.values(currentJob.results).forEach((result) => {
      resultsByBin[result.bin].push(result);
    });
  }

  const handleApprove = async () => {
    setApproving(true);
    try {
      await approveSelections();
      // Note: approveSelections already removes approved performers from currentJob.results
      // Do NOT call fetchJobStatus here as it would overwrite the local state with server state
    } finally {
      setApproving(false);
    }
  };

  const selectedCount = Object.values(selections).filter((s) => s !== null).length;

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          {error}
        </div>
        <Button variant="outline" className="mt-4" onClick={() => router.back()}>
          Go Back
        </Button>
      </div>
    );
  }

  if (!currentJob) {
    return <div className="p-8 text-muted-foreground">Loading job...</div>;
  }

  const isRunning = currentJob.status === "running" || currentJob.status === "pending";
  const progress = currentJob.total_performers > 0
    ? (currentJob.processed_count / currentJob.total_performers) * 100
    : 0;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Button variant="outline" size="sm" onClick={() => router.push("/performers")}>
            &larr; Back to Performers
          </Button>
        </div>
        <div className="flex items-center gap-4">
          {isRunning && (
            <Button variant="destructive" size="sm" onClick={() => cancelJob(jobId)}>
              Cancel Job
            </Button>
          )}
        </div>
      </div>

      {/* Job Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Face Matching: {currentJob.site_name}</h1>
        <div className="mt-2 flex items-center gap-4">
          <Badge variant={isRunning ? "default" : currentJob.status === "completed" ? "secondary" : "destructive"}>
            {currentJob.status}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {currentJob.processed_count} of {currentJob.total_performers} processed
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      {isRunning && (
        <div className="mb-6">
          <Progress value={progress} className="h-2" />
        </div>
      )}

      {/* Error Message */}
      {currentJob.error && (
        <div className="mb-6 rounded-md bg-destructive/10 p-4 text-destructive">
          {currentJob.error}
        </div>
      )}

      {/* Results Tabs */}
      {currentJob.status === "completed" && (
        <>
          <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
            <TabsList>
              <TabsTrigger value="easy">
                Easy ({resultsByBin.easy.length})
              </TabsTrigger>
              <TabsTrigger value="difficult">
                Difficult ({resultsByBin.difficult.length})
              </TabsTrigger>
              <TabsTrigger value="no_match">
                No Match ({resultsByBin.no_match.length})
              </TabsTrigger>
              <TabsTrigger value="no_image">
                No Image ({resultsByBin.no_image.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="easy" className="mt-4">
              <PerformerMatchList
                results={resultsByBin.easy}
                selections={selections}
                onSelectionChange={setSelection}
                autoSelect
              />
            </TabsContent>

            <TabsContent value="difficult" className="mt-4">
              <PerformerMatchList
                results={resultsByBin.difficult}
                selections={selections}
                onSelectionChange={setSelection}
              />
            </TabsContent>

            <TabsContent value="no_match" className="mt-4">
              {resultsByBin.no_match.length === 0 ? (
                <div className="text-muted-foreground">No performers in this category</div>
              ) : (
                <div className="space-y-4 pb-24">
                  <div className="text-muted-foreground mb-4">
                    {resultsByBin.no_match.length} performers with no face matches found.
                    Use manual search to find matches.
                  </div>
                  {resultsByBin.no_match.map((result) => (
                    <NoMatchPerformerCard
                      key={result.performer_uuid}
                      result={result}
                      selection={selections[result.performer_uuid]}
                      onSelectionChange={(selection) => setSelection(result.performer_uuid, selection)}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="no_image" className="mt-4">
              {resultsByBin.no_image.length === 0 ? (
                <div className="text-muted-foreground">No performers in this category</div>
              ) : (
                <div className="space-y-4 pb-24">
                  <div className="text-muted-foreground mb-4">
                    {resultsByBin.no_image.length} performers without images.
                    Use manual search to find matches.
                  </div>
                  {resultsByBin.no_image.map((result) => (
                    <NoMatchPerformerCard
                      key={result.performer_uuid}
                      result={result}
                      selection={selections[result.performer_uuid]}
                      onSelectionChange={(selection) => setSelection(result.performer_uuid, selection)}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>

          {/* Action Bar */}
          <div className="fixed bottom-0 left-0 right-0 border-t bg-background p-4">
            <div className="mx-auto flex max-w-screen-xl items-center justify-between">
              <div className="text-sm text-muted-foreground">
                {selectedCount} performer(s) selected
              </div>
              <div className="flex gap-4">
                <Button variant="outline" onClick={clearSelections} disabled={selectedCount === 0}>
                  Clear Selection
                </Button>
                <Button onClick={handleApprove} disabled={selectedCount === 0 || approving}>
                  {approving ? "Approving..." : `Approve ${selectedCount} Matches`}
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

interface PerformerMatchListProps {
  results: PerformerMatchResult[];
  selections: Record<string, MatchSelection | null>;
  onSelectionChange: (performerUuid: string, selection: MatchSelection | null) => void;
  autoSelect?: boolean;
}

function PerformerMatchList({
  results,
  selections,
  onSelectionChange,
  autoSelect,
}: PerformerMatchListProps) {
  // Auto-select best match for easy matches on first render
  useEffect(() => {
    if (autoSelect) {
      results.forEach((result) => {
        if (result.matches.length > 0 && selections[result.performer_uuid] === undefined) {
          onSelectionChange(result.performer_uuid, {
            performerUuid: result.performer_uuid,
            match: result.matches[0],
          });
        }
      });
    }
  }, [autoSelect, results, selections, onSelectionChange]);

  if (results.length === 0) {
    return <div className="text-muted-foreground">No performers in this category</div>;
  }

  return (
    <div className="space-y-4 pb-24">
      {results.map((result) => (
        <PerformerMatchCard
          key={result.performer_uuid}
          result={result}
          selection={selections[result.performer_uuid]}
          onSelectionChange={(selection) => onSelectionChange(result.performer_uuid, selection)}
        />
      ))}
    </div>
  );
}

interface PerformerMatchCardProps {
  result: PerformerMatchResult;
  selection: MatchSelection | null | undefined;
  onSelectionChange: (selection: MatchSelection | null) => void;
}

function PerformerMatchCard({ result, selection, onSelectionChange }: PerformerMatchCardProps) {
  const isSelected = selection !== null && selection !== undefined;
  const selectedMatch = selection?.match;

  const handleMatchSelect = (match: EnrichedMatch) => {
    if (selectedMatch?.stashdb_id === match.stashdb_id) {
      // Deselect if clicking the same match
      onSelectionChange(null);
    } else {
      onSelectionChange({
        performerUuid: result.performer_uuid,
        match,
      });
    }
  };

  return (
    <div className={`rounded-lg border p-4 ${isSelected ? "border-primary bg-primary/5" : ""}`}>
      <div className="grid grid-cols-[280px_1fr] gap-6">
        {/* Left Column: CE Performer */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2 mb-3">
            <Checkbox
              checked={isSelected}
              onCheckedChange={(checked) => {
                if (!checked) {
                  onSelectionChange(null);
                } else if (result.matches.length > 0) {
                  onSelectionChange({
                    performerUuid: result.performer_uuid,
                    match: result.matches[0],
                  });
                }
              }}
            />
            <a
              href={`/performers/${result.performer_uuid}`}
              className="text-lg font-semibold hover:underline text-primary"
              onClick={(e) => e.stopPropagation()}
            >
              {result.performer_name}
            </a>
            <Badge variant={result.bin === "easy" ? "default" : "secondary"}>
              {result.bin}
            </Badge>
          </div>
          {result.performer_image_available ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`${API_BASE_URL}/performers/${result.performer_uuid}/image`}
              alt={result.performer_name}
              className="w-full aspect-[3/4] rounded-lg object-cover"
            />
          ) : (
            <div className="w-full aspect-[3/4] flex items-center justify-center rounded-lg bg-muted">
              <span className="text-sm text-muted-foreground">No image</span>
            </div>
          )}
          <PerformerSearchDialog
            performerName={result.performer_name}
            onSelect={(match) => handleMatchSelect(match)}
            trigger={
              <Button variant="outline" size="sm" className="mt-2 w-full">
                Search StashDB/Stashapp
              </Button>
            }
          />
        </div>

        {/* Right Column: Match Candidates */}
        <div className="grid grid-cols-2 gap-3 content-start">
          {/* Show manually selected match first if it's not in the original matches */}
          {selectedMatch && !result.matches.some(m => m.stashdb_id === selectedMatch.stashdb_id) && (
            <MatchCard
              key={selectedMatch.stashdb_id}
              match={selectedMatch}
              isSelected={true}
              onSelect={() => handleMatchSelect(selectedMatch)}
              isManualSearch
            />
          )}
          {result.matches.map((match) => (
            <MatchCard
              key={match.stashdb_id}
              match={match}
              isSelected={selectedMatch?.stashdb_id === match.stashdb_id}
              onSelect={() => handleMatchSelect(match)}
            />
          ))}
          {result.matches.length === 0 && !selectedMatch && (
            <div className="col-span-2 flex items-center justify-center h-32 text-muted-foreground">
              No matches found - use search to find a match
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface MatchCardProps {
  match: EnrichedMatch;
  isSelected: boolean;
  onSelect: () => void;
  isManualSearch?: boolean;
}

function MatchCard({ match, isSelected, onSelect, isManualSearch }: MatchCardProps) {
  return (
    <div
      className={`cursor-pointer rounded-lg border p-3 transition-colors ${
        isSelected ? "border-primary bg-primary/10 ring-2 ring-primary" : "hover:bg-muted/50"
      }`}
      onClick={onSelect}
    >
      {/* Header with name and badges */}
      <div className="mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <a
            href={`https://stashdb.org/performers/${match.stashdb_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium hover:underline text-primary"
            onClick={(e) => e.stopPropagation()}
          >
            {match.name}
          </a>
          {!isManualSearch && (
            <Badge variant={match.confidence >= 90 ? "default" : "outline"} className="text-xs">
              {match.confidence}%
            </Badge>
          )}
        </div>
        <div className="flex gap-1 mt-1 flex-wrap">
          {isManualSearch && (
            <Badge variant="secondary" className="text-purple-600 text-xs">
              Manual search
            </Badge>
          )}
          {match.name_match.match_type === "exact" && (
            <Badge variant="secondary" className="text-green-600 text-xs">
              Name match
            </Badge>
          )}
          {match.stashapp_exists && (
            <Badge variant="outline" className="text-blue-600 text-xs">
              In Stashapp
            </Badge>
          )}
        </div>
      </div>

      {/* Large Match Image */}
      {match.stashdb_image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={match.stashdb_image_url}
          alt={match.name}
          className="w-full aspect-[3/4] rounded-lg object-cover"
        />
      ) : (
        <div className="w-full aspect-[3/4] flex items-center justify-center rounded-lg bg-muted">
          <span className="text-sm text-muted-foreground">No image</span>
        </div>
      )}

      {/* Aliases */}
      {match.aliases.length > 0 && (
        <div className="mt-2 text-xs text-muted-foreground">
          <span className="font-medium">Aliases:</span>{" "}
          {match.aliases.join(", ")}
        </div>
      )}

      {/* Selection indicator */}
      {isSelected && (
        <div className="mt-2 pt-2 border-t text-xs text-primary font-medium text-center">
          Selected
        </div>
      )}
    </div>
  );
}

// Card for performers with no face matches or no image - allows manual search
interface NoMatchPerformerCardProps {
  result: PerformerMatchResult;
  selection: MatchSelection | null | undefined;
  onSelectionChange: (selection: MatchSelection | null) => void;
}

function NoMatchPerformerCard({ result, selection, onSelectionChange }: NoMatchPerformerCardProps) {
  const isSelected = selection !== null && selection !== undefined;
  const selectedMatch = selection?.match;

  const handleSearchSelect = (match: EnrichedMatch) => {
    onSelectionChange({
      performerUuid: result.performer_uuid,
      match,
    });
  };

  return (
    <div className={`rounded-lg border p-4 ${isSelected ? "border-primary bg-primary/5" : ""}`}>
      <div className="flex gap-6">
        {/* Left: Performer info */}
        <div className="w-64 flex-shrink-0">
          <div className="flex items-center gap-2 mb-3">
            <Checkbox
              checked={isSelected}
              onCheckedChange={(checked) => {
                if (!checked) {
                  onSelectionChange(null);
                }
              }}
              disabled={!isSelected}
            />
            <a
              href={`/performers/${result.performer_uuid}`}
              className="text-lg font-semibold hover:underline text-primary"
            >
              {result.performer_name}
            </a>
            <Badge variant="secondary">{result.bin.replace("_", " ")}</Badge>
          </div>
          {result.performer_image_available ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`${API_BASE_URL}/performers/${result.performer_uuid}/image`}
              alt={result.performer_name}
              className="w-full aspect-[3/4] rounded-lg object-cover"
            />
          ) : (
            <div className="w-full aspect-[3/4] flex items-center justify-center rounded-lg bg-muted">
              <span className="text-sm text-muted-foreground">No image</span>
            </div>
          )}
          <PerformerSearchDialog
            performerName={result.performer_name}
            onSelect={handleSearchSelect}
            trigger={
              <Button variant="outline" size="sm" className="mt-2 w-full">
                Search StashDB/Stashapp
              </Button>
            }
          />
        </div>

        {/* Right: Selected match (if any) */}
        <div className="flex-1">
          {selectedMatch ? (
            <div className="p-4 border rounded-lg bg-primary/5">
              <div className="flex items-center gap-2 mb-2">
                <span className="font-medium">Selected:</span>
                <a
                  href={`https://stashdb.org/performers/${selectedMatch.stashdb_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  {selectedMatch.name}
                </a>
                {selectedMatch.stashapp_exists && (
                  <Badge variant="outline" className="text-blue-600 text-xs">
                    In Stashapp
                  </Badge>
                )}
              </div>
              {selectedMatch.stashdb_image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={selectedMatch.stashdb_image_url}
                  alt={selectedMatch.name}
                  className="w-32 h-40 rounded object-cover"
                />
              )}
              {selectedMatch.aliases.length > 0 && (
                <div className="mt-2 text-xs text-muted-foreground">
                  Aliases: {selectedMatch.aliases.join(", ")}
                </div>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="mt-2"
                onClick={() => onSelectionChange(null)}
              >
                Clear selection
              </Button>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Use the search button to find a match
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Search Dialog for finding performers in StashDB/Stashapp
interface PerformerSearchDialogProps {
  performerName: string;
  onSelect: (match: EnrichedMatch) => void;
  trigger: React.ReactNode;
}

function PerformerSearchDialog({
  performerName,
  onSelect,
  trigger,
}: PerformerSearchDialogProps) {
  const [open, setOpen] = useState(false);
  const [searchSource, setSearchSource] = useState<"stashdb" | "stashapp">("stashdb");
  const [searchQuery, setSearchQuery] = useState(performerName);
  const [searching, setSearching] = useState(false);
  const [stashdbResults, setStashdbResults] = useState<StashDBSearchResult[]>([]);
  const [stashappResults, setStashappResults] = useState<StashappSearchResult[]>([]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      if (searchSource === "stashdb") {
        const results = await api.performers.searchStashDB(searchQuery, 10);
        setStashdbResults(results);
        setStashappResults([]);
      } else {
        const results = await api.performers.searchStashapp(searchQuery, 10);
        setStashappResults(results);
        setStashdbResults([]);
      }
    } finally {
      setSearching(false);
    }
  };

  const handleSelectStashDB = (result: StashDBSearchResult) => {
    const match: EnrichedMatch = {
      name: result.name,
      confidence: 0, // Manual search, no confidence score
      stashdb_id: result.id,
      stashdb_image_url: result.image_url,
      aliases: result.aliases,
      country: result.country,
      stashapp_id: null,
      stashapp_exists: false,
      name_match: { match_type: "manual", matched_name: null, score: 0 },
    };
    onSelect(match);
    setOpen(false);
  };

  const handleSelectStashapp = (result: StashappSearchResult) => {
    const match: EnrichedMatch = {
      name: result.name,
      confidence: 0,
      stashdb_id: result.stashdb_id || "",
      stashdb_image_url: null,
      aliases: result.aliases,
      country: null,
      stashapp_id: result.id,
      stashapp_exists: true,
      name_match: { match_type: "manual", matched_name: null, score: 0 },
    };
    onSelect(match);
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Search for {performerName}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex gap-2">
            <Select
              value={searchSource}
              onValueChange={(v) => setSearchSource(v as "stashdb" | "stashapp")}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="stashdb">StashDB</SelectItem>
                <SelectItem value="stashapp">Stashapp</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Search performer name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={searching}>
              {searching ? "Searching..." : "Search"}
            </Button>
          </div>

          {/* StashDB Results */}
          {stashdbResults.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">StashDB Results</h4>
              <div className="grid grid-cols-2 gap-2">
                {stashdbResults.map((result) => (
                  <div
                    key={result.id}
                    className="flex gap-3 p-2 border rounded-lg cursor-pointer hover:bg-muted/50"
                    onClick={() => handleSelectStashDB(result)}
                  >
                    {result.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={result.image_url}
                        alt={result.name}
                        className="w-16 h-20 rounded object-cover flex-shrink-0"
                      />
                    ) : (
                      <div className="w-16 h-20 rounded bg-muted flex items-center justify-center flex-shrink-0">
                        <span className="text-xs text-muted-foreground">?</span>
                      </div>
                    )}
                    <div className="min-w-0">
                      <a
                        href={`https://stashdb.org/performers/${result.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-sm hover:underline text-primary block truncate"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {result.name}
                      </a>
                      {result.disambiguation && (
                        <div className="text-xs text-muted-foreground truncate">
                          {result.disambiguation}
                        </div>
                      )}
                      {result.aliases.length > 0 && (
                        <div className="text-xs text-muted-foreground truncate">
                          {result.aliases.slice(0, 3).join(", ")}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stashapp Results */}
          {stashappResults.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Stashapp Results</h4>
              <div className="grid grid-cols-2 gap-2">
                {stashappResults.map((result) => (
                  <div
                    key={result.id}
                    className="flex gap-3 p-2 border rounded-lg cursor-pointer hover:bg-muted/50"
                    onClick={() => handleSelectStashapp(result)}
                  >
                    <div className="w-16 h-20 rounded bg-muted flex items-center justify-center flex-shrink-0">
                      <span className="text-xs text-muted-foreground">#{result.id}</span>
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-sm truncate">{result.name}</div>
                      {result.disambiguation && (
                        <div className="text-xs text-muted-foreground truncate">
                          {result.disambiguation}
                        </div>
                      )}
                      {result.stashdb_id && (
                        <Badge variant="outline" className="text-xs mt-1">
                          Has StashDB
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* No results message */}
          {!searching &&
            stashdbResults.length === 0 &&
            stashappResults.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                Enter a search query and click Search
              </div>
            )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
