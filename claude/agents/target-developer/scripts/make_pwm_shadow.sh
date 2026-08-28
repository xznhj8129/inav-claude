#!/usr/bin/env bash
# make_pwm_shadow.sh -- scaffold an isolated "shadow" inav_root for testing a
# candidate target.c edit against simulate_pwm_roles.py without touching the
# real checkout and without tripping over parse_target_c()'s #ifdef-
# flattening blind spot (see phase1-findings.md in
# investigate-shared-tim-dma-request-lines: it silently concatenates
# #if/#else DEF_TIM blocks into one array, which can corrupt position
# numbers for targets that use conditional compilation in target.c, e.g.
# FF_PIKOF4/FF_PIKOF4OSD).
#
# What it does:
#   1. Creates <shadow_dir>/src/main/drivers as a symlink to the real
#      inav_root's drivers dir (read-only reuse, no copy).
#   2. Creates <shadow_dir>/src/main/target/<shadow_name>/ with COPIES of
#      the real target's CMakeLists.txt (rewritten to declare
#      <shadow_name> instead of the original target macro) and target.h.
#   3. Copies target.c VERBATIM if the real file has no #if/#ifdef/#ifndef
#      directives; otherwise copies target.c but PRINTS A WARNING -- you
#      must hand-edit the copy down to a single flat DEF_TIM block
#      representing the ONE build variant you actually care about before
#      trusting simulate_pwm_roles.py's output (position numbers WILL be
#      wrong otherwise).
#
# You then hand-edit
# <shadow_dir>/src/main/target/<shadow_name>/target.c to apply your
# candidate DEF_TIM change, and run e.g.:
#   python3 simulate_pwm_roles.py <shadow_dir> --target <shadow_name> \
#       --motor-count 4
#
# Usage: make_pwm_shadow.sh <inav_root> <real_target_name> <shadow_dir> [shadow_name]
set -euo pipefail

INAV_ROOT="$1"
REAL_TARGET="$2"
SHADOW_DIR="$3"
SHADOW_NAME="${4:-${REAL_TARGET}_SHADOW}"

REAL_TARGET_DIR="$INAV_ROOT/src/main/target/$REAL_TARGET"
if [ ! -d "$REAL_TARGET_DIR" ]; then
    echo "error: no such target dir: $REAL_TARGET_DIR" >&2
    exit 1
fi

mkdir -p "$SHADOW_DIR/src/main/target/$SHADOW_NAME"
ln -sfn "$(cd "$INAV_ROOT/src/main/drivers" && pwd)" "$SHADOW_DIR/src/main/drivers"

cp "$REAL_TARGET_DIR/target.h" "$SHADOW_DIR/src/main/target/$SHADOW_NAME/target.h"
cp "$REAL_TARGET_DIR/target.c" "$SHADOW_DIR/src/main/target/$SHADOW_NAME/target.c"
echo "target_stm32_placeholder(${SHADOW_NAME})" > "$SHADOW_DIR/src/main/target/$SHADOW_NAME/CMakeLists.txt"
# detect_family() just scans CMakeLists.txt text for target_stm32<family>xx(
# macro names -- reuse whichever macro the real target used so family
# detection (F4/F7/H7/AT32) still works.
grep -m1 -oE 'target_stm32[a-z0-9]+' "$REAL_TARGET_DIR/CMakeLists.txt" \
    | head -1 | xargs -I{} sed -i "s/target_stm32_placeholder/{}/" \
    "$SHADOW_DIR/src/main/target/$SHADOW_NAME/CMakeLists.txt"

if grep -qE '^\s*#\s*(if|ifdef|ifndef)\b' "$REAL_TARGET_DIR/target.c"; then
    echo "WARNING: $REAL_TARGET/target.c has conditional compilation" \
         "(#if/#ifdef/#ifndef). parse_target_c() will flatten ALL" \
         "branches into one array, corrupting position numbers." \
         "Hand-edit $SHADOW_DIR/src/main/target/$SHADOW_NAME/target.c down" \
         "to a single flat DEF_TIM block for the variant you care about" \
         "before trusting simulate_pwm_roles.py output." >&2
fi

echo "Shadow target ready: $SHADOW_DIR  (--target $SHADOW_NAME)"
