"use client";

import React, { useEffect, useRef } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/stores/chat-store";
import { useTaskStore } from "@/lib/stores/task-store";
import { useTheme } from "@/lib/hooks/use-theme";
import { UserMenu } from "@/components/auth/user-menu";
import { PreferencesPanel } from "@/components/ui/preferences-panel";
import { RecentTasks, type RecentItem } from "@/components/ui/recent-tasks";
import { CreateMenu } from "@/components/ui/create-menu";
import { MenuToggle } from "@/components/ui/menu-toggle";
import { useSidebarStore } from "@/lib/stores/sidebar-store";

interface DesktopSidebarProps {
    className?: string;
}

export function DesktopSidebar({ className }: DesktopSidebarProps) {
    const { desktopSidebarOpen, toggleDesktopSidebar } = useSidebarStore();
    const router = useRouter();
    const { data: session, status } = useSession();
    const {
        conversations,
        activeConversationId,
        hasHydrated: chatHydrated,
        setActiveConversation,
        loadConversations,
        deleteConversation,
    } = useChatStore();
    const {
        tasks,
        activeTaskId,
        hasHydrated: taskHydrated,
        setActiveTask,
        deleteTask,
        loadTasks,
    } = useTaskStore();

    const hasHydrated = chatHydrated && taskHydrated;
    const { theme, setTheme, mounted } = useTheme();

    // Track if we've attempted to load conversations to prevent duplicate calls
    const loadAttempted = useRef(false);

    // Load conversations and tasks on mount (only load conversations if authenticated)
    useEffect(() => {
        // Wait for session to finish loading before making any decisions
        if (status === "loading") {
            return;
        }

        // If we've already attempted to load, don't try again
        if (loadAttempted.current) {
            return;
        }

        // If chat store is already hydrated, don't do anything
        if (chatHydrated) {
            return;
        }

        // Mark that we've attempted to load
        loadAttempted.current = true;

        // Only load from API if authenticated, otherwise just set hydrated
        if (status === "authenticated") {
            console.log("[DesktopSidebar] Loading conversations from database");
            loadConversations();
        } else {
            console.log("[DesktopSidebar] Not authenticated, using local mode");
            useChatStore.setState({ hasHydrated: true });
        }
    }, [status, chatHydrated, loadConversations]);

    // Load tasks (from API if authenticated, otherwise rely on localStorage)
    useEffect(() => {
        if (status === "loading" || taskHydrated) {
            return;
        }

        if (status === "authenticated") {
            console.log("[DesktopSidebar] Loading tasks from database");
            loadTasks();
        } else {
            console.log("[DesktopSidebar] Not authenticated, using local tasks only");
            useTaskStore.setState({ hasHydrated: true });
        }
    }, [status, taskHydrated, loadTasks]);

    const handleItemSelect = (item: RecentItem) => {
        if (item.type === "conversation") {
            setActiveConversation(item.data.id);
            setActiveTask(null);
            router.push("/");
        } else {
            setActiveTask(item.data.id);
            setActiveConversation(null);
            router.push(`/task/${item.data.id}`);
        }
    };

    const handleItemDelete = async (item: RecentItem) => {
        try {
            if (item.type === "conversation") {
                // If deleting current conversation, go home first
                if (item.data.id === activeConversationId) {
                    router.push("/");
                    setActiveConversation(null);
                }
                await deleteConversation(item.data.id);
            } else {
                // If deleting current task, go home first
                if (item.data.id === activeTaskId) {
                    router.push("/");
                    setActiveTask(null);
                }
                await deleteTask(item.data.id);
            }
        } catch (error) {
            console.error("Failed to delete item:", error);
        }
    };

    return (
        <aside
            className={cn(
                "hidden md:flex",
                "h-full flex-col",
                "border-r border-border transition-all duration-300 ease-in-out overflow-hidden z-20",
                "bg-secondary/30",
                desktopSidebarOpen ? "w-72" : "w-0 opacity-0 border-r-0 pointer-events-none",
                className
            )}
            role="navigation"
            aria-label="Main navigation"
        >
            {/* Header */}
            <div className="h-14 px-4 flex items-center justify-between border-b border-border/50">
                <div className="flex items-center gap-3">
                    <div className="w-7 h-7 flex items-center justify-center">
                        <Image
                            src="/images/logo-dark.svg"
                            alt="HyperAgent"
                            width={28}
                            height={28}
                            className="dark:hidden transition-opacity duration-200"
                            style={{ opacity: 0.92 }}
                        />
                        <Image
                            src="/images/logo-light.svg"
                            alt="HyperAgent"
                            width={28}
                            height={28}
                            className="hidden dark:block transition-opacity duration-200"
                            style={{ opacity: 0.95 }}
                        />
                    </div>
                    <span className="text-[15px] font-medium text-foreground tracking-[-0.01em] opacity-90">HyperAgent</span>
                </div>
                <MenuToggle
                    isOpen={true}
                    onClick={toggleDesktopSidebar}
                />
            </div>

            {/* Create Button */}
            <div className="px-3 py-3">
                <CreateMenu
                    onCreate={() => {
                        setActiveConversation(null);
                        setActiveTask(null);
                        router.push("/");
                    }}
                />
            </div>

            {/* Recent Items */}
            {hasHydrated && (
                <RecentTasks
                    conversations={conversations}
                    tasks={tasks}
                    activeConversationId={activeConversationId}
                    activeTaskId={activeTaskId}
                    onSelect={handleItemSelect}
                    onDelete={handleItemDelete}
                    className="flex-1 min-h-0"
                />
            )}

            {/* Footer */}
            <div className="px-3 py-3 border-t border-border space-y-2">
                <PreferencesPanel
                    theme={theme}
                    mounted={mounted}
                    onThemeChange={setTheme}
                />
                <UserMenu />
            </div>
        </aside>
    );
}
