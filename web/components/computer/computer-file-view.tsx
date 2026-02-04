"use client";

import React from "react";
import { Folder, File, ChevronRight, FolderOpen } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { FileEntry } from "@/lib/stores/computer-store";

interface ComputerFileViewProps {
    currentPath: string;
    files: FileEntry[];
    selectedFile: string | null;
    onFileSelect: (file: string | null) => void;
    onPathChange: (path: string) => void;
    className?: string;
}

function Breadcrumb({
    path,
    onNavigate
}: {
    path: string;
    onNavigate: (path: string) => void;
}) {
    const parts = path.split("/").filter(Boolean);

    return (
        <div className="flex items-center gap-1 px-3 py-2 text-xs border-b border-border/30 bg-secondary/30 overflow-x-auto">
            <button
                onClick={() => onNavigate("/")}
                className="text-muted-foreground hover:text-foreground transition-colors"
            >
                /
            </button>
            {parts.map((part, index) => {
                const fullPath = "/" + parts.slice(0, index + 1).join("/");
                const isLast = index === parts.length - 1;
                return (
                    <React.Fragment key={fullPath}>
                        <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
                        <button
                            onClick={() => !isLast && onNavigate(fullPath)}
                            className={cn(
                                "transition-colors truncate max-w-[100px]",
                                isLast
                                    ? "text-foreground font-medium"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                            disabled={isLast}
                        >
                            {part}
                        </button>
                    </React.Fragment>
                );
            })}
        </div>
    );
}

function FileItem({
    entry,
    isSelected,
    onClick,
    onDoubleClick
}: {
    entry: FileEntry;
    isSelected: boolean;
    onClick: () => void;
    onDoubleClick: () => void;
}) {
    const isDir = entry.type === "directory";
    const Icon = isDir ? (isSelected ? FolderOpen : Folder) : File;

    // Format file size
    const formatSize = (bytes?: number) => {
        if (bytes === undefined) return "";
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <button
            onClick={onClick}
            onDoubleClick={onDoubleClick}
            className={cn(
                "w-full flex items-center gap-2 px-3 py-1.5 text-left",
                "hover:bg-secondary/60 transition-colors",
                isSelected && "bg-secondary"
            )}
        >
            <Icon className={cn(
                "w-4 h-4 flex-shrink-0",
                isDir ? "text-amber-500" : "text-muted-foreground"
            )} />
            <span className="flex-1 text-sm truncate">{entry.name}</span>
            {!isDir && entry.size !== undefined && (
                <span className="text-xs text-muted-foreground/60">
                    {formatSize(entry.size)}
                </span>
            )}
        </button>
    );
}

export function ComputerFileView({
    currentPath,
    files,
    selectedFile,
    onFileSelect,
    onPathChange,
    className,
}: ComputerFileViewProps) {
    const t = useTranslations("computer");

    // Sort files: directories first, then alphabetically
    const sortedFiles = [...files].sort((a, b) => {
        if (a.type !== b.type) {
            return a.type === "directory" ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
    });

    const handleDoubleClick = (entry: FileEntry) => {
        if (entry.type === "directory") {
            onPathChange(entry.path);
        }
    };

    const handleParentClick = () => {
        const parentPath = currentPath.split("/").slice(0, -1).join("/") || "/";
        onPathChange(parentPath);
    };

    return (
        <div className={cn("flex-1 flex flex-col overflow-hidden bg-background", className)}>
            {/* Breadcrumb navigation */}
            <Breadcrumb path={currentPath} onNavigate={onPathChange} />

            {/* File list */}
            <ScrollArea className="flex-1">
                <div className="py-1">
                    {/* Parent directory */}
                    {currentPath !== "/" && (
                        <button
                            onClick={handleParentClick}
                            className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-secondary/60 transition-colors"
                        >
                            <Folder className="w-4 h-4 text-amber-500" />
                            <span className="text-sm text-muted-foreground">..</span>
                        </button>
                    )}

                    {/* Files */}
                    {sortedFiles.length === 0 ? (
                        <div className="px-3 py-8 text-center text-sm text-muted-foreground/60">
                            {t("emptyDirectory")}
                        </div>
                    ) : (
                        sortedFiles.map((entry) => (
                            <FileItem
                                key={entry.path}
                                entry={entry}
                                isSelected={selectedFile === entry.path}
                                onClick={() => onFileSelect(entry.path)}
                                onDoubleClick={() => handleDoubleClick(entry)}
                            />
                        ))
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}
