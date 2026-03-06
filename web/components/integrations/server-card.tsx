"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Server,
  RefreshCw,
  Unplug,
  Trash2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Wrench,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ToolList } from "./tool-list";
import type { MCPServer, MCPTool } from "@/lib/types/mcp";

interface ServerCardProps {
  server: MCPServer;
  tools: MCPTool[];
  onReconnect: (name: string) => Promise<void>;
  onDisconnect: (name: string) => Promise<void>;
  onRemove: (name: string) => Promise<void>;
  index?: number;
}

export function ServerCard({
  server,
  tools,
  onReconnect,
  onDisconnect,
  onRemove,
  index = 0,
}: ServerCardProps) {
  const t = useTranslations("integrations");
  const [expanded, setExpanded] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const serverTools = tools.filter((tool) => tool.server === server.name);

  async function handleAction(action: string, fn: (name: string) => Promise<void>) {
    setActionLoading(action);
    try {
      await fn(server.name);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div
      className={cn(
        "border border-border/50 rounded-xl overflow-hidden",
        "transition-all duration-200",
        "hover:border-border hover:shadow-sm",
        "animate-fade-in"
      )}
      style={{ animationDelay: `${index * 40}ms`, animationFillMode: "backwards" }}
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="shrink-0 p-2 rounded-lg bg-secondary">
            <Server className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-sm text-foreground truncate">
                {server.name}
              </h4>
              {/* Connection status dot */}
              <div
                className={cn(
                  "w-2 h-2 rounded-full shrink-0",
                  server.connected ? "bg-success" : "bg-muted-foreground/40"
                )}
                title={server.connected ? t("connected") : t("disconnected")}
              />
            </div>
            {server.description && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                {server.description}
              </p>
            )}
          </div>
        </div>

        {/* Metadata + Actions */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/30">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="uppercase tracking-wider font-medium">
              {server.transport}
            </span>
            <span className="text-border">|</span>
            <span className="flex items-center gap-1">
              <Wrench className="w-2.5 h-2.5" />
              {t("tools", { count: server.tool_count })}
            </span>
          </div>

          <div className="flex items-center gap-1">
            {server.connected ? (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0 cursor-pointer"
                onClick={() => handleAction("disconnect", onDisconnect)}
                disabled={actionLoading !== null}
                title={t("disconnect")}
              >
                {actionLoading === "disconnect" ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Unplug className="w-3.5 h-3.5" />
                )}
              </Button>
            ) : (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0 cursor-pointer"
                onClick={() => handleAction("reconnect", onReconnect)}
                disabled={actionLoading !== null}
                title={t("reconnect")}
              >
                {actionLoading === "reconnect" ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="w-3.5 h-3.5" />
                )}
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0 cursor-pointer text-destructive/70 hover:text-destructive"
              onClick={() => handleAction("remove", onRemove)}
              disabled={actionLoading !== null}
              title={t("remove")}
            >
              {actionLoading === "remove" ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Expandable tool list */}
      {serverTools.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-secondary/50 border-t border-border/30 transition-colors cursor-pointer"
          >
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            {expanded ? t("hideTools") : t("showTools")} ({serverTools.length})
          </button>

          {expanded && (
            <div className="px-4 pb-4">
              <ToolList tools={serverTools} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
