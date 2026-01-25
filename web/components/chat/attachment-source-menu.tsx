"use client";

import React, { useRef } from "react";
import { Upload, Cloud, HardDrive, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { ALL_ACCEPTED_FILES } from "@/lib/types";

interface AttachmentSource {
    id: string;
    nameKey: string;
    descKey: string;
    icon: React.ReactNode;
    available: boolean;
}

const ATTACHMENT_SOURCES: AttachmentSource[] = [
    {
        id: "local",
        nameKey: "sources.local.name",
        descKey: "sources.local.description",
        icon: <Upload className="w-5 h-5" />,
        available: true,
    },
    {
        id: "google-drive",
        nameKey: "sources.googleDrive.name",
        descKey: "sources.googleDrive.description",
        icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12.01 1.485L2.253 17.973h6.503l3.258-5.638L8.756 6.37l3.254-4.885zM8.755 19.39L2.253 19.39 12.01 22.516 15.266 19.39zM21.757 17.973L15.254 6.371 12 12.009l3.257 5.638h6.5z" />
            </svg>
        ),
        available: true,
    },
    {
        id: "onedrive",
        nameKey: "sources.oneDrive.name",
        descKey: "sources.oneDrive.description",
        icon: <Cloud className="w-5 h-5" />,
        available: false, // Coming soon
    },
    {
        id: "dropbox",
        nameKey: "sources.dropbox.name",
        descKey: "sources.dropbox.description",
        icon: <HardDrive className="w-5 h-5" />,
        available: false, // Coming soon
    },
];

interface AttachmentSourceMenuProps {
    isOpen: boolean;
    onClose: () => void;
    onSourceSelect: (sourceId: string, files?: File[]) => void;
    position?: { top: number; left: number };
}

export function AttachmentSourceMenu({
    isOpen,
    onClose,
    onSourceSelect,
    position,
}: AttachmentSourceMenuProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const t = useTranslations("chat.attachments");

    const handleSourceClick = (sourceId: string) => {
        if (sourceId === "local") {
            // Trigger file input for local uploads
            fileInputRef.current?.click();
        } else if (sourceId === "google-drive") {
            // Open Google Drive picker (to be implemented)
            onSourceSelect(sourceId);
            onClose();
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);
        if (files.length > 0) {
            onSourceSelect("local", files);
            onClose();
        }
        // Reset input
        e.target.value = "";
    };

    if (!isOpen) return null;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 z-40"
                onClick={onClose}
            />

            {/* Menu */}
            <div
                className={cn(
                    "fixed z-50 w-[320px]",
                    "bg-card border border-border rounded-xl shadow-lg",
                    "animate-in fade-in slide-in-from-bottom-2 duration-200"
                )}
                style={
                    position
                        ? { top: position.top, left: position.left }
                        : { bottom: "5rem", left: "2rem" }
                }
            >
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                    <h3 className="font-semibold text-sm">{t("title")}</h3>
                    <button
                        onClick={onClose}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* Sources list */}
                <div className="p-2">
                    {ATTACHMENT_SOURCES.map((source) => (
                        <button
                            key={source.id}
                            onClick={() =>
                                source.available && handleSourceClick(source.id)
                            }
                            disabled={!source.available}
                            className={cn(
                                "w-full flex items-start gap-3 px-3 py-2.5 rounded-lg",
                                "text-left transition-colors",
                                source.available
                                    ? "hover:bg-secondary/80 cursor-pointer"
                                    : "opacity-50 cursor-not-allowed"
                            )}
                        >
                            <div
                                className={cn(
                                    "flex items-center justify-center w-10 h-10 rounded-lg",
                                    "bg-secondary/50"
                                )}
                            >
                                {source.icon}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <p className="font-medium text-sm">{t(source.nameKey)}</p>
                                    {!source.available && (
                                        <span className="text-xs text-muted-foreground px-1.5 py-0.5 rounded bg-secondary">
                                            {t("soon")}
                                        </span>
                                    )}
                                </div>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    {t(source.descKey)}
                                </p>
                            </div>
                        </button>
                    ))}
                </div>

                {/* Hidden file input for local uploads */}
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept={ALL_ACCEPTED_FILES}
                    onChange={handleFileChange}
                    className="hidden"
                />
            </div>
        </>
    );
}
