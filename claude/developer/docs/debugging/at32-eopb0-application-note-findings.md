# AT32 EOPB0 Configuration - Application Note AN0026 Findings

**Date:** 2026-01-05
**Source:** AT32_F435_AN0026_Extending_SRAM_in_Users_Program_EN_V2.0.0.pdf
**Branch:** `inav/at32-sram-zw-flash-config`

## Critical Discovery: Why We Bricked the Flight Controller

After bricking the BLUEBERRYF435WING by attempting EOPB0 configuration, we found the official AT32 Application Note AN0026 which explains **exactly why our approach failed**.

### Root Cause: Stack Pointer Initialization Order

**The Problem:**

From AT32 AN0026, page 8:

> "The EOPB0 must be changed at the beginning of Reset_Handler, instead of being modified in the SystemInit( ) function. Because the SRAM size set by the user in the Keil/IAR environment may be the extended 224 KB, and the actually used SRAM may exceed the default 96 KB, in this case, the initial value of the stack point will be set to the address after 96 KB, and error will occur when executing SystemInit( ), or even enter HardFault to trigger a crash."

**What this means:**

1. **Linker Script Says:** 192KB SRAM available (our at32_flash_f43xG.ld)
2. **EOPB0 Register Says:** 96KB SRAM (factory default, or whatever was last configured)
3. **Reset_Handler Does:** Sets `SP = _estack` (end of 192KB RAM = 0x20030000)
4. **Hardware Reality:** Only 96KB RAM exists (ends at 0x20018000)
5. **Result:** Stack pointer points to **non-existent memory**
6. **Outcome:** Any stack operation → HardFault → Flash protection triggered

### The Correct Sequence (per AT32 AN0026)

```
Reset_Handler:
  1. Set SP to SAFE address within guaranteed 96KB
     (e.g., 0x20001000 as shown in AT32 example)

  2. Call extend_sram() to check/configure EOPB0
     - If EOPB0 needs changing: erase USD, program EOPB0, reset
     - If EOPB0 already correct: return immediately

  3. Set SP to full _estack (now safe - EOPB0 configured)

  4. Continue normal boot (persistentObjectInit, etc.)
```

**Why we failed:**
- We called `init_sram_config()` from `systemInit()`
- By that time, `Reset_Handler` had already set `SP = _estack`
- If EOPB0 was default 96KB, SP pointed to invalid memory
- Any function call/stack operation → **immediate HardFault**

## Critical Implementation Requirements

### 1. Timing: MUST Be First in Reset_Handler

From AT32 AN0026, page 8:

> "Before calling the extend_SRAM( ) function, the stack pointer must be placed within 96 KB (changed to 0x20001000 in this example) to prevent the initial value of the stack pointer from being set to the address outside 96 KB and cause an error during the execution of extend_SRAM( )."

**Assembly code pattern (from AT32 example):**

```asm
Reset_Handler:
  ; FIRST: Set temporary SP within safe 96KB range
  MOVW  R0, #0x1000        ; 0x20001000
  MOVT  R0, #0x2000
  MOV   SP, R0

  ; SECOND: Configure EOPB0
  BL    extend_sram        ; Will reset if EOPB0 needs changing

  ; THIRD: Now safe to use full stack
  LDR   SP, =_estack

  ; FOURTH: Continue normal boot
  BL    SystemInit
  ...
```

### 2. Function Constraints

**The `extend_sram()` function has strict limitations:**

1. **No global variables** - Called before .data/.bss initialization
2. **No logging** - No printf, LOG_DEBUG, etc. (not initialized yet)
3. **Minimal stack usage** - Only 4KB stack available (96KB - temp SP position)
4. **No complex library calls** - Keep it simple and direct

### 3. Flash Write Sequence

**Correct sequence (from AT32 SDK and AN0026):**

```c
void extend_sram(void)
{
    // 1. Check if EOPB0 matches desired configuration
    uint8_t current = (USD->eopb0) & MASK;

    if (current != desired) {
        // 2. Unlock USD
        flash_unlock();

        // 3. ERASE entire USD area
        flash_user_system_data_erase();

        // 4. Program new EOPB0 value
        flash_user_system_data_program((uint32_t)&USD->eopb0, desired);

        // 5. MUST reset to apply new configuration
        nvic_system_reset();
    }

    // EOPB0 already correct, return to continue boot
}
```

**Key points:**
- USD erase **clears all bits**, so writing `0x0005` directly is correct
- **NO read-modify-write needed** - erase handles it
- **MUST reset** after programming for EOPB0 to take effect

## What We Tried (Failed Attempts)

### Attempt 1: EOPB0 in systemInit() BEFORE clock config
- **Result:** Bricked FC
- **Why it failed:** SP already pointing to invalid RAM

### Attempt 2: EOPB0 in systemInit() AFTER clock config
- **Result:** Bricked FC
- **Why it failed:** SP still pointing to invalid RAM

### Attempt 3: Disabled EOPB0 (read-only diagnostic)
- **Result:** FC booted successfully
- **Why it worked:** No flash writes, no changes

### Never Tested: CLI command approach
- **Status:** Theoretical only, not proven safe
- **Concern:** Still doesn't solve the boot-time SP problem

## EOPB0 Register Details

### Register Location

- **USD Base Address:** `0x1FFFC000`
- **EOPB0 Offset:** `0x10` (16-bit register)
- **Full Address:** `0x1FFFC010`

### EOPB0 Values for AT32F435/437 (1024KB Flash)

