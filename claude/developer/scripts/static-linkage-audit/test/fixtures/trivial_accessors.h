/* Fixture: trivial one-line accessors — the "safe" pattern from INAV's own
 * code (settings.h, ledstrip.h, utils.h, etc.). No local static data. */
#ifndef FIXTURE_TRIVIAL_H
#define FIXTURE_TRIVIAL_H

#include <stdint.h>

typedef struct {
    uint32_t type;
    uint32_t position;
} cfg_t;

static inline uint32_t cfgGetType(const cfg_t *c) { return c->type & 0xF; }
static inline uint32_t cfgGetPosition(const cfg_t *c) { return c->position; }
static inline int16_t cmp16(uint16_t a, uint16_t b) { return (int16_t)(a - b); }
static inline int32_t cmp32(uint32_t a, uint32_t b) { return (int32_t)(a - b); }

#endif /* FIXTURE_TRIVIAL_H */
