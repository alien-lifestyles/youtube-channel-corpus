# Channel analysis prompt

Use this after a scrape. Point the model at `data/<channel>/videos/` (markdown files) and `index.csv`.

---

You are analyzing a YouTube creator's public body of work. I will give you transcripts and metadata from their channel.

Your job is to extract a **voice and worldview brief**, not a video summary.

## What to look for

1. **Beliefs** — claims they treat as true. Separate core beliefs (repeated across many videos) from one-off opinions.
2. **Values** — what they praise, protect, or attack. What “good” and “bad” look like in their world.
3. **Frameworks** — named models, steps, acronyms, metaphors they reuse. Quote the label they use.
4. **Storytelling** — how a typical video is structured (hook, tension, turn, CTA). Recurring story types (origin, cautionary, conversion, teardown).
5. **Language** — signature phrases, metaphors, audience address (“you”, “we”), humor style.
6. **Contradictions / evolution** — ideas that changed over time. Use upload dates.

## How to cite

- Always cite **video title + URL + timestamp** (from the `[m:ss]` transcript lines).
- Prefer patterns that show up in **3+ videos**. Flag one-offs separately.
- Use `index.csv` for volume: views, duration, upload date. Weight recurring ideas in high-view videos, but do not ignore older low-view videos if they state a framework clearly.

## Output

Write:

1. **One-paragraph thesis** of who this creator is and what they are trying to do to the viewer.
2. **Beliefs** (bullet list, each with 2–3 citations).
3. **Values** (same).
4. **Frameworks** (name, 1–2 sentence explanation, citations).
5. **Storytelling pattern** (typical arc + 2 example videos).
6. **Phrase bank** — 10–20 characteristic lines, verbatim.
7. **Gaps** — what they never talk about, or talk around.

Do not flatten them into generic “thought leadership.” Keep their specific language.
