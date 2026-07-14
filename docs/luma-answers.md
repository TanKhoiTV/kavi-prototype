# OneVoice AI Challenge — Luma Registration Answers

**Project:** Kavi
**Deadline:** June 24, 2026
**Prepared:** June 23, 2026

---

## 1. Project Name

Kavi

---

## 2. Describe Your Solution

Kavi is a fully offline, speech-to-speech translation application purpose-built for Vietnamese and English speakers on consumer Snapdragon Android phones. A speaker talks in either language; Kavi captures the audio, transcribes it to text, translates it , and speaks the translation aloud, all within seconds.

---

## 3. What Makes It Innovative?

Kavi's innovation sits at the intersection of language priority, pipeline completeness, and platform contribution. First, Vietnamese is the primary language, not an afterthought language pack layered onto an English-first architecture. Our ASR front end is designed around Vietnamese phonology and code-switching patterns, enabling accurate transcription even when speakers naturally mix Vietnamese and English terms. Second, Kavi delivers a complete speech-to-speech pipeline on consumer hardware. Competing solutions stop at text translation or require cloud processing; Kavi goes from voice input to voice output on a single Snapdragon device with no external dependencies. Third, we are extending the Qualcomm AI Hub model catalog by contributing a Vietnamese TTS voice based on MeloTTS, filling a confirmed gap in the Hub's current language coverage. Fourth, the system includes a designed-in thermal management strategy: three tiers of operation that gracefully degrade TTS quality as device temperature rises, ensuring stable performance under sustained load in warm environments. These combined make Kavi an architecture built for real field deployment, not a lab demo.

---

## 4. Technical Approach

Kavi's architecture is a four-stage pipeline: voice activity detection, automatic speech recognition, machine translation, and lastly text-to-speech. All stages run on-device with no cloud dependency. For VAD, we use Silero VAD with thresholds optimized for short utterances common in industrial communication. The ASR stage uses a Vietnamese-primary architecture with adaptive code-switching support, combining a lightweight recognition model for Vietnamese with Whisper-family handling of code-switched English terms, targeting accurate transcription of mixed-language utterances typical in manufacturing environments. The MT stage compresses a production-grade neural translation model into an int8-quantized sub-100MB footprint, translating Vietnamese to English entirely on CPU within our 2000ms latency budget. For TTS, the current prototype uses an efficient English voice; the production target replaces this with a MeloTTS-based Vietnamese speaker fine-tuned on native speech data and exported through Qualcomm AI Hub Workbench. The entire pipeline runs through a persistent model server that eliminates per-request model loading overhead. Each pipeline stage has independent optimization capacity, and routing across language pairs is data-driven rather than hardcoded.

---

## 5. Use Case / Industry

Kavi targets the industrial and field-service sectors where language barriers directly affect productivity and safety. Primary users are Vietnamese-speaking workers in foreign-invested manufacturing plants, construction sites, logistics centers, and hospitals who need real-time communication with English-speaking supervisors, trainers, or colleagues. The problem is acute: 87% of FDI companies in Vietnam require English proficiency, yet only 5% of Vietnamese workers are proficient. Current workarounds — gestures, phrasebooks, phone-based translation apps — break down in noisy environments, hands-busy situations, and areas without stable internet. Kavi sits in a shoulder pouch or pocket, activated by voice, delivering spoken translations without the worker needing to stop, look at a screen, or find Wi-Fi. Secondary use cases include safety briefings where mistranslating a hazard warning has real consequences, skills transfer sessions where foreign trainers instruct local operators, and shift handovers across language barriers. Because Kavi runs on standard Android phones, it requires no specialized hardware purchase — any Snapdragon 8 Gen 2 device can run it as a software install, which dramatically lowers the adoption barrier for industrial deployment.

---

## 6. Expected Impact

Language barriers in Vietnam's industrial workforce cost productivity, cause safety incidents, and block skills transfer from foreign experts to local workers. Vietnam's FDI sector employs millions, but the English proficiency gap means companies either invest heavily in language training that takes years and reaches few workers, or accept the productivity loss and safety risk of miscommunication. Kavi addresses this at the point of need: on the factory floor, in the warehouse, on the construction site. With an offline device that works immediately. For the individual worker, Kavi removes a barrier to upward mobility and skills development: understanding a supervisor's instruction no longer requires years of English study. For the employer, it reduces safety incidents from miscommunication and accelerates onboarding of new workers. For Vietnam's economy, it unlocks productivity in the FDI sector, one of the country's largest employment engines, by removing a bottleneck that training alone cannot solve at scale. The approach is pragmatic: rather than waiting for universal English proficiency, Kavi meets workers where they are, in Vietnamese, and lets them do their jobs without friction or difficulty.

---

## 7. Product Evolution

Kavi today is a working CPU prototype with measured baselines, a four-stage pipeline running on a Snapdragon 8 Gen 2 Android phone. The evolution path has four phases. Phase 1 optimizes each stage for the target device: fine-tuning the ASR model on Vietnamese speech for sub-15% WER, profiling MT latency on SD8G2 CPU/NPU, and completing the MeloTTS-VI checkpoint export through Qualcomm AI Hub Workbench. Phase 2 integrates the optimized models into a single Android application with a hands-free interface designed for industrial use: voice activation, audio-only feedback, no screen interaction required during operation. Phase 3 extends language coverage to Vietnamese-Chinese and Vietnamese-Korean, covering all three contest language pairs through the same MT model's multilingual capacity. Phase 4 explores the path from software to product: a dedicated device SKU through hardware partnerships, or distribution through industrial safety equipment providers who already serve target facilities. The architecture supports this growth, each pipeline stage is independently optimizable, language pair routing is data-driven, and the Qualcomm AI Hub contribution creates a natural channel for ongoing model collaboration.
