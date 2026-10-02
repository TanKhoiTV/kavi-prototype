# ADR-012: ASR Thread Tuning Strategy for SD8G2

## Status

Proposed

## Date

2026-08-10

## Deciders

Kavi team

## Context

The Kavi on-device speech-to-speech pipeline runs two Zipformer ASR models concurrently via Kotlin `async` on `Dispatchers.Default`. Each `OfflineRecognizer` spawns a native C++ thread pool for ONNX Runtime inference. On the target device (Meizu 21 Note, Snapdragon 8 Gen 2 / SM8550):

- **8 cores, no SMT:** 1× Cortex-X3 (prime) @ 3.2 GHz + 2× Cortex-A715 (performance) @ 2.8 GHz + 2× Cortex-A710 (performance) @ 2.8 GHz + 3× Cortex-A510 (efficiency) @ 2.0 GHz
- **Single DSU-110 cluster:** All 8 cores share one 8 MB L3 cache (DSU-110 L3 is shared across all cores within the cluster — this is SoC-wide, not per-cluster). Each core has private L1/L2. The 8 MB L3 figure is cited by all public SM8550 spec sheets as a single value for the whole chip, confirming a single scalable domain. EPSS L3 (Epoch Subsystem L3) is a DVFS/bandwidth-voting interconnect present as exactly one node per SoC — corroborating evidence, not direct proof of topology. The single-node DSU-110 architecture is the authoritative basis.
- **Estimated CPU Distribution:** ~80% of CPU time goes to ORT's internal intra-op thread pool (matmul-heavy inference). The custom sherpa-onnx outer `ThreadPool` owns feature extraction and decoder/joiner work (~15% of CPU). UI/AudioRecord/OS consume the remaining ~5%. *(Note: These percentages are baseline estimates; actual thread tuning will be tied to on-device profiling.)*

Three independent thread populations coexist during ASR inference:

| Population | What | Controlled By | CPU Budget |
| --- | --- | --- | --- |
| **ORT intra-op pool** | Matmul-heavy inference per recognizer | `intra_op_num_threads` + `session.intra_op_thread_affinities` or `SetCustomCreateThreadFn` | ~80% |
| **sherpa-onnx outer pipeline** | Feature extraction, decoder/joiner | Custom `ThreadPool` class (this ADR) | ~15% |
| **Everything else** | UI, `AudioRecord`, OS, coroutines | Android scheduler | ~5% |

**Critical insight:** The custom `ThreadPool` in this ADR only ever governs population (2) — the sherpa-onnx outer pipeline, a much smaller slice of CPU time than implied by "thread count alone." ONNX Runtime owns its own internal intra-op thread pool; creating `std::jthread` workers does not replace ORT's matmul dispatch. The only way to inject affinity into ORT's pool is via `SetCustomCreateThreadFn`/`SetCustomJoinThreadFn` (available in the C++ API), which applies uniformly to both intra-op and inter-op pools and cannot selectively control only matmul dispatch.

### Hard Gate

RTF ≤ 0.05 on-device (ADR-008, open item line 337). If OS contention preempts an inference thread, RTF degrades and the 2.0s turnaround budget (`.kavi.yaml`) is at risk.

### Competing Risks

| Risk | Mechanism | Evidence |
| ------ | ----------- | ---------- |
| **Oversubscription** | Multiple thread populations competing for 8 cores → OS preempts inference → RTF jitter | Current config assumes performance-core placement with no validation |
| **Scheduler misplacement** | OS schedules inference threads on efficiency cores (A510) → 2.0 GHz vs 3.2 GHz → up to 2× latency variance | big.LITTLE scheduling is opaque; no guarantee of performance-core placement |
| **Cache contention** | Two Zipformer-30M int8 models (~32 MB each, both exceeding the 8 MB shared L3) compete for L3 with each other AND with OS/UI/audio on the remaining cores | SD8G2's L3 is SoC-wide (single DSU-110, all 8 cores share 8 MB). Pinning to 2+2 performance cores does not isolate the models' cache footprint from OS/UI/audio work on the other cores — it only guarantees core clock speed and reduces OS-preemption jitter. |

### Why Pinning Still Matters (Despite Shared Cache)

Since each model exceeds the L3 on its own, the pipeline is **memory-bandwidth-bound** regardless of affinity. The benefit of pinning is NOT cache isolation — it is:

1. **Clock speed predictability** — threads stay on 2.8 GHz performance cores instead of risking placement on 2.0 GHz efficiency cores
2. **Reduced OS-preemption jitter** — 2 free cores reduce contention between inference and background work
3. **Thermal headroom** — priority-hint mode allows the OS governor to migrate threads away from overheating cores

If Build F's A/B test shows 2+2 pinning winning on RTF, log **memory bandwidth utilization** alongside thermal status to attribute the win to the correct mechanism (clock speed vs. cache vs. preemption reduction).

