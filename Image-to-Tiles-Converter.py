#!/usr/bin/env python3

""" ============================================================================
= GIMP Image to Tiles Converter version 1.0.1                                  =
= Copyrights (C) 2021-2026 Velbazhd Software LLC                               =
=                                                                              =
= developed by Todor Balabanov ( todor.balabanov@gmail.com )                   =
= Sofia, Bulgaria                                                              =
=                                                                              =
= This program is free software: you can redistribute it and/or modify         =
= it under the terms of the GNU General Public License as published by         =
= the Free Software Foundation, either version 3 of the License, or            =
= (at your option) any later version.                                          =
=                                                                              =
= This program is distributed in the hope that it will be useful,              =
= but WITHOUT ANY WARRANTY; without even the implied warranty of               =
= MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                =
= GNU General Public License for more details.                                 =
=                                                                              =
= You should have received a copy of the GNU General Public License            =
= along with this program. If not, see <http://www.gnu.org/licenses/>.         =
=                                                                              =
============================================================================ """

import sys
import random
from copy import deepcopy
from math import ceil, sqrt
import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '3.0')
from gi.repository import Gimp, GObject, Gegl
from gi.repository import GLib

gegl_inited = False
try:
    # Initialize GEGL before any pixel/buffer operations (required by GIMP 3.x)
    Gegl.init([])
    gegl_inited = True
except Exception:
    # In non-GIMP environments (editor/linter) Gegl may not initialize; ignore safely
    gegl_inited = False

# --- GI-only helper functions that call native GI methods (no PDB fallbacks) ---
def image_select_rectangle(image, channel_ops, x, y, w, h):
    # GI-only: use image.select_rectangle
    try:
        image.select_rectangle(channel_ops, x, y, w, h)
        return
    except Exception as e:
        raise RuntimeError('GI image.select_rectangle not available: %s' % e)


def selection_none(image):
    try:
        image.select_none()
        return
    except Exception as e:
        raise RuntimeError('GI image.select_none not available: %s' % e)


def context_set_background(color):
    # GI-only context background setter
    try:
        Gimp.context_set_background(color)
        return
    except Exception as e:
        raise RuntimeError('GI Gimp.context_set_background not available: %s' % e)


def context_set_foreground(color):
    try:
        Gimp.context_set_foreground(color)
        return
    except Exception as e:
        raise RuntimeError('GI Gimp.context_set_foreground not available: %s' % e)


def edit_fill(drawable, fill_type):
    try:
        drawable.fill(fill_type)
        return
    except Exception as e:
        raise RuntimeError('GI drawable.fill not available: %s' % e)


def drawable_histogram(drawable, htype, low, high):
    # GI-only: use drawable.get_histogram
    try:
        return drawable.get_histogram(htype, low, high)
    except Exception as e:
        raise RuntimeError('GI drawable.get_histogram not available: %s' % e)


