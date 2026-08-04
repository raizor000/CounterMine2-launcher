#version 330 core

in vec3 fragPos;
in vec3 normal;
in vec2 uv;

uniform sampler2D tex;

uniform vec3 lightDir;
uniform vec3 lightColor;

uniform vec3 ambientColor;

out vec4 FragColor;

void main()
{
    vec3 N = normalize(normal);

    vec3 L = normalize(-lightDir);

    float diffuse = max(dot(N, L), 0.0);

    vec4 texColor = texture(tex, uv);

    vec3 color =
        texColor.rgb *
        (
            ambientColor +
            diffuse * lightColor
        );

    FragColor = vec4(color, texColor.a);
}