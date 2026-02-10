"use client";

import React, { useEffect, useCallback, useMemo, useState } from "react";
import {
    Folder,
    FolderOpen,
    ChevronRight,
    RefreshCw,
    Loader2,
    Search,
    FileText,
    FileCode,
    FileJson,
    FileImage,
    FileType,
    FileSpreadsheet,
    FileCog,
    FileArchive,
    FolderClosed,
    X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useComputerStore, type FileEntry } from "@/lib/stores/computer-store";
import { ComputerFileContent } from "./computer-file-content";

interface ComputerFileViewProps {
    className?: string;
}

// Map file extensions to specific icons and colors
function getFileIcon(filename: string, isDirectory: boolean, isSelected: boolean) {
    if (isDirectory) {
        const Icon = isSelected ? FolderOpen : Folder;
        return <Icon className="w-4 h-4 flex-shrink-0 text-amber-500" />;
    }

    const ext = filename.split(".").pop()?.toLowerCase() || "";
    const lowerName = filename.toLowerCase();

    // Code files
    if (["ts", "tsx", "js", "jsx", "mjs", "cjs"].includes(ext)) {
        return <FileCode className="w-4 h-4 flex-shrink-0 text-blue-500" />;
    }
    if (["py", "pyw", "pyi"].includes(ext)) {
        return <FileCode className="w-4 h-4 flex-shrink-0 text-yellow-500" />;
    }
    if (["go", "rs", "c", "cpp", "h", "hpp", "java", "kt", "scala", "swift", "rb", "php", "lua", "r"].includes(ext)) {
        return <FileCode className="w-4 h-4 flex-shrink-0 text-orange-500" />;
    }
    if (["sh", "bash", "zsh", "fish"].includes(ext)) {
        return <FileCode className="w-4 h-4 flex-shrink-0 text-green-600" />;
    }

    // Web files
    if (["html", "htm", "vue", "svelte"].includes(ext)) {
        return <FileCode className="w-4 h-4 flex-shrink-0 text-orange-400" />;
    }
    if (["css", "scss", "less", "sass"].includes(ext)) {
        return <FileCode className="w-4 h-4 flex-shrink-0 text-purple-500" />;
    }

    // Data / config files
    if (["json", "jsonl", "json5"].includes(ext)) {
        return <FileJson className="w-4 h-4 flex-shrink-0 text-yellow-600" />;
    }
    if (["yml", "yaml", "toml", "ini", "env", "cfg"].includes(ext)) {
        return <FileCog className="w-4 h-4 flex-shrink-0 text-muted-foreground" />;
    }
    if (["xml", "svg"].includes(ext)) {
        return <FileCode className="w-4 h-4 flex-shrink-0 text-orange-500" />;
    }
    if (["csv", "tsv", "xls", "xlsx"].includes(ext)) {
        return <FileSpreadsheet className="w-4 h-4 flex-shrink-0 text-green-600" />;
    }
    if (["sql", "db", "sqlite"].includes(ext)) {
        return <FileSpreadsheet className="w-4 h-4 flex-shrink-0 text-blue-400" />;
    }

    // Image files
    if (["png", "jpg", "jpeg", "gif", "webp", "ico", "bmp", "tiff"].includes(ext)) {
        return <FileImage className="w-4 h-4 flex-shrink-0 text-pink-500" />;
    }

    // Document files
    if (["md", "mdx", "txt", "rst", "adoc"].includes(ext)) {
        return <FileText className="w-4 h-4 flex-shrink-0 text-muted-foreground" />;
    }
    if (["pdf", "doc", "docx"].includes(ext)) {
        return <FileType className="w-4 h-4 flex-shrink-0 text-red-500" />;
    }

    // Archives
    if (["zip", "tar", "gz", "bz2", "xz", "7z", "rar"].includes(ext)) {
        return <FileArchive className="w-4 h-4 flex-shrink-0 text-amber-600" />;
    }

    // Config-like files without extension
    if (["dockerfile", "makefile", "rakefile", "gemfile", "procfile"].includes(lowerName)) {
        return <FileCog className="w-4 h-4 flex-shrink-0 text-muted-foreground" />;
    }
    if (lowerName.startsWith(".") || lowerName === "license" || lowerName === "readme") {
        return <FileText className="w-4 h-4 flex-shrink-0 text-muted-foreground" />;
    }

    // Lock files
    if (ext === "lock" || lowerName.endsWith("-lock.json") || lowerName.endsWith(".lockb")) {
        return <FileCog className="w-4 h-4 flex-shrink-0 text-muted-foreground/60" />;
    }

    return <FileText className="w-4 h-4 flex-shrink-0 text-muted-foreground" />;
}