## Decision

Adopt a **two-build strategy** with a custom C++ thread pool abstraction for the sherpa-onnx outer pipeline, plus ORT session-level thread controls for the intra-op pool. Both layers support two modes, toggled at runtime.

### Build B (default production config)

- Custom thread pool with `Mode::kPriorityHint`
- `ANDROID_PRIORITY_AUDIO` (-16) on outer pipeline inference threads — **not** `THREAD_PRIORITY_URGENT_AUDIO` (-19)
- ORT sessions configured with `intra_op_num_threads = 2` per recognizer (matching `.kavi.yaml: asr.num_threads`)
- 2 ORT intra-op + 1 custom outer thread per recognizer = 3 per recognizer (6 total threads), leaving 2 cores free for OS/UI/Audio.

**Priority choice rationale:** `THREAD_PRIORITY_URGENT_AUDIO = -19` is annotated `(uncommon)` in Android's `thread_defs.h` and the source comment states: *"A thread priority should be chosen inverse-proportionally to the amount of work the thread is expected to do."* Running 6 heavy inference threads at -19 risks starving the app-side `AudioRecord` reader thread (which runs at `SCHED_OTHER` in your process), causing buffer overruns and dropped audio frames. The actual audio capture path runs at `SCHED_FIFO` inside `system_server`'s AudioFlinger/HAL thread — you cannot starve that. The real risk is delaying the app-side reader.

**Overrun mitigation:** A/B test logging MUST include overrun/drop counters (see §A/B test logging below). RTF-only metrics can mask audio quality degradation from dropped frames.

### Build F (escalation path — only if Build B fails in a specific way)

- Trigger: Build B passes RTF ≤ 0.05 BUT shows unacceptable jitter traced to scheduler misplacement on efficiency cores
- Switch to `Mode::kHardAffinity`, pin to A715+A710 performance cores
- **Static 1+1 ORT + 1+1 custom pinning** — 1 ORT intra-op + 1 custom outer thread per recognizer = 2 per recognizer (4 total threads), providing 1:1 static pinning on the 4 performance cores (A715 + A710).
- ORT `intra_op_num_threads` reduced to 1 per recognizer, and `SetCustomCreateThreadFn` used to inject affinity into ORT's intra-op threads as well as the custom pool's workers
- Keep fallback to `kPriorityHint` if affinity fails (SELinux, core busy, thermal throttling)
- Do NOT use Build F if Build B passes cleanly — the 2 free cores and thermal resilience of priority-hint are strictly better

**Cache thrashing caveat:** 2+2 pinning does NOT isolate cache — the 8 MB L3 is shared across all 8 cores. Each Zipformer-30M model (~32 MB) already exceeds the L3 on its own. The pipeline is memory-bandwidth-bound regardless. If Build F wins on RTF, the mechanism is clock speed predictability and reduced preemption jitter, NOT reduced cache contention. Log memory bandwidth to confirm.

### Global Coordinator (replaces per-recognizer pool isolation)

Two independent `ThreadPool` instances (one per recognizer) make it easy to accidentally breach the 4-thread budget. Replace with a **global coordinator** that enforces the total thread budget across both recognizers:

- Build B: global budget of 6 threads (3 per recognizer)
- Build F: global budget of 4 threads (2 per recognizer), pinned to A715+A710

The coordinator allocates thread slots to recognizers on demand, ensuring the total never exceeds the configured budget.

### Thread pool abstraction (sherpa-onnx outer pipeline)

```cpp
class ThreadPool {
public:
    enum class Mode { kPriorityHint, kHardAffinity };

    // Affinity MUST be set inside the worker function, not here.
    // Calling gettid() in the constructor/SetMode pins the *caller* thread
    // (Main/JNI), not the worker threads. Workers would run freely on all cores.
    void SetMode(Mode mode);
    void SetPreferredCores(const std::vector<int>& cores);
    void SetGlobalBudget(int max_threads);  // enforced by GlobalCoordinator

private:
    void WorkerLoop();  // calls sched_setaffinity(gettid(), ...) at entry
    std::vector<std::jthread> workers_;
    Mode mode_;
    std::vector<int> preferred_cores_;
};
```

### ORT session configuration (intra-op pool)

```cpp
// ORT owns its own intra-op thread pool — the custom ThreadPool does NOT replace this.
// intra_op_num_threads controls the ORT pool size; setting it manually disables
// ORT's automatic per-core affortization.
session_options.intra_op_num_threads = config.num_threads;  // 2 for Build B, 1 for Build F

// Build F only: inject affinity into ORT's intra-op (and inter-op) threads.
// SetCustomCreateThreadFn applies to BOTH pools — cannot target intra-op only.
if (mode == Mode::kHardAffinity) {
    session_options.SetCustomCreateThreadFn([](std::thread* thread) {
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        for (int core : kPreferredCores) CPU_SET(core, &cpuset);
        // pthread_setaffinity_np takes a pthread_t -> sets affinity on the *target* thread.
        pthread_setaffinity_np(thread->native_handle(), sizeof(cpu_set_t), &cpuset);
        // nice = -16 (ANDROID_PRIORITY_AUDIO). Note: setpriority needs a tid; if this
        // callback fires on the creator thread, use pthread_setschedprio / attrs instead.
    });
}
```

