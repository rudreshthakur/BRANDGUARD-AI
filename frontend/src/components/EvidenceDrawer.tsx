import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { citation } from "../lib/format";
import type { Evidence } from "../lib/types";
import { Drawer, ErrorNote, Spinner } from "./ui";

interface EvidenceDetail extends Evidence {
  context: { source_id: string; chunks: { id: string; page: number | null; section: string | null; text: string }[] } | null;
  fact?: { statement: string; status: string; effective_date: string | null; superseded_by: string | null; value: number | null; unit: string | null };
  rule?: { kind: string; term: string; replacement: string | null; variants: string[]; severity: string; channels: string[] | null };
}

const typeLabel: Record<string, string> = {
  fact: "Approved fact", chunk: "Guideline passage", term: "Governance rule", setting: "Workspace setting", palette: "Brand palette colour",
};

function highlight(text: string, needle: string) {
  const n = needle.trim().slice(0, 80);
  const i = n ? text.indexOf(n) : -1;
  if (i < 0) return text;
  return (<>{text.slice(0, i)}<mark className="rounded bg-amber-100 px-0.5 text-ink">{text.slice(i, i + n.length)}</mark>{text.slice(i + n.length)}</>);
}

export function EvidenceDrawer({ evidenceId, onClose }: { evidenceId: string | null; onClose: () => void }) {
  const [data, setData] = useState<EvidenceDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!evidenceId) return;
    setData(null); setErr(null);
    api<EvidenceDetail>(`/knowledge/evidence/${encodeURIComponent(evidenceId)}`).then(setData).catch((e) => setErr(e.message));
  }, [evidenceId]);

  return (
    <Drawer open={!!evidenceId} onClose={onClose} title="Evidence">
      {!data && !err && <Spinner label="Opening source" />}
      {err && <ErrorNote message={err} />}
      {data && (
        <div className="space-y-6">
          <div>
            <div className="text-sm text-graphite-mute">{typeLabel[data.type] ?? data.type}</div>
            <div className="mt-1 text-lg font-semibold leading-snug">{citation(data)}</div>
            <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-1.5 text-sm">
              <dt className="text-graphite-mute">Evidence ID</dt><dd className="font-medium">{data.id}</dd>
              <dt className="text-graphite-mute">Status</dt>
              <dd className={data.status === "superseded" ? "font-medium text-ev-outdated" : "font-medium text-ev-ok"}>
                {data.status === "superseded" ? "Superseded — no longer authoritative" : "Approved and active"}
              </dd>
              {data.fact?.effective_date && (<><dt className="text-graphite-mute">Effective</dt><dd>{data.fact.effective_date}</dd></>)}
              {data.fact?.superseded_by && (<><dt className="text-graphite-mute">Replaced by</dt><dd>{data.fact.superseded_by}</dd></>)}
              {data.rule && (<><dt className="text-graphite-mute">Rule type</dt><dd className="capitalize">{data.rule.kind.replace("_", " ")}{data.rule.channels ? ` (${data.rule.channels.join(", ")} only)` : ""}</dd></>)}
            </dl>
          </div>
          <blockquote className="border-l-2 border-proof bg-paper px-4 py-3 font-serif text-[17px] leading-7 text-ink">{data.excerpt}</blockquote>
          {data.context && data.context.chunks.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold">From the source document</h3>
              <p className="text-xs text-graphite-mute">Extracted text from the approved document, shown as stored. The matching passage is highlighted where it appears.</p>
              <div className="mt-3 space-y-3">
                {data.context.chunks.map((c) => (
                  <div key={c.id} className="rounded-md border border-paper-edge p-3 text-sm leading-6">
                    <div className="mb-1 text-xs text-graphite-mute">{[c.page ? `Page ${c.page}` : null, c.section].filter(Boolean).join(", ")}</div>
                    <p className="text-graphite">{highlight(c.text, data.type === "chunk" ? "" : (data.fact?.statement.split(" ").slice(0, 3).join(" ") ?? data.rule?.term ?? ""))}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          <p className="text-xs text-graphite-mute">
            BrandGuard only shows evidence that exists in this workspace’s approved knowledge. It is reloaded from the database by ID every time, never copied from model output.
          </p>
        </div>
      )}
    </Drawer>
  );
}
