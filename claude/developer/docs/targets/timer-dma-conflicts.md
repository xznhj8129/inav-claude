# Timer and DMA Conflict Resolution

Understanding and resolving timer/DMA conflicts is crucial for target development. STM32 MCUs have limited DMA channels, and conflicts can prevent motors from working properly.

## What Are DMA Conflicts?

**DMA (Direct Memory Access)** allows peripherals like timers to transfer data without CPU intervention. Each timer channel can use specific DMA streams/channels.

**Conflict occurs when:** Multiple timer channels try to use the same DMA stream/channel.

**Result:** One or more motor outputs fail, or only some motors respond to throttle.

## STM32 DMA Architecture

### F4/F7: Fixed DMA Mapping

Each timer channel has 1-3 possible DMA streams:

```
TIM3_CH1 can use: DMA1_Stream4
TIM3_CH2 can use: DMA1_Stream5
TIM3_CH3 can use: DMA1_Stream7
TIM3_CH4 can use: DMA1_Stream2
```

**Conflict example:**
```c
DEF_TIM(TIM3, CH1, PB4,  TIM_USE_OUTPUT_AUTO, 0, 0), // Uses DMA1_Stream4
DEF_TIM(TIM2, CH3, PB10, TIM_USE_OUTPUT_AUTO, 0, 0), // Also uses DMA1_Stream4!
// ^ CONFLICT - only one will work
```

### H7: DMAMUX (Flexible)

H7 series uses DMAMUX which allows any timer to use any DMA channel - much more flexible and fewer conflicts.

## Detecting DMA Conflicts

### Symptoms
- Some motors don't respond to throttle
- Motors work in some configurations but not others
- "DMA conflict" warning in INAV CLI `status` command

### Finding Conflicts

**Use the DMA Resolver Tool:**

Location: `raytools/dma_resolver/dma_resolver.html`

**Steps:**
1. Open `dma_resolver.html` in web browser
2. Select MCU type (F405, F7, H7)
3. Paste your timer definitions from target.c
4. Click "Resolve Conflicts"
5. Tool shows:
   - Which timers conflict
   - Alternative DMA assignments
   - Suggested fixes

**Example input:**
```c
DEF_TIM(TIM1, CH1, PA8,  TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM1, CH2, PA9,  TIM_USE_OUTPUT_AUTO, 0, 1),
DEF_TIM(TIM2, CH3, PB10, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM2, CH4, PB11, TIM_USE_OUTPUT_AUTO, 0, 1),
```

Tool output shows:
- Current DMA assignments
- Conflicts (red highlighting)
- Alternative configurations (if available)

## DMA Assignment in target.c

The last two parameters in `DEF_TIM()` control DMA assignment:

```c
DEF_TIM(TIM, CH, PIN, USE, dmaopt, dmavar)
                           ^^^^^^  ^^^^^^
```

