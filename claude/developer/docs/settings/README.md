# Parameter Group (PG) System Documentation

## Overview

The Parameter Group (PG) system is INAV's mechanism for managing persistent configuration settings stored in EEPROM/flash memory. It provides:

- **Type-safe configuration structures** with compile-time registration
- **Version control** to prevent data corruption when structs change
- **Automatic defaults** when settings are incompatible
- **Linker-based registry** for zero-runtime overhead

## Quick Reference

| Topic | File |
|-------|------|
| Whether a new setting is warranted at all | [when-to-add-a-setting.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/when-to-add-a-setting.md) |
| When to increment versions | [versioning-rules.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/versioning-rules.md) |
| How to register parameter groups | [registration-guide.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/registration-guide.md) |
| Real-world example (PR #11236) | [case-study-pr11236.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/case-study-pr11236.md) |

## Key Concepts

### 1. Parameter Group Registry

The PG system uses **linker sections** to build a compile-time registry:

```c
// Linker provides these symbols
extern const pgRegistry_t __pg_registry_start[];
extern const pgRegistry_t __pg_registry_end[];

// Iterate all registered parameter groups
#define PG_FOREACH(_name) \
    for (const pgRegistry_t *(_name) = __pg_registry_start; \
         (_name) < __pg_registry_end; _name++)
```

Each parameter group is placed in the `.pg_registry` linker section using compiler attributes:
```c
#define PG_REGISTER_ATTRIBUTES __attribute__ ((section(".pg_registry"), used, aligned(4)))
```

### 2. Registry Entry Structure

Each parameter group has a registry entry (`pgRegistry_t`):

```c
typedef struct pgRegistry_s {
    pgn_t pgn;             // Parameter group number + version (top 4 bits)
    uint16_t size;         // Size in bytes + flags (top 4 bits)
    uint8_t *address;      // Runtime address
    uint8_t *copy;         // Copy address (for diff/revert)
    uint8_t **ptr;         // Current profile pointer (for profile configs)
    union {
        void *ptr;         // Default values template
        pgResetFunc *fn;   // Custom reset function
    } reset;
} pgRegistry_t;
```

### 3. Version Encoding

Versions are **embedded in the PGN field** (top 4 bits):

```c
// Extract version from registry entry
static inline uint8_t pgVersion(const pgRegistry_t* reg) {
    return (uint8_t)(reg->pgn >> 12);
}

// Registration macro encodes version
PG_REGISTER_WITH_RESET_TEMPLATE(blackboxConfig_t, blackboxConfig, PG_BLACKBOX_CONFIG, 4);
//                                                                                      ^
//                                                                                   version 4
```

**Important**: Version range is 0-15 (4 bits).

### 4. Version Validation

The `pgLoad()` function enforces version compatibility:

```c
void pgLoad(const pgRegistry_t* reg, int profileIndex,
            const void *from, int size, int version)
{
    pgReset(reg, profileIndex);  // Step 1: Reset to defaults

    if (version == pgVersion(reg)) {  // Step 2: Check version match
        const int take = MIN(size, pgSize(reg));
        memcpy(pgOffset(reg, profileIndex), from, take);  // Step 3: Copy if match
    }
    // If version mismatch, defaults remain (safe fallback)
}
```

**Critical behavior**: If stored version ≠ firmware version, settings **remain at defaults**. This prevents corruption when struct layout changes.

### 5. System vs Profile Groups

Parameter groups can be:

- **System groups**: Single instance (e.g., `systemConfig`)
- **Profile groups**: Multiple instances, one per profile (e.g., `pidConfig`)

Profile groups use the `PGR_SIZE_PROFILE_FLAG` in the size field:
```c
static inline uint16_t pgIsProfile(const pgRegistry_t* reg) {
    return (reg->size & PGR_SIZE_PROFILE_FLAG) == PGR_SIZE_PROFILE_FLAG;
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Compile Time: Registration                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  PG_REGISTER_WITH_RESET_TEMPLATE(...)                  │
│       │                                                  │
│       ├─> Creates: myConfig_System (RAM storage)        │
│       ├─> Creates: myConfig_Copy (for diff/revert)      │
│       ├─> Creates: pgResetTemplate_myConfig (defaults)  │
│       └─> Creates: myConfig_Registry (in .pg_registry)  │
│                                                          │
│  Linker collects all into:                              │
│       .pg_registry section                              │
│       .pg_resetdata section                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Runtime: Loading Settings                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Boot: Iterate PG_FOREACH() to find all groups       │
│  2. EEPROM: Read stored version + data                  │
│  3. pgLoad():                                            │
│       a. Reset group to defaults (pgReset)              │
│       b. Check version match                            │
│       c. If match: Copy stored data                     │
│          If mismatch: Keep defaults (corruption avoided)│
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Common Operations

### Register a New Parameter Group

```c
// In myfeature.h
typedef struct myFeatureConfig_s {
    uint8_t enabled;
    uint16_t rate;
} myFeatureConfig_t;

PG_DECLARE(myFeatureConfig_t, myFeatureConfig);

// In myfeature.c
PG_REGISTER_WITH_RESET_TEMPLATE(myFeatureConfig_t, myFeatureConfig, PG_MY_FEATURE, 0);

PG_RESET_TEMPLATE(myFeatureConfig_t, myFeatureConfig,
    .enabled = 1,
    .rate = 100
);
```

### Change a Parameter Group Structure

**When you modify the struct, you MUST increment the version** (see [versioning-rules.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/versioning-rules.md)):

```c
// Before (version 2)
typedef struct myConfig_s {
    uint8_t field1;
    uint8_t field2;  // <-- Removing this
} myConfig_t;
PG_REGISTER_WITH_RESET_TEMPLATE(myConfig_t, myConfig, PG_MY_CONFIG, 2);

// After (version 3 - MUST increment!)
typedef struct myConfig_s {
    uint8_t field1;
} myConfig_t;
PG_REGISTER_WITH_RESET_TEMPLATE(myConfig_t, myConfig, PG_MY_CONFIG, 3);
```

## File Locations

- **Header**: `src/main/config/parameter_group.h` - Macros and declarations
- **Implementation**: `src/main/config/parameter_group.c` - Runtime functions (pgLoad, pgStore, etc.)
- **Settings mapping**: `src/main/fc/settings.yaml` - Maps CLI settings to PG fields

## Relationship to settings.yaml

The `settings.yaml` file maps CLI setting names to parameter group fields:

```yaml
- name: blackbox_device
  field: blackboxConfig.device
  type: uint8_t
  min: 0
  max: 2
```

When a setting is changed via CLI or configurator:
1. The setting name is looked up in settings.yaml
2. The `field` entry identifies which PG and which field
3. The value is written to the RAM copy of the parameter group
4. On `save`, all dirty parameter groups are written to EEPROM

**Important**: Removing a field from a PG requires removing its settings.yaml entry.

## See Also

- [versioning-rules.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/versioning-rules.md) - Detailed rules for when to increment versions
- [registration-guide.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/registration-guide.md) - Step-by-step guide for registering PGs
- [case-study-pr11236.md](https://github.com/iNavFlight/inav/blob/maintenance-10.x/docs/development/settings/case-study-pr11236.md) - Real-world example of version increment requirement
