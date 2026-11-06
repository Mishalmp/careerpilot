"use client";

import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { PostgreSQL, sql } from "@codemirror/lang-sql";
import { indentWithTab } from "@codemirror/commands";
import { Compartment, EditorState, type Extension } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";
import { EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { useEffect, useRef } from "react";

import type { Language } from "./runner/runner";

function languageExtension(language: Language): Extension {
  switch (language) {
    case "python":
      return python();
    case "sql":
      return sql({ dialect: PostgreSQL });
    case "typescript":
      return javascript({ typescript: true });
    default:
      return javascript();
  }
}

const darkQuery = () => window.matchMedia("(prefers-color-scheme: dark)");

/**
 * A small CodeMirror 6 wrapper. Ctrl/Cmd+Enter runs. Tab indents; press Escape and then Tab to
 * move focus out of the editor with the keyboard.
 */
export function CodeEditor({
  value,
  language,
  label,
  onChange,
  onRun,
}: {
  value: string;
  language: Language;
  label: string;
  onChange: (value: string) => void;
  onRun: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const languageSlot = useRef(new Compartment());
  const themeSlot = useRef(new Compartment());
  // The editor is created once, so it reads the latest callbacks through refs.
  const onChangeRef = useRef(onChange);
  const onRunRef = useRef(onRun);
  useEffect(() => {
    onChangeRef.current = onChange;
    onRunRef.current = onRun;
  });

  useEffect(() => {
    if (!host.current) return;
    const dark = darkQuery();
    const created = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          keymap.of([
            { key: "Mod-Enter", run: () => (onRunRef.current(), true) },
            indentWithTab,
          ]),
          languageSlot.current.of(languageExtension(language)),
          themeSlot.current.of(dark.matches ? oneDark : []),
          EditorView.contentAttributes.of({ "aria-label": label }),
          EditorView.theme({
            "&": { height: "100%", fontSize: "14px" },
            ".cm-scroller": { fontFamily: "var(--font-mono), monospace" },
          }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) onChangeRef.current(update.state.doc.toString());
          }),
        ],
      }),
    });
    view.current = created;

    const onTheme = (event: MediaQueryListEvent) =>
      created.dispatch({ effects: themeSlot.current.reconfigure(event.matches ? oneDark : []) });
    dark.addEventListener("change", onTheme);
    return () => {
      dark.removeEventListener("change", onTheme);
      created.destroy();
      view.current = null;
    };
    // Created once; later changes to value and language are applied by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    view.current?.dispatch({ effects: languageSlot.current.reconfigure(languageExtension(language)) });
  }, [language]);

  // Replace the text only when it was changed from outside (reset, language switch).
  useEffect(() => {
    const current = view.current;
    if (current && current.state.doc.toString() !== value) {
      current.dispatch({ changes: { from: 0, to: current.state.doc.length, insert: value } });
    }
  }, [value]);

  return (
    <div
      ref={host}
      className="h-96 overflow-hidden rounded border border-input"
      data-testid="code-editor"
    />
  );
}