def text_fontname(runmode, image, layer, x, y, text, *args):
    # Try a wide range of GI text APIs in order. If none available, raise informative error.
    tried = []

    # 1) Gimp.TextLayer constructors and variants
    if hasattr(Gimp, 'TextLayer'):
        TL = Gimp.TextLayer
        for ctor in ('new', 'new_from_text', 'new_with_text', 'new_with_font', 'new_from_markup', 'new_wrapped'):
            if hasattr(TL, ctor):
                try:
                    fn = getattr(TL, ctor)
                    text_layer = fn(image, text)
                    try:
                        image.insert_layer(text_layer, None, 0)
                    except Exception:
                        pass
                    return text_layer
                except Exception as e:
                    tried.append(('TextLayer.' + ctor, str(e)))

    # 2) Module-level helper functions (many builds expose helpers)
    for fn_name in (
        'text_layer_new',
        'text_layer_create',
        'create_text_layer',
        'text_layer_new_from_text',
        'text_layer_new_with_font',
    ):
        if hasattr(Gimp, fn_name):
            try:
                fn = getattr(Gimp, fn_name)
                layer_obj = fn(image, text)
                return layer_obj
            except Exception as e:
                tried.append((fn_name, str(e)))

    # 3) Try to create a generic layer and set text via common setters
    try:
        if hasattr(Gimp, 'Layer') and hasattr(Gimp.Layer, 'new'):
            tl = Gimp.Layer.new(image, 1, 1, Gimp.ImageBaseType.RGB, 'Text', 100, Gimp.LayerMode.NORMAL)
            for setter in ('set_text', 'set_markup', 'set_plain_text', 'set_text_with_font'):
                if hasattr(tl, setter):
                    try:
                        getattr(tl, setter)(text)
                        break
                    except Exception as e:
                        tried.append((setter, str(e)))
            try:
                image.insert_layer(tl, None, 0)
            except Exception:
                pass
            return tl
    except Exception as e:
        tried.append(('generic-layer', str(e)))

    # 4) As last resort, try Pango + Cairo rendering into a new layer (best-effort)
    try:
        try:
            import cairo as _cairo
            gi.require_version('Pango', '1.0')
            gi.require_version('PangoCairo', '1.0')
            from gi.repository import Pango, PangoCairo
        except Exception as e:
            tried.append(('pangocairo-import', str(e)))
            raise

        # Create a temporary surface and context to measure text
        surface = _cairo.ImageSurface(_cairo.FORMAT_ARGB32, 1, 1)
        ctx = _cairo.Context(surface)
        layout = PangoCairo.create_layout(ctx)
        layout.set_text(text, -1)

        # Optional font size from args (best-effort)
        try:
            fd = Pango.FontDescription()
            if len(args) >= 2 and isinstance(args[1], (int, float)):
                fd.set_size(int(args[1]) * Pango.SCALE)
            layout.set_font_description(fd)
        except Exception:
            pass

        w, h = layout.get_pixel_size()
        if w <= 0:
            w = max(1, len(text) * 8)
        if h <= 0:
            h = max(1, 12)

        surface = _cairo.ImageSurface(_cairo.FORMAT_ARGB32, w, h)
        ctx = _cairo.Context(surface)
        PangoCairo.update_layout(ctx, layout)
        ctx.set_source_rgba(0, 0, 0, 1)
        PangoCairo.show_layout(ctx, layout)

        # Extract surface bytes and convert ARGB32 -> RGBA
        src_buf = surface.get_data()
        src = memoryview(src_buf)
        total_pixels = w * h
        dst_bytes = bytearray(total_pixels * 4)
        # Cairo image surface uses native-endian ARGB32 storing 4 bytes per pixel.
        # Best-effort conversion: assume src order is BGRA or ARGB depending on endian.
        try:
            for i in range(total_pixels):
                si = i * 4
                b0 = src[si]
                b1 = src[si + 1]
                b2 = src[si + 2]
                b3 = src[si + 3]
                # treat as ARGB32 little-endian: b0 = B, b1 = G, b2 = R, b3 = A
                r = b2
                g = b1
                b = b0
                a = b3
                di = i * 4
                dst_bytes[di] = r
                dst_bytes[di + 1] = g
                dst_bytes[di + 2] = b
                dst_bytes[di + 3] = a
        except Exception as e:
            tried.append(('cairo-conversion', str(e)))
            raise

        # Create a new layer and write bytes into its GEGL buffer
        try:
            text_layer = Gimp.Layer.new(image, w, h, Gimp.ImageBaseType.RGBA, 'Text', 100, Gimp.LayerMode.NORMAL)
            try:
                image.insert_layer(text_layer, None, 0)
            except Exception:
                pass
            if not gegl_inited:
                raise RuntimeError('GEGL not initialized; cannot write text pixels')
            buf = text_layer.get_buffer()
            if buf is None:
                raise RuntimeError('Created text layer has no GEGL buffer')

            # attempt multiple writer methods
            written = False
            for writer in ('set_bytes', 'set_data', 'set_region', 'set_pixels', 'set_patch', 'write'):
                if hasattr(buf, writer):
                    try:
                        fn = getattr(buf, writer)
                        try:
                            fn(0, 0, w, h, Gegl.Format.RGBA_U8, bytes(dst_bytes))
                        except Exception:
                            try:
                                fn(bytes(dst_bytes))
                            except Exception:
                                fn()
                        written = True
                        break
                    except Exception:
                        pass

            if not written:
                raise RuntimeError('Failed to write text pixels into layer GEGL buffer')

            try:
                if hasattr(text_layer, 'queue_draw'):
                    text_layer.queue_draw()
            except Exception:
                pass

            return text_layer
        except Exception as e:
            tried.append(('create-text-layer', str(e)))
            raise
    except Exception:
        # If pangocairo attempt failed, fall through to raising a diagnostic
        raise RuntimeError('No suitable GI text-layer API found; tried: %s' % tried)


