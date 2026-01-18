"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface MenuToggleProps {
    isOpen: boolean;
    onClick: () => void;
    className?: string;
}

export function MenuToggle({ isOpen, onClick, className }: MenuToggleProps) {
    return (
        <button
            onClick={onClick}
            className={cn(
                "relative flex items-center justify-center",
                "min-h-[44px] min-w-[44px] p-2.5",
                "text-muted-foreground hover:text-foreground",
                "rounded-lg hover:bg-secondary",
                "transition-colors duration-200",
                "touch-manipulation",
                className
            )}
            aria-label={isOpen ? "Close sidebar" : "Open sidebar"}
            aria-expanded={isOpen}
        >
            <svg
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="transition-transform duration-200"
            >
                {/* Outer frame */}
                <rect
                    x="3"
                    y="3"
                    width="14"
                    height="14"
                    rx="1.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="transition-all duration-300 ease-out"
                />

                {/* Vertical divider */}
                <line
                    x1="8.5"
                    y1="3"
                    x2="8.5"
                    y2="17"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    className={cn(
                        "transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
                        "origin-center",
                        isOpen && "translate-x-[8.5px] opacity-0"
                    )}
                />

                {/* Left panel fill (shows when open) */}
                <rect
                    x="4"
                    y="4"
                    width="3.5"
                    height="12"
                    rx="0.5"
                    fill="currentColor"
                    className={cn(
                        "transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
                        isOpen
                            ? "opacity-25 scale-100"
                            : "opacity-0 scale-75"
                    )}
                />
            </svg>
        </button>
    );
}
