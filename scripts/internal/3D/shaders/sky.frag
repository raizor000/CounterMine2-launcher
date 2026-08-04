#version 150

in vec3 v_view_dir;
out vec4 fragColor;

uniform vec3 sun_dir;

void main() {

    vec3 view = normalize(v_view_dir);

    float elevation = clamp(view.z, -1.0, 1.0);

    // --------------------------------------------------
    // БАЗОВОЕ НЕБО
    // --------------------------------------------------

    vec3 zenith  = vec3(0.03, 0.12, 0.45);
    vec3 horizon = vec3(0.42, 0.68, 0.98);
    vec3 ground  = vec3(0.10, 0.09, 0.09);

    vec3 sky;

    if (elevation >= 0.0)
    {
        float t = pow(elevation, 0.55);
        sky = mix(horizon, zenith, t);
    }
    else
    {
        float t = pow(-elevation, 0.35);
        sky = mix(horizon, ground, t);
    }

    // --------------------------------------------------
    // СОЛНЦЕ
    // --------------------------------------------------

    float sunDot = max(dot(view, normalize(sun_dir)), 0.0);

    // широкое теплое свечение
    float glow = pow(sunDot, 7.0);

    // яркий ореол
    float halo = pow(sunDot, 35.0);

    // диск солнца
    float disk = smoothstep(0.998, 0.9997, sunDot);

    // --------------------------------------------------
    // ЗАКАТНАЯ ОБЛАСТЬ
    // --------------------------------------------------

    float horizonMask = 1.0 - smoothstep(0.0, 0.45, elevation);

    vec3 sunsetOrange = vec3(1.00, 0.42, 0.14);
    vec3 sunsetRed    = vec3(1.00, 0.18, 0.12);
    vec3 sunsetPurple = vec3(0.60, 0.18, 0.75);

    sky = mix(
        sky,
        sunsetOrange,
        glow * horizonMask * 0.75
    );

    sky = mix(
        sky,
        sunsetRed,
        pow(sunDot, 18.0) * horizonMask * 0.45
    );

    sky = mix(
        sky,
        sunsetPurple,
        pow(sunDot, 3.0) * horizonMask * 0.20
    );

    // --------------------------------------------------
    // СОЛНЦЕ
    // --------------------------------------------------

    vec3 sunColor = vec3(1.8, 1.15, 0.55);

    vec3 color = sky;

    color += halo * sunColor * 0.45;
    color += disk * sunColor * 8.0;

    // --------------------------------------------------
    // ЛЕГКАЯ АТМОСФЕРА
    // --------------------------------------------------

    color += vec3(0.02,0.03,0.05) * (1.0 - elevation);

    // --------------------------------------------------
    // ACES TONEMAP
    // --------------------------------------------------

    color *= 1.05;

    vec3 x = max(color, vec3(0.0));

    color = (x * (2.51 * x + 0.03))
          / (x * (2.43 * x + 0.59) + 0.14);

    color = pow(color, vec3(1.0 / 2.2));

    fragColor = vec4(color, 1.0);
}