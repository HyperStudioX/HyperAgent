import dynamic from "next/dynamic";

export const SkillCodeEditor = dynamic(
  () =>
    import("./skill-code-editor").then((mod) => mod.SkillCodeEditor),
  {
    ssr: false,
    loading: () => (
      <div className="border border-border/50 rounded-xl overflow-hidden bg-secondary/30 animate-pulse h-[400px]" />
    ),
  }
);
