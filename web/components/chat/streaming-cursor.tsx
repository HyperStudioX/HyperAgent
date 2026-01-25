"use client";

/**
 * Streaming cursor that blinks at the end of content
 * Uses pure CSS animation to avoid React re-renders
 * Refined for precise alignment and visual polish
 */
export function StreamingCursor(): JSX.Element {
    return (
        <span className="streaming-cursor-wrapper" aria-hidden="true">
            <span className="streaming-cursor-bar" />
        </span>
    );
}
