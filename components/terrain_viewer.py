# components/terrain_viewer.py
import streamlit.components.v1 as components
import os

_RELEASE = True

if not _RELEASE:
    _component_func = components.declare_component(
        "terrain_viewer",
        url="http://localhost:3000",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component(
        "terrain_viewer", path=build_dir
    )

def terrain_viewer(show_shadow_overlay=True, key=None):
    component_value = _component_func(
        show_shadow_overlay=show_shadow_overlay, 
        key=key
    )
    return component_value
