"use client";

import React, { useState } from "react";
import { Menu } from "lucide-react";
import { Sidebar } from "./sidebar";

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header with hamburger menu */}
        <div className="md:hidden h-14 px-4 flex items-center border-b border-border bg-card sticky top-0 z-30">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 -ml-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-secondary transition-colors"
            aria-label="Open sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="ml-3 font-semibold text-foreground tracking-tight">HyperAgent</span>
        </div>

        {children}
      </main>
    </div>
  );
}
