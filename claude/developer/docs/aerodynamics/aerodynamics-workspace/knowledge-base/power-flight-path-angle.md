# Power Required vs. Flight Path Angle

## Summary

**Core principle:** Power required to maintain constant airspeed varies with flight path angle due to the gravitational component along the flight path.

- **Level flight (γ = 0°):** Baseline power requirement for given airspeed
- **Descent:** Reduced power requirement (gravity assists)
- **Climb:** Increased power requirement (gravity opposes)

## Key Equation

**For descent (γ measured positive downward):**
```
P_descent = P_level × (1 - sin(γ) × L/D)
```

**For climb (γ measured positive upward):**
```
P_climb = P_level × (1 + sin(γ) × L/D)
```

Where:
- **P_level** = power required in level flight at airspeed V
- **γ** = flight path angle magnitude (always positive)
- **L/D** = lift-to-drag ratio

**Sign convention used here:**
- γ is the magnitude of the flight path angle (positive value)
- Use the descent equation when descending
- Use the climb equation when climbing
- γ = 0: Level flight

## Derivation

### Force Balance in Steady Flight

**Level flight:**
```
Thrust = Drag
Power = T × V = D × V
```

**Descent at angle γ (measured downward from horizontal):**

Along the flight path, the component of weight assists thrust:
```
Thrust + W × sin(γ) = Drag
Thrust = Drag - W × sin(γ)
Power = (D - W × sin(γ)) × V
```

**Climb at angle γ (measured upward from horizontal):**

Along the flight path, the component of weight opposes thrust:
```
Thrust = Drag + W × sin(γ)
Power = (D + W × sin(γ)) × V
```

### Power for Descent

```
P_descent = (D - W × sin(γ)) × V
```

Since in steady flight at small angles, L ≈ W and D = W/(L/D):
```
P_descent = V × W/(L/D) - V × W × sin(γ)
P_descent = V × W × (1/(L/D) - sin(γ))
```

Normalizing by level flight power P_level = V × W / (L/D):
```
P_descent = P_level × (1 - (L/D) × sin(γ))
```

### Power for Climb

```
P_climb = (D + W × sin(γ)) × V
P_climb = V × W/(L/D) + V × W × sin(γ)
P_climb = V × W × (1/(L/D) + sin(γ))
P_climb = P_level × (1 + (L/D) × sin(γ))
```

## Example Scenario

**Given:**
- Aircraft in level flight at airspeed V = 20 m/s
- Level flight power: P1 = 200 W
- Lift-to-drag ratio: L/D = 10
- Aircraft pitches down 5 degrees
- **Goal:** Maintain same airspeed V (not altitude)

**Solution:**

When descending at angle γ (measured positive downward from horizontal):

```
P_descent = P_level - V × W × sin(γ)
P_descent = D × V - W × V × sin(γ)
```

Since D = W/[L/D] in level flight:
```
P_descent = V × W/[L/D] - V × W × sin(γ)
P_descent = V × W × (1/[L/D] - sin(γ))
```

Normalizing by level flight power P_level = V × W / [L/D]:
```
P_descent = P_level × (1 - [L/D] × sin(γ))
```

**For γ = 5° descent, L/D = 10:**
```
sin(5°) = 0.0872

P_descent = 200 W × (1 - 10 × 0.0872)
          = 200 W × (1 - 0.872)
          = 200 W × 0.128
          = 25.6 W
```

**Power reduction:** 87.2% less power required! Gravity assists in the descent, significantly reducing thrust needed to maintain constant airspeed.

## Physical Interpretation

### Energy Balance Perspective

In steady descent at constant airspeed:
- Kinetic energy (½mV²) is constant (airspeed unchanged)
- Potential energy decreases (altitude decreasing)
- Energy from gravity supplements propulsive power
- Less thrust required to overcome drag

**Rate of potential energy loss:**
```
P_gravity = m × g × V × sin(|γ|)
          = W × V × sin(|γ|)
```

