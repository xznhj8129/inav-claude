# Analysis Scripts

Code analysis tools for INAV development.

## nm Symbol Size Diff

**Script:** `diff_nm_symbols.py`

Diffs `arm-none-eabi-nm --size-sort` output between two builds (e.g. a PR's
head vs. its merge-base) to attribute a flash/RAM delta to specific symbols
instead of guessing from line count or trusting a single top-line number.

**Usage:**
```bash
arm-none-eabi-nm --size-sort -C before.elf > before.txt
arm-none-eabi-nm --size-sort -C after.elf > after.txt
python3 claude/developer/scripts/analysis/diff_nm_symbols.py before.txt after.txt
```

**Note:** with LTO + `-freorder-blocks-and-partition`, single-call-site
`static` functions are often inlined into the caller's hot/cold partition
(a `<caller>.part.0` symbol) instead of staying as separate symbols — a
large new `.part.0` entry usually means several new static helpers got
folded into that caller, not one giant new function.

**Created:** 2026-08-25, during `review-pr11812-navfw-flash-usage`.

## DMA Conflict Analyzer

**Script:** `dma_conflict_analyzer.py`

Analyzes DMA stream conflicts for INAV flight controller targets.

**Usage:**
```bash
python3 claude/developer/scripts/analysis/dma_conflict_analyzer.py
```

**What it does:**
- Parses timer definitions from target.c
- Checks for DMA stream conflicts between:
  - Motor outputs (TIM1-TIM8 channels)
  - LED strip output
  - UART peripherals (if DMA enabled)
  - SPI peripherals (if DMA enabled)
  - ADC channels
- Validates timer availability for specific MCU types (F405/F7/H7)
- Reports conflicts and warnings

**Customization:**
Edit the script to change:
- `timers[]` - Your timer configuration from target.c
- `uart_dma[]` - UART DMA streams (if USE_UART_DMA is defined)
- `adc_dma[]` - ADC DMA configuration

**Example output:**
```
✓  S1 - Motor 1         TIM2_CH2     PA1    → DMA1 Stream 6
✓  S4 - Motor 4         TIM1_CH1     PA8    → DMA2 Stream 6
🔴 S2 - Motor 2         TIM12_CH1    PB14   - TIM12 NOT AVAILABLE ON F405!
```

**Common issues detected:**
- TIM12 used on F405 (only available on F7/H7)
- Multiple outputs sharing same DMA stream
- UART DMA conflicts with timer outputs (usually harmless - INAV uses interrupts)

---

## Dead Code Detection Scripts

Scripts for detecting and removing unused conditional compilation blocks:

- `detect_dead_code_preprocessor.py` - Find unused #ifdef blocks
- `detect_dead_code_preprocessor_v2.py` - Enhanced version
- `detect_dead_code_gcc_dD.py` - Uses GCC preprocessor output
- `find_dead_else_blocks.sh` - Find dead #else branches
- `remove_dead_conditionals.py` - Automated removal

## Target Splitting Scripts

For splitting multi-board targets (like OMNIBUS):

- `split_omnibus_targets.py` - Python-based target splitter
- `split_omnibus_with_unifdef.sh` - Shell script using unifdef
- `cleanup_omnibusf4_unifdef.sh` - Cleanup helper

## Verification Scripts

- `comprehensive_verification.py` - Multi-stage verification
- `verify_target_conditionals.py` - Check conditional compilation
- `verify_unifdef_simple.py` - Simple unifdef verification
- `verify_with_unifdef.sh` - Shell-based verification
