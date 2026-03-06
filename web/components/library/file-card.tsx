"use client";

import { useTranslations } from "next-intl";
import {
  ImageIcon,
  FileText,
  Presentation,
  Code,
  Sheet,
  File,
  Download,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePreviewStore } from "@/lib/stores/preview-store";
import { formatRelativeTime } from "@/lib/utils/relative-time";
import type { LibraryFile } from "@/lib/api/library";

function getFileIcon(contentType: string) {
  if (contentType.startsWith("image/")) return { Icon: ImageIcon, accent: "bg-accent-cyan/10 text-accent-cyan" };
  if (
    contentType === "application/pdf" ||
    contentType === "text/plain" ||
    contentType === "text/markdown" ||
    contentType.includes("wordprocessingml")
  )
    return { Icon: FileText, accent: "bg-accent-cyan/10 text-accent-cyan" };
  if (contentType.includes("presentationml"))
    return { Icon: Presentation, accent: "bg-accent-cyan/10 text-accent-cyan" };
  if (
    contentType === "text/x-python" ||
    contentType === "application/javascript" ||
    contentType === "application/typescript" ||
    contentType === "text/html" ||
    contentType === "text/css" ||
    contentType === "application/json"
  )
    return { Icon: Code, accent: "bg-accent-cyan/10 text-accent-cyan" };
  if (contentType === "text/csv" || contentType.includes("spreadsheetml"))
    return { Icon: Sheet, accent: "bg-accent-cyan/10 text-accent-cyan" };
  return { Icon: File, accent: "bg-accent-cyan/10 text-accent-cyan" };
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

interface FileCardProps {
  file: LibraryFile;
  index?: number;
  onDelete?: (file: LibraryFile) => void;
}

export function FileCard({ file, index = 0, onDelete }: FileCardProps) {
  const t = useTranslations("library");
  const openPreview = usePreviewStore((s) => s.openPreview);
  const { Icon, accent } = getFileIcon(file.content_type);

  const handleClick = () => {
    openPreview({
      id: file.id,
      filename: file.filename,
      contentType: file.content_type,
      fileSize: file.file_size,
      previewUrl: file.preview_url,
      status: "uploaded",
    });
  };

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (file.preview_url) {
      const a = document.createElement("a");
      a.href = file.preview_url;
      a.download = file.filename;
      a.click();
    }
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete?.(file);
  };

  return (
    <div
      className={cn(
        "group relative border border-border/50 rounded-xl p-4",
        "hover:border-border hover:shadow-sm",
        "transition-all duration-200",
        "cursor-pointer",
        "animate-fade-in"
      )}
      style={{ animationDelay: `${index * 40}ms`, animationFillMode: "backwards" }}
      onClick={handleClick}
    >
      {/* Header: icon + filename */}
      <div className="flex items-start gap-3">
        <div className={cn("shrink-0 p-2 rounded-lg", accent)}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm text-foreground truncate">
            {file.filename}
          </h4>
          <p className="text-xs text-muted-foreground mt-1">
            {formatFileSize(file.file_size)}
          </p>
        </div>
      </div>

      {/* Footer: date + download */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/30">
        <span className="text-xs text-muted-foreground">
          {formatRelativeTime(file.created_at, t as (key: string, params?: Record<string, number>) => string)}
        </span>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
          <button
            onClick={handleDownload}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs",
              "text-muted-foreground hover:text-foreground hover:bg-secondary",
              "transition-colors duration-150 cursor-pointer"
            )}
          >
            <Download className="w-3 h-3" />
            {t("download")}
          </button>
          <button
            onClick={handleDelete}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs",
              "text-muted-foreground hover:text-destructive hover:bg-destructive/10",
              "transition-colors duration-150 cursor-pointer"
            )}
          >
            <Trash2 className="w-3 h-3" />
            {t("delete")}
          </button>
        </div>
      </div>
    </div>
  );
}