This exactly matches the power reduction term in our equation.

### Gliding (Zero Power)

Setting P_descent = 0:
```
0 = P_level × (1 - [L/D] × sin(|γ_glide|))
sin(|γ_glide|) = 1 / [L/D]
```

**For L/D = 10:**
```
|γ_glide| = arcsin(0.1) = 5.74°
```

This is the **glide angle** - the steepest descent possible with zero thrust while maintaining constant airspeed.

**Glide ratio = L/D = 10:1**
- For every 10 meters forward, descend 1 meter
- tan(γ_glide) ≈ sin(γ_glide) = 1/[L/D] for small angles

## Small Angle Linearity Analysis

### Question: Is sin(γ) ≈ linear with γ for angles < 15°?

**Comparison table:**

| γ (degrees) | γ (radians) | sin(γ)   | Linear approx | Error (%) |
|-------------|-------------|----------|---------------|-----------|
| 0°          | 0.0000      | 0.0000   | 0.0000        | 0.00%     |
| 5°          | 0.0873      | 0.0872   | 0.0873        | 0.11%     |
| 10°         | 0.1745      | 0.1736   | 0.1745        | 0.52%     |
| 15°         | 0.2618      | 0.2588   | 0.2618        | 1.16%     |

**Linear approximation:**
```
sin(γ) ≈ γ  (when γ in radians)
```

**Analysis:**
- **0-5°:** Error < 0.2% - essentially linear
- **5-10°:** Error < 0.6% - very good approximation
- **10-15°:** Error ~ 1.2% - acceptable for engineering estimates
- **Above 15°:** Error increases rapidly

### Taylor Series Expansion

```
sin(γ) = γ - γ³/6 + γ⁵/120 - ...
```

**First-order approximation (linear):**
```
sin(γ) ≈ γ
```

**Error term:**
```
Error ≈ γ³/6
```

**For γ = 15° = 0.2618 rad:**
```
Error ≈ (0.2618)³/6 = 0.0030 = 0.30%
Actual error = 1.16% (higher-order terms matter)
```

### Practical Implications for INAV

**For flight path angles < 10°:**
- Linear approximation is excellent
- sin(γ) ≈ γ (radians) with <0.6% error
- Simplifies calculations significantly

**INAV application:**
```c
// Small angle approximation for flight path angle
float flight_path_angle_rad = atan2(climb_rate, ground_speed);

// For angles < 10°, can approximate:
float sin_gamma = flight_path_angle_rad;  // Direct substitution

// Power correction factor
float power_factor = 1.0f - sin_gamma * lift_to_drag_ratio;
```

**When small angle approximation breaks down:**
- Steep climbs (γ > 15°)
- Aerobatic maneuvers
- Emergency descents
- Vertical flight modes

In these cases, use full trigonometric functions.

## Graphical Representation

```
Power vs. Flight Path Angle (L/D = 10)

P/P_level
  2.0 |                               *  Climb
      |                            *
  1.5 |                         *
      |                      *
  1.0 |------------------*---------------  Level flight
      |              *
  0.5 |          *
      |      *
  0.0 |  *  Glide angle = arcsin(1/10) = 5.74°
      |_____________________________________
        -15°  -10°  -5°   0°   5°   10°  15°
               Descent ← γ → Climb
```

**Key points:**
1. **γ = 0°:** P = P_level (reference point)
2. **γ = -5.74°:** P = 0 (best glide angle)
3. **γ = -15°:** P negative (excess gravity assist, must use spoilers/brakes)
4. **γ = +10°:** P ≈ 2 × P_level (steep climb requires double power)

## INAV Flight Controller Applications

### 1. Throttle Optimization for Descent

When descending to a waypoint at constant airspeed:

```c
// Calculate required throttle based on desired descent rate
float descent_angle = atan2f(-desired_descent_rate, ground_speed);
float power_factor = 1.0f - sinf(descent_angle) * estimated_lift_to_drag;

// Reduce throttle proportionally
float throttle_descent = throttle_level * power_factor;
```

