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
gi.require_version('Gtk', '3.0')
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, GObject, Gegl, Gtk
from gi.repository import GLib

gegl_inited = False
try:
    Gegl.init([])
    gegl_inited = True
except Exception:
    gegl_inited = False

def image_select_rectangle(image, channel_ops, x, y, w, h):
    try:
        image.select_rectangle(channel_ops, x, y, w, h)
    except Exception as e:
        raise RuntimeError('GI image.select_rectangle not available: %s' % e)

def selection_none(image):
    try:
        Gimp.Selection.none(image)
    except Exception as e:
        raise RuntimeError('GI image.select_none not available: %s' % e)

def get_layer_by_name(image, name):
    for layer in image.get_layers():
        if layer.get_name() == name:
            return layer
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
        rectangle = Gegl.Rectangle.new(0, 0, width, height)
        data = buffer.get(rectangle, 1.0, "RGBA u8", Gegl.AbyssPolicy.NONE)
    except Exception:
        return colors

    channels = 4
    for y in range(height):
        row_start = y * width * channels
        for x in range(width):
            pos = row_start + x * channels
            colors.add((data[pos], data[pos + 1], data[pos + 2]))
    return colors

def average_color(layer, x, y, width, height):
    if not gegl_inited:
        return 0, 0, 0

    buffer = layer.get_buffer()

    try:
        rect = Gegl.Rectangle.new(x, y, width, height)
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
            tile_x = x * side
            tile_y = y * side
            average = average_color(layer, tile_x, tile_y, side, side)
            matched.append(match_color(colors, average))
    selection_none(layer.get_image())
    return matched

def draw_rectangle(drawable, x, y, w, h, color):
    rectangle = Gegl.Rectangle.new(x, y, w, h)
    tile = (bytes([color[0], color[1], color[2], 255]) * w) * h
    drawable.get_buffer().set(rectangle, "RGBA u8", tile)
    drawable.update(x, y, w, h)

def draw_solution_tiles(layer, solution, columns, rows, side):
    i = 0
    for x in range(int(columns)):
        for y in range(int(rows)):
            draw_rectangle(layer, x * side, y * side, side, side, solution[i])
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

def set_visibility(layers, visible=False):
    for layer in layers:
        layer.set_visible(visible)
        if layer.is_group():
            set_visibility(layer.list_children(), visible)

def evaluate(original, approximated, x_tiles, y_tiles, tile_side_length, solution):
    draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)

    set_visibility(original.get_image().get_layers(), visible=False)
    original.set_visible(True)
    approximated.set_visible(True)
    
    Gimp.message('Checking: {0}'.format(True))
    merged = Gimp.Layer.new_from_visible(original.get_image(), original.get_image(), "Composite Layer")
    original.get_image().insert_layer(merged, None, 0)
    original.set_visible(False)

    r, g, b = average_color(merged, 0, 0, merged.get_width(), merged.get_height())
    fitness = (r + g + b) / 3.0
    
    original.get_image().remove_layer(merged)
    
    return fitness

def genetic_algorithm(image, original, approximated, colors, x_tiles, y_tiles, tile_side_length,
                      suboptimal_initialization, number_of_generations, population_size, crossover_rate, mutation_rate):
    if population_size < 1:
        population_size = 1

    if suboptimal_initialization:
        base_solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)
        population = [deepcopy(base_solution) for _ in range(population_size)]
    else:
        population = [random_chromosome(colors, x_tiles * y_tiles) for _ in range(population_size)]

    fitness = [evaluate(original, approximated, x_tiles, y_tiles, tile_side_length, individual) for individual in population]
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

