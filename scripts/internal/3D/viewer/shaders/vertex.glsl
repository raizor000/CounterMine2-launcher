#version 330 core

layout(location = 0) in vec3 in_position;
layout(location = 1) in vec3 in_normal;
layout(location = 2) in vec2 in_uv;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

out vec3 fragPos;
out vec3 normal;
out vec2 uv;

void main()
{
    vec4 worldPos = model * vec4(in_position, 1.0);

    fragPos = worldPos.xyz;

    normal = mat3(transpose(inverse(model))) * in_normal;

    uv = in_uv;

    gl_Position = projection * view * worldPos;
}