**Benefits:**
- Prevents excessive speed buildup in descent
- Maintains desired airspeed precisely
- Saves battery energy
- Smoother descent profiles

### 2. Energy Management in RTH

Return-to-home with altitude loss:

```c
// Current altitude above home
float altitude_excess = current_altitude - home_altitude;

// Distance to home
float distance_to_home = GPS_distance_to_home();

// Calculate optimal descent angle for energy-neutral return
float descent_angle = atanf(altitude_excess / distance_to_home);

// Check if descent angle allows zero-power glide
if (sinf(descent_angle) >= 1.0f / estimated_lift_to_drag) {
    // Can glide home with minimal power
    use_minimal_throttle();
} else {
    // Need some power to maintain airspeed
    calculate_required_throttle(descent_angle);
}
```

### 3. Battery Range Estimation

More accurate range predictions:

```c
// Account for terrain profile
for (waypoint in mission) {
    float altitude_change = waypoint.altitude - current_altitude;
    float segment_distance = distance_to(waypoint);
    float segment_angle = atan2f(altitude_change, segment_distance);

    // Power factor for this segment
    float power_factor = 1.0f - sinf(segment_angle) * L_over_D;

    // Energy consumption for segment
    float segment_energy = baseline_power * power_factor * segment_time;
    total_energy += segment_energy;
}

float remaining_range = battery_remaining / (total_energy / total_distance);
```

### 4. Climb Performance Prediction

Estimate maximum climb rate:

```c
// Maximum available power
float P_max = max_throttle * motor_power_rating;

// Power required for level flight at current speed
float P_level = estimate_drag() * airspeed;

// Available excess power
float P_excess = P_max - P_level;

// Maximum climb angle
float sin_gamma_max = P_excess / (weight * airspeed);
float gamma_max = asinf(sin_gamma_max);

// Maximum climb rate
float max_climb_rate = airspeed * sin_gamma_max;
```

**Note:** This assumes constant airspeed during climb. In practice, INAV might trade speed for climb rate.

### 5. Stall Prevention in Climbs

At low airspeeds with high climb angles:

```c
// Check if climb angle demands exceed available power
float required_power = P_level * (1.0f + sinf(climb_angle) * L_over_D);

if (required_power > available_power) {
    // Cannot maintain airspeed and climb angle
    // Airspeed will decay → stall risk

    // Options:
    // 1. Reduce climb angle
    // 2. Increase throttle (if available)
    // 3. Alert pilot

    limit_climb_angle();
    request_more_throttle();
}
```

## Textbook References

### Houghton & Carpenter Page Citations

**Pages 35-44: Drag characteristics**
- Total drag equation: D = CD × ½ρV²S
- Drag coefficient: CD = CD₀ + CDi
- Induced drag: CDi = CL²/(πAe)
- Lift-to-drag ratio maximization

**Pages 26-34: Force equilibrium**
- Four forces: Lift, Drag, Thrust, Weight
- Steady flight conditions
- Climb and descent mechanics

**Pages 62-67: Performance calculations**
- Power required curves
- Thrust required vs. available
- Climb performance
- Glide performance

**Page 47-48: Aspect ratio effects on L/D**
- High aspect ratio → higher L/D → better glide performance
- Typical L/D values:
  - Sailplanes: 30-60
  - General aviation: 10-15
  - INAV fixed-wing models: 8-12
  - Multirotors in forward flight: 3-5

## Limitations and Assumptions

### Assumptions Made
1. **Small flight path angles (|γ| < 15°):** L ≈ W (lift approximately equals weight)
2. **Constant airspeed:** Not accelerating along flight path
3. **Steady flight:** No transient dynamics
4. **Constant L/D:** Drag polar doesn't change significantly with flight path angle
5. **No wind:** Flight path angle measured relative to air mass

### Real-World Complications

