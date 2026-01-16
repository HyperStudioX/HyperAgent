"use client";

import React, { useState, useRef, useEffect } from "react";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { AttachmentSourceMenu } from "./attachment-source-menu";
import { SUPPORTED_FILE_TYPES } from "@/lib/types";

interface AttachmentButtonProps {
    onFilesSelected: (files: File[]) => void;
    onSourceSelect?: (sourceId: string) => void;
    disabled?: boolean;
    className?: string;
}

export function AttachmentButton({
    onFilesSelected,
    onSourceSelect,
    disabled = false,
    className,
}: AttachmentButtonProps) {
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [menuPosition, setMenuPosition] = useState<{ top: number; left: number }>();
    const buttonRef = useRef<HTMLButtonElement>(null);
    const t = useTranslations("chat.attachments");

    const handleClick = () => {
        if (buttonRef.current) {
            const rect = buttonRef.current.getBoundingClientRect();
            setMenuPosition({
                top: rect.top - 320, // Menu height is ~320px
                left: rect.left,
            });
        }
        setIsMenuOpen(true);
    };

    const validateFile = (file: File): string | null => {
        // Check if file type is supported
        const allMimeTypes = Object.values(SUPPORTED_FILE_TYPES).flatMap(
            (t) => t.mimeTypes
        );
        if (!allMimeTypes.includes(file.type)) {
            return t("validation.unsupportedType", { type: file.type });
        }

        // Check file size
        const typeConfig = Object.values(SUPPORTED_FILE_TYPES).find((t) =>
            t.mimeTypes.includes(file.type)
        );
        if (typeConfig && file.size > typeConfig.maxSize) {
            return t("validation.maxSize", { size: typeConfig.maxSize / (1024 * 1024) });
        }

        return null;
    };

    const handleSourceSelect = (sourceId: string, files?: File[]) => {
        if (sourceId === "local" && files) {
            const validFiles: File[] = [];
            const errors: string[] = [];

            files.forEach((file) => {
                const error = validateFile(file);
                if (error) {
                    errors.push(`${file.name}: ${error}`);
                } else {
                    validFiles.push(file);
                }
            });

            if (errors.length > 0) {
                console.error("File validation errors:", errors);
            }

            if (validFiles.length > 0) {
                onFilesSelected(validFiles);
            }
        } else {
            // Handle other sources (Google Drive, etc.)
            onSourceSelect?.(sourceId);
        }
    };

    return (
        <>
            <button
                ref={buttonRef}
                type="button"
                onClick={handleClick}
                disabled={disabled}
                className={cn(
                    "flex items-center justify-center",
                    "w-9 h-9 rounded-lg",
                    "transition-colors",
                    "text-muted-foreground hover:text-foreground",
                    "hover:bg-secondary/80",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                    className
                )}
                title={t("title")}
            >
                <Plus className="w-5 h-5" />
            </button>

            <AttachmentSourceMenu
                isOpen={isMenuOpen}
                onClose={() => setIsMenuOpen(false)}
                onSourceSelect={handleSourceSelect}
                position={menuPosition}
            />
        </>
    );
}

// Export with old name for backward compatibility
export { AttachmentButton as FileUploadButton };
