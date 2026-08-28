# Pitch Angle vs. Airspeed Relationship (Constant Throttle)

## Summary

**Core principle:** With constant thrust, pitch angle and airspeed have an **inverse relationship** in steady flight.

- **Pitch up** → Angle of attack increases → CL increases → Airspeed decreases
- **Pitch down** → Angle of attack decreases → CL decreases → Airspeed increases

## Fundamental Equations

### Lift Equation
```
L = CL × ½ρV²S
```

### Equilibrium Condition
```
L = W  (steady flight)
```

### Airspeed as Function of Lift Coefficient
```
V = √(2W / ρSCL)
```

**Key insight:** V ∝ 1/√CL

### Lift Coefficient vs. Angle of Attack
```
CL = a₀ × α

Where a₀ ≈ 2π per radian (theoretical, thin airfoil)
      a₀ ≈ 1.8π(1 + 0.8t/c) per radian (finite thickness)
```

**Reference:** Houghton & Carpenter Eqn 1.66, page 62

### Relationship Chain
```
Pitch (θ) → Angle of Attack (α) → Lift Coefficient (CL) → Airspeed (V)
```

More precisely:
```
α ≈ θ - γ  (where γ is flight path angle)
```

## Textbook References

### Houghton & Carpenter Page Citations

**Pages 45-46:** Lift coefficient definition and basic aerodynamics
- CL = lift / (½ρV²S)
- Fundamental relationship between forces

**Pages 62-63:** Lift curve slope and stalling characteristics
- Two-dimensional lift-curve slope: dCL/dα = 2π per radian (thin airfoil)
- Finite thickness correction: dCL/dα = 1.8π(1 + 0.8t/c)
- Stalling angle αs ≈ 18° for conventional sections
- Maximum lift coefficient CLmax ≈ 1.5 (typical)

**Pages 64-65:** Drag characteristics
- Total drag: CD = CD₀ + CDi
- Induced drag: CDi = CL² / (πAe)
- Drag varies with lift coefficient
- Minimum drag occurs at specific CL

**Page 47-48:** Aspect ratio effects
- Three-dimensional wings have induced drag
- Aspect ratio affects lift-curve slope

## Stall Constraints

### Minimum Airspeed
```
Vmin = √(2W / ρSCLmax)
```

**Critical:** Pitching up beyond stall angle (αs) does NOT increase CL. Instead, the wing stalls and lift collapses.

**Stall characteristics (page 62):**
- Occurs at αs ≈ 18° (typical conventional airfoil)
- CLmax ≈ 1.5 (typical value)
- After stall, CL decreases despite higher angle of attack

### Factors Affecting Stall Speed
1. **Wing loading (W/S):** Higher loading → higher Vstall
2. **Air density (ρ):** Lower density (altitude, temperature) → higher Vstall
3. **Bank angle:** Effective weight = W/cos(φ) → Vstall increases in turns
4. **Airfoil design:** CLmax varies by section type

## Drag and Speed Equilibrium

With constant thrust T, the aircraft seeks equilibrium where:
```
T = D = CD × ½ρV²S
```

**Speed stability regions:**

### Below Minimum Drag Speed
- High CL (nose up, slow)
- Induced drag dominates: CDi = CL²/(πAe)
- Pitching up further → CL increases → drag increases faster than thrust can compensate
- Result: Deceleration

### Above Minimum Drag Speed
- Low CL (nose down, fast)
- Parasitic drag dominates: CD₀ × V²
- Pitching down → speed increases → parasitic drag increases
- Result: Acceleration until new equilibrium

## INAV Flight Controller Applications

### 1. Altitude and Speed Control
In fixed-wing mode, INAV uses coupled control:
- **Pitch controls airspeed** (by modulating angle of attack)
- **Throttle controls altitude/energy**

This is aerodynamically correct for constant-throttle scenarios.

### 2. Stall Prevention Logic
```c
// Conceptual INAV logic
if (airspeed < safety_margin * Vstall) {
    limit_pitch_up_command();
    increase_throttle();
    alert_pilot();
}
```

### 3. Angle of Attack Estimation
Without AoA sensor, INAV can estimate:
```
α ≈ pitch_angle - flight_path_angle
α ≈ θ - arctan(climb_rate / ground_speed)
```

Combined with airspeed, this provides:
- Proximity to stall warning
- CL estimation: CL ≈ 2W / (ρV²S)
- Flight efficiency assessment

### 4. Mission Planning Implications
Understanding V-CL relationship helps predict:
- **Climb performance:** Higher pitch → slower speed → higher induced drag → reduced rate of climb
- **Descent profiles:** Lower pitch → higher speed → energy management for landing
- **Loiter efficiency:** Minimum drag speed (L/Dmax) occurs at specific CL

### 5. Wind and Turbulence Compensation
- Vertical gusts change effective angle of attack independently of pitch
- INAV must filter transient airspeed changes from true pitch-speed relationship
- Phugoid damping requires understanding coupled pitch-speed dynamics

## Practical Flight Considerations

### 1. Phugoid Oscillation
Disturbing pitch at constant throttle induces long-period oscillation:
- Aircraft exchanges potential energy (altitude) for kinetic energy (speed)
- Period: typically 30-60 seconds
- Damping depends on drag characteristics

### 2. Trim Speed
In cruise, aircraft naturally seeks trim speed where:
- Pitch moment balanced (CM = 0 about CG)
- Lift = Weight
- Thrust = Drag

Changing pitch from trim requires sustained control input or re-trimming.

### 3. Power Effects (Real Engines)
- Propeller efficiency varies with speed
- Thrust decreases at high speeds (prop efficiency drops)
- Thrust varies with RPM (constant throttle ≠ constant thrust exactly)

### 4. Configuration Changes
- Flaps extended → CLmax higher → Vstall lower → different pitch-speed relationship
- Landing gear extended → CD₀ higher → higher drag at all speeds

## Key Flight Maxims

**"Pitch for speed, power for altitude"** - Traditional pilot wisdom for constant-throttle flight

**More precisely:**
- Short term: Pitch affects speed immediately via AoA change
- Long term: Energy management couples pitch, power, altitude, and speed
- Complete system: All four forces (L, D, T, W) interact dynamically

## Mathematical Summary

Starting from equilibrium:
```
L = W = CL × ½ρV²S
V = √(2W / ρSCL)

CL = a₀ × α
α ≈ θ - γ

Therefore:
V ∝ 1/√CL ∝ 1/√α ∝ 1/√(θ - γ)
```

**In words:** Airspeed is inversely proportional to the square root of angle of attack, which is directly influenced by pitch angle.

## References

**Primary source:** Houghton, E.L. and Carpenter, P.W. (2003) *Aerodynamics for Engineering Students*, 5th Edition, Butterworth-Heinemann.

**Key pages:**
- 26-49: Basic aerodynamics and force coefficients
- 45-46: Lift coefficient definition
- 47-48: Aspect ratio effects
- 62-67: Lift curves, stall, and drag characteristics

**INAV relevance:**
- Fixed-wing navigation control laws
- Stall prevention and airspeed protection
- Mission planning and energy management
- Flight dynamics modeling

**Complementary scenario:** this file covers pitch's effect on airspeed at
*constant throttle*. For the reverse — throttle's compensation for pitch to
hold *constant airspeed* (the `nav_fw_pitch2thr` setting) — see
`power-flight-path-angle.md` in this directory and
`inav/docs/development/fixed-wing-pitch2thr-tuning.md` upstream.

---

*Created: 2026-01-18*
*Agent: aerodynamics-expert*
*Task: Explain airspeed-pitch relationship at constant throttle*
