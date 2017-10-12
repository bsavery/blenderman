# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 - 2017 Pixar
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#
# ##### END MIT LICENSE BLOCK #####

import os
import bpy
import bpy.utils.previews

renderman_icon_collections = {}
renderman_icons_loaded = False


def load_icons():
    global renderman_icon_collections
    global renderman_icons_loaded

    if renderman_icons_loaded:
        return renderman_icon_collections["main"]

    custom_icons = bpy.utils.previews.new()

    icons_dir = os.path.join(os.path.dirname(__file__))

    # Render Current Frame
    custom_icons.load("render", os.path.join(
        icons_dir, "rman_render.png"), 'IMAGE')
    # Start IPR
    custom_icons.load("start_ipr", os.path.join(
        icons_dir, "rman_rerender_controls.png"), 'IMAGE')
    # Stop IPR
    custom_icons.load("stop_ipr", os.path.join(
        icons_dir, "rman_batch_cancel.png"), 'IMAGE')
    # STart IT
    custom_icons.load("start_it", os.path.join(
        icons_dir, "rman_it.png"), 'IMAGE')
    # Batch Render
    custom_icons.load("batch_render", os.path.join(
        icons_dir, "rman_batch.png"), 'IMAGE')
    # Dynamic Binding Editor

    # Create PxrLM Material

    # Create Disney Material
    custom_icons.load("pxrdisney", os.path.join(
        icons_dir, "render_PxrDisney.png"), 'IMAGE')
    # Create Holdout

    # Open Linking Panel

    # Create Env Light
    custom_icons.load("envlight", os.path.join(
        icons_dir, "rman_RMSEnvLight.png"), 'IMAGE')
    # Daylight
    custom_icons.load("daylight", os.path.join(
        icons_dir, "rman_PxrStdEnvDayLight.png"), 'IMAGE')
    # Create GEO Area Light
    custom_icons.load("geoarealight", os.path.join(
        icons_dir, "rman_RMSGeoAreaLight.png"), 'IMAGE')
    # Create Area Light
    custom_icons.load("arealight", os.path.join(
        icons_dir, "rman_RMSAreaLight.png"), 'IMAGE')
    # Create Point Light
    custom_icons.load("pointlight", os.path.join(
        icons_dir, "rman_RMSPointLight.png"), 'IMAGE')
    # Create Spot Light
    #custom_icons.load("spotlight", os.path.join(icons_dir, "rman_RMSPointLight.png"), 'IMAGE')

    # Create Geo LightBlocker

    # Make Selected Geo Emissive

    # Create Archive node

    # Update Archive

    # Open Last RIB
    custom_icons.load("open_last_rib", os.path.join(
        icons_dir, "rman_open_last_rib.png"), 'IMAGE')
    # Inspect RIB Selection

    # Shared Geometry Attribute

    # Add Subdiv Sheme

    custom_icons.load("add_subdiv_sheme", os.path.join(
        icons_dir, "rman_subdiv.png"), 'IMAGE')
    # Add/Atach Coordsys

    # Add/Create RIB Box
    custom_icons.load("archive_RIB", os.path.join(
        icons_dir, "rman_CreateArchive.png"), 'IMAGE')
    # Open Tmake Window

    # Create OpenVDB Visualizer

    # RenderMan Doc
    custom_icons.load("help", os.path.join(
        icons_dir, "rman_help.png"), 'IMAGE')
    # About RenderMan
    custom_icons.load("info", os.path.join(
        icons_dir, "rman_info.png"), 'IMAGE')

    # Reload plugin
    custom_icons.load("reload_plugin", os.path.join(
        icons_dir, "rman_loadplugin.png"), 'IMAGE')

    # RenderMan for Blender UI-Panels Icon - "R"
    custom_icons.load("rfb_panel", os.path.join(
        icons_dir, "rman_blender.png"), 'IMAGE')

    renderman_icon_collections["main"] = custom_icons
    renderman_icons_loaded = True

    return renderman_icon_collections["main"]


def clear_icons():
    global renderman_icons_loaded
    for icon in renderman_icon_collections.values():
        bpy.utils.previews.remove(icon)
    renderman_icon_collections.clear()
    renderman_icons_loaded = False
