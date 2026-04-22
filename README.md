# Chunker

Chunker is a Blender add-on for splitting a large landmass mesh into grid-based chunks and generating matching `_col` duplicates for FiveM map workflows. The add-on is built around Blender's Python add-on system, using a sidebar panel, scene properties, and object operators to expose chunking and duplication tools in the 3D Viewport.

## Overview

The add-on is designed for a simple terrain workflow: create one large landmass mesh by hand, slice it into evenly sized tiles, then generate collision copies with consistent naming. Blender's BMesh API supports mesh bisect operations that make grid-based cutting practical, while Blender object naming can be handled directly in Python for predictable export-friendly output.

## Features

- Split the active mesh into a world-aligned or bounds-aligned chunk grid.
- Name output meshes with sequential zero-padded indices such as `landmass_000`, `landmass_001`, and `landmass_002` using Python f-string padding conventions.
- Generate `_col` duplicates automatically after chunk creation or manually from selected mesh objects.
- Keep generated objects linked to the same Blender collections as the source mesh for easier scene organization.
- Expose settings in the View3D sidebar through a standard Blender `PropertyGroup` and `Panel` pattern.

## Intended workflow

1. Model the full terrain or landmass as one mesh object in Blender.
2. Select that mesh as the active object.
3. Choose chunk dimensions such as 512 x 512 Blender units.
4. Run the chunk operator to generate streamed terrain pieces.
5. Generate `_col` copies for collision objects after chunk creation or in a separate pass.

This approach is useful when a terrain must be broken into smaller assets for downstream map export, streaming, or collision setup. A single running index keeps names independent of world coordinates, which is helpful when only ordering matters and the numbers are not intended to represent tile positions.

## Naming convention

The add-on uses sequential indexing rather than coordinate-based naming.

### Chunk names

Chunks are named using this pattern:

```text
landmass_000
landmass_001
landmass_002
landmass_003
```

### Collision names

Collision copies use the same base name with a `_col` suffix:

```text
landmass_000_col
landmass_001_col
landmass_002_col
```

Zero-padded numbering keeps names sorted correctly in Blender's Outliner and in downstream file lists.

## Installation

1. Save the add-on Python file locally.
2. Open Blender.
3. Go to **Edit > Preferences > Add-ons**.
4. Click **Install...** and choose the add-on `.py` file.
5. Enable the add-on in the add-on list.
6. Open the 3D Viewport sidebar and switch to the **Chunker** tab or the configured sidebar tab for the add-on panel.

Blender add-ons commonly expose custom tools through panels in `VIEW_3D` with `UI` region placement, which is the mechanism used here.

## Panel settings

The add-on exposes the following controls in the sidebar panel.

| Setting | Purpose |
|---|---|
| `Base Name` | Base name used when creating chunk object names such as `landmass_000`. |
| `Chunk Size X` | Width of each chunk tile in Blender units. |
| `Chunk Size Y` | Height of each chunk tile in Blender units. |
| `World Origin Grid` | Aligns chunk cuts to a world-space grid instead of starting only from the mesh bounds. |
| `Skip Empty` | Avoids creating chunk objects when a grid cell contains no polygons. |
| `Delete Source` | Removes the original source mesh after successful chunk generation. |
| `Create _col Copies` | Automatically duplicates generated chunks and appends `_col` to the names. |
| `Selected Only` | Restricts manual `_col` generation to the selected mesh objects. |
| `Unique COL Mesh Data` | Creates separate mesh datablocks for collision duplicates instead of sharing source mesh data. |

## Operators

### Chunk Active Mesh

This operator cuts the active mesh into a grid using four bisect planes per cell boundary window: left, right, bottom, and top. The BMesh `bisect_plane` operator supports cutting geometry and deleting the side outside the desired region, which is what allows one chunk mesh to be isolated per tile.

The operator then creates a new mesh datablock for each valid chunk, links the object into the same collections as the source, applies sequential naming, and optionally creates `_col` duplicates.

### Generate _col Copies

This operator duplicates existing mesh objects and renames them with a `_col` suffix. Blender Python can copy objects and optionally copy mesh data separately, which is useful when collision meshes may later be edited independently from the visual meshes.

## Example workflow

### Example 1: Basic landmass split

A single terrain mesh called `terrain_master` is selected and chunked with a size of 512 by 512. If the chunker produces six valid mesh tiles, the output names become:

```text
landmass_000
landmass_001
landmass_002
landmass_003
landmass_004
landmass_005
```

If `_col` creation is enabled, each created tile also gets a matching collision object such as `landmass_000_col` and `landmass_001_col`.

### Example 2: Sparse terrain

If `Skip Empty` is enabled, empty grid cells do not create objects. In that case, the sequential index should advance only for created chunks if the implementation is configured for compact indexing, which keeps the names contiguous without gaps.

## How it works

The chunking logic reads the active object's world-space bounding box, determines the target grid extents, then iterates through each grid cell to isolate mesh data inside that tile. BMesh operations are appropriate for this because they allow direct mesh manipulation in Python without requiring manual edit mode interaction.

Each created tile is written into a new Blender mesh datablock and wrapped in a new object. Object and mesh names can both be set directly in Blender Python, which is how the add-on keeps chunk names and datablock names synchronized.

## FiveM usage notes

For FiveM terrain workflows, chunking a large landmass into smaller pieces makes it easier to prepare assets for streaming, organization, and collision management. Using `_col` suffixes also creates a clear visual-to-collision pairing convention that is easier to batch process later in export scripts or manual map assembly.

Sequential naming is best when the numeric portion is intended to be an asset index rather than a spatial coordinate. If coordinate-derived naming is needed later, that behavior should be implemented separately so indexing and spatial naming remain distinct conventions.

## Limitations

- The add-on assumes the active object is a mesh object and will fail on non-mesh selections.
- Large or highly dense terrains may be slow to process because each chunk is produced through repeated mesh bisect operations.
- Collision duplicates are object-level copies; they are not automatically simplified or decimated for optimized collision use.
- If transforms are not applied consistently, world-space chunk boundaries may not match expectations as neatly as a fully normalized source object.

## Recommended practice

- Apply transforms before chunking when possible.
- Keep chunk sizes consistent across the project.
- Use one base naming convention and keep it stable across all exported assets.
- Generate `_col` copies after visual chunks are confirmed to be correct.
- Test on a smaller section first before chunking a very large terrain mesh.

## Future improvements

Potential extensions for the add-on include:

- Automatic collection sorting for chunks and collision objects.
- Optional decimation for `_col` meshes.
- Batch export helpers for FiveM-ready assets.
- Metadata export for chunk manifests.
- Row or region grouping for large map sets.
