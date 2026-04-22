bl_info = {
    "name": "Chunker",
    "author": "lughworks",
    "version": (1, 0, 1),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Chunker",
    "description": "Chunk landmass meshes into grid tiles and generate _col duplicates for FiveM workflows.",
    "category": "Object",
}

import math
import bpy
import bmesh
from mathutils import Vector
from bpy.props import (
    StringProperty,
    FloatProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.types import Operator, Panel, PropertyGroup


def ensure_object_mode(context):
    obj = context.object
    if obj and obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def get_active_mesh(context):
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        raise RuntimeError("Select one mesh object as the active object.")
    return obj


def world_bbox(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_x = min(v.x for v in corners)
    min_y = min(v.y for v in corners)
    min_z = min(v.z for v in corners)
    max_x = max(v.x for v in corners)
    max_y = max(v.y for v in corners)
    max_z = max(v.z for v in corners)
    return min_x, min_y, min_z, max_x, max_y, max_z


def link_to_same_collections(src_obj, new_obj):
    linked = False
    for coll in src_obj.users_collection:
        coll.objects.link(new_obj)
        linked = True
    if not linked:
        bpy.context.scene.collection.objects.link(new_obj)


def create_chunk_mesh(src_obj, x0, x1, y0, y1, skip_empty=True):
    bm = bmesh.new()
    bm.from_mesh(src_obj.data)
    inv_world = src_obj.matrix_world.inverted()

    def bisect(plane_co_world, plane_no_world, clear_inner=False, clear_outer=False):
        plane_co_local = inv_world @ plane_co_world
        plane_no_local = (inv_world.to_3x3() @ plane_no_world).normalized()
        bmesh.ops.bisect_plane(
            bm,
            geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
            plane_co=plane_co_local,
            plane_no=plane_no_local,
            clear_inner=clear_inner,
            clear_outer=clear_outer,
            dist=0.00001,
        )

    bisect(Vector((x0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), clear_inner=True)
    bisect(Vector((x1, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), clear_outer=True)
    bisect(Vector((0.0, y0, 0.0)), Vector((0.0, 1.0, 0.0)), clear_inner=True)
    bisect(Vector((0.0, y1, 0.0)), Vector((0.0, 1.0, 0.0)), clear_outer=True)

    bm.faces.ensure_lookup_table()
    if not bm.faces:
        bm.free()
        return None

    mesh = bpy.data.meshes.new("chunk_mesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    if skip_empty and len(mesh.polygons) == 0:
        bpy.data.meshes.remove(mesh)
        return None

    obj = bpy.data.objects.new("chunk", mesh)
    obj.matrix_world = src_obj.matrix_world.copy()
    link_to_same_collections(src_obj, obj)
    return obj


def format_chunk_name(base_name, index):
    return f"{base_name}_{index:03d}"


class chunker_LANDMASS_PG_settings(PropertyGroup):
    base_name: StringProperty(
        name="Base Name",
        default="landmass",
        description="Base object name used for chunk naming",
    )
    chunk_size_x: FloatProperty(
        name="Chunk Size X",
        default=512.0,
        min=0.001,
        description="Grid width in Blender units",
    )
    chunk_size_y: FloatProperty(
        name="Chunk Size Y",
        default=512.0,
        min=0.001,
        description="Grid height in Blender units",
    )
    use_world_origin_grid: BoolProperty(
        name="World Origin Grid",
        default=True,
        description="Align cuts to a world-aligned grid, but names remain local from 000_000",
    )
    axis_order: EnumProperty(
        name="Name Order",
        description="Choose whether names are base_X_Y or base_Y_X",
        items=[
            ('XY', 'X then Y', 'Names look like landmass_000_001'),
            ('YX', 'Y then X', 'Names look like landmass_001_000'),
        ],
        default='XY',
    )
    skip_empty: BoolProperty(
        name="Skip Empty",
        default=True,
        description="Do not create tiles with no polygons",
    )
    delete_source: BoolProperty(
        name="Delete Source",
        default=False,
        description="Delete the original source mesh after chunking",
    )
    create_col_after_chunk: BoolProperty(
        name="Create _col Copies",
        default=False,
        description="Duplicate generated chunks and suffix them with _col",
    )
    selected_only_for_col: BoolProperty(
        name="Selected Only",
        default=True,
        description="For manual _col generation, duplicate only selected mesh objects",
    )
    separate_mesh_data_for_col: BoolProperty(
        name="Unique COL Mesh Data",
        default=True,
        description="Copy mesh data for each _col object instead of sharing mesh datablocks",
    )


class chunker_LANDMASS_OT_chunk_selected(Operator):
    bl_idname = "chunker_landmass.chunk_selected"
    bl_label = "Chunk Active Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chunker_landmass_tools

        try:
            ensure_object_mode(context)
            src = get_active_mesh(context)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        min_x, min_y, _min_z, max_x, max_y, _max_z = world_bbox(src)

        if settings.use_world_origin_grid:
            start_gx = math.floor(min_x / settings.chunk_size_x)
            start_gy = math.floor(min_y / settings.chunk_size_y)
            end_gx = math.ceil(max_x / settings.chunk_size_x)
            end_gy = math.ceil(max_y / settings.chunk_size_y)
        else:
            start_gx = 0
            start_gy = 0
            end_gx = math.ceil((max_x - min_x) / settings.chunk_size_x)
            end_gy = math.ceil((max_y - min_y) / settings.chunk_size_y)

        created = []
        chunk_index = 0

        for local_gy, gy in enumerate(range(start_gy, end_gy)):
            for local_gx, gx in enumerate(range(start_gx, end_gx)):
                if settings.use_world_origin_grid:
                    x0 = gx * settings.chunk_size_x
                    y0 = gy * settings.chunk_size_y
                else:
                    x0 = min_x + (local_gx * settings.chunk_size_x)
                    y0 = min_y + (local_gy * settings.chunk_size_y)

                x1 = x0 + settings.chunk_size_x
                y1 = y0 + settings.chunk_size_y

                chunk = create_chunk_mesh(src, x0, x1, y0, y1, skip_empty=settings.skip_empty)
                if not chunk:
                    continue

                chunk.name = format_chunk_name(settings.base_name, chunk_index)
                chunk.data.name = f"{chunk.name}_mesh"
                created.append(chunk)
                chunk_index += 1

        if settings.create_col_after_chunk:
            for obj in created:
                dup = obj.copy()
                dup.data = obj.data.copy() if settings.separate_mesh_data_for_col else obj.data
                dup.animation_data_clear()
                dup.name = f"{obj.name}_col"
                dup.data.name = f"{dup.name}_mesh"
                link_to_same_collections(obj, dup)

        if settings.delete_source:
            bpy.data.objects.remove(src, do_unlink=True)

        self.report({'INFO'}, f"Created {len(created)} chunk objects")
        return {'FINISHED'}


class chunker_LANDMASS_OT_make_col(Operator):
    bl_idname = "chunker_landmass.make_col"
    bl_label = "Generate _col Copies"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.chunker_landmass_tools
        ensure_object_mode(context)

        if settings.selected_only_for_col:
            source_objects = list(context.selected_objects)
        else:
            source_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']

        created = 0
        for obj in source_objects:
            if obj.type != 'MESH' or obj.name.endswith("_col"):
                continue

            dup = obj.copy()
            dup.data = obj.data.copy() if settings.separate_mesh_data_for_col else obj.data
            dup.animation_data_clear()
            dup.name = f"{obj.name}_col"
            dup.data.name = f"{dup.name}_mesh"
            link_to_same_collections(obj, dup)
            created += 1

        self.report({'INFO'}, f"Created {created} _col objects")
        return {'FINISHED'}


class chunker_LANDMASS_PT_panel(Panel):
    bl_label = "chunker"
    bl_idname = "chunker_LANDMASS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'chunker'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.chunker_landmass_tools

        col = layout.column(align=True)
        col.label(text="Chunk Settings")
        col.prop(settings, "base_name")
        col.prop(settings, "chunk_size_x")
        col.prop(settings, "chunk_size_y")
        col.prop(settings, "use_world_origin_grid")
        col.prop(settings, "axis_order")
        col.prop(settings, "skip_empty")
        col.prop(settings, "delete_source")

        box = layout.box()
        box.label(text="Collision Options")
        box.prop(settings, "create_col_after_chunk")
        box.prop(settings, "separate_mesh_data_for_col")
        box.prop(settings, "selected_only_for_col")

        layout.separator()
        layout.operator("chunker_landmass.chunk_selected", icon='MOD_REMESH')
        layout.operator("chunker_landmass.make_col", icon='DUPLICATE')

        layout.separator()
        layout.label(text="Example names:")
        layout.label(text=format_chunk_name(settings.base_name, 0))
        layout.label(text=format_chunk_name(settings.base_name, 1))
        layout.label(text=format_chunk_name(settings.base_name, 2))
        layout.label(text=f"{format_chunk_name(settings.base_name, 0)}_col")


classes = (
    chunker_LANDMASS_PG_settings,
    chunker_LANDMASS_OT_chunk_selected,
    chunker_LANDMASS_OT_make_col,
    chunker_LANDMASS_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.chunker_landmass_tools = PointerProperty(type=chunker_LANDMASS_PG_settings)


def unregister():
    del bpy.types.Scene.chunker_landmass_tools
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
