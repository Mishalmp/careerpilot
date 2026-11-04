"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { card, muted } from "@/components/ui";

import { useGuide, useGuides } from "./hooks";
import { PrepNav } from "./PrepNav";

const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;

// `practice:two-sum` in a guide opens that problem in the editor. Every other link keeps
// react-markdown's default safety rules (no javascript: or data: links).
const urlTransform = (url: string) =>
  url.startsWith("practice:") ? url : defaultUrlTransform(url);

function GuideLink({ href, children }: { href?: string; children?: React.ReactNode }) {
  if (href?.startsWith("practice:")) {
    const slug = href.slice("practice:".length);
    return SLUG.test(slug) ? (
      <Link href={`/practice/${slug}`} className="font-medium">
        {children} &rarr;
      </Link>
    ) : (
      <span>{children}</span>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

export function GuidesListPage() {
  const guides = useGuides();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Prep</h1>
      <PrepNav />
      {guides.isPending && <p className={muted}>Loading...</p>}
      <ul className="grid gap-2 md:grid-cols-2">
        {guides.data?.map((guide) => (
          <li key={guide.name} className={card}>
            <Link href={`/prep/guides/${guide.name}`} className="font-medium hover:underline">
              {guide.title}
            </Link>
            {guide.private && <span className={`${muted} ml-2`}>(private, not in git)</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function GuideReaderPage() {
  const { name } = useParams<{ name: string }>();
  const guide = useGuide(name);
  return (
    <div className="space-y-4">
      <Link href="/prep/guides" className={`${muted} hover:underline`}>
        &larr; All guides
      </Link>
      {guide.isPending && <p className={muted}>Loading...</p>}
      {guide.isError && <p role="alert" className="text-red-600">Could not load this guide.</p>}
      {guide.data && (
        // Raw HTML in Markdown is ignored (react-markdown's default), so guide text cannot inject markup.
        <article className="guide">
          <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={urlTransform} components={{ a: GuideLink }}>
            {guide.data.markdown}
          </ReactMarkdown>
        </article>
      )}
    </div>
  );
}
