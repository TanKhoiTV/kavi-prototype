# ADR-029: Shipping license gate — adopt/avoid verdicts

## Status

Accepted — the gate is in force; one policy fork remains open
([ADR-031](ADR-031-piper-engine-gpl-split.md))

## Date

2026-07-15 (QAIRT gate resolved 2026-07-19)

## Deciders

Project lead

## Context


Kavi is a **commercial product** (OneVoice contest → product). We **ship a
binary that bundles three independent license layers**, so all three must permit
closed-source commercial distribution:

1. **Model weights** (ASR / MT / TTS) — each has its own license.
2. **Engine / runtime code** (whisper.cpp, CTranslate2, Piper, ORT/QNN) —
   each its own license.
3. **SDK / toolchain** (QAIRT Community Edition, Qualcomm AI Hub) — separate
   from the models.

One **copyleft (GPL)** or **non-commercial (CC-BY-NC / CPML)** item anywhere
in the shipped stack is **disqualifying** unless isolated (subprocess, not linked)
or dropped.

Two nuances:

+ **Eval-time vs ship-time.** NC datasets (VIVOS, viVoice, NOISEX-92) are fine
  to *evaluate* internally; they are forbidden to *bundle* in the shipped app.
+ **Public parent must stay clean.** `aivoice-2026` (public) can host only
  CC0 / CC-BY / permissive content — never NC weights or data.

> **Split note (2026-09-25):** this record was the unnumbered
> `license-situation.md`, and held the whole license position in one file —
> the gate, the verdict tables, the resolved lookups, **and** two substantive
> determinations plus a deferred fork. It is now numbered and split:
> [ADR-030](ADR-030-qairt-runtime-redistribution.md) records the QAIRT runtime
> redistribution determination (with its PKLA confirmation), and
> [ADR-031](ADR-031-piper-engine-gpl-split.md) records the still-open Piper engine
> GPL fork. The resolved **lookups** remain here as reference tables — they are
> licence facts, not decisions.

## Decision


**Adopt (commercial-safe):**

| Layer | Component | License | Basis |
| --- | --- | --- | --- |
| ASR | Whisper Small | MIT | OpenAI Whisper — confirmed MIT; the plan's 'Apache-2.0' note was wrong |
| ASR | PhoWhisper Small | BSD-3 | same arch as Whisper Small |
| ASR | Zipformer-30M-VI | Apache-2.0 | |
| ASR | Moonshine Tiny VI | Apache-2.0 | |
| ASR | Silero VAD | MIT | `silero-vad` dep |
| MT | Opus-MT (vi-en + en-vi) | Apache-2.0 | current prototype |
| MT | M2M-100 | MIT | realistic finalist vs Opus-MT |
| MT | MADLAD-400 | Apache-2.0 | size-blocked, not license |
| TTS | MeloTTS | MIT | AI-Hub-backed EN/ZH/ES; VI needs self-export |
| TTS | Kokoro | Apache-2.0 | EN-leg only (no VI confirmed) |
| TTS | SpeechT5 | MIT | EN only (needs VI fine-tune) |
| TTS voice | Piper `vais1000` (VI) | CC BY 4.0 | attribution required (VAIS/IEEE DataPort); clean VI voice |
| TTS engine | Piper (MIT-era `rhasspy/piper`) | MIT | **option**; run via subprocess isolation; GPL build (`OHF-Voice/piper1-gpl`) deferred |
| SDK | QAIRT Community Edition | free for contest | via free Qualcomm ID; AI Hub build-time only |
| Data (eval-only) | VIVOS, viVoice, NOISEX-92 | NC / ambiguous | internal eval, never bundle |
| Data (public-safe) | Common Voice (CC0), LibriSpeech/FLEURS/LibriTTS (CC-BY-4.0), MUSAN (PD), RIRS_NOISES (CC-BY-4.0), DEMAND (CC-BY-SA-3.0), VietSuperSpeech (MIT; labels Zipformer pseudo-labeled, not gold) | various | credit / share-alike as noted; VSS usable but verify labels |

**Avoid (blocked):**

| Layer | Component | License | Why |
| --- | --- | --- | --- |
| MT | NLLB-200-distilled-600M | CC-BY-NC-4.0 | non-commercial |
| MT | SeamlessM4T v2 | CC-BY-NC-4.0 | non-commercial |
| TTS | MMS-TTS-vie | CC-BY-NC-4.0 | non-commercial |
| TTS | Coqui XTTS v2 | CPML + Coqui shut down | non-commercial + no licensor |
| Voice | Piper `vivos` (VI) | inherits VIVOS CC-BY-NC-SA | do not ship |
| Data | PhoST | **research or educational purposes ONLY**; no distribution (VinAI terms) | **AVOID** to ship/redistribute or build the product on it. *Internal benchmarking* (eval-only, no redistribute) is lower-risk — but the "research/educational only" purpose clause is the catch: a **commercial contest** may fall outside it. Also **EN→VI only**, so it does not serve Kavi's **VI→EN** v0 benchmark (use FLEURS CC BY-4.0 + bespoke gold set). Cite INTERSPEECH 2022 if published. |
| Voice | Piper `25hours_single` (VI) | **License: Unknown** — voice MODEL_CARD (verified 2026-07-18); trained on "InfoRe Technology 1" (InfoRe-derived) | AVOID — no license grant; do not ship |
| Data | InfoRe (vietTTS corpus) | no formal license; canonical `VINAI/InfoRe` is **gated** (HF HTTP 401, no published terms — verified 2026-07-18) | AVOID — no commercial grant; taints any voice trained on it |