// Format relative time for modification dates
function formatModifiedTime(date?: Date): string | null {
    if (!date) return null;
    const now = Date.now();
    const modified = new Date(date).getTime();
    const diffMs = now - modified;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return "now";
    if (diffMin < 60) return `${diffMin}m`;
    if (diffHr < 24) return `${diffHr}h`;
    if (diffDay < 30) return `${diffDay}d`;
    return new Date(date).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Check if a file was recently modified (within last 5 minutes)
function isRecentlyModified(date?: Date): boolean {
    if (!date) return false;
    const now = Date.now();
    const modified = new Date(date).getTime();
    return now - modified < 5 * 60 * 1000;
}

function Breadcrumb({
    path,
    onNavigate,
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
    onDoubleClick,
}: {
    entry: FileEntry;
    isSelected: boolean;
    onClick: () => void;
    onDoubleClick: () => void;
}) {
    const isDir = entry.type === "directory";

    // Format file size
    const formatSize = (bytes?: number) => {
        if (bytes === undefined) return "";
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const modifiedLabel = formatModifiedTime(entry.modifiedAt);
    const recentlyModified = isRecentlyModified(entry.modifiedAt);

    return (
        <button
            onClick={onClick}
            onDoubleClick={onDoubleClick}
            className={cn(
                "w-full flex items-center gap-2 px-3 py-1.5 text-left group",
                "hover:bg-secondary/60 transition-colors",
                isSelected && "bg-secondary"
            )}
        >
            {getFileIcon(entry.name, isDir, isSelected)}
            <span className="flex-1 text-sm truncate">{entry.name}</span>
            {recentlyModified && (
                <span className="text-[9px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                    mod
                </span>
            )}
            {!isDir && modifiedLabel && !recentlyModified && (
                <span className="text-[10px] text-muted-foreground/50 hidden group-hover:inline">
                    {modifiedLabel}
                </span>
            )}
            {!isDir && entry.size !== undefined && (
                <span className="text-xs text-muted-foreground/60">{formatSize(entry.size)}</span>
            )}
        </button>
    );
}

export function ComputerFileView({ className }: ComputerFileViewProps) {
    const t = useTranslations("computer");
    const [searchQuery, setSearchQuery] = useState("");
    const [isSearchOpen, setIsSearchOpen] = useState(false);

    // Per-conversation state via a single consolidated selector
    const convState = useComputerStore((state) => {
        const id = state.activeConversationId;
        if (!id) return null;
        return state.conversationStates[id] ?? null;
    });

    const currentPath = convState?.currentPath ?? "/home/ubuntu";
    const files = convState?.files ?? [];
    const selectedFile = convState?.selectedFile ?? null;
    const workspaceSandboxType = convState?.workspaceSandboxType ?? null;
    const workspaceTaskId = convState?.workspaceTaskId ?? null;
    const fileContent = convState?.fileContent ?? null;
    const fileContentLoading = convState?.fileContentLoading ?? false;
    const fileContentError = convState?.fileContentError ?? null;
    const fileContentIsBinary = convState?.fileContentIsBinary ?? false;

    // Actions
    const setSelectedFile = useComputerStore((state) => state.setSelectedFile);
    const loadWorkspaceFiles = useComputerStore((state) => state.loadWorkspaceFiles);
    const loadFileContent = useComputerStore((state) => state.loadFileContent);

    const [isRefreshing, setIsRefreshing] = React.useState(false);

    // Load files when component mounts or path changes
    // Track a generation counter to discard stale responses
    const loadGenRef = React.useRef(0);
    useEffect(() => {
        if (workspaceSandboxType && workspaceTaskId) {
            const gen = ++loadGenRef.current;
            loadWorkspaceFiles(currentPath).then(() => {
                // If another navigation happened while this was in flight, discard
                if (gen !== loadGenRef.current) return;
            });
        }
        // Bump generation on cleanup to invalidate any in-flight request
        const ref = loadGenRef;
        return () => {
            ref.current++;
        };
    }, [workspaceSandboxType, workspaceTaskId, currentPath, loadWorkspaceFiles]);

    // Sort files: directories first, then alphabetically
    // Also filter by search query if present
    const sortedFiles = useMemo(() => {
        let filtered = [...files];
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            filtered = filtered.filter((f) => f.name.toLowerCase().includes(query));
        }
        return filtered.sort((a, b) => {
            if (a.type !== b.type) {
                return a.type === "directory" ? -1 : 1;
            }
            return a.name.localeCompare(b.name);
        });
    }, [files, searchQuery]);

    const handlePathChange = useCallback(
        (path: string) => {
            setSelectedFile(null);
            setSearchQuery("");
            loadWorkspaceFiles(path);
        },
        [setSelectedFile, loadWorkspaceFiles]
    );

    const handleFileSelect = useCallback(
        (entry: FileEntry) => {
            if (entry.type === "directory") {
                // Single click on directory - just select it
                setSelectedFile(entry.path);
            } else {
                // Single click on file - select and load content
                setSelectedFile(entry.path);
                loadFileContent(entry.path);
            }
        },
        [setSelectedFile, loadFileContent]
    );

    const handleDoubleClick = useCallback(
        (entry: FileEntry) => {
            if (entry.type === "directory") {
                handlePathChange(entry.path);
            }
        },
        [handlePathChange]
    );

    const handleParentClick = useCallback(() => {
        const parentPath = currentPath.split("/").slice(0, -1).join("/") || "/";
        handlePathChange(parentPath);
    }, [currentPath, handlePathChange]);

    const handleRefresh = useCallback(async () => {
        setIsRefreshing(true);
        try {
            await loadWorkspaceFiles(currentPath);
        } finally {
            setIsRefreshing(false);
        }
    }, [loadWorkspaceFiles, currentPath]);

    const toggleSearch = useCallback(() => {
        setIsSearchOpen((prev) => {
            if (prev) setSearchQuery("");
            return !prev;
        });
    }, []);

    // Get filename from selected path
    const selectedFileName = selectedFile ? selectedFile.split("/").pop() || "" : "";

    // Check if workspace is connected
    const isConnected = workspaceSandboxType && workspaceTaskId;

    return (
        <div className={cn("flex-1 flex flex-col overflow-hidden bg-background", className)}>
            {/* Header with refresh and search buttons */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-border/30 bg-secondary/20">
                <span className="text-xs font-medium text-muted-foreground">
                    {t("workspace.title")}
                </span>
                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={toggleSearch}
                        disabled={!isConnected}
                    >
                        <Search className={cn("w-3.5 h-3.5", isSearchOpen && "text-primary")} />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={handleRefresh}
                        disabled={!isConnected || isRefreshing}
                    >
                        {isRefreshing ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                            <RefreshCw className="w-3.5 h-3.5" />
                        )}
                    </Button>
                </div>
            </div>

            {!isConnected ? (
                // No workspace connected - improved disconnected state
                <div className="flex-1 flex flex-col items-center justify-center py-12 px-6">
                    <div className="w-16 h-16 rounded-2xl bg-secondary/50 flex items-center justify-center mb-4">
                        <FolderClosed className="w-8 h-8 text-muted-foreground/40" />
                    </div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">
                        {t("workspace.empty")}
                    </p>
                </div>
            ) : (
                // Split view: file tree and content preview
                <div className="flex-1 flex overflow-hidden">
                    {/* File tree (left side) */}
                    <div className="w-1/2 flex flex-col border-r border-border/30 overflow-hidden">
                        {/* Breadcrumb navigation */}
                        <Breadcrumb path={currentPath} onNavigate={handlePathChange} />

                        {/* Search input */}
                        {isSearchOpen && (
                            <div className="px-2 py-1.5 border-b border-border/30 bg-secondary/10">
                                <div className="relative">
                                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground/50" />
                                    <Input
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        placeholder={t("workspace.searchPlaceholder")}
                                        className="h-7 text-xs pl-7 pr-7 border-border/30 bg-background/50"
                                        autoFocus
                                    />
                                    {searchQuery && (
                                        <button
                                            onClick={() => setSearchQuery("")}
                                            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-muted-foreground"
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* File list */}
                        <ScrollArea className="flex-1">
                            <div className="py-1">
                                {/* Parent directory */}
                                {currentPath !== "/" && !searchQuery && (
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
                                    <div className="px-3 py-8 flex flex-col items-center text-center">
                                        {searchQuery ? (
                                            <>
                                                <Search className="w-6 h-6 text-muted-foreground/30 mb-2" />
                                                <p className="text-sm text-muted-foreground/60">
                                                    {t("workspace.noResults")}
                                                </p>
                                            </>
                                        ) : (
                                            <>
                                                <FolderOpen className="w-6 h-6 text-muted-foreground/30 mb-2" />
                                                <p className="text-sm text-muted-foreground/60">
                                                    {t("emptyDirectory")}
                                                </p>
                                            </>
                                        )}
                                    </div>
                                ) : (
                                    sortedFiles.map((entry) => (
                                        <FileItem
                                            key={entry.path}
                                            entry={entry}
                                            isSelected={selectedFile === entry.path}
                                            onClick={() => handleFileSelect(entry)}
                                            onDoubleClick={() => handleDoubleClick(entry)}
                                        />
                                    ))
                                )}
                            </div>
                        </ScrollArea>

                        {/* File count footer */}
                        {files.length > 0 && (
                            <div className="px-3 py-1 border-t border-border/30 bg-secondary/10">
                                <span className="text-[10px] text-muted-foreground/50">
                                    {files.filter((f) => f.type === "file").length} {t("workspace.fileCount")}{" "}
                                    {files.filter((f) => f.type === "directory").length > 0 &&
                                        `/ ${files.filter((f) => f.type === "directory").length} ${t("workspace.folderCount")}`}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Content preview (right side) */}
                    <div className="w-1/2 flex flex-col overflow-hidden">
                        <ComputerFileContent
                            filename={selectedFileName}
                            content={fileContent}
                            isLoading={fileContentLoading}
                            error={fileContentError}
                            isBinary={fileContentIsBinary}
                            className="flex-1"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
