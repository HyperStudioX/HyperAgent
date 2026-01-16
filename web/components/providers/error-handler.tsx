"use client";

import { useEffect } from "react";

/**
 * Global error handler to suppress harmless browser extension errors
 * that don't affect application functionality.
 */
export function ErrorHandler() {
    useEffect(() => {
        // Handle unhandled promise rejections
        const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
            const errorMessage = event.reason?.message || String(event.reason);
            
            // Suppress common browser extension errors
            if (
                errorMessage.includes("message channel closed") ||
                errorMessage.includes("asynchronous response") ||
                errorMessage.includes("Extension context invalidated")
            ) {
                event.preventDefault();
                // Optionally log in debug mode
                if (process.env.NODE_ENV === "development") {
                    console.debug("Suppressed browser extension error:", errorMessage);
                }
                return;
            }
            
            // Let other errors through normally
        };

        // Handle general errors
        const handleError = (event: ErrorEvent) => {
            const errorMessage = event.message || String(event.error);
            
            // Suppress common browser extension errors
            if (
                errorMessage.includes("message channel closed") ||
                errorMessage.includes("asynchronous response") ||
                errorMessage.includes("Extension context invalidated")
            ) {
                event.preventDefault();
                // Optionally log in debug mode
                if (process.env.NODE_ENV === "development") {
                    console.debug("Suppressed browser extension error:", errorMessage);
                }
                return;
            }
            
            // Let other errors through normally
        };

        window.addEventListener("unhandledrejection", handleUnhandledRejection);
        window.addEventListener("error", handleError);

        return () => {
            window.removeEventListener("unhandledrejection", handleUnhandledRejection);
            window.removeEventListener("error", handleError);
        };
    }, []);

    return null;
}
