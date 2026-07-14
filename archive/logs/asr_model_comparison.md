# ASR Model Comparison — greeting_vi.wav

| Model | ASR Text | ASR Time | MT Time | TTS Time | Total (warm) |
|-------|----------|----------|---------|----------|-------------|
| base   | Xin chào, tôi có thể giúp **nhìn chào lại** | 2.86s | 0.33s | 0.81s | **12.09s** |
| small  | Xin chào, tôi có thể giúp **lý cho bạn** | 1.56s | 0.11s | 0.69s | **24.40s** |
| medium | Xin chào! Tôi có thể **giúp đỡ** cho bạn | 6.04s | 0.53s | 3.09s | **214s** (inc. dl) |

## Observations

- **base (74M):** Fastest total time (~12s) but ASR is most wrong ("nhìn chào lại")
- **small (244M):** ASR better ("lý cho bạn"), but model loading increases total to ~24s
- **medium (1.5B):** ASR best ("giúp đỡ cho bạn") but MT degenerates into repetitive garbage
- All miss the likely intended phrase (probably "giúp **gì** cho bạn")
- MT fails differently at each level, suggesting ASR noise is the root cause

## Recommendation

Use **small** as default. It's the best accuracy/speed tradeoff for CPU.
