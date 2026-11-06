"use client";

import {
  Background,
  type Edge,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  Controls,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { List, Network } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

import type { Diagram, DiagramNode } from "./hooks";

const KIND_LABEL: Record<DiagramNode["kind"], string> = {
  ui: "Browser",
  service: "Service",
  store: "Data store",
  external: "External",
  module: "Module",
  core: "Shared",
};

type NodeData = {
  node: DiagramNode;
  active: boolean;
  dim: boolean;
  selected: boolean;
};

const SIDES = [
  [Position.Left, "l"],
  [Position.Right, "r"],
  [Position.Top, "t"],
  [Position.Bottom, "b"],
] as const;

/** A card for one part of the system. Colour marks the kind; the kind and status are also written. */
function ArchNode({ data }: NodeProps<Node<NodeData>>) {
  const { node, active, dim, selected } = data;
  return (
    <div
      className={cn(
        "w-44 rounded-lg border bg-surface px-3 py-2 text-left shadow-sm transition-opacity",
        node.status === "planned" ? "border-dashed border-border" : "border-border-subtle",
        selected && "border-primary ring-2 ring-ring",
        active && "border-primary bg-accent-soft",
        dim && "opacity-40",
      )}
    >
      {SIDES.map(([position, id]) => (
        <span key={id}>
          <Handle type="target" position={position} id={`${id}-t`} className="!size-1.5 !border-0 !bg-border-strong" />
          <Handle type="source" position={position} id={`${id}-s`} className="!size-1.5 !border-0 !bg-border-strong" />
        </span>
      ))}
      <p className="text-[0.6875rem] font-medium uppercase tracking-wide text-muted-foreground">
        {KIND_LABEL[node.kind]}
        {node.status === "planned" ? " · planned" : ""}
      </p>
      <p className="text-sm font-semibold leading-snug text-foreground">{node.title}</p>
    </div>
  );
}

const nodeTypes = { arch: ArchNode };

/** Pick the sides to connect, from where the two nodes are relative to each other. */
function sides(a: DiagramNode, b: DiagramNode): [string, string] {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? ["r-s", "l-t"] : ["l-s", "r-t"];
  return dy >= 0 ? ["b-s", "t-t"] : ["t-s", "b-t"];
}

export function DiagramCanvas({
  diagram,
  highlightNodes,
  highlightEdge,
  selectedId,
  onSelect,
  height = 520,
}: {
  diagram: Diagram;
  /** Node ids to emphasise (used by the flow player); everything else is dimmed. */
  highlightNodes?: string[];
  /** The edge (source->target) that is currently active in a flow. */
  highlightEdge?: { source: string; target: string } | null;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  height?: number;
}) {
  const { resolved } = useTheme();
  const [view, setView] = useState<"diagram" | "list">("diagram");
  const byId = useMemo(() => new Map(diagram.nodes.map((n) => [n.id, n])), [diagram.nodes]);
  const lit = useMemo(() => (highlightNodes?.length ? new Set(highlightNodes) : null), [highlightNodes]);

  const nodes: Node<NodeData>[] = useMemo(
    () =>
      diagram.nodes.map((n) => ({
        id: n.id,
        type: "arch",
        position: { x: n.x, y: n.y },
        data: { node: n, active: lit?.has(n.id) ?? false, dim: lit ? !lit.has(n.id) : false, selected: selectedId === n.id },
        draggable: false,
        ariaLabel: `${n.title}. ${KIND_LABEL[n.kind]}${n.status === "planned" ? ", planned" : ""}. ${n.summary}`,
      })),
    [diagram.nodes, lit, selectedId],
  );

  const edges: Edge[] = useMemo(
    () =>
      diagram.edges.flatMap((e, i) => {
        const a = byId.get(e.source);
        const b = byId.get(e.target);
        if (!a || !b) return [];
        const [sourceHandle, targetHandle] = sides(a, b);
        const active = highlightEdge?.source === e.source && highlightEdge?.target === e.target;
        return [
          {
            id: `${e.source}->${e.target}:${i}`,
            source: e.source,
            target: e.target,
            sourceHandle,
            targetHandle,
            label: e.label ?? undefined,
            type: "smoothstep",
            animated: active,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { strokeWidth: active ? 2.5 : 1.25, opacity: highlightEdge && !active ? 0.25 : 1 },
            labelStyle: { fontSize: 11 },
          } satisfies Edge,
        ];
      }),
    [diagram.edges, byId, highlightEdge],
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{diagram.title}</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">{diagram.summary}</p>
        </div>
        <div role="group" aria-label="View" className="inline-flex rounded-md border border-input bg-surface p-0.5">
          <Button
            size="sm"
            variant={view === "diagram" ? "soft" : "ghost"}
            aria-pressed={view === "diagram"}
            onClick={() => setView("diagram")}
          >
            <Network aria-hidden="true" /> Diagram
          </Button>
          <Button
            size="sm"
            variant={view === "list" ? "soft" : "ghost"}
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <List aria-hidden="true" /> List
          </Button>
        </div>
      </div>

      {view === "diagram" ? (
        <div
          className="overflow-hidden rounded-lg border border-border-subtle bg-surface-muted"
          style={{ height }}
          role="region"
          aria-label={`${diagram.title} diagram. Use the List view for a text version.`}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            colorMode={resolved}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            minZoom={0.3}
            maxZoom={1.6}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            onNodeClick={(_, node) => onSelect?.(node.id)}
            onPaneClick={() => onSelect?.(null)}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} />
            <Controls showInteractive={false} />
            {diagram.nodes.length > 12 && <MiniMap pannable zoomable ariaLabel="Diagram overview" />}
          </ReactFlow>
        </div>
      ) : (
        <NodeList diagram={diagram} selectedId={selectedId ?? null} onSelect={onSelect} />
      )}
    </div>
  );
}