- **dmaopt (DMA Option):** Which alternate DMA mapping to use (0, 1, 2...)
- **dmavar:** On F4/F7 this selects among a short, fixed list of real alternate DMA
  mappings (often just 1-2 choices, sometimes none). **On H7 it is not legacy** —
  `DEF_TIM_DMA_FULL(req)` in `timer_def_stm32h7xx.h` expands to all 16 DMA1/DMA2
  streams for that same request (H7's DMAMUX can route any request to any stream),
  so `dmavar` directly picks which of the 16 streams (0-7 = DMA1, 8-15 = DMA2) that
  channel's own DMA tag nominally points to. It matters for H7 targets too — see
  "H7-Specific: DMAMUX Ownership Gotchas" below.

### F405/F411 Example

```c
// TIM3_CH1 has only one DMA option: DMA1_Stream4
DEF_TIM(TIM3, CH1, PB4, TIM_USE_OUTPUT_AUTO, 0, 0),  // dmaopt=0

// TIM2_CH4 has two DMA options: DMA1_Stream7 or DMA1_Stream6
DEF_TIM(TIM2, CH4, PB11, TIM_USE_OUTPUT_AUTO, 0, 0), // dmaopt=0 → uses DMA1_Stream7
DEF_TIM(TIM2, CH4, PB11, TIM_USE_OUTPUT_AUTO, 1, 0), // dmaopt=1 → uses DMA1_Stream6
```

## Resolving Conflicts

### Strategy 1: Use Different Timers

Instead of multiple channels on same timer, spread across timers:

```c
// Before (potential conflicts)
DEF_TIM(TIM3, CH1, PB4, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM3, CH2, PB5, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM3, CH3, PB0, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM3, CH4, PB1, TIM_USE_OUTPUT_AUTO, 0, 0),

// After (distributed across timers)
DEF_TIM(TIM3, CH1, PB4, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM2, CH3, PB0, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM4, CH1, PB6, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM1, CH1, PA8, TIM_USE_OUTPUT_AUTO, 0, 0),
```

### Strategy 2: Change DMA Option (dmaopt)

Use alternate DMA mapping:

```c
// Before (conflict)
DEF_TIM(TIM1, CH1, PA8,  TIM_USE_OUTPUT_AUTO, 0, 0), // DMA2_Stream6
DEF_TIM(TIM1, CH3, PA10, TIM_USE_OUTPUT_AUTO, 0, 0), // DMA2_Stream6 - CONFLICT!

// After (use alternate for CH1)
DEF_TIM(TIM1, CH1, PA8,  TIM_USE_OUTPUT_AUTO, 1, 0), // DMA2_Stream1
DEF_TIM(TIM1, CH3, PA10, TIM_USE_OUTPUT_AUTO, 0, 0), // DMA2_Stream6 - OK!
```

### Strategy 3: Check Hardware Design

If conflicts can't be resolved, hardware may have design issue. Check:
- Can pins be reassigned to different timers?
- Are all motor outputs necessary?
- Can LED strip use different pin?

## Pin to Timer Mapping

Not all pins can use all timers. Check STM32 datasheet "Alternate Functions" table.

**Example for PA8:**
- Can be TIM1_CH1 (AF1)
- Can be TIM8_CH1 (AF3)
- Cannot be TIM2, TIM3, TIM4

**Finding alternate functions:**
1. STM32 datasheet → Pinout section
2. Look up pin (e.g., PA8)
3. Check "AF" (Alternate Function) columns
4. Look for TIMx_CHy entries

## Common DMA Mappings Reference

### STM32F405/F411

| Timer_Channel | DMA Options |
|---------------|-------------|
| TIM1_CH1 | DMA2_S6, DMA2_S1, DMA2_S3 |
| TIM1_CH2 | DMA2_S6, DMA2_S2 |
| TIM1_CH3 | DMA2_S6, DMA2_S6 |
| TIM2_CH1 | DMA1_S5 |
| TIM2_CH4 | DMA1_S7, DMA1_S6 |
| TIM3_CH1 | DMA1_S4 |
| TIM3_CH2 | DMA1_S5 |
| TIM3_CH3 | DMA1_S7 |
| TIM3_CH4 | DMA1_S2 |
| TIM4_CH1 | DMA1_S0 |
| TIM4_CH2 | DMA1_S3 |

Full mappings available in `dma_maps.js` file in DMA resolver tool.

## Best Practices

1. **Use DMA Resolver Tool** - Always run tool before finalizing target.c
2. **Spread Timers** - Don't put all motors on one timer if avoidable
3. **Reserve for UART/SPI** - Some DMA streams may be needed for UART/SPI
4. **Test All Outputs** - Test every motor output after defining timers
5. **Document** - Add comments showing DMA assignment

```c
// Good: Shows DMA usage
DEF_TIM(TIM3, CH1, PB4, TIM_USE_OUTPUT_AUTO, 0, 0), // DMA1_S4
DEF_TIM(TIM3, CH2, PB5, TIM_USE_OUTPUT_AUTO, 0, 0), // DMA1_S5
```

## Testing for Conflicts

After defining timers:

1. **Build firmware**
2. **Flash to FC**
3. **Open INAV Configurator**
4. **Go to Motors tab**
5. **Test each motor slider** - all should respond
6. **Check CLI:** Type `status` - look for DMA warnings

## Tool Usage Example

**Problem:** Motors 3 and 4 don't work on new target

**Solution:**

1. Open `raytools/dma_resolver/dma_resolver.html`
2. Select "F405" (your MCU)
3. Paste timer definitions:
```c
DEF_TIM(TIM3, CH1, PB4,  TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM3, CH2, PB5,  TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM2, CH3, PB10, TIM_USE_OUTPUT_AUTO, 0, 0),
DEF_TIM(TIM2, CH4, PB11, TIM_USE_OUTPUT_AUTO, 0, 0),
```
4. Click "Resolve Conflicts"
5. Tool shows TIM3_CH1 and TIM2_CH3 both want DMA1_Stream4
6. Tool suggests changing TIM2_CH3 to use different pin or dmaopt
7. Apply fix and retest

## H7 Advantages

STM32H7 uses DMAMUX which eliminates most DMA conflicts:
- Any timer can use any DMA channel
- Much more flexible
- Fewer headaches for target developers
- Conflicts still possible but rare

## H7-Specific: DMAMUX Ownership Gotchas

Found while investigating a single-motor-only DSHOT failure on an H743 target
(PD15/TIM4_CH4, PR #11632). Two things that look like plausible DMA-stream
collision candidates on H7 turn out **not** to be, because they don't participate
in the ownership tracking `impl_timerPWMConfigDMABurst()` (`timer_impl_hal.c`)
checks via `dmaGetByTag()`/`dmaGetOwner()`:

- **SPI never uses DMA on H7 in INAV.** `bus_spi_hal_ll.c` (used for H7/F7) does
  all transfers through polled `LL_SPI_TransmitData8()`/`LL_SPI_ReceiveData8()` —
  no `HAL_SPI_*_DMA`, no `dmaInit()`, no `dmaGetByTag()` anywhere in the file, on
  any platform. Gyro/OSD/blackbox-flash SPI can never be the "something else has
  this stream" culprit.
- **ADC1 is hardcoded to `DMA2_Stream0`** on H7 (`adc_stm32h7xx.c`, `adcHardware[]`
  table) and configures it via a raw `HAL_DMA_Init()` call — it never calls
  `dmaGetByTag()`/`dmaInit()`, so it's invisible to the ownership table regardless
  of which stream it's on. The `ADC1_DMA_STREAM`/`ADC1_DMA_OPT` override pattern
  that exists for F4/AT32 (`adc_stm32f4xx.c`, `adc_at32f43x.c`) has no H7
  equivalent — any target.h define of that name on an H7 target is dead code.
- **`USE_DSHOT_DMAR` burst mode has an ownership-check quirk worth knowing about
  even though it didn't turn out to be the bug here:** only the *first* channel of
  a timer to initialize actually claims/uses its DMA stream for the shared burst
  transfer (`if (!tch->timCtx->dmaBurstRef)` in `timer_impl_hal.c`) — but *every*
  channel, including ones that will never use their own stream, still runs
  `dmaGetByTag()` + `dmaGetOwner() != OWNER_FREE` on its own nominal stream first
  and bails out (silently leaving that one motor unconfigured) if something else
  already owns it. A stray dmavar collision on a channel that never gets that far
  (e.g. a servo channel, which doesn't use the DMA path at all) is harmless — only
  matters if the colliding peripheral actually calls `dmaInit()`.
- **Practical implication:** on H7, the DMA-conflict search space for a
  single-motor DSHOT failure is much narrower than F4/F7 — realistically just other
  *timer* channels (motors/servos/LED strip) that call `dmaInit()`, since SPI and
  ADC are structurally excluded. If a static read-through of `timerHardware[]`
  doesn't turn up a real collision, the fault is more likely non-DMA (hardware/pad
  issue, mixer/output-count logic, or something outside this subsystem) — check
  for `LOG_ERROR(PWM, "Timer allocation failed for motor %d", idx)` in
  `pwm_mapping.c` in a real boot log before spending more time on DMA theories.

## Related Documentation

- **overview.md** - Target system basics
- **inav/docs/development/targets/common-issues.md** - See "Timer Configuration" section for real examples
- **creating-targets.md** - Timer setup during target creation
- **STM32 Reference Manual** - Complete DMA tables

## External Resources

- **DMA Resolver Tool:** `raytools/dma_resolver/dma_resolver.html`
- **STM32F4 Reference Manual:** RM0090 - Chapter 10 (DMA)
- **STM32F7 Reference Manual:** RM0385 - Chapter 9 (DMA)
- **STM32H7 Reference Manual:** RM0433 - Chapter 17 (DMAMUX)
