/* Fixture: static data used in a compile-time constant context — the tool
 * must flag this as "keep, needs constant-expression", NOT "safe to
 * extern". */
#ifndef FIXTURE_CONSTEXPR_H
#define FIXTURE_CONSTEXPR_H

#include <stdint.h>

static const uint8_t lookup_size = 16; /* file-scope static object in header */

static inline uint8_t tableSize(void) { return lookup_size; }

#endif /* FIXTURE_CONSTEXPR_H */