/** The same content as text: for screen readers, keyboards and anyone who prefers reading. */
function NodeList({
  diagram,
  selectedId,
  onSelect,
}: {
  diagram: Diagram;
  selectedId: string | null;
  onSelect?: (id: string | null) => void;
}) {
  const titles = new Map(diagram.nodes.map((n) => [n.id, n.title]));
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {diagram.nodes.map((n) => {
        const out = diagram.edges.filter((e) => e.source === n.id);
        const into = diagram.edges.filter((e) => e.target === n.id);
        return (
          <li
            key={n.id}
            className={cn(
              "rounded-lg border bg-surface p-3",
              selectedId === n.id ? "border-primary" : "border-border-subtle",
            )}
          >
            <button type="button" className="w-full text-left" onClick={() => onSelect?.(n.id)}>
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{n.title}</span>
                <Badge tone="outline">{KIND_LABEL[n.kind]}</Badge>
                {n.status === "planned" && <Badge tone="warning">Planned</Badge>}
              </span>
              <span className="mt-1 block text-sm text-muted-foreground">{n.summary}</span>
            </button>
            {(out.length > 0 || into.length > 0) && (
              <p className="mt-2 text-xs text-muted-foreground">
                {out.length > 0 && <>Uses: {out.map((e) => titles.get(e.target) ?? e.target).join(", ")}. </>}
                {into.length > 0 && <>Used by: {into.map((e) => titles.get(e.source) ?? e.source).join(", ")}.</>}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Side panel with the details of the selected node. */
export function NodeDetails({ node }: { node: DiagramNode | null }) {
  if (!node) {
    return (
      <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Select a part of the diagram to see what it does and where its code is.
      </p>
    );
  }
  return (
    <aside aria-label={`Details: ${node.title}`} className="rounded-lg border border-border-subtle bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{node.title}</h3>
        <Badge tone="outline">{KIND_LABEL[node.kind]}</Badge>
        {node.status === "planned" && <Badge tone="warning">Planned, not built yet</Badge>}
      </div>
      <p className="mt-2 text-sm">{node.summary}</p>
      {node.links.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-muted-foreground">Where the code is</p>
          <ul className="mt-1 text-sm">
            {node.links.map((l) => (
              <li key={l}>
                <code className="rounded bg-surface-hover px-1.5 py-0.5 text-xs">{l}</code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
