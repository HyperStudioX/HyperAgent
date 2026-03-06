interface ChatHomeViewProps {
    welcomeTitle: string;
    welcomeSubtitle: string;
}

export function ChatHomeView({ welcomeTitle, welcomeSubtitle }: ChatHomeViewProps) {
    return (
        <div className="text-center mb-12">
            <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight leading-[1.15]">
                {welcomeTitle}
            </h1>
            <p className="mt-3 text-muted-foreground text-sm md:text-base leading-relaxed max-w-md mx-auto">
                {welcomeSubtitle}
            </p>
        </div>
    );
}