def get_layer_by_name(image, name):
    # Search manually through image.layers (GI)
    for l in image.layers:
        if getattr(l, 'name', None) == name:
            return l
    return None


def insert_layer(image, layer, parent, position):
    try:
        image.insert_layer(layer, parent, position)
        return
    except Exception as e:
        raise RuntimeError('GI image.insert_layer not available: %s' % e)


def create_layer(image, width, height, image_type, name, opacity, mode):
    # GI-only Layer creation
    if not hasattr(Gimp, 'Layer') or not hasattr(Gimp.Layer, 'new'):
        raise RuntimeError('Gimp.Layer.new not available in this GI binding')
    try:
        return Gimp.Layer.new(image, width, height, image_type, name, opacity, mode)
    except Exception as e:
        raise RuntimeError('Failed to create layer via GI: %s' % e)


def layer_scale(layer, width, height, resize):
    try:
        layer.scale(width, height)
        return
    except Exception as e:
        raise RuntimeError('GI layer.scale not available: %s' % e)


def resize_image_to_layers(image):
    try:
        image.resize_to_layers()
        return
    except Exception as e:
        raise RuntimeError('GI image.resize_to_layers not available: %s' % e)


def copy_visible(image):
    # GI-only: use image.merge_visible_layers to obtain a merged layer and return it
    if not hasattr(image, 'merge_visible_layers'):
        raise RuntimeError('GI image.merge_visible_layers not available')
    try:
        merged = image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        return merged
    except Exception as e:
        raise RuntimeError('Failed to merge visible layers via GI: %s' % e)


def paste_into(drawable, source_layer):
    # Ensure GEGL initialized before buffer operations
    if not gegl_inited:
        raise RuntimeError('GEGL not initialized; call Gegl.init() before paste_into')

    # Copy pixel bytes from source_layer into drawable using GEGL buffers
    src_buf = None
    dst_buf = None
    for getter in ('get_buffer', 'get_gegl_buffer', 'buffer'):
        if hasattr(source_layer, getter):
            try:
                src_buf = getattr(source_layer, getter)()
                break
            except Exception:
                try:
                    src_buf = getattr(source_layer, getter)
                    break
                except Exception:
                    pass

    for getter in ('get_buffer', 'get_gegl_buffer', 'buffer'):
        if hasattr(drawable, getter):
            try:
                dst_buf = getattr(drawable, getter)()
                break
            except Exception:
                try:
                    dst_buf = getattr(drawable, getter)
                    break
                except Exception:
                    pass

    if src_buf is None or dst_buf is None:
        raise RuntimeError('Source or destination GEGL buffer missing')

    w = min(getattr(source_layer, 'width', 0), getattr(drawable, 'width', 0))
    h = min(getattr(source_layer, 'height', 0), getattr(drawable, 'height', 0))

    # Read bytes from source using multiple possible methods
    data = None
    for reader in ('get_bytes', 'get_data', 'get_region', 'get_pixels', 'get_patch', 'read'):
        if hasattr(src_buf, reader):
            try:
                fn = getattr(src_buf, reader)
                # try a few call signatures
                try:
                    data = fn(0, 0, w, h, Gegl.Format.RGBA_U8)
                except Exception:
                    try:
                        data = fn()
                    except Exception:
                        data = None
                if data is not None:
                    break
            except Exception:
                pass

    if data is None:
        raise RuntimeError('Failed to read bytes from source GEGL buffer')

    if hasattr(data, 'get_data'):
        try:
            data_bytes = data.get_data()
        except Exception:
            data_bytes = bytes(data)
    else:
        data_bytes = bytes(data)

    # Write bytes into destination buffer using multiple possible methods
    written = False
    for writer in ('set_bytes', 'set_data', 'set_region', 'set_pixels', 'set_patch', 'write'):
        if hasattr(dst_buf, writer):
            try:
                fn = getattr(dst_buf, writer)
                try:
                    fn(0, 0, w, h, Gegl.Format.RGBA_U8, data_bytes)
                except Exception:
                    try:
                        fn(data_bytes)
                    except Exception:
                        fn()
                written = True
                break
            except Exception:
                pass

    if not written:
        raise RuntimeError('Destination GEGL buffer does not support writing bytes')

    # Mark drawable as changed if possible
    try:
        if hasattr(drawable, 'queue_draw'):
            drawable.queue_draw()
        elif hasattr(drawable, 'update'):
            drawable.update(0, 0, drawable.width, drawable.height)
    except Exception:
        pass

    return drawable


