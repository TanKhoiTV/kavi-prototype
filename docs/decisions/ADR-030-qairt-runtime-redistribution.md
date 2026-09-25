# ADR-030: QAIRT runtime redistribution is permitted

## Status

Accepted — gate resolved 2026-07-19

## Date

2026-07-19

## Deciders

Project lead

## Context

[ADR-003](ADR-003-hexagon-runtime.md) selects QAIRT/QNN accessed through the
ONNX Runtime QNN Execution Provider as the NPU path, and
[ADR-019](ADR-019-qnn-runtime-bundling.md) requires the `libQnn*.so` runtime to be
**bundled in the APK** — because the target device's preinstalled runtime is not
in `/vendor/etc/public.libraries.txt` or `/system/etc/public.libraries.txt`, so a
third-party app cannot `dlopen` it directly (linker-namespace/SELinux).

Bundling a vendor runtime in a commercial closed-source APK is a licence question.
Until it was answered, the entire NPU path was blocked behind an "escalate to
Qualcomm" item — and with it the platform choice itself.

> **Split note (2026-09-25):** extracted from `license-situation.md` (now
> [ADR-029](ADR-029-license-gate.md)). This determination was a sub-section of the
> gate record, but it is a distinct, independently-reversible decision: had it gone
> the other way, the NPU path and much of the platform strategy would have
> collapsed to CPU-only. The PKLA analysis that confirms the same conclusion is
> retained below.

## Decision

**QAIRT → ADOPT (clean).** Bundle the QNN runtime in the APK; no Qualcomm
escalation is required.


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

The PKLA (Product Kit License Agreement) was signed when installing the Linux
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

- Unblocks the NPU path ([ADR-003](ADR-003-hexagon-runtime.md)) and the APK
  runtime bundling in [ADR-019](ADR-019-qnn-runtime-bundling.md) without vendor
  negotiation.
- Removes the largest open legal risk from the platform decision
  ([ADR-002](ADR-002-target-platform.md)).

### Negative / risk

- The grant is **revocable** (at-will 30-day termination, PKLA §7) — captured, not
  eliminated. Re-conversion or a fallback to CPU-only remains the mitigation.
- Standalone redistribution of the runtime is **not** permitted; only bundling
  inside the application is. This constrains how the runtime may be shipped.

## References

- [ADR-029](ADR-029-license-gate.md) — Shipping license gate (parent record)
- [ADR-003](ADR-003-hexagon-runtime.md) — Hexagon runtime / compiler strategy
- [ADR-019](ADR-019-qnn-runtime-bundling.md) — QNN runtime bundling (what this permits)
- [ADR-002](ADR-002-target-platform.md) — Target platform