**Fork #2 — Hy-MT1.5 regional carve-out: ADOPT (resolved).** The contest is in
**Vietnam**; no launch is planned for the excluded regions (EU / UK / South
Korea). The HY Community License therefore **permits commercial use** of
Hy-MT1.5. The **100M MAU** threshold is noted as a **sky-high ceiling** (not a
current concern) — approaching it would require a separate Tencent license.
Outputs must not train non-Hunyuan models. Hy-MT is a usable MT candidate
alongside Opus-MT / M2M-100.

### Verification lookups (licence facts, resolved)

| # | Item | Status |
| --- | --- | --- |
| 3 | Piper VI voice licenses: `vais1000`, `25hours_single`, `vivos` | RESOLVED — `vais1000` = **CC BY 4.0** (ADOPT, attribution to VAIS/IEEE DataPort); `vivos` = CC BY-NC-SA (**AVOID**, confirmed); `25hours_single` = **License: Unknown** (voice MODEL_CARD, verified 2026-07-18; trained on InfoRe-derived data) → **AVOID** (no grant). |
| 4 | InfoRe donation / usage terms (vietTTS VI reference) | RESOLVED — **AVOID**. Informal donation with **no formal license, no commercial grant, no indemnification**; canonical `VINAI/InfoRe` is **gated** (HF HTTP 401, no published terms — verified 2026-07-18), only derivative community sets are public. Taints any voice trained on it (incl. `25hours_single`, `vivos`, reference vietTTS). Treat research-only. |
| 5 | VietSuperSpeech dataset license | RESOLVED — **MIT** (commercial-safe). Quality caveat: labels are Zipformer pseudo-labeled, not gold. |
| 6 | PhoST dataset license | RESOLVED (lookup complete) — VinAI terms: **research or educational purposes ONLY**, **no distribution** (original or modified), cite INTERSPEECH 2022 if published. **AVOID** to ship/redistribute the dataset or build the product on it. *Internal benchmarking* (evaluate models without redistributing) is lower-risk — but the "research/educational only" purpose clause is the catch: a **commercial contest** may sit outside it. PhoST is **EN→VI only**, so it does **not** serve Kavi's **VI→EN** v0 benchmark; FLEURS (CC BY-4.0) + a bespoke gold set are the v0 corpora. Moot for v0. |
| 7 | QAIRT / Qualcomm AI Hub commercial terms | **RESOLVED — ADOPT (clean)**. `qai_hub_models` pip = **BSD-3**. AI Hub compile is free today but revocable (build-time only; runtime stays offline). QAIRT **runtime** is governed by the **AI Stack License (QTI)** §1(iv) (royalty-free object-code redistribution within the app) + §1(v) (benchmarking); preinstalled + version-matched on the 8 Gen 2 (qnn-2.31 / HTP v73). **No escalation required.** See "Resolved — QAIRT runtime redistribution (2026-07-19)". |
| 8 | Whisper exact license | RESOLVED — **MIT** (plan's 'Apache-2.0' note was wrong). |
| 9 | PKLA (portal master agreement, signed 2026-07-19) vs AI Stack License | RESOLVED — PKLA does **not** reopen the QAIRT ADOPT (clean) gate; §2.1(b) confirms object-code bundling, conditional fee sections (§2.3(a)/§2.5/§2.6) don't apply to the royalty-free AI Stack kit, §3.6/§3.10 satisfied. See "PKLA (portal master agreement, signed 2026-07-19)". Tracking #46. |

### Open policy fork

**Piper engine — GPL split.** Deferred to
**[ADR-031](ADR-031-piper-engine-gpl-split.md)**. This fork shapes all of TTS; a
late resolution is the main route to a forced TTS swap.

## Consequences

### Positive


+ De-risks ADR-004 **before** the benchmark harness runs — most candidates
  are already license-decided.
+ The adopt/avoid lists let us wire candidates into the harness with no legal
  ambiguity.

- The QAIRT runtime gate is resolved (see
  [ADR-030](ADR-030-qairt-runtime-redistribution.md)), which unblocks the NPU path
  ([ADR-003](ADR-003-hexagon-runtime.md)).

### Negative / risk


+ The two policy forks can force a **late TTS/MT swap** if resolved against the
  current picks.
+ Eval-only NC datasets are easy to **accidentally bundle** — enforce in the
  harness data-prep step.
- The open Piper fork can force a **late TTS swap** if resolved against the
  current picks ([ADR-031](ADR-031-piper-engine-gpl-split.md)).

## Open items


ADR-004 (architecture / tech-stack) records the licensed-clean candidate set
but **defers the final tech-stack pick** until the v0 benchmark harness runs.
Remaining gates: **Piper engine GPL split** (deferred — MIT-era is the clean
option), and harness confirmation that the CPU-default stack is license-clean.
The **QAIRT runtime gate is RESOLVED** (ADOPT, clean — see above). Lookups #3–#8
are closed or advanced. Candidate shortlist in `docs/reference/benchmarking-plan.md` §4
stands, with the avoid-list already dropped.


**Updated (2026-09-25):** the QAIRT runtime gate is resolved in
[ADR-030](ADR-030-qairt-runtime-redistribution.md); the Piper engine fork is
[ADR-031](ADR-031-piper-engine-gpl-split.md).

## References


+ `docs/reference/benchmarking-plan.md` §3.6 (license watch-outs), §4.4 (MT), §4.5 (TTS).
+ `docs/onboarding.md` (commercial-clean vs avoid rule).
+ ADR-001 / 002 / 003.
+ **Corrections to `docs/reference/benchmarking-plan.md`** (this record supersedes): §3.3 / §3.6 — VietSuperSpeech is **MIT** (not "verify"); PhoST is **research-only, no redistribution** (not "verify") → move to avoid; §4.1 — Whisper is **MIT** (plan's "Apache-2.0" is wrong).