def anchor_floating(floating):
    try:
        floating.anchor()
        return
    except Exception as e:
        raise RuntimeError('GI floating.anchor not available: %s' % e)


def remove_layer(image, layer):
    try:
        image.remove_layer(layer)
        return
    except Exception as e:
        raise RuntimeError('GI image.remove_layer not available: %s' % e)


def message(text):
    # GI-only message
    try:
        Gimp.message(text)
    except Exception:
        # As a last resort, print to stdout (for debug purposes)
        print(text)

# --- End wrappers ---
"""Estimating the size of the image in the number of tiles by x and y.

@param width Image width in pixels.
@param height Image height in pixels.
@param tiles A total number of desired tiles to fill the image.

@return A tuple of image width in tiles, image height in tiles, and single square tile size in pixels.
"""


def dimensions_as_tiles(width, height, tiles):
    tile_area = width * height / tiles
    tile_side = ceil(sqrt(tile_area))
    width_in_tiles = ceil(width / tile_side)
    height_in_tiles = ceil(height / tile_side)
    return width_in_tiles, height_in_tiles, tile_side


"""Calculation of image resize parameters.

@param x Width of the image in a number of tiles.
@param y Height of the image in a number of tiles.
@param length Length of single square tile in pixels.

@return A tuple of total tiles needed, image new width in pixels, and image new height in pixels.
"""


def image_setup(x, y, length):
    return x * y, x * length, y * length


"""List all colors used for the tiles by extracting them from a colormap layer.
Each pixel with a specific color is included.

@param layer Colormap layer.

@return Set of tile colors.
"""


def list_of_colors(layer):
    colors = set()
    if not gegl_inited:
        raise RuntimeError('GEGL not initialized; call Gegl.init() before using buffers')

    buffer = layer.get_buffer()
    if buffer is None:
        return colors

    width = layer.width
    height = layer.height
    pixel_bytes = None

    if hasattr(buffer, 'get_bytes'):
        try:
            pixel_bytes = buffer.get_bytes(0, 0, width, height, Gegl.Format.RGBA_U8)
        except TypeError:
            pixel_bytes = None
    elif hasattr(buffer, 'get_data'):
        pixel_bytes = buffer.get_data()

    if pixel_bytes is None:
        return colors

    if hasattr(pixel_bytes, 'get_data'):
        data = pixel_bytes.get_data()
    else:
        data = bytes(pixel_bytes)

    if not data:
        return colors

    channels = 4
    for y in range(height):
        row_start = y * width * channels
        for x in range(width):
            pos = row_start + x * channels
            colors.add((data[pos], data[pos + 1], data[pos + 2]))

    return colors


"""Assembling random tiles with the shape of the original image.

@param layer Resulting layer for the random image.
@param colors List of tile colors.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tile side in pixels.
"""


def draw_random_tiles(layer, colors, columns, rows, side):
    for x in range(int(columns)):
        for y in range(int(rows)):
            image_select_rectangle(
                layer.image,
                Gimp.ChannelOps.REPLACE,
                x * side,
                y * side,
                side,
                side,
            )
            context_set_background(random.choice(colors))
            edit_fill(layer, Gimp.FillType.FOREGROUND)

    selection_none(layer.image)


"""Estimate the average color in a layer.

@param layer The layer in which region average color is calculated.

@return Average color as RGB values.
"""


