# RTranslator 2.1.5 — Baseline Test Protocol

> **Purpose:** Produce a single, reproducible RTranslator baseline row for the Kavi
> benchmarking suite. This is a **semi-manual** procedure (install APK, feed audio
> via UI, capture outputs). Scoring happens off-device via `bench/score_rtranslator.py`.
>
> **Target mode:** WalkieTalkie (one-phone, continuous listen + ASR → MT → TTS) —
> the closest comparator to Kavi's single-phone speech-to-speech pipeline.
> See `docs/reference/benchmarking-plan.md` §5.1 for the rationale.

---

## 1. Snapshot metadata

| Field | Value |
| --- | --- |
| **App** | RTranslator |
| **Version** | 2.1.5 |
| **Tag** | `2.1.5` |
| **Commit** | `49e7f20d020f5202d099029ab4c4ed35a57ecdd1` |
| **Release date** | 2026-02-22 |
| **APK SHA-256** | `6dbc90f569cb5f0a4ed6520ebe40e3d77ae314a0a79a2b40245a71efb45649f7` |
| **APK path** | `eval_data/rtranslator/RTranslator_2.1.5.apk` |
| **GitHub** | <https://github.com/niedev/RTranslator> |
| **License** | Apache-2.0 (app code); NLLB-600M weights CC-BY-NC-4.0 |
| **3.0 notice** | RTranslator 3.0 (NGI Mobifree-funded) is imminent and swaps NLLB for Bergamot/MADLAD/HY-MT. **Numbers in this protocol apply only to 2.x (NLLB) backend.** |

---

## 2. Device state checklist

Before each run, record and verify every item below.

| # | Item | Check | Record |
| --- | --- | --- | --- |
| 1 | **Device** | Meizu 21 Note | model / chipset / RAM |
| 2 | **Android version** | API 36 (Android 16) | `adb shell getprop ro.build.version.sdk` |
| 3 | **Chipset** | Snapdragon 8 Gen 2 (SM8550) | `adb shell getprop ro.hardware` |
| 4 | **RAM** | ~15 GB | `adb shell cat /proc/meminfo \| grep MemTotal` |
| 5 | **Airplane mode** | **ON** (verify no cellular/WiFi) | visual + `adb shell dumpsys connectivity` |
| 6 | **Play Services blocked** | Block network access for Play Services if possible (see §2.1) | record method used |
| 7 | **Thermal state** | Record before and after run | `adb shell dumpsys thermalservice \| grep 'ThermalStatus'` or `cat /sys/class/thermal/thermal_zone*/temp` |
| 8 | **Battery level** | > 80% recommended | `adb shell dumpsys battery` |
| 9 | **Charging** | **Disconnect** charger (avoid thermal throttling) | visual |
| 10 | **Screen brightness** | Fixed (e.g. 50%) | record |
| 11 | **System TTS engine** | Record engine + version | Settings → Accessibility → Text-to-speech output |
| 12 | **System TTS voice pack** | Record language pack + offline availability | Check in TTS settings per language |
| 13 | **RAM-mode switch** | RTranslator Settings → Low RAM mode (0.5 GB vs 0.9 GB Whisper) | record which setting |
| 14 | **Beam search** | RTranslator Settings → Beam search on/off | record |
| 15 | **Model bundle version** | Record version shown in RTranslator's model download screen | visual |
| 16 | **ML Kit pre-warmed?** | See §5 pre-warm sequence | record |
| 17 | **Audio input source** | Built-in mic vs BT headset | record |
| 18 | **Screen-on time since charge** | Avoid long uptime (thermal creep) | `adb shell dumpsys batterystats \| grep 'Screen on'` |

### 2.1 Blocking Play Services network

On the Meizu 21 Note (Android 16), use one of:

- **Settings → Apps → Google Play Services → Mobile data & WiFi → toggle OFF** (most reliable)
- **`adb shell pm disable com.google.android.gms`** — more aggressive, may need re-enable after
- **Firewall app** (e.g. NetGuard) if available

Record which method was used. Re-enable Play Services after the test is complete.

---

## 3. Pre-run verification (do once per session)

1. Install APK: `adb install eval_data/rtranslator/RTranslator_2.1.5.apk`
2. Launch RTranslator, accept permissions (Microphone, Notifications).
3. Download the model bundle (~1.2 GB) over WiFi **before** enabling airplane mode.
4. Verify WalkieTalkie mode works: short test phrase, confirm audio plays back.
5. Verify system TTS speaks both VI and EN (test each direction).
6. **Enable airplane mode** + block Play Services **after** model download completes.
7. Confirm no network calls: run 30 s of silence in WalkieTalkie mode; check
   `adb shell dumpsys connectivity` or a packet-capture tool for zero egress.
8. Record all device-state items from §2.

---

## 4. WalkieTalkie testing steps

### 4.1 Audio preparation

Prepare WAV files (16 kHz, 16-bit mono) from the lean eval set
(`eval_data/eval_manifest_v1.json` items). Use a reference player app or
`adb push` to the device's internal storage.

### 4.2 Per-utterance procedure

For each utterance in the eval set (processed in order):

