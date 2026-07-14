# ADR-001: Prioritize Hy-MT1.5 over NLLB-600M for Machine Translation

**Status:** Accepted  
**Date:** 2026-06-14  
**Author:** Project lead  

---

## Context

The OneVoice AI Challenge entry originally planned to use **NLLB-600M int8** (Meta) as the Machine Translation layer. During pre-registration research (June 12–13, 2026), two problems emerged:

1. **License conflict:** NLLB-600M is licensed under CC-BY-NC-4.0 (non-commercial). The competition offers a $20,000 first prize and commercial partnership/incubation paths, creating a potential IP incompatibility.
2. **Better alternative discovered:** Tencent released **Hy-MT1.5-1.8B-1.25bit** (April 29, 2026), a 440MB model covering 33 languages and all three contest language pairs (VI↔EN, VI↔ZH, VI↔KO) in a single model.

### Hy-MT1.5 key facts

| Attribute | Value |
|-----------|-------|
| Size | 440MB (1.25-bit quantization via Sherry framework, ACL 2026) |
| Coverage | 33 languages, 1,056 translation directions |
| Quality | Surpasses Tower-Plus-72B and Qwen3-32B on Flores-200 |
| On-device precedent | Tested on Snapdragon 888 with 8x speedup over FP16; real Android APK exists |
| License | Tencent HY Community License — permits commercial use |
| Tradeoff | CPU-only (custom STQ kernel), no NPU acceleration path yet |

---

## Decision

**Hy-MT1.5 is the sole production MT model.** NLLB-600M is excluded from the production pipeline entirely and used only as a **benchmark reference** for translation quality comparisons (BLEU/chrF on FLORES-200). No fallback path, no NPU fallback plan — Hy-MT's CPU-only path is the primary and only path.

### Rationale for removing NLLB entirely

- **Zero licensing stress:** No need to argue whether contest participation, prize winnings, or commercial partnership count as "commercial use" under CC-BY-NC-4.0
- **Simpler stack:** One translation model, one execution path, no conditional routing logic
- **Sufficient quality margin:** Hy-MT1.5 surpasses 72B-class models — the quality gap over NLLB is positive, not negative
- **Latency confidence:** Even CPU-only, the estimated ~400-800ms for Hy-MT fits within the 2s budget alongside all other pipeline stages (~915ms-1.5s total). SD8G2 is faster than the SD888 it was tested on.

---

## Consequences

### Positive

- Completely eliminates the CC-BY-NC license risk that was flagged in §5.4 of architecture.md as unresolved
- Single model covers all three language pairs, simplifying routing logic
- Higher reported quality than the NLLB class on Flores-200 benchmarks
- Smaller total model footprint (440MB vs NLLB-600M's 600MB+)
- One less thing to worry about during the 11-day sprint

### Negative

- **CPU-only** execution (custom STQ quantization kernel) — no NPU acceleration path. Estimated ~200-400ms slower than an NPU-accelerated alternative
- Unknown latency on SD8G2 specifically (tested on SD888, not SD8G2)
- Less community prior art than NLLB (RTranslator, various demos)
- Thermal degradation may affect CPU inference more than NPU inference

### Risk mitigation

- The latency budget in §4.1 has ~200ms headroom (total 800ms–1.3s vs 2s requirement). CPU-only Hy-MT estimated at 400-800ms still fits
- SD8G2 has faster CPU cores than SD888 (Cortex-X3 vs X2) — Hy-MT may actually be faster than published numbers
- Phase 2 profiling on the actual device will reveal real latency; if Hy-MT breaks the budget, architectural alternatives exist (model parallelism, speculative decoding) before touching NLLB
- NLLB remains available as a benchmark reference if needed for judge Q&A about baseline comparisons

---

## Reference

- Hy-MT1.5 announcement: Tencent (April 29, 2026)
- NLLB license: CC-BY-NC-4.0
- Architecture doc §5.4 (original NLLB entry with flagged license concern)
- Architecture doc §8.4 (latency budget targets)
- Registration checklist — Tech Research Findings section