### Affinity implementation (inside worker function)

```cpp
#include <sched.h>
#include <unistd.h>

void ThreadPool::WorkerLoop() {
    if (mode_ == Mode::kHardAffinity) {
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        // kPreferredCores populated at runtime probe — see Open Question #1.
        for (int core : preferred_cores_) CPU_SET(core, &cpuset);
        pid_t tid = gettid();  // correct: called inside the worker thread
        sched_setaffinity(tid, sizeof(cpuset), &cpuset);
    }

    // ANDROID_PRIORITY_AUDIO = -16 (not URGENT_AUDIO = -19)
    setpriority(PRIO_PROCESS, gettid(), -16);

    // ... actual work ...
}
```

### Thermal fallback

Static 2+2 pinning means sustained continuous load on the two pinned cores — no thermal migration relief from the OS governor. Primary fallback signal: `PowerManager.getCurrentThermalStatus()` / `addThermalStatusListener()` (API 29+). On `SEVERE` or above, fall back to `kPriorityHint`. Treat cpufreq sysfs reads as an optional finer-grained signal if readable on this device.

### A/B test logging

Run 100 utterances per mode. For each utterance, log:

- RTF (wall-clock inference time / audio duration)
- `PowerManager.getCurrentThermalStatus()` (NONE / LIGHT / MODERATE / SEVERE / CRITICAL / EMERGENCY / SHUTDOWN)
- Per-core temperature via `ThermalManager.getTemperature()` (API 30+) if available
- **Audio overrun/drop counters:** Monitored via `AudioRecord.getTimestamp()` + frame-position delta tracking (calculating timestamp gaps against sample rates to detect input buffer overflows caused by CPU starvation).
- **Memory bandwidth utilization** (read via `perf_event_open` with `PERF_COUNT_HW_CACHE_MISSES` if accessible, or Qualcomm PMU via sysfs if readable) — attributes Build F wins to clock speed vs. cache vs. preemption reduction
- Optional: per-core `scaling_cur_freq` from sysfs if readable

**Why:** A pinned run that wins on P50/P95 RTF for the first 20 utterances but thermal-throttles by utterance 60 must not get misread as the better mode. Overrun counters catch audio quality degradation from priority starvation. Memory bandwidth logging attributes wins to the correct mechanism.

## Alternatives Considered

### Priority-hint only (current `.kavi.yaml` stance)

- **Pros:** No root needed, no SELinux risk, scheduler retains flexibility
- **Cons:** No guarantee of performance-core placement; scheduler may still place threads on efficiency cores under load

### Hard affinity to all 4 performance cores (winterSolstice25's original proposal)

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

### THREAD_PRIORITY_URGENT_AUDIO on inference threads (rejected)

- **Pros:** Stronger priority hint to the scheduler
- **Cons:** `-19` annotated `(uncommon)` in Android source; running 6 heavy threads at this priority risks starving the app-side `AudioRecord` reader (which runs at `SCHED_OTHER`, not `SCHED_FIFO` like the actual audio capture path). `ANDROID_PRIORITY_AUDIO = -16` is the correct priority for sustained heavy work that should not starve other app threads.

### Per-recognizer pools with local budgets (rejected)

- **Pros:** Simpler to reason about per-recognizer resource usage
- **Cons:** Two independent pools can accidentally breach the total thread budget. No global coordination.
- **Rejected:** Global coordinator enforces the total budget across both recognizers.

## Open Questions