def average_color(layer):
    if not gegl_inited:
        raise RuntimeError('GEGL not initialized; call Gegl.init() before computing average color')

    buffer = layer.get_buffer()
    if buffer is None:
        return 0, 0, 0

    width = layer.width
    height = layer.height
    pixel_bytes = None

    if hasattr(buffer, 'get_bytes'):
        try:
            pixel_bytes = buffer.get_bytes(0, 0, width, height, Gegl.Format.RGBA_U8)
        except TypeError:
            pixel_bytes = None
    elif hasattr(buffer, 'get_data'):
        pixel_bytes = buffer.get_data()

    if pixel_bytes is None:
        return 0, 0, 0

    if hasattr(pixel_bytes, 'get_data'):
        data = pixel_bytes.get_data()
    else:
        data = bytes(pixel_bytes)

    if not data:
        return 0, 0, 0

    channels = 4
    total_pixels = width * height
    total_r = 0
    total_g = 0
    total_b = 0

    for i in range(total_pixels):
        pos = i * channels
        total_r += data[pos]
        total_g += data[pos + 1]
        total_b += data[pos + 2]

    return (
        int(total_r / total_pixels),
        int(total_g / total_pixels),
        int(total_b / total_pixels),
    )


"""Match an RGB color to the closest color in a list of colors.

@param colors List of tile colors.
@param average The RGB value of the average color.

@return The closest color by Euclidean distance in RGB channels.
"""


def match_color(colors, average):
    result = colors[0]
    min_distance = (
        (result[0] - average[0]) ** 2
        + (result[1] - average[1]) ** 2
        + (result[2] - average[2]) ** 2
    )

    for candidate in colors:
        distance = (
            (candidate[0] - average[0]) ** 2
            + (candidate[1] - average[1]) ** 2
            + (candidate[2] - average[2]) ** 2
        )
        if distance < min_distance:
            result = candidate
            min_distance = distance

    return result


"""Match tiles to average close colors.

@param layer Layer of the original image.
@param colors List of tile colors.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tile side in pixels.

@return List of matched colors for the tiles.
"""


def match_tiles(layer, colors, columns, rows, side):
    matched = []
    for x in range(int(columns)):
        for y in range(int(rows)):
            image_select_rectangle(
                layer.image,
                Gimp.ChannelOps.REPLACE,
                x * side,
                y * side,
                side,
                side,
            )
            average = average_color(layer)
            matched.append(match_color(colors, average))

    selection_none(layer.image)
    return matched


"""Draw the list of tiles.

@param layer Layer to draw on.
@param solution List of tile colors for the image approximation.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tile side in pixels.
"""


def draw_solution_tiles(layer, solution, columns, rows, side):
    i = 0
    for x in range(int(columns)):
        for y in range(int(rows)):
            image_select_rectangle(
                layer.image,
                Gimp.ChannelOps.REPLACE,
                x * side,
                y * side,
                side,
                side,
            )
            context_set_background(solution[i])
            edit_fill(layer, Gimp.FillType.FOREGROUND)
            i += 1
    selection_none(layer.image)


"""Draw numbers on tiles.

@param layer Layer of the approximated image.
@param colors List of tile colors.
@param solution List of tile colors for the image approximation.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tile side in pixels.
"""


def draw_tiles_numbering(layer, colors, solution, columns, rows, side):
    color_indices = {color: index for index, color in enumerate(colors)}
    i = 0

    for x in range(int(columns)):
        for y in range(int(rows)):
            tile_color = solution[i]
            context_set_foreground(
                (255 - tile_color[0], 255 - tile_color[1], 255 - tile_color[2])
            )
            text_fontname(
                Gimp.RunMode.NONINTERACTIVE,
                layer.image,
                layer,
                x * side,
                y * side,
                str(color_indices[tile_color] + 1),
                -1,
                False,
                int(3 * side / 4),
                0,
                "Sans",
            )
            i += 1

    temp_layer = text_fontname(
        Gimp.RunMode.NONINTERACTIVE,
        layer.image,
        layer,
        0,
        0,
        "",
        2,
        1,
        1,
        0,
        "Sans",
    )
    if temp_layer is not None:
        remove_layer(layer.image, temp_layer)


