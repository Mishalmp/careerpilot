"use client";

import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";

import { useConcept, useConcepts } from "./hooks";

export function ConceptPage() {
  const { id } = useParams<{ id: string }>();
  const concept = useConcept(id);
  const all = useConcepts();

  const back = (
    <Link href="/architecture" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ChevronLeft className="size-4" aria-hidden="true" /> How it works
    </Link>
  );

  if (concept.isPending) return <Skeleton className="h-72" aria-busy="true" />;
  if (concept.isError) {
    const missing = concept.error instanceof ApiError && concept.error.status === 404;
    return (
      <div className="flex flex-col gap-3">
        {back}
        <ErrorState title={missing ? "No such concept" : "Could not load this concept"} description={concept.error.message} />
      </div>
    );
  }
  const c = concept.data;
  const titleOf = (cid: string) => all.data?.find((x) => x.id === cid)?.title ?? cid;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      {back}
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">{c.title}</h1>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="accent">{c.level}</Badge>
          {c.appears_in.map((a) => (
            <Badge key={a} tone="outline">
              {a}
            </Badge>
          ))}
        </div>
      </header>

      {/* react-markdown renders to React elements and does not allow raw HTML, so content cannot inject markup. */}
      <article className="guide">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{c.body}</ReactMarkdown>
      </article>

      {c.proof.length > 0 && (
        <section aria-labelledby="proof-heading" className="rounded-lg border border-border-subtle bg-surface p-4">
          <h2 id="proof-heading" className="text-sm font-semibold">
            Proven by
          </h2>
          <ul className="mt-2 flex flex-col gap-1 text-sm">
            {c.proof.map((p) => (
              <li key={p}>
                <code className="rounded bg-surface-hover px-1.5 py-0.5 text-xs">{p}</code>
              </li>
            ))}
          </ul>
        </section>
      )}

      {c.related.length > 0 && (
        <section aria-labelledby="related-heading">
          <h2 id="related-heading" className="text-sm font-semibold">
            Related
          </h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {c.related.map((r) => (
              <li key={r}>
                <Link
                  href={`/architecture/concepts/${r}`}
                  className="rounded-full border border-border px-3 py-1 text-sm text-accent-text hover:border-primary"
                >
                  {titleOf(r)}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
