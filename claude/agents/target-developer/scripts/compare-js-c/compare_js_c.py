#!/usr/bin/env python3
"""Compare the configurator's JS output-mapping algorithm against the C model.

The firmware's pwmBuildTimerOutputList() mutates the global timerHardware[]
usageFlags at boot, and MSP2_INAV_OUTPUT_MAPPING_EXT2 returns those
post-resolution flags. The configurator's outputMapping.js getTimerMap()
then re-derives the output table from those flags + the current mixer
motor/servo counts. If the JS algorithm doesn't match the C algorithm, the
Mixer tab preview disagrees with what the firmware actually drives.

This harness:
  1. Runs the C model (simulate_pwm_roles.simulate) on a target or synthetic
     fixture to get the ground-truth per-output buckets and the
     post-resolution flags (what MSP would send).
  2. Feeds those flags + motor/servo counts into the REAL outputMapping.js
     (via node drive.mjs) to get the JS table.
  3. Diffs per output pad and prints mismatches.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "claude/agents/target-developer/scripts"))
import simulate_pwm_roles as sim

DRIVE_JS = Path(__file__).resolve().parent / "drive.mjs"
BUNDLE = Path(__file__).resolve().parent / ".bundle" / "drive.bundle.mjs"
ESBUILD = REPO / "inav-configurator/node_modules/.bin/esbuild"


def ensure_bundle():
    """Bundle drive.mjs + the real outputMapping.js/bitHelper with the
    configurator's own esbuild (resolves the extensionless `./bitHelper`
    import the same way Vite does)."""
    if BUNDLE.is_file() and BUNDLE.stat().st_mtime >= DRIVE_JS.stat().st_mtime:
        return
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(ESBUILD), str(DRIVE_JS), "--bundle", "--platform=node",
         "--format=esm", f"--outfile={BUNDLE}"],
        check=True, capture_output=True, text=True,
    )

TIM_USE_MOTOR = 1 << 2
TIM_USE_SERVO = 1 << 3
TIM_USE_LED = 1 << 24
TIM_USE_PPM = 1 << 0
TIM_USE_PWM = 1 << 1


def run_js(entries, motors, servos, is_mr):
    """Feed post-resolution flags to the real JS and return its output table."""
    js_entries = [
        {
            "timerId": e["timerId"],
            "usageFlags": e["usageFlags"],
            "specialLabels": e.get("specialLabels", 0),
        }
        for e in entries
        # mirror the firmware MSP filter: PPM/PWM pads are not sent
        if not (e["usageFlags"] & (TIM_USE_PPM | TIM_USE_PWM))
    ]
    payload = {"entries": js_entries, "motors": motors, "servos": servos, "isMR": is_mr}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    try:
        out = subprocess.run(
            ["node", str(BUNDLE), path], capture_output=True, text=True, check=True
        )
        # outputMapping.js logs per-output debug lines to stdout; the JSON
        # result is the final line.
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        Path(path).unlink(missing_ok=True)


def c_model_table(target_dir, motor_count, servo_count, timer_output_modes=None,
                  entries_override=None, servos=None):
    """Run the C model; return (feed, c_labels).

    feed:     list of {timerId, usageFlags} in MSP order (post-resolution flags)
    c_labels: per-output display strings in the same order, derived from the C
              model buckets ("Motor N", "Servo <name>", "Led", "-")
    """
    if entries_override is not None:
        entries = sim.parse_target_c(entries_override)
        family, adc_pins, led_strip, dshot_dmar, target_h_text = "F4", set(), False, False, ""
    else:
        target_c = target_dir / "target.c"
        target_h = target_dir / "target.h"
        cmake = target_dir / "CMakeLists.txt"
        entries = sim.parse_target_c(target_c.read_text(errors="ignore"))
        family = sim.detect_family(cmake.read_text(errors="ignore")) if cmake.is_file() else None
        adc_pins, led_strip, dshot_dmar = (set(), False, False)
        if target_h.is_file():
            adc_pins, led_strip, dshot_dmar = sim.parse_target_h(target_h.read_text(errors="ignore"))
        target_h_text = target_h.read_text(errors="ignore") if target_h.is_file() else ""

    dma_resolver = sim.DmaResolver(family or "F4", target_dir, target_h_text, dshot_dmar)
    if servos is not None:
        servo_count = len(servos)
    result = sim.simulate(entries, motor_count, servo_count, adc_pins, led_strip,
                          dma_resolver, True, timer_output_modes)

    feed, c_labels = [], []
    for row in result.rows:
        e = row["entry"]
        if e.flags & (TIM_USE_PPM | TIM_USE_PWM):
            continue  # firmware MSP filter
        feed.append({"timerId": e.tim, "usageFlags": e.flags})
        b, pos, driven = row["bucket"], row["position"], row["driven"]
        # Driven-semantics reference: only pads the firmware actually drives
        # (pwmInitMotors/pwmInitServos truncate by mixer budget) get labels;
        # servo labels use the mixer's servo names like the JS does.
        if b == "MOTOR" and driven:
            c_labels.append(f"Motor {pos + 1}")
        elif b == "SERVO" and driven and servos:
            c_labels.append(f"Servo {servos[pos] if pos < len(servos) else pos + 1}")
        elif b.startswith("LED"):
            c_labels.append("Led")
        else:
            c_labels.append("-")  # undriven motor/servo, unclaimed, or skipped
    return feed, c_labels


def compare(name, feed, c_labels, motors, servos, is_mr):
    js = run_js(feed, motors, servos, is_mr)
    js_table = js["outputTable"]
    mismatches = []
    for i, (js_label, c_label) in enumerate(zip(js_table, c_labels)):
        if js_label != c_label:
            mismatches.append((i, js_label, c_label))
    if not mismatches and len(js_table) != len(c_labels):
        mismatches.append(("LEN", len(js_table), len(c_labels)))
    status = "OK" if not mismatches else f"{len(mismatches)} MISMATCH(ES)"
    print(f"[{status}] {name} (motors={motors}, servos={servos})")
    for i, js_label, c_label in mismatches:
        print(f"    output {i}: JS='{js_label}'  C='{c_label}'")
    return not mismatches


def main():
    ensure_bundle()
    inav3 = REPO / "inav3" / "src" / "main" / "target"
    resolver_dir = inav3 / "MATEKF405"  # any real target dir: DmaResolver only
                                          # needs it to locate the family header
    all_ok = True

    # --- Synthetic: all-motor-only group (the PR #11787 regression shape) ---
    SYN = """
