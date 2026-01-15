"use client";

import React, { useState } from "react";
import { DesktopSidebar } from "./desktop-sidebar";
import { MobileSidebar } from "./mobile-sidebar";
import { MenuToggle } from "@/components/ui/menu-toggle";
import { useSidebarStore } from "@/lib/stores/sidebar-store";

import { FilePreviewSidebar } from "@/components/chat/file-preview-sidebar";

interface MainLayoutProps {
    children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
    const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
    const { desktopSidebarOpen, toggleDesktopSidebar } = useSidebarStore();

    return (
        <div className="flex h-screen overflow-hidden bg-background">
            {/* Desktop Sidebar - Always visible on desktop */}
            <DesktopSidebar />

            {/* Mobile Sidebar - Overlay on mobile */}
            <MobileSidebar
                isOpen={mobileSidebarOpen}
                onClose={() => setMobileSidebarOpen(false)}
            />

            <main className="flex-1 flex flex-col overflow-hidden relative">
                {/* Mobile header with menu toggle */}
                <div className="md:hidden h-14 px-4 flex items-center border-b border-border bg-card sticky top-0 z-30">
                    <MenuToggle
                        isOpen={mobileSidebarOpen}
                        onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
                    />
                    <span className="ml-3 font-semibold text-foreground tracking-tight">HyperAgent</span>
                </div>

                {/* Desktop floating toggle - only when sidebar is closed */}
                {!desktopSidebarOpen && (
                    <div className="hidden md:flex absolute left-4 top-4 z-40 bg-background/50 backdrop-blur-sm rounded-lg border border-border/50 shadow-sm p-0.5">
                        <MenuToggle
                            isOpen={false}
                            onClick={toggleDesktopSidebar}
                        />
                    </div>
                )}

                {children}

                {/* File Preview Sidebar */}
                <FilePreviewSidebar />
            </main>
        </div>
    );
}
