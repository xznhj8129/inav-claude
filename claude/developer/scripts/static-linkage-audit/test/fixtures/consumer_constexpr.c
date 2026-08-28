/* Fixture consumer: uses the constexpr fixture's static object in a
 * compile-time constant context (static initializer) — the safety pass must
 * detect this. */
#include "constexpr_usage.h"

static uint8_t buf[lookup_size]; /* array bound from static-in-header object */