class ImageToTilesConverter (Gimp.PlugIn):

    def do_query_procedures(self):
        return [ 'plug-in-image-to-tiles' ]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        
        procedure.set_image_types("*")
        procedure.set_menu_label("Image to Tiles Converter")
        procedure.add_menu_path("<Image>/Image/Custom/")
        procedure.set_documentation(
            'Raster image to tiles converter plug-in.',
            'Converts a raster image into a tile-based approximation.',
            'Todor Balabanov'
        )

        procedure.add_int_argument(
            'number-of-tiles', 'Number of tiles', 'Total number of desired tiles',
            1, 2147483647, 100, GObject.ParamFlags.READWRITE
        )
        procedure.add_string_argument(
            'optimizer-type', 'Optimizer', 'Optimizer to use',
            'Simple', GObject.ParamFlags.READWRITE
        )
        procedure.add_boolean_argument(
            'suboptimal-initialization', 'Suboptimal initialization', 'Use suboptimal initialization',
            True, GObject.ParamFlags.READWRITE
        )
        procedure.add_int_argument(
            'number-of-generations', 'Number of generations', 'Number of evolution generations',
            0, 2147483647, 10, GObject.ParamFlags.READWRITE
        )
        procedure.add_int_argument(
            'population-size', 'Population size', 'Population size for GA',
            1, 2147483647, 20, GObject.ParamFlags.READWRITE
        )
        procedure.add_double_argument(
            'crossover-rate', 'Crossover rate', 'Crossover probability',
            0.0, 1.0, 0.95, GObject.ParamFlags.READWRITE
        )
        procedure.add_double_argument(
            'mutation-rate', 'Mutation rate', 'Mutation probability',
            0.0, 1.0, 0.01, GObject.ParamFlags.READWRITE
        )
        procedure.add_boolean_argument(
            'image-resize', 'Resize image', 'Resize image to fit generated tiles',
            True, GObject.ParamFlags.READWRITE
        )
        
        return procedure

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        if run_mode == Gimp.RunMode.INTERACTIVE:
            try:
                dialog = Gtk.Dialog(
                    title="Image to Tiles Converter",
                    flags=Gtk.DialogFlags.MODAL,
                    buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                             Gtk.STOCK_OK, Gtk.ResponseType.OK)
                )
                dialog.set_size_request(400, 400)
                
                vbox = dialog.get_content_area()
                
                # Number of tiles
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label="Number of tiles:")
                spin = Gtk.SpinButton()
                spin.set_range(1, 2147483647)
                spin.set_value(config.get_property('number-of-tiles'))
                hbox.pack_start(label, False, False, 0)
                hbox.pack_end(spin, False, False, 0)
                vbox.pack_start(hbox, False, False, 0)
                
                # Optimizer type
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label="Optimizer:")
                combo = Gtk.ComboBoxText()
                combo.append_text("Simple")
                combo.append_text("Genetic Algorithm")
                optimizer_type = config.get_property('optimizer-type')
                if optimizer_type == "Simple":
                    combo.set_active(0)
                else:
                    combo.set_active(1)
                hbox.pack_start(label, False, False, 0)
                hbox.pack_end(combo, False, False, 0)
                vbox.pack_start(hbox, False, False, 0)
                
                # Suboptimal initialization
                check_subopt = Gtk.CheckButton(label="Suboptimal initialization")
                check_subopt.set_active(config.get_property('suboptimal-initialization'))
                vbox.pack_start(check_subopt, False, False, 0)
                
                # Number of generations
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label="Number of generations:")
                spin_gen = Gtk.SpinButton()
                spin_gen.set_range(0, 2147483647)
                spin_gen.set_value(config.get_property('number-of-generations'))
                hbox.pack_start(label, False, False, 0)
                hbox.pack_end(spin_gen, False, False, 0)
                vbox.pack_start(hbox, False, False, 0)
                
                # Population size
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label="Population size:")
                spin_pop = Gtk.SpinButton()
                spin_pop.set_range(1, 2147483647)
                spin_pop.set_value(config.get_property('population-size'))
                hbox.pack_start(label, False, False, 0)
                hbox.pack_end(spin_pop, False, False, 0)
                vbox.pack_start(hbox, False, False, 0)
                
                # Crossover rate
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label="Crossover rate:")
                spin_cross = Gtk.SpinButton()
                spin_cross.set_range(0.0, 1.0)
                spin_cross.set_digits(2)
                spin_cross.set_value(config.get_property('crossover-rate'))
                hbox.pack_start(label, False, False, 0)
                hbox.pack_end(spin_cross, False, False, 0)
                vbox.pack_start(hbox, False, False, 0)
                
                # Mutation rate
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                label = Gtk.Label(label="Mutation rate:")
                spin_mut = Gtk.SpinButton()
                spin_mut.set_range(0.0, 1.0)
                spin_mut.set_digits(2)
                spin_mut.set_value(config.get_property('mutation-rate'))
                hbox.pack_start(label, False, False, 0)
                hbox.pack_end(spin_mut, False, False, 0)
                vbox.pack_start(hbox, False, False, 0)
                
                # Image resize
                check_resize = Gtk.CheckButton(label="Resize image")
                check_resize.set_active(config.get_property('image-resize'))
                vbox.pack_start(check_resize, False, False, 0)
                
                vbox.show_all()
                
                response = dialog.run()
                if response == Gtk.ResponseType.OK:
                    config.set_property('number-of-tiles', int(spin.get_value()))
                    config.set_property('optimizer-type', combo.get_active_text())
                    config.set_property('suboptimal-initialization', check_subopt.get_active())
                    config.set_property('number-of-generations', int(spin_gen.get_value()))
                    config.set_property('population-size', int(spin_pop.get_value()))
                    config.set_property('crossover-rate', spin_cross.get_value())
                    config.set_property('mutation-rate', spin_mut.get_value())
                    config.set_property('image-resize', check_resize.get_active())
                
                dialog.destroy()
                
                if response != Gtk.ResponseType.OK:
                    return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            except Exception as e:
                Gimp.message('Dialog error: {0}'.format(str(e)))
                return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())
        
        number_of_tiles = config.get_property('number-of-tiles')
        optimizer_type = config.get_property('optimizer-type')
        suboptimal_initialization = config.get_property('suboptimal-initialization')
        number_of_generations = config.get_property('number-of-generations')
        population_size = config.get_property('population-size')
        crossover_rate = config.get_property('crossover-rate')
        mutation_rate = config.get_property('mutation-rate')
        image_resize = config.get_property('image-resize')

        original = get_layer_by_name(image, 'Original Image')
        if original is None:
            Gimp.message('Original Image layer not found.')
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

        original.set_mode(Gimp.LayerMode.DIFFERENCE)

        color_map_layer = get_layer_by_name(image, 'Color Map')
        if color_map_layer is None:
            Gimp.message('Color Map layer not found.')
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

        colors = list(list_of_colors(color_map_layer))
        if not colors:
            Gimp.message('Color Map layer contains no colors.')
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

        approximated = get_layer_by_name(image, 'Approximated Image')
        if approximated is None:
            approximated = create_layer(
                image, image_new_width, image_new_height,
                Gimp.ImageType.RGBA_IMAGE, 'Approximated Image', 100.0, Gimp.LayerMode.NORMAL
            )
            insert_layer(image, approximated, None, 0)

        if optimizer_type == 'Simple':
            solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)
        elif optimizer_type == 'Genetic Algorithm':
            solution = genetic_algorithm(image,
                original, approximated, colors, x_tiles, y_tiles,
                tile_side_length, suboptimal_initialization,
                number_of_generations, population_size, crossover_rate, mutation_rate
            )
            Gimp.message('Checking: {0}'.format(colors))
            Gimp.message('Checking: {0}'.format(solution))

        draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)
        Gimp.displays_flush()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

Gimp.main(ImageToTilesConverter.__gtype__, sys.argv)