1. **Start recording** on the device (use a voice recorder app or enable
   RTranslator's internal logging — see §6).
2. **Play audio** through a calibrated speaker or direct file playback
   at a fixed volume level (record dB SPL at the phone's mic position).
3. **Wait** for RTranslator to finish synthesizing the response.
4. **Stop recording** / capture the output.
5. **Wait 10+ seconds** between utterances (thermal cooldown + avoid overlap).
6. **Log** the result using the template in §7.

### 4.3 Direction-switch procedure

Run **two passes**:

| Pass | Input language | Expected output | Focus |
| --- | --- | --- | --- |
| **Pass A (VI→EN)** | Vietnamese speech | English text + synthesized EN speech | Requires ML Kit to detect VI → route through Whisper VI → NLLB vi-en → system TTS EN |
| **Pass B (EN→VI)** | English speech | Vietnamese text + synthesized VI speech | Requires ML Kit to detect EN → route through Whisper EN → NLLB en-vi → system TTS VI |

### 4.4 What to capture per pass

| Output | Method | Notes |
| --- | --- | --- |
| **ASR transcript** (source language) | RTranslator's on-screen transcription text | Record exact text displayed |
| **MT translation** (target language) | RTranslator's on-screen translation text | Record exact text displayed |
| **Synthesized audio** | Audio recording or `adb pull` of cache | Map to the eval item's TTS output |
| **End-to-end latency** | Smartphone stopwatch or ADB logcat timestamps | Start = audio playback start; End = first synthesized audio sample |
| **Per-stage latency** | Not available without RTranslator source modification | Leave blank; note "not accessible" |

---

## 5. Pre-warm sequence

RTranslator lazily initializes ML Kit language identification and system TTS on
first use. To avoid cold-start distortion on early utterances:

1. **Enter WalkieTalkie mode** and speak 2–3 short phrases in each language
   (VI then EN), discard those results.
2. **Verify system TTS voice packs** are downloaded for both VI and EN:
   - Settings → Accessibility → Text-to-speech output → Preferred engine →
     Settings icon → Install voice data
3. **Wait 30 seconds** after pre-warm before starting the actual eval run.
4. **Record** whether ML Kit seemed to correctly identify language on the
   pre-warm utterances.
5. **Note** any "Downloading voice data" toast or network activity during
   pre-warm (this would violate the no-internet-at-runtime DQ rule if it
   happened during the actual run).

---

## 6. Output capture method

### 6.1 Primary: Transcription via screen capture + manual transcription

Since RTranslator 2.1.5 does not expose a batch export mechanism:

1. **Enable "Show both transcription and translation"** in RTranslator Settings
   (added in 2.1.5 per PR #128) to see both on screen.
2. **Screenshot** each utterance result.
3. **Transcribe manually** into the per-utterance log template (§7).
4. **Audio** (TTS output): record via a voice recorder app held near the phone
   speaker, or use `adb shell screenrecord --audio-source=mic` as a backup.

### 6.2 Alternative: ADB log analysis

If RTranslator emits text to logcat:

```
adb logcat -c && adb logcat | grep -i "rtranslator\|transcript\|translation" > capture.log
```

Parse the log to extract ASR and MT outputs. **Verify one utterance manually**
that the log output matches the on-screen text before relying on it.

### 6.3 Output file layout

After the run, organize captured outputs under a dated directory:

```
eval_data/rtranslator/outputs/2026-03-01/
├── manifest.json           # copy of eval_manifest_v1.json for this run
├── device-state.json       # device state checklist values
├── vi-en/
│   ├── asr_vi_1824.txt     # ASR transcript for ID vi-asr-1824-clean
│   ├── mt_en_1824.txt      # MT translation for ID vi-en-mt-1824
│   ├── tts_vi_1824.wav     # TTS audio (if captured)
│   └── ...
└── en-vi/
    ├── asr_en_0001.txt
    ├── mt_vi_0001.txt
    └── ...
```

---

## 7. Per-utterance recording template

Use one block per utterance. Copy-paste the template below.

```yaml
---
id: "vi-asr-1824-clean"
direction: "vi->en"
timestamp: "2026-03-01T10:30:00Z"
input_audio: "eval_data/mixed/vi_1824_clean.wav"
input_language: "vi"
output_asr_text: ""
  # RTranslator's on-screen Vietnamese transcription
output_asr_confidence: ""
  # if visible
output_mt_text: ""
  # RTranslator's on-screen English translation
output_tts_audio_path: ""
  # path to captured TTS WAV
latency_e2e_s: ""
  # seconds from audio-playback-start to first audible TTS output
latency_asr_s: ""
  # if available (logcat)
latency_mt_s: ""
  # if available (logcat)
notes: ""
  # any anomalies (wrong language, garbled output, network request)
```

---

## 8. Post-run checklist

- [ ] Screenshots / screen recordings saved
- [ ] Logcat output saved (if applicable)
- [ ] Per-utterance YAML records compiled into a single file
- [ ] All text outputs transcribed and cleaned
- [ ] TTS audio files organised by item ID
- [ ] Device state snapshot saved
- [ ] APK version + commit hash + date confirmed in records
- [ ] Run scoring: `uv run python -m bench.score_rtranslator \
       --manifest eval_data/eval_manifest_v1.json \
       --outputs eval_data/rtranslator/outputs/2026-03-01`

---

## 9. References

- `docs/reference/benchmarking-plan.md` §5 — RTranslator as product baseline
- `docs/reference/benchmarking-todo.md` §7 Phase 5 — checklist
- `bench/score_rtranslator.py` — scoring script
- `bench/candidates/rtranslator.py` — RTranslatorCandidate adapter
- GitHub release: <https://github.com/niedev/RTranslator/releases/tag/2.1.5>
