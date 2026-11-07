import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { ErrorNote } from "../components/ui";
import { useSession } from "../lib/session";

function ExampleProof() {
  return (
    <figure className="panel overflow-hidden shadow-[0_1px_0_#E3E6EC,0_12px_32px_-16px_rgba(22,33,58,0.25)]">
      <div className="flex items-center justify-between border-b border-paper-edge px-5 py-3 text-xs text-graphite-mute">
        <span>Advertisement copy, audited against Northstar Labs knowledge</span>
        <span className="chip bg-red-50 text-sev-critical ring-red-200">2 findings</span>
      </div>
      <div className="grid gap-0 md:grid-cols-[1fr_15rem]">
        <p className="manuscript px-6 py-7 text-[21px]">
          Our new product improves productivity <span className="mark mark-gap">by 50%</span> and is{" "}
          <span className="mark mark-gap">the best solution in the market</span>.
        </p>
        <div className="space-y-4 border-t border-paper-edge bg-paper/60 px-5 py-6 text-[13px] leading-5 md:border-l md:border-t-0">
          <div>
            <div className="font-medium text-ink">Unsupported numerical claim</div>
            <p className="text-graphite-mute">Unable to verify against approved knowledge. Cites Brand Guidelines v3, p. 3, Claims Policy.</p>
          </div>
          <div>
            <div className="font-medium text-ink">Unsubstantiated superlative</div>
            <p className="text-graphite-mute">Suggested edit: “a great solution”. Accept, edit or reject.</p>
          </div>
        </div>
      </div>
      <figcaption className="border-t border-paper-edge px-5 py-2.5 text-xs text-graphite-mute">
        This is the output the live engine produces for this sample. Wavy underline = evidence gap, not proof the claim is false.
      </figcaption>
    </figure>
  );
}

export default function Landing() {
  const { session, launchDemo, createWorkspace } = useSession();
  const nav = useNavigate();
  const [busy, setBusy] = useState<"demo" | "blank" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showBlank, setShowBlank] = useState(false);
  const [brand, setBrand] = useState("");

  async function demo() {
    setBusy("demo"); setErr(null);
    try { await launchDemo(); nav("/app/auditor"); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }
  async function blank(e: React.FormEvent) {
    e.preventDefault();
    if (!brand.trim()) return;
    setBusy("blank"); setErr(null);
    try { await createWorkspace(`${brand.trim()} workspace`, brand.trim()); nav("/app/knowledge"); }
    catch (e2) { setErr((e2 as Error).message); } finally { setBusy(null); }
  }

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        {session && <button className="btn-quiet" onClick={() => nav("/app/overview")}>Return to {session.brandName}</button>}
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 pb-16 pt-6 lg:grid-cols-[1fr_1.05fr] lg:pt-12">
        <div>
          <h1 className="max-w-xl text-[40px] font-semibold leading-[1.1] tracking-tight sm:text-[48px]">
            Check every claim against what your brand actually approved.
          </h1>
          <p className="mt-5 max-w-lg text-lg leading-7 text-graphite">
            BrandGuard reviews marketing content before it’s published. It checks terminology, product facts and claims
            against your approved knowledge. Each finding cites its source and comes with a small, editable fix.
            A person makes the final call.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button className="btn-primary px-5 py-2.5 text-[15px]" onClick={demo} disabled={busy !== null}>
              {busy === "demo" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
              Launch demo workspace
            </button>
            <button className="btn-quiet px-5 py-2.5 text-[15px]" onClick={() => setShowBlank((v) => !v)} disabled={busy !== null}>
              Start with my own brand
            </button>
          </div>
          <p className="mt-3 text-sm text-graphite-mute">No sign-up. The demo opens a private copy of a fictional brand, Northstar Labs, with sample content ready to audit.</p>
          {showBlank && (
            <form onSubmit={blank} className="mt-5 flex max-w-md gap-2">
              <label className="sr-only" htmlFor="brand">Brand name</label>
              <input id="brand" className="field" placeholder="Your brand name" value={brand} onChange={(e) => setBrand(e.target.value)} maxLength={120} />
              <button className="btn-ink shrink-0" disabled={!brand.trim() || busy !== null}>
                {busy === "blank" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />} Create workspace
              </button>
            </form>
          )}
          {err && <div className="mt-4 max-w-lg"><ErrorNote message={err} /></div>}
        </div>
        <ExampleProof />
      </section>

      <section className="border-t border-paper-edge bg-white">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 md:grid-cols-3">
          {[
            ["Approved knowledge in", "Admins upload brand guidelines and spec sheets, then approve facts and terminology. Documents are never trusted automatically."],
            ["Content checked", "Code-based rules catch exact violations. Claims are matched to approved facts, and an optional AI model adds context under strict validation."],
            ["A person decides", "Creators accept, edit or reject each fix, and every change becomes a new version. Reviewers approve or request changes, and every decision is logged."],
          ].map(([t, d], i) => (
            <div key={t}>
              <div className="mb-3 flex h-7 w-7 items-center justify-center rounded-full border border-paper-rule text-sm font-medium text-graphite">{i + 1}</div>
              <h2 className="text-lg font-semibold">{t}</h2>
              <p className="mt-1.5 text-graphite">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-14">
        <h2 className="text-xl font-semibold">What you can try in the demo</h2>
        <div className="mt-5 grid gap-x-10 gap-y-3 text-graphite sm:grid-cols-2">
          <p>Audit a compliant sample and see that it stays clean, with its figures verified against cited facts.</p>
          <p>Catch an outdated battery specification that was approved in v1 and replaced in v2.</p>
          <p>Open any citation to read the exact passage, page and document it came from.</p>
          <p>Accept a fix, then compare versions side by side. The original is never overwritten.</p>
          <p>Switch to Reviewer to request changes or approve. High-severity overrides need a reason.</p>
          <p>Upload a draft guideline that contains a hidden instruction and watch it get flagged.</p>
        </div>
        <p className="mt-10 border-t border-paper-edge pt-6 text-sm text-graphite-mute">
          BrandGuard AI by Team Khiladi 786 for CodeNexus India 2026. All demo brand data is synthetic. Findings are recommendations,
          and publication decisions stay with people.
        </p>
      </section>
    </div>
  );
}
