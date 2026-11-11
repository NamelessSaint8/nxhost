#version 460
layout(location=0) in vec4 value;
layout(location=0) out vec4 color;
layout(push_constant) uniform Draw { uint first; uint count; uint mode; } draw;
void main() {
    float group = draw.mode == 0u ? 1.0 : 0.0;
    color = value.x == 1.0 && value.y == group ? vec4(0,1,0,1) : vec4(1,0,0,1);
}
