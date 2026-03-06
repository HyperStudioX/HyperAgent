"use client";

import { useEffect, useState, useDeferredValue, useCallback } from "react";
import { useTranslations } from "next-intl";
import {
  Search,
  Loader2,
  AlertCircle,
  Plug,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PresetCard } from "./preset-card";
import { ServerCard } from "./server-card";
import { AddServerDialog } from "./add-server-dialog";
import {
  listServers,
  listPresets,
  listTools,
  addServer,
  removeServer,
  reconnectServer,
  disconnectServer,
  enablePreset,
} from "@/lib/api/mcp";
import type {
  MCPServer,
  MCPPreset,
  MCPTool,
  AddServerRequest,
} from "@/lib/types/mcp";

export function IntegrationBrowser() {
  const t = useTranslations("integrations");
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [presets, setPresets] = useState<MCPPreset[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const deferredSearch = useDeferredValue(searchQuery);

  const refreshData = useCallback(async () => {
    try {
      setError(null);
      const [serverData, presetData, toolData] = await Promise.all([
        listServers(),
        listPresets(),
        listTools(),
      ]);
      setServers(serverData);
      setPresets(presetData);
      setTools(toolData);
    } catch (err) {
      console.error("Failed to load integrations:", err);
      setError(t("loadError"));
    }
  }, [t]);

  useEffect(() => {
    refreshData().finally(() => setLoading(false));
  }, [refreshData]);

  const connectedServerNames = new Set(
    servers.filter((s) => s.connected).map((s) => s.name)
  );

  // Filter presets and servers by search
  const filteredPresets = presets.filter(
    (p) =>
      deferredSearch === "" ||
      p.name.toLowerCase().includes(deferredSearch.toLowerCase()) ||
      p.description.toLowerCase().includes(deferredSearch.toLowerCase())
  );

  const filteredServers = servers.filter(
    (s) =>
      deferredSearch === "" ||
      s.name.toLowerCase().includes(deferredSearch.toLowerCase()) ||
      s.description.toLowerCase().includes(deferredSearch.toLowerCase())
  );

  async function handleEnablePreset(name: string) {
    await enablePreset(name);
    await refreshData();
  }

  async function handleAddServer(request: AddServerRequest) {
    await addServer(request);
    await refreshData();
  }

  async function handleReconnect(name: string) {
    await reconnectServer(name);
    await refreshData();
  }

  async function handleDisconnect(name: string) {
    await disconnectServer(name);
    await refreshData();
  }

  async function handleRemove(name: string) {
    await removeServer(name);
    await refreshData();
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">{t("loading")}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <div className="w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
          <AlertCircle className="w-5 h-5 text-destructive" />
        </div>
        <p className="text-sm text-muted-foreground">{error}</p>
        <button
          onClick={async () => {
            setLoading(true);
            try {
              await refreshData();
            } finally {
              setLoading(false);
            }
          }}
          className="text-sm text-foreground font-medium underline underline-offset-4 hover:text-foreground/80 cursor-pointer"
        >
          {t("retry")}
        </button>
      </div>
    );
  }

  const hasNoResults =
    deferredSearch !== "" &&
    filteredPresets.length === 0 &&
    filteredServers.length === 0;

  return (
    <div className="space-y-8">
      {/* Search + Add button */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <Input
            placeholder={t("search")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <Button
          size="sm"
          className="h-9 gap-1.5 cursor-pointer"
          onClick={() => setAddDialogOpen(true)}
        >
          <Plus className="w-3.5 h-3.5" />
          {t("addServer")}
        </Button>
      </div>

      {hasNoResults ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2">
          <Search className="w-5 h-5 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">{t("noResults")}</p>
        </div>
      ) : (
        <>
          {/* Presets section */}
          {filteredPresets.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide">
                  {t("presets")}
                </h3>
                <span className="text-xs text-muted-foreground tabular-nums">
                  ({filteredPresets.length})
                </span>
              </div>
              <p className="text-xs text-muted-foreground mb-4">
                {t("presetsDescription")}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {filteredPresets.map((preset, idx) => {
                  const matchedServer = servers.find(
                    (s) => s.name === preset.name
                  );
                  return (
                    <PresetCard
                      key={preset.name}
                      preset={preset}
                      isConnected={connectedServerNames.has(preset.name)}
                      connectedToolCount={matchedServer?.tool_count}
                      onEnable={handleEnablePreset}
                      index={idx}
                    />
                  );
                })}
              </div>
            </section>
          )}

          {/* Connected servers section */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide">
                {t("connectedServers")}
              </h3>
              <span className="text-xs text-muted-foreground tabular-nums">
                ({filteredServers.length})
              </span>
            </div>

            {filteredServers.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 border border-dashed border-border/50 rounded-xl">
                <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center">
                  <Plug className="w-5 h-5 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">{t("noServers")}</p>
                <p className="text-xs text-muted-foreground/70">
                  {t("noServersDescription")}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {filteredServers.map((server, idx) => (
                  <ServerCard
                    key={server.name}
                    server={server}
                    tools={tools}
                    onReconnect={handleReconnect}
                    onDisconnect={handleDisconnect}
                    onRemove={handleRemove}
                    index={idx}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {/* Add Server Dialog */}
      <AddServerDialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        onAdd={handleAddServer}
      />
    </div>
  );
}
