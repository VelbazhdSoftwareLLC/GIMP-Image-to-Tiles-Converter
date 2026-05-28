#!/usr/bin/env python3

""" ============================================================================
= GIMP Image to Tiles Converter version 1.0.2                                  =
= Copyrights (C) 2021-2026 Velbazhd Software LLC                               =
=                                                                              =
= developed by Todor Balabanov ( todor.balabanov@gmail.com )                   =
= Sofia, Bulgaria                                                              =
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
    Gegl.init([])
    gegl_inited = True
except Exception:
    gegl_inited = False

# --- GI-only helper functions ---
def image_select_rectangle(image, channel_ops, x, y, w, h):
    try:
        image.select_rectangle(channel_ops, x, y, w, h)
    except Exception as e:
        raise RuntimeError('GI image.select_rectangle not available: %s' % e)

def selection_none(image):
    try:
        image.select_none()
    except Exception as e:
        raise RuntimeError('GI image.select_none not available: %s' % e)

def context_set_background(color):
    try:
        gimp_color = Gimp.RGB()
        gimp_color.set(color[0]/255.0, color[1]/255.0, color[2]/255.0)
        Gimp.context_set_background(gimp_color)
    except Exception as e:
        raise RuntimeError('GI Gimp.context_set_background not available: %s' % e)

def context_set_foreground(color):
    try:
        gimp_color = Gimp.RGB()
        gimp_color.set(color[0]/255.0, color[1]/255.0, color[2]/255.0)
        Gimp.context_set_foreground(gimp_color)
    except Exception as e:
        raise RuntimeError('GI Gimp.context_set_foreground not available: %s' % e)

def edit_fill(drawable, fill_type):
    try:
        drawable.fill(fill_type)
        return
    except Exception:
        pass
    raise RuntimeError('GI drawable fill not available')

def get_layer_by_name(image, name):
    for l in image.list_layers():
        if getattr(l, 'get_name', lambda: None)() == name or getattr(l, 'name', None) == name:
            return l
    return None

def insert_layer(image, layer, parent, position):
    try:
        image.insert_layer(layer, parent, position)
    except Exception as e:
        raise RuntimeError('GI image.insert_layer not available: %s' % e)

def create_layer(image, width, height, image_type, name, opacity, mode):
    try:
        return Gimp.Layer.new(image, name, width, height, image_type, opacity, mode)
    except Exception as e:
        raise RuntimeError('Failed to create layer via GI: %s' % e)

def layer_scale(layer, width, height, resize):
    try:
        layer.scale(width, height, True)
    except Exception as e:
        raise RuntimeError('GI layer.scale not available: %s' % e)

def resize_image_to_layers(image):
    try:
        image.resize_to_layers()
    except Exception as e:
        raise RuntimeError('GI image.resize_to_layers not available: %s' % e)

def copy_visible(image):
    try:
        return image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
    except Exception as e:
        raise RuntimeError('Failed to merge visible layers via GI: %s' % e)

def paste_into(drawable, source_layer):
    if not gegl_inited:
        raise RuntimeError('GEGL not initialized')

    src_buf = source_layer.get_buffer()
    dst_buf = drawable.get_buffer()

    if src_buf is None or dst_buf is None:
        raise RuntimeError('Source or destination GEGL buffer missing')

    w = min(source_layer.get_width(), drawable.get_width())
    h = min(source_layer.get_height(), drawable.get_height())

    try:
        rect = Gegl.Rectangle.new(0, 0, w, h)
        data = src_buf.get(rect, 1.0, "RGBA u8", Gegl.AbyssPolicy.NONE)
        dst_buf.set(rect, "RGBA u8", data)
    except Exception as e:
        raise RuntimeError('GEGL buffer operation failed: %s' % e)

    try:
        drawable.update(0, 0, w, h)
    except Exception:
        pass
    return drawable

# --- Logic Core ---
def dimensions_as_tiles(width, height, tiles):
    tile_area = width * height / tiles
    tile_side = ceil(sqrt(tile_area))
    width_in_tiles = ceil(width / tile_side)
    height_in_tiles = ceil(height / tile_side)
    return width_in_tiles, height_in_tiles, tile_side

def image_setup(x, y, length):
    return x * y, x * length, y * length

def list_of_colors(layer):
    colors = set()
    if not gegl_inited or layer is None:
        return colors

    buffer = layer.get_buffer()
    width = layer.get_width()
    height = layer.get_height()

    try:
        rect = Gegl.Rectangle.new(0, 0, width, height)
        data = buffer.get(rect, 1.0, "RGBA u8", Gegl.AbyssPolicy.NONE)
    except Exception:
        return colors

    channels = 4
    for y in range(height):
        row_start = y * width * channels
        for x in range(width):
            pos = row_start + x * channels
            colors.add((data[pos], data[pos + 1], data[pos + 2]))
    return colors

def average_color(layer):
    if not gegl_inited:
        return 0, 0, 0

    buffer = layer.get_buffer()
    width = layer.get_width()
    height = layer.get_height()

    try:
        rect = Gegl.Rectangle.new(0, 0, width, height)
        data = buffer.get(rect, 1.0, "RGBA u8", Gegl.AbyssPolicy.NONE)
    except Exception:
        return 0, 0, 0

    channels = 4
    total_pixels = width * height
    total_r, total_g, total_b = 0, 0, 0

    for i in range(total_pixels):
        pos = i * channels
        total_r += data[pos]
        total_g += data[pos + 1]
        total_b += data[pos + 2]

    return int(total_r / total_pixels), int(total_g / total_pixels), int(total_b / total_pixels)

def match_color(colors, average):
    result = colors[0]
    min_distance = (result[0] - average[0]) ** 2 + (result[1] - average[1]) ** 2 + (result[2] - average[2]) ** 2
    for candidate in colors:
        distance = (candidate[0] - average[0]) ** 2 + (candidate[1] - average[1]) ** 2 + (candidate[2] - average[2]) ** 2
        if distance < min_distance:
            result = candidate
            min_distance = distance
    return result

def match_tiles(layer, colors, columns, rows, side):
    matched = []
    for x in range(int(columns)):
        for y in range(int(rows)):
            image_select_rectangle(layer.get_image(), Gimp.ChannelOps.REPLACE, x * side, y * side, side, side)
            average = average_color(layer)
            matched.append(match_color(colors, average))
    selection_none(layer.get_image())
    return matched

def draw_solution_tiles(layer, solution, columns, rows, side):
    i = 0
    for x in range(int(columns)):
        for y in range(int(rows)):
            image_select_rectangle(layer.get_image(), Gimp.ChannelOps.REPLACE, x * side, y * side, side, side)
            context_set_background(solution[i])
            edit_fill(layer, Gimp.FillType.BACKGROUND)
            i += 1
    selection_none(layer.get_image())

def random_chromosome(colors, length):
    return [random.choice(colors) for _ in range(int(length))]

def select(population, fitness):
    population_size = len(population)
    while True:
        child_idx = random.randrange(population_size)
        p1_idx = random.randrange(population_size)
        p2_idx = random.randrange(population_size)
        if child_idx != p1_idx and child_idx != p2_idx and p1_idx != p2_idx:
            break

    if fitness[child_idx] < fitness[p1_idx]:
        child_idx, p1_idx = p1_idx, child_idx
    if fitness[child_idx] < fitness[p2_idx]:
        child_idx, p2_idx = p2_idx, child_idx

    return child_idx, p1_idx, p2_idx

def crossover(probability, child, parent1, parent2):
    if random.random() >= probability:
        return
    for i in range(len(child)):
        child[i] = parent1[i] if random.choice([True, False]) else parent2[i]

def mutation(probability, colors, child):
    for i in range(len(child)):
        if random.random() < probability:
            child[i] = random.choice(colors)

def evaluate(original, approximated, x_tiles, y_tiles, tile_side_length, solution):
    draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)
    for layer in original.get_image().list_layers():
        layer.set_visible(False)
    original.set_visible(True)
    approximated.set_visible(True)

    merged = copy_visible(original.get_image())
    paste_into(approximated, merged)
    original.set_visible(False)

    r, g, b = average_color(approximated)
    return (r + g + b) / 3.0

def genetic_algorithm(original, approximated, colors, x_tiles, y_tiles, tile_side_length,
                      suboptimal_initialization, number_of_generations, population_size, crossover_rate, mutation_rate):
    if population_size < 1:
        population_size = 1

    if suboptimal_initialization:
        base_solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)
        population = [deepcopy(base_solution) for _ in range(population_size)]
    else:
        population = [random_chromosome(colors, x_tiles * y_tiles) for _ in range(population_size)]

    fitness = [evaluate(original, approximated, x_tiles, y_tiles, tile_side_length, ind) for ind in population]
    best_idx = min(range(population_size), key=lambda idx: fitness[idx])
    best = deepcopy(population[best_idx])
    best_fitness = fitness[best_idx]

    for _ in range(number_of_generations * population_size):
        c_idx, p1_idx, p2_idx = select(population, fitness)
        child = population[c_idx]
        parent1 = population[p1_idx]
        parent2 = population[p2_idx]

        crossover(crossover_rate, child, parent1, parent2)
        mutation(mutation_rate, colors, child)

        fitness[c_idx] = evaluate(original, approximated, x_tiles, y_tiles, tile_side_length, child)
        if fitness[c_idx] < best_fitness:
            best_fitness = fitness[c_idx]
            best = deepcopy(child)

    return best

# --- GIMP 3.x Class Initialization ---
class ImageToTilesConverter(Gimp.PlugIn):

    def do_query_procedure(self):
        procedure = Gimp.ImageProcedure.new(
            self,
            'python-fu-image-to-tiles',
            Gimp.PDBProcType.PLUGIN,
            self.run_plugin,
            None
        )
        procedure.set_image_types("*")
        procedure.set_menu_label('Image to Tiles Converter')
        procedure.add_menu_path('<Image>/Image/Custom')
        procedure.set_documentation(
            'Raster image to tiles converter plug-in.',
            'Converts a raster image into a tile-based approximation.',
            'Todor Balabanov'
        )

        procedure.add_argument(GObject.ParamSpec.int(
            'number-of-tiles', 'Number of tiles', 'Total number of desired tiles',
            1, 2147483647, 100, GObject.ParamFlags.READWRITE
        ))
        procedure.add_argument(GObject.ParamSpec.string(
            'optimizer', 'Optimizer', 'Optimizer to use',
            'Simple', GObject.ParamFlags.READWRITE
        ))
        procedure.add_argument(GObject.ParamSpec.boolean(
            'suboptimal-initialization', 'Suboptimal initialization', 'Use suboptimal initialization',
            True, GObject.ParamFlags.READWRITE
        ))
        procedure.add_argument(GObject.ParamSpec.int(
            'number-of-generations', 'Number of generations', 'Number of evolution generations',
            0, 2147483647, 10, GObject.ParamFlags.READWRITE
        ))
        procedure.add_argument(GObject.ParamSpec.int(
            'population-size', 'Population size', 'Population size for GA',
            1, 2147483647, 20, GObject.ParamFlags.READWRITE
        ))
        procedure.add_argument(GObject.ParamSpec.double(
            'crossover-rate', 'Crossover rate', 'Crossover probability',
            0.0, 1.0, 0.95, GObject.ParamFlags.READWRITE
        ))
        procedure.add_argument(GObject.ParamSpec.double(
            'mutation-rate', 'Mutation rate', 'Mutation probability',
            0.0, 1.0, 0.01, GObject.ParamFlags.READWRITE
        ))
        procedure.add_argument(GObject.ParamSpec.boolean(
            'image-resize', 'Resize image', 'Resize image to fit generated tiles',
            True, GObject.ParamFlags.READWRITE
        ))

        return procedure

    def run_plugin(self, procedure, run_mode, image, drawables, config, data):
        number_of_tiles = config.get_property('number-of-tiles')
        optimizer = config.get_property('optimizer')
        suboptimal_initialization = config.get_property('suboptimal-initialization')
        number_of_generations = config.get_property('number-of-generations')
        population_size = config.get_property('population-size')
        crossover_rate = config.get_property('crossover-rate')
        mutation_rate = config.get_property('mutation-rate')
        image_resize = config.get_property('image-resize')

        original = get_layer_by_name(image, 'Original Image')
        if original is None:
            message('Original Image layer not found.')
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

        x_tiles, y_tiles, tile_side_length = dimensions_as_tiles(
            original.get_width(), original.get_height(), number_of_tiles
        )
        _, image_new_width, image_new_height = image_setup(
            x_tiles, y_tiles, tile_side_length
        )

        if image_resize:
            layer_scale(original, image_new_width, image_new_height, False)
            resize_image_to_layers(image)

        # Force structural mode conversion instead of missing GIMP 2 properties
        original.set_mode(Gimp.LayerMode.DIFFERENCE)

        color_map_layer = get_layer_by_name(image, 'Color Map')
        if color_map_layer is None:
            message('Color Map layer not found.')
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

        colors = list(list_of_colors(color_map_layer))
        if not colors:
            message('Color Map layer contains no colors.')
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

        approximated = get_layer_by_name(image, 'Approximated Image')
        if approximated is None:
            approximated = create_layer(
                image, image_new_width, image_new_height,
                Gimp.ImageType.RGBA_IMAGE, 'Approximated Image', 100.0, Gimp.LayerMode.NORMAL
            )
            insert_layer(image, approximated, None, 0)

        if optimizer == 'Genetic Algorithm':
            solution = genetic_algorithm(
                original, approximated, colors, x_tiles, y_tiles,
                tile_side_length, suboptimal_initialization,
                number_of_generations, population_size, crossover_rate, mutation_rate
            )
        else:
            solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)

        draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

GObject.type_register(ImageToTilesConverter)
sys.exit(Gimp.main(ImageToTilesConverter.__gtype_name__, sys.argv))
