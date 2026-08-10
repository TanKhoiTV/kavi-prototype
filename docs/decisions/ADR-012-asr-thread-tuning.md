# ADR-012: ASR Thread Tuning Strategy for SD8G2

## Status

Proposed

## Date

2026-08-10

## Context

The Kavi on-device speech-to-speech pipeline runs two Zipformer ASR models concurrently via Kotlin `async` on `Dispatchers.Default`. Each `OfflineRecognizer(numThreads=4)` spawns a native C++ thread pool for ONNX Runtime inference. On the target device (Meizu 21 Note, Snapdragon 8 Gen 2 / SM8550):

- **8 cores, no SMT:** 1× Cortex-X3 (prime) @ 3.2 GHz + 2× Cortex-A715 (performance) @ 2.8 GHz + 2× Cortex-A710 (performance) @ 2.8 GHz + 3× Cortex-A510 (efficiency) @ 2.0 GHz
- **4+4 = 8 native threads** + 2 Kotlin coroutines = **10 threads competing for 8 cores** during the ASR stage
- **Zero headroom** for OS, `AudioRecord`, UI thread, and background services

The hard gate is **RTF ≤ 0.05** on-device (ADR-008, open item line 337). If OS contention preempts an inference thread, RTF degrades and the 2.0s turnaround budget (`.kavi.yaml:182`) is at risk.

Two risks compete:

| Risk | Mechanism | Evidence |
|------|-----------|----------|
| **Oversubscription** | 10 threads on 8 cores → OS preempts inference → RTF jitter | Current config assumes 1:1 core mapping with no validation |
| **Scheduler misplacement** | OS schedules inference threads on efficiency cores (A510) → 2.0 GHz vs 3.2 GHz → up to 2× latency variance | big.LITTLE scheduling is opaque; no guarantee of performance-core placement |

A proposal on PR #97 (winterSolstice25) suggested hard CPU affinity pinning to solve both — but introduces a third risk:

| Risk | Mechanism |
|------|-----------|
| **Affinity fragility** | If the pinned cores are busy (e.g., audio processing already there), threads are stuck on busy cores with no migration fallback. SELinux may block `sched_setaffinity()` on some devices. |

## Decision

Adopt a **two-build strategy** with a custom C++ thread pool abstraction that supports both modes, toggled at runtime.

### Build B (default production config)

- Custom thread pool with `Mode::kPriorityHint`
- `THREAD_PRIORITY_URGENT_AUDIO` on all inference threads
- 3+3 threads (leaves 2 cores for OS/UI/audio)
- This IS the production config if RTF ≤ 0.05 passes — no migration needed

### Build F (escalation path — only if Build B fails in a specific way)

- Trigger: Build B passes RTF ≤ 0.05 BUT shows unacceptable jitter traced to scheduler misplacement on efficiency cores
- Switch to `Mode::kHardAffinity`, pin to A715+A710 performance cores
- **Static 2+2 pinning** — one thread per dedicated core, 4 threads on 4 cores (1:1 ratio). This is the only hard-affinity configuration that delivers actual determinism.
- Keep fallback to `kPriorityHint` if affinity fails (SELinux, core busy, thermal throttling)
- Do NOT use Build F if Build B passes cleanly — the 2 free cores and thermal resilience of priority-hint are strictly better

### Thread pool abstraction

```cpp
class ThreadPool {
public:
    enum class Mode { kPriorityHint, kHardAffinity };

    void SetMode(Mode mode);
    void SetPreferredCores(const std::vector<int>& cores);  // A715+A710 core IDs (4–7 — PLACEHOLDER, unconfirmed)
    // Uses sched_setaffinity() (API 14+) via gettid() — no pthread_setaffinity_np() dependency

private:
    std::vector<std::jthread> workers_;
    Mode mode_;
    std::vector<int> preferred_cores_;
};
```

### Affinity implementation

```cpp
#include <sched.h>
#include <unistd.h>

cpu_set_t cpuset;
CPU_ZERO(&cpuset);
// PLACEHOLDER — core IDs 4–7 are unconfirmed (see Open Question #1).
// Must probe at runtime on the Meizu 21 Note before shipping Build F.
CPU_SET(4, &cpuset);  // asserted A715+A710 performance cores
CPU_SET(5, &cpuset);
CPU_SET(6, &cpuset);
CPU_SET(7, &cpuset);

// sched_setaffinity() via <sched.h> — available since API 14 (2011).
// Source: Android NDK <sched.h> __ANDROID_API__ gate (#if __ANDROID_API__ >= 14).
// pthread_setaffinity_np() is just a thin wrapper around this syscall
//   (requires API 36 — #if __ANDROID_API__ >= 36 — which is why we avoid it).
pid_t tid = gettid();
sched_setaffinity(tid, sizeof(cpuset), &cpuset);
```

### Thermal fallback

Static 2+2 pinning means sustained continuous load on the two pinned cores — no thermal migration relief from the OS governor. Primary fallback signal: `PowerManager.getCurrentThermalStatus()` / `addThermalStatusListener()` (API 29+). On `SEVERE` or above, fall back to `kPriorityHint`. Treat cpufreq sysfs reads as an optional finer-grained signal if readable on this device.

### A/B test logging

Run 100 utterances per mode. For each utterance, log:

