/** Split content into plain and marked segments for the redline manuscript view.
 *  Overlapping marks are resolved by priority: the first mark (highest severity) owns overlapping characters. */
export interface Mark { id: string; start: number; end: number; kind: string }
export interface Segment { text: string; mark: Mark | null }

export function segment(text: string, marks: Mark[]): Segment[] {
  const owner: (Mark | null)[] = new Array(text.length).fill(null);
  for (const m of marks) {
    const s = Math.max(0, m.start), e = Math.min(text.length, m.end);
    if (e <= s || text.slice(s, e).length === 0) continue;
    for (let i = s; i < e; i++) if (owner[i] === null) owner[i] = m;
  }
  const out: Segment[] = [];
  let i = 0;
  while (i < text.length) {
    const m = owner[i];
    let j = i + 1;
    while (j < text.length && owner[j] === m) j++;
    out.push({ text: text.slice(i, j), mark: m });
    i = j;
  }
  return out;
}
