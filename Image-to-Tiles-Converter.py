#!/usr/bin/python

""" ============================================================================
= GIMP Image to Tiles Converter version 1.0.0                                  =
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

import random
from copy import deepcopy
from gimpfu import *
from math import ceil, sqrt


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
    for y in range(layer.height):
        for x in range(layer.width):
            colors.add(layer.get_pixel(x, y))
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
            pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
            pdb.gimp_context_set_background(random.choice(colors))
            pdb.gimp_edit_fill(layer, 1)

    pdb.gimp_selection_none(layer.image)


"""Estimate the average color in a layer.

@param layer The layer in which region average color is calculated.

@return Average color as RGB values.
"""


def average_color(layer):
    r, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_RED, 0, 1)
    g, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_GREEN, 0, 1)
    b, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_BLUE, 0, 1)
    return int(r), int(g), int(b)


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
            pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
            average = average_color(layer)
            matched.append(match_color(colors, average))

    pdb.gimp_selection_none(layer.image)
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
            pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
            pdb.gimp_context_set_background(solution[i])
            pdb.gimp_edit_fill(layer, 1)
            i += 1
    pdb.gimp_selection_none(layer.image)


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
            pdb.gimp_context_set_foreground(
                (255 - tile_color[0], 255 - tile_color[1], 255 - tile_color[2])
            )
            pdb.gimp_text_fontname(
                layer.image,
                layer,
                x * side,
                y * side,
                str(color_indices[tile_color] + 1),
                -1,
                FALSE,
                int(3 * side / 4),
                0,
                "Sans",
            )
            i += 1

    pdb.gimp_image_remove_layer(
        layer.image,
        pdb.gimp_text_fontname(layer.image, layer, 0, 0, "", 2, 1, 1, 0, "Sans"),
    )


"""Draw tiles statistics.