- RTF (wall-clock inference time / audio duration)
- `PowerManager.getCurrentThermalStatus()` (NONE / LIGHT / MODERATE / SEVERE / CRITICAL / EMERGENCY / SHUTDOWN)
- Per-core temperature via `ThermalManager.getTemperature()` (API 30+) if available
- Optional: per-core `scaling_cur_freq` from sysfs if readable

**Why:** A pinned run that wins on P50/P95 RTF for the first 20 utterances but thermal-throttles by utterance 60 must not get misread as the better mode.

## Alternatives Considered

### Priority-hint only (current `.kavi.yaml` stance)

- **Pros:** No root needed, no SELinux risk, scheduler retains flexibility
- **Cons:** No guarantee of performance-core placement; scheduler may still place threads on efficiency cores under load

### Hard affinity to all 4 performance cores (winterSolstice25's proposal)

- **Pros:** Deterministic core placement; reserves Prime + Efficiency for UI/OS
- **Cons:** Risky if pinned cores are busy; SELinux may block; no migration fallback; requires per-device core ID probing

### 4+4 on shared cores (8 threads on 4 performance cores)

- **Pros:** Keeps thread count high for throughput
- **Cons:** 2:1 oversubscription — worse than the original 10-on-8 problem. Throws away the determinism that hard affinity was supposed to buy.
- **Rejected:** The entire value proposition of hard affinity is predictable core placement with no contention.

### 3+3 with time-sharing on 2+2 cores

- **Pros:** Keeps thread count from the priority-hint experiment
- **Cons:** Loses determinism — the thing hard affinity was supposed to buy.
- **Rejected:** Time-sharing on fewer cores than threads reintroduces the jitter problem.

## Open Questions

1. **Core ID mapping:** Which Linux core IDs map to A715 vs A510 on the SD8G2? Must probe at runtime — cannot hardcode. The 4–7 = performance-core mapping is asserted but NOT validated on the Meizu 21 Note. Build F cannot ship until this mapping is confirmed empirically.
2. **SELinux policy:** Does `sched_setaffinity()` require special SELinux permissions on the Meizu 21 Note? The call may be overridden by Android's cgroup-based thread management.
3. **Audio thread placement:** `AudioRecord` runs on a high-priority audio framework thread — we don't control its core. If it lands on a performance core we've pinned to, contention is unavoidable. **Defer** — revisit only if Build F is triggered.
4. **cgroup interaction:** Android 10+ uses cgroups (schedtune, cpuset) for thread placement. `SetTaskProfiles(tid, {"MaxPerformance"})` joins the `top-app` cgroup, which hints the scheduler to prefer performance cores. This may conflict with or complement `sched_setaffinity()` — needs empirical testing.
5. **C++20 `std::jthread` support:** The ThreadPool sketch uses `std::jthread` (C++20). `jthread`/`stop_token` support depends on the NDK's libc++ version and `minSdkVersion`. Confirm NDK r26c + libc++ supports `std::jthread` on min supported API level before adopting.
6. **Thermal throttling under static 2+2 pinning:** Static pinning means the OS governor cannot migrate threads away from overheating cores. If the SoC thermal-throttles the two pinned cores, RTF degrades with no relief. See thermal fallback strategy above.
7. **Coroutine thread accounting:** Are the 2 Kotlin `async` coroutines genuinely block-waiting on the native pool (cheap, doesn't count against the CPU budget), or do they perform real work on the dispatcher thread? The Build B headroom rationale ("6 active threads on 8 cores = 2 free") hinges on the former. Validate by profiling coroutine CPU time during inference.

## Consequences

### Positive

- Build B (3+3 + `THREAD_PRIORITY_URGENT_AUDIO`) is the production config unless proven otherwise — 2 free cores for OS/UI/audio + thermal resilience
- Custom thread pool centralizes thread lifecycle management and enables runtime mode switching
- Build F escalation path preserves deterministic core placement as an option if empirical evidence justifies it
- `sched_setaffinity()` available since API 14 — no dependency on API 36 or `pthread_setaffinity_np()`

### Negative / risk

- Core ID mapping is unconfirmed — Build F cannot ship until runtime probe validates which IDs are performance cores
- Hard affinity risks pinning threads to busy cores, making latency *worse* — only justified if Build B shows scheduler misplacement
- Affinity is a one-way door: once pinned, you can't easily move threads if the device is under unexpected load
- `AudioRecord` thread placement is out of our control — if it lands on a pinned core, contention is unavoidable (deferred risk)

## References

- ADR-007: Production Inference Architecture (parent architecture — threading decisions in context of overall pipeline)
- ADR-008: v1 Android ASR Decision — Dual Zipformer (RTF 0.011 desktop benchmark, go/no-go gate at RTF > 0.05, streaming transducer architecture)
- ADR-002: Target Platform — Snapdragon 8 Gen 2, Android 16
- `.kavi.yaml` — single source of truth for pinned config values (`rtf: 0.05`, `turnaround_gate_sec: 2.0`, thread tuning params)
- PR #97 (Kotlin+C++ implementation plan) — winterSolstice25's hard affinity proposal
- PR #98 (.kavi.yaml) — aFlyingSeal's review findings on config contradictions
- [sherpa-onnx Zipformer transducer models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.html) — RTF 0.011 desktop benchmark source
