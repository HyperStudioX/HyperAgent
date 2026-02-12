"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

const MAX_RETRIES = 3;

interface Props {
    children: ReactNode;
    fallbackMessage?: string;
    translations?: {
        title: string;
        maxRetries: string;
        retry: (count: number) => string;
    };
}

interface State {
    hasError: boolean;
    error: Error | null;
    retryCount: number;
}

export class ComputerErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null, retryCount: 0 };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("ComputerPanel Error:", error, errorInfo);
    }

    handleRetry = () => {
        this.setState((prev) => ({
            hasError: false,
            error: null,
            retryCount: prev.retryCount + 1,
        }));
    };

    render() {
        if (this.state.hasError) {
            const canRetry = this.state.retryCount < MAX_RETRIES;
            const translations = this.props.translations;
            const titleText = this.props.fallbackMessage || translations?.title || "Something went wrong";
            const maxRetriesText = translations?.maxRetries || "Maximum retries reached. Please reload the page.";
            const retryText = translations?.retry
                ? translations.retry(MAX_RETRIES - this.state.retryCount)
                : `Try Again (${MAX_RETRIES - this.state.retryCount} left)`;
            return (
                <div className="flex flex-col items-center justify-center h-full p-6 text-center">
                    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-destructive/10 mb-4">
                        <AlertTriangle className="w-6 h-6 text-destructive" />
                    </div>
                    <h3 className="text-sm font-medium mb-2">
                        {titleText}
                    </h3>
                    <p className="text-xs text-muted-foreground mb-4 max-w-[300px]">
                        {this.state.error?.message || this.props.fallbackMessage || "An unexpected error occurred in the computer panel."}
                    </p>
                    {canRetry ? (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={this.handleRetry}
                            className="gap-2"
                        >
                            <RefreshCw className="w-3.5 h-3.5" />
                            {retryText}
                        </Button>
                    ) : (
                        <p className="text-xs text-muted-foreground">
                            {maxRetriesText}
                        </p>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}