@param layer Layer of the approximated image statistics.
@param colors List of tile colors.
@param solution List of tile colors for the image approximation.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tile side in pixels.
"""


def draw_solution_statistics(layer, colors, solution, columns, rows, side):
    pdb.gimp_image_select_rectangle(layer.image, 2, 0, 0, layer.width, layer.height)
    pdb.gimp_context_set_background((255, 255, 255))
    pdb.gimp_edit_fill(layer, 1)

    counters = {c: 0 for c in colors}
    for c in solution:
        counters[c] += 1

    size = side
    if size < 20:
        size = 20

    for index, color in enumerate(colors):
        pdb.gimp_image_select_rectangle(layer.image, 2, 0, index * size, size, size)
        pdb.gimp_context_set_background(color)
        pdb.gimp_edit_fill(layer, 1)
        pdb.gimp_context_set_foreground((0, 0, 0))
        pdb.gimp_text_fontname(
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
        pdb.gimp_text_fontname(
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
        pdb.gimp_text_fontname(
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

    pdb.gimp_selection_none(layer.image)
    pdb.gimp_image_remove_layer(
        layer.image,
        pdb.gimp_text_fontname(layer.image, layer, 0, 0, "", 2, 1, 1, 0, "Sans"),
    )


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

    pdb.gimp_edit_copy_visible(original.image)
    floating = pdb.gimp_edit_paste(approximated, False)
    pdb.gimp_floating_sel_anchor(floating)
    original.visible = False

    r, _, _, _, _, _ = pdb.gimp_drawable_histogram(approximated, HISTOGRAM_RED, 0, 1)
    g, _, _, _, _, _ = pdb.gimp_drawable_histogram(approximated, HISTOGRAM_GREEN, 0, 1)
    b, _, _, _, _, _ = pdb.gimp_drawable_histogram(approximated, HISTOGRAM_BLUE, 0, 1)
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


def plugin_main(
    image,
    drawable,
    number_of_tiles=1,
    optimizer="Simple",
    suboptimal_initialization=TRUE,
    number_of_generations=0,
    population_size=3,
    crossover_rate=1.0,
    mutation_rate=0.0,
    solution_numbering=FALSE,
    solution_statistics=FALSE,
    image_resize=TRUE,
):
    original = pdb.gimp_image_get_layer_by_name(image, "Original Image")
    if original is None:
        pdb.gimp_message("Original Image layer not found.")
        return

    if number_of_tiles < 1:
        number_of_tiles = 1

    x_tiles, y_tiles, tile_side_length = dimensions_as_tiles(
        original.width, original.height, number_of_tiles
    )
    number_of_tiles, image_new_width, image_new_height = image_setup(
        x_tiles, y_tiles, tile_side_length
    )

    if image_resize:
        pdb.gimp_context_set_interpolation(INTERPOLATION_LANCZOS)
        pdb.gimp_layer_scale(original, image_new_width, image_new_height, False)
        pdb.gimp_image_resize_to_layers(image)

    original.mode = DIFFERENCE_MODE
    color_map_layer = pdb.gimp_image_get_layer_by_name(image, "Color Map")
    if color_map_layer is None:
        pdb.gimp_message("Color Map layer not found.")
        return

    colors = list(list_of_colors(color_map_layer))
    if not colors:
        pdb.gimp_message("Color Map layer contains no colors.")
        return

    approximated = pdb.gimp_image_get_layer_by_name(image, "Approximated Image")
    if approximated is None:
        approximated = pdb.gimp_layer_new(
            image,
            image_new_width,
            image_new_height,
            RGB_IMAGE,
            "Approximated Image",
            100,
            NORMAL_MODE,
        )
        pdb.gimp_image_insert_layer(image, approximated, None, 2)

    if optimizer == "Simple":
        solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)
    elif optimizer == "Genetic Algorithm":
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
        solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)

    draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)

    if solution_numbering:
        draw_tiles_numbering(
            approximated,
            colors,
            solution,
            x_tiles,
            y_tiles,
            tile_side_length,
        )

    statistics = pdb.gimp_image_get_layer_by_name(image, "Tiles Statistics")
    if solution_statistics:
        if statistics is None:
            statistics = pdb.gimp_layer_new(
                image,
                10 * x_tiles * tile_side_length,
                10 * len(colors) * tile_side_length,
                RGB_IMAGE,
                "Tiles Statistics",
                100,
                NORMAL_MODE,
            )
            pdb.gimp_image_insert_layer(image, statistics, None, 3)
            pdb.gimp_image_resize_to_layers(image)
        draw_solution_statistics(
            statistics,
            colors,
            solution,
            x_tiles,
            y_tiles,
            tile_side_length,
        )


register(
    "python_fu_image_to_tiles",
    "Raster image to tiles converter plug-in.",
    "When run this plug-in converts a raster image into a tiles image.",
    "Todor Balabanov",
    "Velbazhd Software LLC\nGPLv3 License",
    "2021",
    "<Image>/Image/Custom/Image to Tiles Converter",
    "RGB*",
    [
        (PF_INT32, "number_of_tiles", "Desired Number of Tiles", 1),
        (
            PF_RADIO,
            "optimizer",
            "Optimizer",
            "Simple",
            (("Simple", "Simple"), ("Genetic Algorithm", "Genetic Algorithm")),
        ),
        (
            PF_BOOL,
            "suboptimal_initialization",
            "Initialize the Population with Suboptimal Solutions",
            TRUE,
        ),
        (
            PF_INT32,
            "number_of_generations",
            "Number of Genetic Algorithm Generations",
            0,
        ),
        (
            PF_INT32,
            "population_size",
            "Genetic Algorithm Population Size",
            3,
        ),
        (
            PF_FLOAT,
            "crossover_rate",
            "Genetic Algorithm Crossover Rate",
            0.95,
        ),
        (
            PF_FLOAT,
            "mutation_rate",
            "Genetic Algorithm Mutation Rate",
            0.01,
        ),
        (
            PF_BOOL,
            "solution_numbering",
            "Numbering of the Result Solution",
            FALSE,
        ),
        (
            PF_BOOL,
            "solution_statistics",
            "Statistics of the Result Solution",
            FALSE,
        ),
        (
            PF_BOOL,
            "image_resize",
            "Image Resize to Fit Exact Tiles",
            TRUE,
        ),
    ],
    [],
    plugin_main,
)

main()