"""Draw tiles statistics.

@param layer Layer of the approximated image statistics.
@param colors List of tile colors.
@param solution List of tile colors for the image approximation.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tile side in pixels.
"""


def draw_solution_statistics(layer, colors, solution, columns, rows, side):
    image_select_rectangle(
        layer.image,
        Gimp.ChannelOps.REPLACE,
        0,
        0,
        layer.width,
        layer.height,
    )
    context_set_background((255, 255, 255))
    edit_fill(layer, Gimp.FillType.BACKGROUND)

    counters = {c: 0 for c in colors}
    for c in solution:
        counters[c] += 1

    size = side
    if size < 20:
        size = 20

    for index, color in enumerate(colors):
        image_select_rectangle(
            layer.image,
            Gimp.ChannelOps.REPLACE,
            0,
            index * size,
            size,
            size,
        )
        context_set_background(color)
        edit_fill(layer, Gimp.FillType.BACKGROUND)
        context_set_foreground((0, 0, 0))
        text_fontname(
            Gimp.RunMode.NONINTERACTIVE,
            layer.image,
            layer,
            size,
            index * size,
            str(index + 1),
            2,
            0,
            int(size / 2),
            0,
            "Sans",
        )
        text_fontname(
            Gimp.RunMode.NONINTERACTIVE,
            layer.image,
            layer,
            2 * size,
            index * size,
            str(counters[color]),
            2,
            0,
            int(size / 2),
            0,
            "Sans",
        )
        text_fontname(
            Gimp.RunMode.NONINTERACTIVE,
            layer.image,
            layer,
            4 * size,
            index * size,
            str(color),
            2,
            0,
            int(size / 2),
            0,
            "Sans",
        )

    selection_none(layer.image)
    temp_layer = text_fontname(
        Gimp.RunMode.NONINTERACTIVE,
        layer.image,
        layer,
        0,
        0,
        "",
        2,
        1,
        1,
        0,
        "Sans",
    )
    if temp_layer is not None:
        remove_layer(layer.image, temp_layer)


"""Generation of a random chromosome.

@param colors List of tile colors.
@param length The length of the newly generated chromosome.

@return Randomly generated chromosome.
"""


def random_chromosome(colors, length):
    chromosome = []
    for _ in range(int(length)):
        chromosome.append(random.choice(colors))
    return chromosome


"""Selection of two parents and a single child.

@param population Genetic algorithm population.
@param fitness The fitness values of the individuals in the population.

@return Selected parents and the child.
"""


def select(population, fitness):
    population_size = len(population)
    while True:
        child_index = random.randrange(population_size)
        parent1_index = random.randrange(population_size)
        parent2_index = random.randrange(population_size)
        if (
            child_index == parent1_index
            or child_index == parent2_index
            or parent1_index == parent2_index
        ):
            continue
        break

    if fitness[child_index] < fitness[parent1_index]:
        child_index, parent1_index = parent1_index, child_index
    if fitness[child_index] < fitness[parent2_index]:
        child_index, parent2_index = parent2_index, child_index

    return child_index, parent1_index, parent2_index


"""Uniform crossover.

@param probability Crossover probability rate.
@param child Crossover result.
@param parent1 First parent.
@param parent2 Second parent.
"""


def crossover(probability, child, parent1, parent2):
    if random.random() >= probability:
        return

    for i in range(len(child)):
        child[i] = parent1[i] if random.choice([True, False]) else parent2[i]


"""Tile color mutation.

@param probability Mutation probability rate.
@param colors List of tile colors.
@param child Mutation result.
"""


def mutation(probability, colors, child):
    for i in range(len(child)):
        if random.random() < probability:
            child[i] = random.choice(colors)


"""Chromosome fitness value evaluation.

@param original Layer of the original image.
@param approximated Layer of the approximated image.
@param x_tiles Width of the approximated image in tiles.
@param y_tiles Height of the approximated image in tiles.
@param tile_side_length Size of a single square tile side in pixels.
@param solution The solution to be evaluated.

@return Fitness value calculated.
"""


def evaluate(original, approximated, x_tiles, y_tiles, tile_side_length, solution):
    draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)

    for layer in original.image.layers:
        layer.visible = False
    original.visible = True
    approximated.visible = True

    merged = copy_visible(original.image)
    pasted = paste_into(approximated, merged)
    original.visible = False

    r, g, b = average_color(approximated)
    return (r + g + b) / 3.0