| SRAM Size | EOPB0 Value | Zero-Wait Flash | Non-Zero-Wait Flash |
|-----------|-------------|-----------------|---------------------|
| 512KB     | 0x00        | 128KB           | 864KB               |
| 448KB     | 0x01        | 192KB           | 800KB               |
| 384KB     | 0x02        | 256KB           | 736KB               |
| 320KB     | 0x03        | 320KB           | 672KB               |
| 256KB     | 0x04        | 384KB           | 608KB               |
| **192KB** | **0x05**    | **448KB**       | **560KB**           |
| 128KB     | 0x06        | 512KB           | 480KB               |

**Recommended for INAV:** 192KB SRAM (EOPB0 = 0x05)
- Good balance for INAV workloads
- 448KB zero-wait flash (runs at full 288MHz CPU speed)
- 560KB non-zero-wait flash (2-3 wait states, 3-4x slower)

### Bit Masking

**For 1024KB flash targets:**
- Mask: `0x7` (bits 0-2)
- Bits 3-15: Reserved (should be 0 after USD erase)

**For 256KB/448KB flash targets:**
- Mask: `0x3` (bits 0-1)
- Bits 2-15: Reserved

### Flash Write Method

**Question:** Should we use read-modify-write to preserve upper bits?

**Answer:** NO - `flash_user_system_data_erase()` clears ALL bits in USD area first.

From Betaflight code:
```c
flash_unlock();
flash_user_system_data_erase();  // ← Clears ENTIRE USD area
flash_user_system_data_program((uint32_t)&USD->eopb0, value);
```

Upper bits are already zero after erase, so writing `0x0005` directly is correct.

## Hardware Compatibility

AT32F43x chips are **compatible with STM32 tools** despite being from different manufacturers:

- **Artery Technology:** AT32F435/437 (ARM Cortex-M4)
- **STMicroelectronics:** STM32F4 family (same core)
- **USB VID:PID:** `2E3C:DF11` (Artery) vs `0483:DF11` (STM32)
- **DFU Protocol:** Same protocol, tools are cross-compatible
- **Programming Tools:** STM32CubeProgrammer, ST-Link all work with AT32

## Recovery Information

See `inav/docs/development/at32-flash-recovery.md` for:
- STM32CubeProgrammer recovery procedure
- ST-Link SWD recovery
- Alternative recovery methods
- Flash protection unlocking

## Implementation Status

**Current Code State:**

1. ✅ `extend_sram()` function created in `system_at32f43x.c`
   - Minimal implementation, no logging
   - No global variables
   - Follows AT32 SDK sequence

2. ✅ `startup_at32f435_437.s` modified
   - Sets temporary SP to 0x20001000 (within 96KB)
   - Calls `extend_sram()` FIRST
   - Then sets SP to _estack
   - Continues normal boot

3. ✅ `systemInit()` updated
   - Removed `init_sram_config()` call
   - Added documentation note

**Testing Status:**
- ⚠️ **NOT TESTED YET** - Requires FC recovery first
- ⚠️ Current FC is bricked with flash protection
- ⚠️ Need STM32CubeProgrammer or ST-Link to recover

## Lessons Learned

### 1. Read Vendor Documentation FIRST
The AT32 Application Note AN0026 existed all along and would have prevented the bricked FC. **Always check vendor app notes before attempting risky flash operations.**

### 2. Betaflight May Not Be Universal
Betaflight's approach (EOPB0 in systemInit) worked for them, but our testing shows it's not reliable across all hardware. Vendor documentation is more authoritative than reference implementations.

### 3. Stack Pointer is Critical
Understanding the boot sequence and stack initialization is **essential** for low-level configuration. The SP initialization order was the root cause we missed.

### 4. Flash Protection is Catastrophic
Once flash protection is triggered:
- DFU cannot help
- Requires hardware debugger (ST-Link/J-Link)
- No software-only recovery possible
- Prevention is critical

### 5. Test Incrementally with Recovery Plan
**Before attempting risky operations:**
- Have ST-Link hardware available
- Document recovery procedures FIRST
- Test on expendable hardware if possible
- Keep backup of known-good firmware

## Next Steps

1. **Recover bricked BLUEBERRYF435WING**
   - Use STM32CubeProgrammer or ST-Link
   - Unlock flash protection
   - Mass erase flash
   - Flash known-good firmware

2. **Test corrected implementation**
   - Build firmware with new Reset_Handler code
   - Flash to recovered FC
   - Verify EOPB0 configuration works
   - Monitor via serial (if possible) or LED indicators

3. **Document results**
   - Update recovery guide with actual recovery experience
   - Document successful (or failed) EOPB0 configuration
   - Share findings with INAV community

## References

1. **AT32_F435_AN0026_Extending_SRAM_in_Users_Program_EN_V2.0.0.pdf**
   - Official Artery Technology application note
   - Location: `~/Documents/electronics/`

2. **AT32F435/437 Reference Manual**
   - Flash Controller chapter
   - USD (User System Data) section

3. **AT32F435/437 Datasheet**
   - https://www.arterychip.com/en/product/AT32F435.jsp

4. **INAV Implementation**
   - Branch: `at32-sram-zw-flash-config`
   - Files: `system_at32f43x.c`, `startup_at32f435_437.s`

5. **Recovery Documentation**
   - `inav/docs/development/at32-flash-recovery.md`

---

**Author:** Developer (with Claude Code assistance)
**Last Updated:** 2026-01-05
**Status:** Implementation complete, testing blocked on FC recovery
