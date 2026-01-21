"use client";

import React, { useState } from "react";
import { DesktopSidebar } from "./desktop-sidebar";
import { MobileSidebar } from "./mobile-sidebar";
import { MenuToggle } from "@/components/ui/menu-toggle";
import { UserProfileMenu } from "@/components/auth/user-profile-menu";
import { useSidebarStore } from "@/lib/stores/sidebar-store";
import { useAgentProgressStore } from "@/lib/stores/agent-progress-store";
import { cn } from "@/lib/utils";

import { FilePreviewSidebar } from "@/components/chat/file-preview-sidebar";
import { AgentProgressPanel } from "@/components/sidebar/sidebar-agent-progress";

interface MainLayoutProps {
    children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
    const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
    const { desktopSidebarOpen, toggleDesktopSidebar } = useSidebarStore();
    const { isPanelOpen, activeProgress } = useAgentProgressStore();

    // Calculate the right panel width for content adjustment
    const hasBrowserStream = activeProgress?.browserStream;
    const rightPanelWidth = isPanelOpen
        ? hasBrowserStream
            ? "lg:pr-[680px]"  // Browser stream active - wider panel
            : "lg:pr-[340px]"  // Normal panel width
        : "";

    return (
        <div className="flex h-screen overflow-hidden bg-background">
            {/* Desktop Sidebar - Always visible on desktop */}
            <DesktopSidebar />

            {/* Mobile Sidebar - Overlay on mobile */}
            <MobileSidebar
                isOpen={mobileSidebarOpen}
                onClose={() => setMobileSidebarOpen(false)}
            />

            <main className={cn(
                "flex-1 flex flex-col overflow-hidden relative transition-all duration-300",
                rightPanelWidth
            )}>
                {/* Mobile header with menu toggle and user profile */}
                <div className="md:hidden h-14 px-2 flex items-center justify-between border-b border-border bg-card sticky top-0 z-30">
                    <div className="flex items-center">
                        <MenuToggle
                            isOpen={mobileSidebarOpen}
                            onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
                        />
                        <span className="ml-1 font-semibold text-foreground tracking-tight">HyperAgent</span>
                    </div>
                    <div className="pr-2">
                        <UserProfileMenu />
                    </div>
                </div>

                {/* Desktop floating toggle - animated visibility when sidebar is closed */}
                <div
                    className={cn(
                        "hidden md:flex absolute left-4 top-4 z-40",
                        "glass-card rounded-lg",
                        "transition-all duration-300 ease-out",
                        desktopSidebarOpen
                            ? "opacity-0 -translate-x-2 pointer-events-none"
                            : "opacity-100 translate-x-0"
                    )}
                >
                    <MenuToggle
                        isOpen={false}
                        onClick={toggleDesktopSidebar}
                    />
                </div>

                {/* Desktop user profile - top right corner */}
                <div className="hidden md:block absolute right-4 top-4 z-40">
                    <UserProfileMenu />
                </div>

                {children}

                {/* File Preview Sidebar */}
                <FilePreviewSidebar />

                {/* Agent Progress Panel - Right side panel for agent activity */}
                <AgentProgressPanel />
            </main>
        </div>
    );
}