"""Genetic algorithm optimizer.

@param original Layer of the original image.
@param approximated Layer of the approximated image.
@param colors List of tile colors.
@param x_tiles Width of the approximated image in tiles.
@param y_tiles Height of the approximated image in tiles.
@param tile_side_length Size of a single square tile side in pixels.
@param number_of_generations Number of evolution generations.
@param population_size Population size.
@param crossover_rate Crossover rate.
@param mutation_rate Mutation rate.

@return The best solution found.
"""


def genetic_algorithm(
    original,
    approximated,
    colors,
    x_tiles,
    y_tiles,
    tile_side_length,
    suboptimal_initialization,
    number_of_generations,
    population_size,
    crossover_rate,
    mutation_rate,
):
    if population_size < 1:
        population_size = 1

    if suboptimal_initialization:
        base_solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)
        population = [deepcopy(base_solution) for _ in range(population_size)]
    else:
        population = [
            random_chromosome(colors, x_tiles * y_tiles)
            for _ in range(population_size)
        ]

    fitness = [
        evaluate(original, approximated, x_tiles, y_tiles, tile_side_length, individual)
        for individual in population
    ]

    best_index = min(range(population_size), key=lambda idx: fitness[idx])
    best = deepcopy(population[best_index])
    best_fitness = fitness[best_index]

    for _ in range(number_of_generations * population_size):
        child_index, parent1_index, parent2_index = select(population, fitness)
        child = population[child_index]
        parent1 = population[parent1_index]
        parent2 = population[parent2_index]

        crossover(crossover_rate, child, parent1, parent2)
        mutation(mutation_rate, colors, child)

        fitness[child_index] = evaluate(
            original,
            approximated,
            x_tiles,
            y_tiles,
            tile_side_length,
            child,
        )

        if fitness[child_index] < best_fitness:
            best_fitness = fitness[child_index]
            best = deepcopy(child)

    return best


"""Plug-in single entry point.

@param image Image reference.
@param drawable Drawable object reference.
@param number_of_tiles Number of desired tiles into approximated image.
@param optimizer Selection from the available optimizers.
@param number_of_generations Number of generations for genetic algorithm evolutions.
@param population_size Population size.
@param crossover_rate Crossover rate.
@param mutation_rate Mutation rate.
@param solution_numbering Numbers on tiles flag.
@param solution_statistics Solution tiles statistics flag.
@param image_resize Image to fit tiles resize flag.
"""


