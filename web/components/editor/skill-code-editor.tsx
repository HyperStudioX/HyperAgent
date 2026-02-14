"use client";

import Editor from "@monaco-editor/react";
import { useTheme } from "@/lib/hooks/use-theme";

interface SkillCodeEditorProps {
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: string;
  language?: string;
  className?: string;
}

export function SkillCodeEditor({
  value,
  onChange,
  readOnly,
  height = "400px",
  language = "python",
  className,
}: SkillCodeEditorProps) {
  const { resolvedTheme } = useTheme();
  const isReadOnly = readOnly ?? !onChange;

  return (
    <div
      className={`border border-border/50 rounded-xl overflow-hidden ${className ?? ""}`}
    >
      <Editor
        height={height}
        language={language}
        theme={resolvedTheme === "dark" ? "vs-dark" : "vs"}
        value={value}
        onChange={(val) => onChange?.(val ?? "")}
        options={{
          readOnly: isReadOnly,
          domReadOnly: isReadOnly,
          minimap: { enabled: false },
          automaticLayout: true,
          padding: { top: 12, bottom: 12 },
          fontFamily:
            "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace",
          fontSize: 13,
          lineHeight: 20,
          scrollBeyondLastLine: false,
          renderLineHighlight: isReadOnly ? "none" : "line",
          overviewRulerBorder: false,
          hideCursorInOverviewRuler: true,
          scrollbar: {
            verticalScrollbarSize: 6,
            horizontalScrollbarSize: 6,
          },
        }}
      />
    </div>
  );
}