1. **Core ID mapping:** Which Linux core IDs map to A715 vs A510 on the SD8G2? Must probe at runtime — cannot hardcode. Build F cannot ship until this mapping is confirmed empirically on the Meizu 21 Note.
2. **SELinux policy:** Does `sched_setaffinity()` require special SELinux permissions on the Meizu 21 Note? The call may be overridden by Android's cgroup-based thread management.
3. **Audio thread placement:** `AudioRecord` runs on a high-priority audio framework thread — we don't control its core. If it lands on a performance core we've pinned to, contention is unavoidable. **Defer** — revisit only if Build F is triggered.
4. **cgroup interaction:** Android 10+ uses cgroups (schedtune, cpuset) for thread placement. `SetTaskProfiles(tid, {"MaxPerformance"})` joins the `top-app` cgroup, which hints the scheduler to prefer performance cores. This may conflict with or complement `sched_setaffinity()` — needs empirical testing.
5. **C++20 `std::jthread` support:** The ThreadPool sketch uses `std::jthread` (C++20). `jthread`/`stop_token` support depends on the NDK's libc++ version and `minSdkVersion`. Confirm NDK r26c + libc++ supports `std::jthread` on min supported API level before adopting.
6. **Thermal throttling under static 2+2 pinning:** Static pinning means the OS governor cannot migrate threads away from overheating cores. If the SoC thermal-throttles the two pinned cores, RTF degrades with no relief. See thermal fallback strategy above.
7. **Coroutine thread accounting:** Are the 2 Kotlin `async` coroutines genuinely block-waiting on the native pool (cheap, doesn't count against the CPU budget), or do they perform real work on the dispatcher thread? The Build B headroom rationale ("6 active threads on 8 cores = 2 free") hinges on the former. Validate by profiling coroutine CPU time during inference.
8. **`SetCustomCreateThreadFn` scope:** Does the ORT callback fire once at session init or per-inference? If per-inference, affinity injection has no overhead concern; if once, it's a one-time cost. Verify against ORT C++ API source before relying on it for Build F.
9. **Memory bandwidth logging feasibility:** Can `perf_event_open` with `PERF_COUNT_HW_CACHE_MISSES` or Qualcomm PMU sysfs be read from the app process on the Meizu 21 Note without root? If not, the Build F mechanism-attribution log must rely on thermal + RTF + inference latency decomposition instead.

## Consequences

### Positive

- Build B (`ANDROID_PRIORITY_AUDIO` + `intra_op_num_threads=2`) is the production config unless proven otherwise — 2 free cores for OS/UI/audio + thermal resilience
- ORT session-level controls (`intra_op_num_threads`) and custom thread pool controls are clearly separated — each layer is independently tunable
- Global coordinator enforces total thread budget across both recognizers — prevents accidental oversubscription
- Build F escalation path preserves deterministic core placement as an option if empirical evidence justifies it
- `sched_setaffinity()` available since API 14 (used in WorkerLoop via gettid());
Build F additionally uses pthread_setaffinity_np() on the ORT thread handle,
which requires API 21+ (minimum supported API is Android 16 per ADR-002, so OK).
- A/B logging captures audio overruns and memory bandwidth — prevents RTF-only blind spots and enables mechanism attribution

### Negative / risk

- Core ID mapping is unconfirmed — Build F cannot ship until runtime probe validates which IDs are performance cores
- Hard affinity risks pinning threads to busy cores, making latency *worse* — only justified if Build F shows scheduler misplacement
- Affinity is a one-way door: once pinned, you can't easily move threads if the device is under unexpected load
- `AudioRecord` thread placement is out of our control — if it lands on a pinned core, contention is unavoidable (deferred risk)
- `SetCustomCreateThreadFn` applies to both intra-op and inter-op pools — cannot selectively target only matmul dispatch
- Memory bandwidth logging may require root or privileged PMU access — may not be available on the Meizu 21 Note without engineering build

## References

- ADR-007: TranslationService — two-mode foreground service (the service this threading configures; the wider inference architecture spans ADR-013–ADR-022)
- ADR-008: v1 Android ASR Decision — Dual Zipformer (RTF 0.011 desktop benchmark, go/no-go gate at RTF > 0.05, streaming transducer architecture)
- ADR-002: Target Platform — Snapdragon 8 Gen 2, Android 16
- ADR-010: All-Opt Decoder Optimisation
- `.kavi.yaml` — single source of truth for pinned config values (`rtf: 0.05`, `turnaround_gate_sec: 2.0`, `asr.num_threads: 2`)
- PR #97 (Kotlin+C++ implementation plan) — winterSolstice25's hard affinity proposal
- PR #98 (.kavi.yaml) — aFlyingSeal's review findings on config contradictions
- PR #100 — winterSolstice25 and aFlyingSeal's technical review of this ADR (5 validated concerns incorporated)
- [sherpa-onnx Zipformer transducer models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/zipformer-transducer-models.html) — RTF 0.011 desktop benchmark source
- Android `thread_defs.h` — `ANDROID_PRIORITY_URGENT_AUDIO = -19 (uncommon)`, `ANDROID_PRIORITY_AUDIO = -16`
- Android audio latency documentation — AudioFlinger capture threads run `SCHED_FIFO` since Android 4.1; app-side `AudioRecord` reader runs `SCHED_OTHER`
- Arm DSU-110 Technical Reference Manual — single DSU-110 cluster, L3 shared across all cores within cluster
- ONNX Runtime C++ API — `intra_op_num_threads`, `SetCustomCreateThreadFn`, `SetCustomJoinThreadFn` (custom threading callbacks apply uniformly to intra-op and inter-op pools)
