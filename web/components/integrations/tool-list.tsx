"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, ChevronRight, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MCPTool } from "@/lib/types/mcp";

interface ToolListProps {
  tools: MCPTool[];
}

const RISK_COLORS: Record<string, string> = {
  low: "bg-success/10 text-success",
  medium: "bg-warning/10 text-warning",
  high: "bg-destructive/10 text-destructive",
};

export function ToolList({ tools }: ToolListProps) {
  const t = useTranslations("integrations");
  const [expandedTool, setExpandedTool] = useState<string | null>(null);

  if (tools.length === 0) return null;

  return (
    <div className="space-y-1">
      {tools.map((tool) => {
        const isExpanded = expandedTool === tool.name;
        return (
          <div key={tool.name} className="rounded-lg border border-border/30">
            <button
              onClick={() => setExpandedTool(isExpanded ? null : tool.name)}
              className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-secondary/50 rounded-lg transition-colors cursor-pointer"
            >
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              )}
              <span className="text-xs font-medium text-foreground truncate">
                {tool.name}
              </span>
              <span className="text-xs text-muted-foreground truncate flex-1 min-w-0">
                {tool.description}
              </span>
              <span
                className={cn(
                  "shrink-0 inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded",
                  RISK_COLORS[tool.policy.risk_level] || RISK_COLORS.low
                )}
              >
                <Shield className="w-2.5 h-2.5" />
                {tool.policy.risk_level}
              </span>
            </button>

            {isExpanded && tool.input_schema && (
              <div className="px-3 pb-3">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                  {t("inputSchema")}
                </div>
                <pre className="text-xs text-muted-foreground bg-secondary/50 rounded-md p-2 overflow-x-auto max-h-48">
                  {JSON.stringify(tool.input_schema, null, 2)}
                </pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