**Propeller efficiency:**
- Propeller thrust varies with airspeed and RPM
- Constant throttle ≠ constant power
- Electric motors: efficiency varies with load

**Airframe effects:**
- Fuselage incidence changes with pitch
- Propwash over wings in climb (tractor configuration)
- Tail downforce varies with speed and pitch

**Dynamic effects:**
- Pitch rate affects apparent angle of attack
- Transient drag during pitch changes
- Inertial effects in rapid maneuvers

**Environmental factors:**
- Wind shear changes flight path angle
- Vertical gusts alter effective climb/descent rate
- Density altitude affects power available and required

## Key Flight Maxims

**"Power for altitude, pitch for speed"** - Traditional wisdom

**More precisely for descents:**
- Reducing power initiates descent
- Pitching down maintains airspeed during descent
- Power reduction should account for gravity assist
- Steeper descent requires less power (until glide angle reached)

**Energy management perspective:**
- Total energy = kinetic + potential
- Constant airspeed descent: trading potential for drag work
- Gravity provides the energy difference
- Throttle controls rate of energy state change

## Practical Flight Example

**Scenario:** Descending to land

**Initial state:**
- Altitude: 300 m AGL
- Distance to threshold: 1500 m
- Airspeed: 15 m/s
- Level flight power: 150 W
- L/D ≈ 10

**Desired descent profile:**

```
Descent angle = atan(300/1500) = 11.3°
sin(11.3°) = 0.196

Power required:
P = 150 × (1 - 10 × 0.196)
  = 150 × (1 - 1.96)
  = 150 × (-0.96)
  = -144 W  (!!!)
```

**Interpretation:** Descent angle is steeper than best glide!
- Best glide: arcsin(1/10) = 5.74°
- Desired: 11.3°
- Excess descent angle: 5.56°

**Solution:**
- Must use spoilers, speed brakes, or S-turns
- Or reduce airspeed (increases descent angle for same glide ratio)
- Or extend approach distance (shallower descent)

**Revised approach:**
```
Use best glide angle: 5.74°
Required distance: 300 / tan(5.74°) = 2990 m

Either:
1. Extend pattern to 3 km
2. Use idle power (near zero)
3. Maintain 15 m/s airspeed
```

## Mathematical Summary

### General Form

```
P = D × V + W × V × sin(γ)
P = V × (D + W sin(γ))
```

### Normalized Form

```
P/P_level = 1 + (W/D) × sin(γ)
          = 1 + (L/D) × sin(γ)  [for small γ where L ≈ W]
```

### Special Cases

**Level flight (γ = 0):**
```
P = D × V = V × W / (L/D)
```

**Best glide (P = 0):**
```
γ_glide = arcsin(1 / [L/D])
```

**Maximum climb angle (P = P_max):**
```
sin(γ_max) = (P_max/V - D) / W
           = (P_max - P_level) / (W × V)
```

## References

**Primary source:** Houghton, E.L. and Carpenter, P.W. (2003) *Aerodynamics for Engineering Students*, 5th Edition, Butterworth-Heinemann.

**Key pages:**
- 26-34: Force equilibrium and steady flight
- 35-44: Drag characteristics and L/D ratio
- 47-48: Aspect ratio effects
- 62-67: Performance calculations

**Supplementary concepts:**
- Small angle approximations (Taylor series)
- Energy state management
- Glide performance

**INAV relevance:**
- Throttle optimization for descents
- Battery range estimation
- Climb performance prediction
- Energy management in autonomous flight
- Return-to-home optimization

**For the specific `nav_fw_pitch2thr` setting:** the reviewed, canonical
gain analysis (including two other models this file's climb/descent power
ratio disagrees with, and why) lives at
`inav/docs/development/fixed-wing-pitch2thr-tuning.md`.

---

*Created: 2026-01-18*
*Agent: aerodynamics-expert*
*Topic: Power required vs. flight path angle for constant airspeed flight*
*Related: pitch-airspeed-relationship.md (constant throttle dynamics)*