timerHardware_t timerHardware[] = {
    DEF_TIM(TIM_A,  CH1, PA1,  TIM_USE_MOTOR,            1, 0), // A1
    DEF_TIM(TIM_A,  CH2, PA2,  TIM_USE_MOTOR,            1, 0), // A2
    DEF_TIM(TIM_B,  CH1, PA3,  TIM_USE_OUTPUT_AUTO,      1, 0), // B1
};
"""
    feed, c = c_model_table(resolver_dir, 2, None, entries_override=SYN, servos=[])
    all_ok &= compare("synthetic: all-motor-only group, mc=2", feed, c, 2, [], True)
    feed, c = c_model_table(resolver_dir, 3, None, entries_override=SYN, servos=[])
    all_ok &= compare("synthetic: all-motor-only group, mc=3", feed, c, 3, [], True)

    # --- Synthetic: mixed group (1 motor + 1 AUTO sibling on same timer) ---
    MIX = """
timerHardware_t timerHardware[] = {
    DEF_TIM(TIM_A,  CH1, PA1,  TIM_USE_MOTOR,            1, 0), // A1
    DEF_TIM(TIM_A,  CH2, PA2,  TIM_USE_OUTPUT_AUTO,      1, 0), // A2
    DEF_TIM(TIM_B,  CH1, PA3,  TIM_USE_OUTPUT_AUTO,      1, 0), // B1
};
"""
    feed, c = c_model_table(resolver_dir, 2, None, entries_override=MIX, servos=[])
    all_ok &= compare("synthetic: mixed group, mc=2", feed, c, 2, [], True)
    feed, c = c_model_table(resolver_dir, 3, None, entries_override=MIX, servos=[])
    all_ok &= compare("synthetic: mixed group, mc=3", feed, c, 3, [], True)

    # --- Synthetic: motor + servo-declared sibling on the SAME timer (the
    # "a timer used for motors can't also drive servos" rule) ---
    MS = """
timerHardware_t timerHardware[] = {
    DEF_TIM(TIM_A,  CH1, PA1,  TIM_USE_MOTOR,            1, 0), // A1 motor
    DEF_TIM(TIM_A,  CH2, PA2,  TIM_USE_SERVO,            1, 0), // A2 servo (same timer!)
    DEF_TIM(TIM_B,  CH1, PA3,  TIM_USE_OUTPUT_AUTO,      1, 0), // B1
};
"""
    feed, c = c_model_table(resolver_dir, 1, None, entries_override=MS, servos=["S1"])
    all_ok &= compare("synthetic: motor+servo same timer, mc=1, 1 servo",
                      feed, c, 1, ["S1"], True)

    # --- Real targets from the shared-timer survey ---
    for tgt, mc, servos in [
        ("AOCODARCF722AIO", 4, []),
        ("AOCODARCF722AIO", 2, ["S1"]),
        ("FOXEERF405V2", 4, []),
        ("FOXEERF405V2", 2, ["S3"]),
        ("SPRACINGF7DUAL", 6, []),
        ("SPRACINGF7DUAL", 4, ["S1"]),
        ("MATEKF405", 4, []),
        ("MATEKF405", 3, ["S1", "S2"]),
    ]:
        d = inav3 / tgt
        if not d.exists():
            print(f"[SKIP] {tgt} not on this branch")
            continue
        feed, c = c_model_table(d, mc, None, servos=servos)
        all_ok &= compare(f"real: {tgt} mc={mc}", feed, c, mc, servos, True)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
