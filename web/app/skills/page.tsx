import { SkillBrowser } from "@/components/skills";

export default function SkillsPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Skills</h1>
          <p className="text-muted-foreground mt-2">
            Browse and discover composable skills that agents can use to complete specialized tasks
          </p>
        </div>
        <SkillBrowser />
      </div>
    </div>
  );
}
