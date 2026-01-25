"use client";

import { FileText, ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FileAttachment } from "@/lib/types";

interface MessageAttachmentsProps {
    attachments: FileAttachment[];
    onAttachmentClick?: (attachment: FileAttachment) => void;
}

export function MessageAttachments({
    attachments,
    onAttachmentClick,
}: MessageAttachmentsProps): JSX.Element | null {
    if (!attachments || attachments.length === 0) {
        return null;
    }

    return (
        <div className="flex flex-wrap gap-2">
            {attachments.map((attachment) => {
                // Handle both camelCase (frontend) and snake_case (backend) formats
                const contentType =
                    attachment.contentType ||
                    (attachment as unknown as { content_type?: string }).content_type ||
                    "";
                const isImage = contentType.startsWith("image/");

                return (
                    <button
                        key={attachment.id}
                        onClick={() => onAttachmentClick?.(attachment)}
                        className={cn(
                            "flex items-center gap-2 px-3 py-2",
                            "rounded-lg",
                            "bg-secondary hover:bg-secondary/80",
                            "border border-border",
                            "transition-colors",
                            "text-sm font-medium"
                        )}
                    >
                        {isImage ? (
                            <ImageIcon className="w-4 h-4 text-primary/70" />
                        ) : (
                            <FileText className="w-4 h-4 text-primary/70" />
                        )}
                        <span className="max-w-[180px] truncate text-foreground/90">
                            {attachment.filename}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}
