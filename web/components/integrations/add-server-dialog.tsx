"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { AddServerRequest } from "@/lib/types/mcp";

interface AddServerDialogProps {
  open: boolean;
  onClose: () => void;
  onAdd: (request: AddServerRequest) => Promise<void>;
}

type Transport = "stdio" | "sse";

export function AddServerDialog({ open, onClose, onAdd }: AddServerDialogProps) {
  const t = useTranslations("integrations");
  const [transport, setTransport] = useState<Transport>("stdio");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [envVars, setEnvVars] = useState("");
  const [url, setUrl] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  function resetForm() {
    setTransport("stdio");
    setName("");
    setDescription("");
    setCommand("");
    setArgs("");
    setEnvVars("");
    setUrl("");
    setAuthToken("");
    setError(null);
  }

  function handleClose() {
    resetForm();
    onClose();
  }

  function validate(): string | null {
    if (!name.trim()) return t("nameRequired");
    if (transport === "stdio" && !command.trim()) return t("commandRequired");
    if (transport === "sse" && !url.trim()) return t("urlRequired");
    return null;
  }

  function parseEnvVars(raw: string): Record<string, string> {
    const env: Record<string, string> = {};
    for (const line of raw.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const eqIndex = trimmed.indexOf("=");
      if (eqIndex > 0) {
        env[trimmed.slice(0, eqIndex).trim()] = trimmed.slice(eqIndex + 1).trim();
      }
    }
    return env;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setAdding(true);
    try {
      const request: AddServerRequest = {
        name: name.trim(),
        transport,
        description: description.trim() || undefined,
        ...(transport === "stdio"
          ? {
              command: command.trim(),
              args: args.trim()
                ? args.split(",").map((a) => a.trim()).filter(Boolean)
                : undefined,
              env: envVars.trim() ? parseEnvVars(envVars) : undefined,
            }
          : {
              url: url.trim(),
              auth_token: authToken.trim() || undefined,
            }),
      };
      await onAdd(request);
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add server");
    } finally {
      setAdding(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div className="relative bg-background border border-border rounded-xl shadow-lg w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border/50">
          <h2 className="text-base font-semibold">{t("addServerTitle")}</h2>
          <button
            onClick={handleClose}
            className="p-1 rounded-md hover:bg-secondary transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Transport selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">
              {t("transport")}
            </label>
            <div className="flex gap-2">
              {(["stdio", "sse"] as const).map((tp) => (
                <button
                  key={tp}
                  type="button"
                  onClick={() => setTransport(tp)}
                  className={cn(
                    "flex-1 px-3 py-2 rounded-lg text-sm font-medium cursor-pointer",
                    "transition-colors duration-150",
                    transport === tp
                      ? "bg-foreground text-background"
                      : "bg-secondary text-muted-foreground hover:text-foreground"
                  )}
                >
                  {t(tp)}
                </button>
              ))}
            </div>
          </div>

          {/* Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">
              {t("name")}
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("namePlaceholder")}
              className="h-9"
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">
              {t("description")}
            </label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("descriptionPlaceholder")}
              className="h-9"
            />
          </div>

          {/* Transport-specific fields */}
          {transport === "stdio" ? (
            <>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  {t("command")}
                </label>
                <Input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder={t("commandPlaceholder")}
                  className="h-9"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  {t("args")}
                </label>
                <Input
                  value={args}
                  onChange={(e) => setArgs(e.target.value)}
                  placeholder={t("argsPlaceholder")}
                  className="h-9"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  {t("envVars")}
                </label>
                <textarea
                  value={envVars}
                  onChange={(e) => setEnvVars(e.target.value)}
                  placeholder={t("envVarsPlaceholder")}
                  rows={3}
                  className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
                />
              </div>
            </>
          ) : (
            <>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  {t("url")}
                </label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder={t("urlPlaceholder")}
                  className="h-9"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  {t("authToken")}
                </label>
                <Input
                  type="password"
                  value={authToken}
                  onChange={(e) => setAuthToken(e.target.value)}
                  placeholder={t("authTokenPlaceholder")}
                  className="h-9"
                />
              </div>
            </>
          )}

          {/* Error */}
          {error && (
            <p className="text-xs text-destructive">{error}</p>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleClose}
              className="cursor-pointer"
            >
              {t("cancel")}
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={adding}
              className="cursor-pointer"
            >
              {adding ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                  {t("adding")}
                </>
              ) : (
                t("add")
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
