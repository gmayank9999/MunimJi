"use client";

import { useMemo } from "react";
import { Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

export type RunPhase = "idle" | "sensing" | "processing" | "summarizing" | "done" | "failed";

const NODE_LAYERS: Record<string, string> = {
  supervisor: "Reasoning",
  sense: "Execution",
  invoices: "Policy",
  governance: "Execution",
  summary: "Reasoning",
};

function PhaseNode({ data }: NodeProps<Node<{ label: string; active: boolean; sub: string }>>) {
  return (
    <div
      className={`rounded-lg border px-3 py-2 text-center transition-colors ${
        data.active
          ? "border-saffron bg-saffron/10 text-foreground"
          : "border-border bg-surface text-muted"
      }`}
      style={{ width: 150 }}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <div className="text-xs font-semibold">{data.label}</div>
      <div className="text-[10px] uppercase tracking-wide opacity-70">{data.sub}</div>
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}

const NODE_TYPES = { phase: PhaseNode };

const BASE_NODES: { id: string; label: string; x: number }[] = [
  { id: "supervisor", label: "Supervisor", x: 0 },
  { id: "sense", label: "Sense", x: 190 },
  { id: "invoices", label: "Invoice Loop", x: 380 },
  { id: "governance", label: "Governance Gate", x: 570 },
  { id: "summary", label: "Summary", x: 760 },
];

const EDGES: Edge[] = [
  { id: "e1", source: "supervisor", target: "sense", animated: true },
  { id: "e2", source: "sense", target: "invoices", animated: true },
  { id: "e3", source: "invoices", target: "governance", animated: true },
  { id: "e4", source: "governance", target: "summary", animated: true },
];

const PHASE_TO_ACTIVE_NODE: Record<RunPhase, string | null> = {
  idle: null,
  sensing: "sense",
  processing: "invoices",
  summarizing: "summary",
  done: "summary",
  failed: null,
};

export function AgentGraphView({ phase }: { phase: RunPhase }) {
  const activeId = PHASE_TO_ACTIVE_NODE[phase];

  const nodes: Node[] = useMemo(
    () =>
      BASE_NODES.map((n) => ({
        id: n.id,
        type: "phase",
        position: { x: n.x, y: 0 },
        data: { label: n.label, sub: NODE_LAYERS[n.id], active: n.id === activeId },
        draggable: false,
        selectable: false,
      })),
    [activeId],
  );

  return (
    <div className="h-40 w-full">
      <ReactFlow
        nodes={nodes}
        edges={EDGES}
        nodeTypes={NODE_TYPES}
        fitView
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} color="var(--border)" />
      </ReactFlow>
    </div>
  );
}
