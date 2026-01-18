"use client";

import React from "react";
import {
  X,
  FileText,
  FileSpreadsheet,
  FileCode,
  File,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { FileAttachment } from "@/lib/types";

interface AttachmentPreviewProps {
  attachments: FileAttachment[];
  onRemove: (id: string) => void;
  className?: string;
}

function getFileIcon(contentType: string) {
  // File type color coding: Blue (images), Amber (code), Rose (data), Cyan (docs)
  if (contentType.startsWith("image/")) return null; // Will show image preview
  if (
    contentType.includes("pdf") ||
    contentType.includes("word") ||
    contentType.includes("document")
  ) {
    return <FileText className="w-6 h-6 text-accent-cyan" />;
  }
  if (
    contentType.includes("sheet") ||
    contentType.includes("excel") ||
    contentType === "text/csv"
  ) {
    return <FileSpreadsheet className="w-6 h-6 text-accent-rose" />;
  }
  if (
    contentType.includes("javascript") ||
    contentType.includes("python") ||
    contentType.includes("json") ||
    contentType.includes("typescript")
  ) {
    return <FileCode className="w-6 h-6 text-accent-amber" />;
  }
  return <File className="w-6 h-6 text-muted-foreground" />;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AttachmentPreview({
  attachments,
  onRemove,
  className,
}: AttachmentPreviewProps) {
  if (attachments.length === 0) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap gap-2 p-3 border-b border-border/50",
        className
      )}
    >
      {attachments.map((attachment) => {
        const isImage = attachment.contentType.startsWith("image/");
        const icon = getFileIcon(attachment.contentType);
        const isUploading = attachment.status === "uploading";
        const hasError = attachment.status === "error";

        return (
          <div
            key={attachment.id}
            className={cn(
              "relative group",
              "flex items-center gap-2",
              "px-3 py-2 rounded-lg",
              "bg-secondary/50 border border-border",
              hasError && "border-destructive/50 bg-destructive/5"
            )}
          >
            {/* File icon or image preview */}
            {isImage && attachment.previewUrl ? (
              <div className="w-8 h-8 relative rounded overflow-hidden">
                <img
                  src={attachment.previewUrl}
                  alt={attachment.filename}
                  className="w-full h-full object-cover"
                />
              </div>
            ) : (
              <div className="w-8 h-8 flex items-center justify-center text-muted-foreground">
                {icon}
              </div>
            )}

            {/* File info */}
            <div className="flex flex-col min-w-0 max-w-[150px]">
              <span className="text-sm font-medium truncate">
                {attachment.filename}
              </span>
              <span className="text-xs text-muted-foreground">
                {formatFileSize(attachment.fileSize)}
              </span>
            </div>

            {/* Upload progress / status */}
            {isUploading && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <Loader2 className="w-3 h-3 animate-spin" />
                {attachment.uploadProgress !== undefined && (
                  <span className="text-xs">{attachment.uploadProgress}%</span>
                )}
              </div>
            )}

            {/* Error message */}
            {hasError && attachment.error && (
              <span className="text-xs text-destructive">{attachment.error}</span>
            )}

            {/* Remove button */}
            <button
              onClick={() => onRemove(attachment.id)}
              className={cn(
                "absolute -top-1.5 -right-1.5",
                "w-5 h-5 rounded-full",
                "bg-foreground text-background",
                "flex items-center justify-center",
                "opacity-0 group-hover:opacity-100",
                "transition-opacity",
                "hover:bg-foreground/80"
              )}
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
