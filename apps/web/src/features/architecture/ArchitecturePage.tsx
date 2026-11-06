"use client";

import { BookOpenText, Network, Workflow } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { DiagramCanvas, NodeDetails } from "./DiagramCanvas";
import { FlowPlayer } from "./FlowPlayer";
import { useConcepts, useDiagrams, useFlows } from "./hooks";

export function ArchitecturePage() {
  const diagrams = useDiagrams();
  const flows = useFlows();
  const concepts = useConcepts();
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");

  const overview = diagrams.data?.find((d) => d.id === "overview");
  const modules = diagrams.data?.find((d) => d.id === "modules");
  const active = tab === "modules" ? modules : overview;
  const selectedNode = active?.nodes.find((n) => n.id === selected) ?? null;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="How CareerPilot works"
        description="The parts, the code behind them, the paths a request takes, and the ideas you can be asked about. Everything here is checked against the code."
      />
      <Tabs
        value={tab}
        onValueChange={(v) => {
          setTab(v);
          setSelected(null);
        }}
      >
        <TabsList className="max-w-full overflow-x-auto">
          <TabsTrigger value="overview">
            <Network className="mr-1.5 inline size-4" aria-hidden="true" />
            System
          </TabsTrigger>
          <TabsTrigger value="modules">Modules</TabsTrigger>
          <TabsTrigger value="flows">
            <Workflow className="mr-1.5 inline size-4" aria-hidden="true" />
            Flows
          </TabsTrigger>
          <TabsTrigger value="concepts">
            <BookOpenText className="mr-1.5 inline size-4" aria-hidden="true" />
            Concepts
          </TabsTrigger>
        </TabsList>

        {diagrams.isPending && <Skeleton className="mt-4 h-96" aria-busy="true" />}
        {diagrams.isError && (
          <div className="mt-4">
            <ErrorState title="Could not load the diagrams" description={diagrams.error.message} onRetry={() => void diagrams.refetch()} />
          </div>
        )}

        {overview && (
          <TabsContent value="overview" className="flex flex-col gap-4">
            <DiagramCanvas diagram={overview} selectedId={selected} onSelect={setSelected} />
            <NodeDetails node={selectedNode} />
          </TabsContent>
        )}
        {modules && (
          <TabsContent value="modules" className="flex flex-col gap-4">
            <DiagramCanvas diagram={modules} selectedId={selected} onSelect={setSelected} height={620} />
            <NodeDetails node={selectedNode} />
          </TabsContent>
        )}
        <TabsContent value="flows">
          {flows.isError && <ErrorState title="Could not load the flows" description={flows.error.message} />}
          {flows.data && overview && <FlowPlayer flows={flows.data} overview={overview} />}
        </TabsContent>
        <TabsContent value="concepts">
          {concepts.isError && <ErrorState title="Could not load the concepts" description={concepts.error.message} />}
          {concepts.data && <ConceptGrid concepts={concepts.data} />}
        </TabsContent>
      </Tabs>
    </div>
  );
}

const LEVEL_TONE = { beginner: "success", intermediate: "accent", advanced: "warning" } as const;

function ConceptGrid({ concepts }: { concepts: NonNullable<ReturnType<typeof useConcepts>["data"]> }) {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? concepts.filter((c) => c.title.toLowerCase().includes(q) || c.id.includes(q)) : concepts;
  }, [concepts, query]);
  return (
    <div className="flex flex-col gap-4">
      <Input
        type="search"
        aria-label="Search concepts"
        placeholder="Search concepts"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="max-w-sm"
      />
      {shown.length === 0 && <p className="text-sm text-muted-foreground">No concept matches “{query}”.</p>}
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((c) => (
          <li key={c.id}>
            <Link
              href={`/architecture/concepts/${c.id}`}
              className="flex h-full flex-col gap-2 rounded-lg border border-border-subtle bg-surface p-4 transition-colors hover:border-primary"
            >
              <span className="font-semibold leading-snug">{c.title}</span>
              <span className="mt-auto flex flex-wrap items-center gap-1.5">
                <Badge tone={LEVEL_TONE[c.level]}>{c.level}</Badge>
                {c.proof.length > 0 && <Badge tone="outline">{c.proof.length} proof</Badge>}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