# --- GIMP 3.x plugin entrypoint ---
# GIMP requires a Gimp.PlugIn subclass and registration via Gimp.main().
class ImageToTilesConverter(Gimp.PlugIn):
    __gtype_name__ = 'PythonFuImageToTilesConverter'

    def do_query_procedure(self):
        procedure = Gimp.Procedure.new(
            self,
            'python-fu-image-to-tiles',
            Gimp.ProcedureFlags.NONE,
            Gimp.PDBProcType.PLUGIN,
            None,
        )

        procedure.set_menu_label('Image to Tiles Converter')
        procedure.add_menu_path('<Image>/Image/Custom')
        procedure.set_documentation(
            'Raster image to tiles converter plug-in.',
            'Converts a raster image into a tile-based approximation.',
            'Todor Balabanov',
        )
        procedure.set_image_types('*')

        procedure.add_argument(
            GObject.ParamSpec.int(
                'number_of_tiles',
                'Number of tiles',
                'Total number of desired tiles',
                1,
                2147483647,
                1,
            )
        )
        procedure.add_argument(
            GObject.ParamSpec.string(
                'optimizer',
                'Optimizer',
                'Optimizer to use',
                'Genetic Algorithm',
            )
        )
        procedure.add_argument(
            GObject.ParamSpec.boolean(
                'suboptimal_initialization',
                'Suboptimal initialization',
                'Use suboptimal initialization for the genetic algorithm',
                False,
            )
        )
        procedure.add_argument(
            GObject.ParamSpec.int(
                'number_of_generations',
                'Number of generations',
                'Number of evolution generations',
                1,
                2147483647,
                1,
            )
        )
        procedure.add_argument(
            GObject.ParamSpec.int(
                'population_size',
                'Population size',
                'Population size for genetic algorithm',
                1,
                2147483647,
                1,
            )
        )
        procedure.add_argument(
            GObject.ParamSpec.double(
                'crossover_rate',
                'Crossover rate',
                'Genetic algorithm crossover probability',
                0.0,
                1.0,
                0.5,
            )
        )
        procedure.add_argument(
            GObject.ParamSpec.double(
                'mutation_rate',
                'Mutation rate',
                'Genetic algorithm mutation probability',
                0.0,
                1.0,
                0.05,
            )
        )
        procedure.add_argument(
            GObject.ParamSpec.boolean(
                'image_resize',
                'Resize image',
                'Resize image to fit generated tiles',
                False,
            )
        )

        self.add_procedure(procedure)

    def do_run(self, procedure, run_mode, image, drawables, config, data):
        number_of_tiles = config.get_property('number_of_tiles')
        optimizer = config.get_property('optimizer')
        suboptimal_initialization = config.get_property('suboptimal_initialization')
        number_of_generations = config.get_property('number_of_generations')
        population_size = config.get_property('population_size')
        crossover_rate = config.get_property('crossover_rate')
        mutation_rate = config.get_property('mutation_rate')
        image_resize = config.get_property('image_resize')

        first_drawable = None
        try:
            if drawables and len(drawables) >= 1:
                first_drawable = drawables[0]
        except Exception:
            first_drawable = None

        self.run_plugin(
            image,
            first_drawable,
            number_of_tiles,
            optimizer,
            suboptimal_initialization,
            number_of_generations,
            population_size,
            crossover_rate,
            mutation_rate,
            image_resize,
        )

        return procedure.new_return_values(
            Gimp.PDBStatusType.SUCCESS,
            GLib.Error(),
        )

    def run_plugin(
        self,
        image,
        drawable,
        number_of_tiles,
        optimizer,
        suboptimal_initialization,
        number_of_generations,
        population_size,
        crossover_rate,
        mutation_rate,
        image_resize,
    ):
        original = get_layer_by_name(image, 'Original Image')
        if original is None:
            message('Original Image layer not found.')
            return

        if number_of_tiles is None or number_of_tiles < 1:
            number_of_tiles = 1

        x_tiles, y_tiles, tile_side_length = dimensions_as_tiles(
            original.width, original.height, number_of_tiles
        )
        _, image_new_width, image_new_height = image_setup(
            x_tiles, y_tiles, tile_side_length
        )

        if image_resize:
            try:
                Gimp.context_set_interpolation(Gimp.Interpolation.LANCZOS)
            except Exception:
                pass
            layer_scale(original, image_new_width, image_new_height, False)
            resize_image_to_layers(image)

        color_map_layer = get_layer_by_name(image, 'Color Map')
        if color_map_layer is None:
            message('Color Map layer not found.')
            return

        colors = list(list_of_colors(color_map_layer))
        if not colors:
            message('Color Map layer contains no colors.')
            return

        approximated = get_layer_by_name(image, 'Approximated Image')
        if approximated is None:
            approximated = create_layer(
                image,
                image_new_width,
                image_new_height,
                Gimp.ImageBaseType.RGB,
                'Approximated Image',
                100,
                Gimp.LayerMode.NORMAL,
            )
            insert_layer(image, approximated, None, 2)

        if optimizer == 'Genetic Algorithm':
            solution = genetic_algorithm(
                original,
                approximated,
                colors,
                x_tiles,
                y_tiles,
                tile_side_length,
                suboptimal_initialization,
                number_of_generations,
                population_size,
                crossover_rate,
                mutation_rate,
            )
        else:
            solution = match_tiles(
                original,
                colors,
                x_tiles,
                y_tiles,
                tile_side_length,
            )

        draw_solution_tiles(
            approximated,
            solution,
            x_tiles,
            y_tiles,
            tile_side_length,
        )


# Register the plugin class with GIMP 3.x.
GObject.type_register(ImageToTilesConverter)
Gimp.main(ImageToTilesConverter.__gtype_name__, sys.argv)
