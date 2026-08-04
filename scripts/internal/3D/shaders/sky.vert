#version 150

in vec4 p3d_Vertex;
out vec3 v_view_dir;

uniform mat4 p3d_ModelViewProjectionMatrix;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    // Локальные координаты сферы служат идеальным вектором направления в небо
    v_view_dir = normalize(p3d_Vertex.xyz);
}