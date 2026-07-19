# License Situation & Gate

**Status:** Proposed — clean/avoid resolved; **Piper engine GPL split (fork #1)
deferred** (MIT-era Piper is the clean option; GPL build not decided); **QAIRT
runtime ADOPT (clean) — gate resolved** (AI Stack License §1(iv) + §1(v); runtime
preinstalled on the 8 Gen 2, HTP v73, qnn-2.31; PKLA portal master agreement
signed 2026-07-19 confirms — see #46); **Hy-MT
ADOPT** (Vietnam contest, no blocked-region launch; 100M MAU = sky-high
ceiling). All dataset/voice licenses closed via Claude lookup (see #3 / #4 / #7).
This record **gates ADR-004 (architecture / tech-stack)**.
**Date:** 2026-07-15 (QAIRT gate resolved 2026-07-19)
**Author:** Project lead

---

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

## Decision

### Resolved now — no further action

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
| Data | PhoST | research/educational ONLY, no redistribution (VinAI terms) | was VI→EN corpus candidate in plan; now avoid for commercial |
| Voice | Piper `25hours_single` (VI) | **License: Unknown** — voice MODEL_CARD (verified 2026-07-18); trained on "InfoRe Technology 1" (InfoRe-derived) | AVOID — no license grant; do not ship |
| Data | InfoRe (vietTTS corpus) | no formal license; canonical `VINAI/InfoRe` is **gated** (HF HTTP 401, no published terms — verified 2026-07-18) | AVOID — no commercial grant; taints any voice trained on it |

### Open — policy forks (fork #1 requires a decision; fork #2 resolved)

1. **Piper engine — GPL split deferred.** MIT-era `rhasspy/piper` (frozen,
   archived Oct 2025) is a **licensed-clean option** (MIT) and can run via
   **subprocess isolation** so the GPL `espeak-ng`/engine never links into our
   binary. The GPL build `OHF-Voice/piper1-gpl` (GPL-3.0) is **deferred** — not
   decided now. **No tech-stack decision yet:** Piper (MIT-era) is one TTS
   *option* alongside MeloTTS (MIT) / Kokoro (Apache-2.0); the final pick waits
   for the benchmark harness. Shapes *all* TTS.
2. **Hy-MT1.5 regional carve-out — RESOLVED: ADOPT.** Contest is in
   **Vietnam**; no launch planned for the excluded regions (EU / UK / South
   Korea). The HY Community License therefore **permits commercial use** of
   Hy-MT1.5. The **100M MAU** threshold is noted as a **sky-high ceiling** (not
   a current concern) — if we ever approach it, a separate Tencent license is
   required. Outputs must not train non-Hunyuan models. Hy-MT is a usable MT
   candidate alongside Opus-MT / M2M-100.

### Open — verification lookups (facts pending, no judgment)

| # | Item | Status |
| --- | --- | --- |
| 3 | Piper VI voice licenses: `vais1000`, `25hours_single`, `vivos` | RESOLVED — `vais1000` = **CC BY 4.0** (ADOPT, attribution to VAIS/IEEE DataPort); `vivos` = CC BY-NC-SA (**AVOID**, confirmed); `25hours_single` = **License: Unknown** (voice MODEL_CARD, verified 2026-07-18; trained on InfoRe-derived data) → **AVOID** (no grant). |
| 4 | InfoRe donation / usage terms (vietTTS VI reference) | RESOLVED — **AVOID**. Informal donation with **no formal license, no commercial grant, no indemnification**; canonical `VINAI/InfoRe` is **gated** (HF HTTP 401, no published terms — verified 2026-07-18), only derivative community sets are public. Taints any voice trained on it (incl. `25hours_single`, `vivos`, reference vietTTS). Treat research-only. |
| 5 | VietSuperSpeech dataset license | RESOLVED — **MIT** (commercial-safe). Quality caveat: labels are Zipformer pseudo-labeled, not gold. |
| 6 | PhoST dataset license | RESOLVED — **research/educational ONLY, no redistribution** (VinAI terms). → AVOID for commercial; was a VI→EN corpus candidate in the plan. |
| 7 | QAIRT / Qualcomm AI Hub commercial terms | **RESOLVED — ADOPT (clean)**. `qai_hub_models` pip = **BSD-3**. AI Hub compile is free today but revocable (build-time only; runtime stays offline). QAIRT **runtime** is governed by the **AI Stack License (QTI)** §1(iv) (royalty-free object-code redistribution within the app) + §1(v) (benchmarking); preinstalled + version-matched on the 8 Gen 2 (qnn-2.31 / HTP v73). **No escalation required.** See "Resolved — QAIRT runtime redistribution (2026-07-19)". |
| 8 | Whisper exact license | RESOLVED — **MIT** (plan's 'Apache-2.0' note was wrong). |
| 9 | PKLA (portal master agreement, signed 2026-07-19) vs AI Stack License | RESOLVED — PKLA does **not** reopen the QAIRT ADOPT (clean) gate; §2.1(b) confirms object-code bundling, conditional fee sections (§2.3(a)/§2.5/§2.6) don't apply to the royalty-free AI Stack kit, §3.6/§3.10 satisfied. See "PKLA (portal master agreement, signed 2026-07-19)". Tracking #46. |

### Resolved — QAIRT runtime redistribution (2026-07-19)

The "escalate to Qualcomm" blocker is **closed**. The operative license is the
**AI Stack License (QTI)** shipped in the SDK install (`LICENSE.pdf`):

+ **§1(iv)** grants a royalty-free, non-exclusive license to **distribute and
  sublicense the Software (the QNN runtime) in object code, as incorporated in
  Your software application** — i.e. we may bundle `libQnn*.so` in the Kavi APK.
  Standalone redistribution is not permitted (we don't do that).
+ **§1(v)** explicitly permits **benchmarking** — covers the whole harness.
+ **Export (§10(f))**: Vietnam is not embargoed/restricted; Kavi is not a
  military/supercomputer/semiconductor end-use. **Export-clear.**
+ **Use-case (§2(d)/(e))**: Kavi (assistive speech translation) is not an
  unacceptable- or high-risk application. **Clear.**
+ **Third-party (§10(h), `QNN_NOTICE.txt`)**: stack is permissive (Apache-2.0,
  MIT, BSD, Boost, zlib, LLVM-exception, Unlicense) + **MPL-2.0**; the only
  copyleft is **Eigen LGPL-2.1**, confined to the **host build tools** (header
  lib used by the converters), **not** the on-device runtime. No GPL anywhere.

**Device verification (Meizu 21 Note, 2026-07-19):** the runtime is
**preinstalled** on the target — `/system/lib64/libQnnHtp.so`,
`libQnnHtpV73.so`, and a full `/system/lib64/qnn/qnn-2.31/` tree (Cpu, Dsp, Gpu,
HTP v73, Ir, Lpai, ModelDlc, System). `qnn-2.31` matches our locally-installed
QAIRT **2.31.0.250130**, and `libQnnHtpV73.so` confirms **HTP v73** (ADR-002).
Because `libQnn*.so` is **not** listed in `/vendor/etc/public.libraries.txt` or
`/system/etc/public.libraries.txt`, a third-party app cannot `dlopen` the
device runtime directly (linker-namespace/SELinux) — so we **bundle** the runtime
`.so` in the APK, which §1(iv) permits. `libadsprpc.so`/`libcdsprpc.so` (FastRPC
transport to the DSP) **are** public, so the HTP path is reachable.

**Verdict:** QAIRT → **ADOPT (clean)**. No Qualcomm escalation required. The
runtime is both preinstalled (version-matched) and freely redistributable in
object code within the app.

### PKLA (portal master agreement, signed 2026-07-19) — confirms the gate

The PKLA (Product License Key Agreement) was signed when installing the Linux
QAIRT 2.31.0.250130 SDK via QPM. It is the **portal master agreement** that sits
above the AI Stack License (`LICENSE.pdf`) shipped in the SDK. It does **not**
reopen the ADOPT (clean) gate — it affirms the bundling right and adds only
*conditional* obligations that do not apply to the AI Stack:

+ **§2.1(b) License Grant** — *"distribute and sublicense … the Object Code of
  Licensed Software as bundled … into LICENSEE Products"* — confirms the AI
  Stack License §1(iv) bundling right (we may ship `libQnn*.so` in the APK).
+ **§2.3(a) Software License Fee / §2.5 fee-bearing kits / §2.6 Revenue Share**
  are **conditional** ("if a PKLA Product Kit includes … fee-bearing Licensed
  Software"). They apply only to fee-bearing / revenue-share kits. The AI Stack
  is represented as **royalty-free** (its own `LICENSE.pdf`), so they should not
  apply to Kavi. **Verify the kit is non-fee-bearing before commercial launch.**
+ **§3.6 Open Source Prohibition** — do not contribute the Licensed Software to
  an OSS project; ship the `Notice File`; this Agreement controls on conflict.
  Does **not** forbid shipping a product that also contains MIT/Apache code.
  Satisfied: we bundle unmodified object code and never upstream it.
+ **§3.10 / §3.11 Unacceptable / High-Risk** — biometric ID, social scoring,
  etc. Kavi (speech-to-speech translation, **not** biometric ID, no consequential
  decision) is **not** high / unacceptable-risk.
+ **Export (§13.3)** — Vietnam not restricted (consistent with prior finding).
+ Grant is **revocable** (at-will 30-day termination, §7) — already captured.

The PKLA text is **Confidential** and is kept local (not committed), per project
rule. Tracking issue: #46.

## Consequences

### Positive

+ De-risks ADR-004 **before** the benchmark harness runs — most candidates
  are already license-decided.
+ The adopt/avoid lists let us wire candidates into the harness with no legal
  ambiguity.

### Negative / risk

+ The two policy forks can force a **late TTS/MT swap** if resolved against the
  current picks.
+ Eval-only NC datasets are easy to **accidentally bundle** — enforce in the
  harness data-prep step.

## Open items → ADR-004

ADR-004 (architecture / tech-stack) records the licensed-clean candidate set
but **defers the final tech-stack pick** until the v0 benchmark harness runs.
Remaining gates: **Piper engine GPL split** (deferred — MIT-era is the clean
option), and harness confirmation that the CPU-default stack is license-clean.
The **QAIRT runtime gate is RESOLVED** (ADOPT, clean — see above). Lookups #3–#8
are closed or advanced. Candidate shortlist in `docs/benchmarking-plan.md` §4
stands, with the avoid-list already dropped.

## References

+ `docs/benchmarking-plan.md` §3.6 (license watch-outs), §4.4 (MT), §4.5 (TTS).
+ `docs/onboarding.md` (commercial-clean vs avoid rule).
+ ADR-001 / 002 / 003.
+ **Corrections to `docs/benchmarking-plan.md`** (this record supersedes): §3.3 / §3.6 — VietSuperSpeech is **MIT** (not "verify"); PhoST is **research-only, no redistribution** (not "verify") → move to avoid; §4.1 — Whisper is **MIT** (plan's "Apache-2.0" is wrong).
