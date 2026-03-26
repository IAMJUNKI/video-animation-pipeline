shader_type spatial;
render_mode unshaded, cull_disabled;

uniform sampler2D sprite_texture : source_color;
uniform vec4 chroma_key_color : source_color = vec4(0.0, 1.0, 0.0, 1.0);
uniform float chroma_threshold = 0.2;

void fragment() {
    vec4 tex = texture(sprite_texture, UV);
    float diff = distance(tex.rgb, chroma_key_color.rgb);
    if (diff < chroma_threshold) {
        discard;
    }
    ALBEDO = tex.rgb;
    ALPHA = tex.a;
}
