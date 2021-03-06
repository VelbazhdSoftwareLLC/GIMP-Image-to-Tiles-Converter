#!/usr/bin/python

""" ============================================================================
= GIMP Image to Tiles Converter version 1.0.0                                  =
= Copyrights (C) 2021 Velbazhd Software LLC                                    =
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
from gimpfu import *
from math import sqrt, ceil
from array import array

"""
Estimating the size of the image in the number of tiles by x and y.

@param width Image width in pixels.
@param height Image height in pixels.
@param tilse A total number of desired tiles to fill the image.

@return A tuple of image width in tiles, image height in tiles, and single square tile size in pixels.
"""


def dimensions_as_tiles(width, height, tiles):
	tile_area = width * height / tiles

	tile_side = ceil(sqrt(tile_area))

	width_in_tiles = ceil(width / tile_side)
	height_in_tiles = ceil(height / tile_side)

	return (width_in_tiles, height_in_tiles, tile_side)

"""
Calculation of image resize parameters.

@param x Width of the image in a number of tiles.
@param y Height of the image in a number of tiles.
@param length Length of single square tile in pixels.

@return A tuple of total tiles needed, image new width in pixels, and image new height in pixels.
"""


def image_setup(x, y, length):
	return (x * y, x * length, y * length)

"""
List all colors used for the tiles by extracting them from a colormap layer. Each pixel with specific color is included.

@param layer Colormap layer.

@return List of tiles colors.
"""


def list_of_colors(layer):
	colors = set()
	for y in range(layer.height):
		for x in range(layer.width):
			colors.add(layer.get_pixel(x, y))
	return colors

"""
Assembling random tiles with the shape of the original image.

@param layer Resulting layer for the random image.
@param colors List of tiles colors.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param size Length of a single square tiles side in pixels.
"""


def draw_random_tiles(layer, colors, columns, rows, side):
	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
			pdb.gimp_context_set_background(random.choice(colors))
			pdb.gimp_edit_fill(layer, 1)

	pdb.gimp_selection_none(layer.image)

"""
Estimation of an average color in a layer.

@param layer The layer in which region average color is calculated.

@return Average color as RGB values.
"""


def average_color(layer):
		r, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_RED, 0, 1)
		g, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_GREEN, 0, 1)
		b, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_BLUE, 0, 1)
		return (int(r), int(g), int(b))

"""
Match an RGB color to the closest color in a list of colors.

@param colors List of tiles colors.
@param average The RGB value of the average color.

@return The closest color by Euclidean distance in RGB channels.
"""


def match_color(colors, average):
	result = colors[0]
	min = sqrt((result[0] - average[0]) ** 2 + (result[1] - average[1]) ** 2 + (result[2] - average[2]) ** 2)

	for candidate in colors:
		distance = sqrt((candidate[0] - average[0]) ** 2 + (candidate[1] - average[1]) ** 2 + (candidate[2] - average[2]) ** 2)
		if distance < min:
			result = candidate
			min = distance

	return result

"""
Match tiles to average close colors.

@param layer Layer of the original image.
@param colors List of tiles colors.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tiles side in pixels.

@return List of matched colors for the tiles.
"""


def match_tiles(layer, colors, columns, rows, side):
	matched = list()
	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
			average = average_color(layer)
			corresponding = match_color(colors, average)
			matched.append(corresponding)

	pdb.gimp_selection_none(layer.image)
	return matched

"""
Drawing the list of tiles.

@param solution List of tiles colors for the image approximation.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tiles side in pixels.
"""


def draw_solution_tiles(layer, solution, columns, rows, side):
	i = 0
	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
			pdb.gimp_context_set_background(solution[i])
			pdb.gimp_edit_fill(layer, 1)
			i += 1
	pdb.gimp_selection_none(layer.image)

"""
Draw numbers on tiles.

@param layer Layer of the approximated image.
@param colors List of tiles colors.
@param solution List of tiles colors for the image approximation.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tiles side in pixels.
"""


def draw_tiles_numbering(layer, colors, solution, columns, rows, side):
	i = 0
	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_context_set_foreground((255 - solution[i][0], 255 - solution[i][1], 255 - solution[i][2]))
			pdb.gimp_text_fontname(layer.image, layer, x * side, y * side, str(colors.index(solution[i]) + 1), -1, FALSE, int(3 * side / 4), 0, "Sans")
			i += 1
	pdb.gimp_image_remove_layer(layer.image, pdb.gimp_text_fontname(layer.image, layer, 0, 0, "", 2, 1, 1, 0, "Sans"))

"""
Draw tiles statistics.

@param layer Layer of the approximated image statistics.
@param colors List of tiles colors.
@param solution List of tiles colors for the image approximation.
@param columns Width of the resulting image as a number of tiles.
@param rows Height of the resulting image as a number of tiles.
@param side Length of a single square tiles side in pixels.
"""


def draw_solution_statistics(layer, colors, solution, columns, rows, side):
	pdb.gimp_image_select_rectangle(layer.image, 2, 0, 0, layer.width, layer.height)
	pdb.gimp_context_set_background((255, 255, 255))
	pdb.gimp_edit_fill(layer, 1)

	counters = {}
	for c in colors:
		counters[c] = 0
	for c in solution:
		counters[c] += 1

	''' Statistics text should be big enough. '''
	size = side
	if size < 20:
		size = 20

	for y in range(0, len(colors)):
		pdb.gimp_image_select_rectangle(layer.image, 2, 0, y * size, size, size)
		pdb.gimp_context_set_background(colors[y])
		pdb.gimp_edit_fill(layer, 1)
		pdb.gimp_context_set_foreground((0, 0, 0))
		pdb.gimp_text_fontname(layer.image, layer, 1 * size, y * size, str(y + 1), 2, 0, int(size / 2), 0, "Sans")
		pdb.gimp_text_fontname(layer.image, layer, 2 * size, y * size, str(counters[colors[y]]), 2, 0, int(size / 2), 0, "Sans")
		pdb.gimp_text_fontname(layer.image, layer, 4 * size, y * size, str(colors[y]), 2, 0, int(size / 2), 0, "Sans")

	pdb.gimp_selection_none(layer.image)
	pdb.gimp_image_remove_layer(layer.image, pdb.gimp_text_fontname(layer.image, layer, 0, 0, "", 2, 1, 1, 0, "Sans"))

"""
Generation of a random chromosome.

@param colors List of tiles colors.
@param length The length of the newly generated chromosome.

@return Randomly generated chromosome.
"""


def random_chromosome(colors, length):
	chromosome = list()
	for x in range(0, int(length)):
		chromosome.append(random.choice(colors))
	return chromosome

"""
Selection of two parents and a single child.

@param population Genetic algorithm population.
@param fitness The fitness values of the individuals in the population.

@return Selected parents and the child.
"""


def select(population, fitness):
	''' Selection of three unique individuals. '''
	while True:
		child = random.choice(population)
		parent1 = random.choice(population)
		parent2 = random.choice(population)
		if child == parent1:
			continue
		if child == parent2:
			continue
		if parent1 == parent2:
			continue
		break

	''' Implement elitism in such a way that the child always is the weakest individual. '''
	if fitness[population.index(child)] < fitness[population.index(parent1)]:
		buffer = child
		child = parent1
		parent1 = buffer
	if fitness[population.index(child)] < fitness[population.index(parent2)]:
		buffer = child
		child = parent2
		parent2 = buffer

	return [child, parent1, parent2]

"""
Uniform crossover.

@param probability Crossover probability rate.
@param child Crossover result. 
@param parent1 First parent.
@param parent2 Second parent.
"""


def crossover(probability, child, parent1, parent2):
	if random.random() >= probability:
		return

	for i in range(0, len(child)):
		if random.choice([True, False]):
			child[i] = parent1[i]
		else:
			child[i] = parent2[i]

"""
Tile color mutation.

@param probability Mutation probability rate.
@param colors List of tiles colors.
@param child Mutation result. 
"""


def mutation(probability, colors, child):
	for i in range(0, len(child)):
		if random.random() >= probability:
			continue
		else:
			child[i] = random.choice(colors)

"""
Fitness value estimation.

"""

"""
Chromosome fitness value evaluation.

@param original Layer of the original image.
@param approximated Layer of the approximated image.
@param colors List of tiles colors.
@param x_tiles Width of the approximated image in tiles.
@param y_tiles Height of the approximated image in tiles.
@param tile_side_length Size of a single square tile side in pixels.
@param solution The solution to be evaluated.

@return Fitness value calculated.
"""


def evaluate(original, approximated, colors, x_tiles, y_tiles, tile_side_length, solution):
	value = float('inf');
	draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)

	''' Make visible only original image and approximated image.  '''
	for layer in original.image.layers:
		layer.visible = False
	original.visible = True
	approximated.visible = True

	''' Generate the difference between the original image and the approximated image.  '''
	pdb.gimp_edit_copy_visible(original.image)
	floating = pdb.gimp_edit_paste(approximated, False)
	pdb.gimp_floating_sel_anchor(floating)
	original.visible = False

	''' Average color calculation. '''
	r, _, _, _, _, _ = pdb.gimp_drawable_histogram(approximated, HISTOGRAM_RED, 0, 1)
	g, _, _, _, _, _ = pdb.gimp_drawable_histogram(approximated, HISTOGRAM_GREEN, 0, 1)
	b, _, _, _, _, _ = pdb.gimp_drawable_histogram(approximated, HISTOGRAM_BLUE, 0, 1)
	value = (r + g + b) / 3.0

	return value

"""
Genetic algorithm optimizer.

@param original Layer of the original image. 
@param approximated Layer of the approximated image.
@param colors List of tiles colors.
@param x_tiles Width of the approximated image in tiles.
@param y_tiles Height of the approximated image in tiles.
@param tile_side_length Size of a single square tile side in pixels. 
@param number_of_generations Number of evolution generations. 
@param population_size Population size.
@param crossover_rate Crossover rate.
@param mutation_rate Mutation rate.

@return The best solution found.
"""


def genetic_algorithm(original, approximated, colors, x_tiles, y_tiles, tile_side_length,
					  number_of_generations, population_size, crossover_rate, mutation_rate):
	fitness = list()
	population = list()

	# TODO Implement initial population which is not random.

	''' Initialize random population. '''
	for p in range(0, population_size):
		population.append(random_chromosome(colors, (x_tiles * y_tiles)))
		fitness.append(float('inf'))
	best = random.choice(population)

	''' Each generation has a population size of individuals. '''
	for g in range(0, number_of_generations * population_size):
		[child, parent1, parent2] = select(population, fitness)
		crossover(crossover_rate, child, parent1, parent2)
		mutation(mutation_rate, colors, child)
		fitness[population.index(child)] = evaluate(original, approximated, colors, x_tiles, y_tiles, tile_side_length, child)

	return best

"""
Plug-in single entry point.

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


def plugin_main(image, drawable, number_of_tiles=1, optimizer="Simple",
			number_of_generations=0, population_size=3, crossover_rate=1.0, mutation_rate=0.0,
			solution_numbering=FALSE, solution_statistics=FALSE, image_resize=TRUE):
	''' Layer of the original image.  '''
	original = pdb.gimp_image_get_layer_by_name(image, "Original Image")

	''' Calculate dimensions as number of tiles and tiles size. '''
	(x_tiles, y_tiles, tile_side_length) = dimensions_as_tiles(original.width, original.height, number_of_tiles)

	''' Calculate image resize parameters. '''
	(number_of_tiles, image_new_width, image_new_height) = image_setup(x_tiles, y_tiles, tile_side_length)

	''' Resize image.  '''
	if image_resize == TRUE:
		pdb.gimp_context_set_interpolation(INTERPOLATION_LANCZOS)
		pdb.gimp_layer_scale(original, image_new_width, image_new_height, False)
		pdb.gimp_image_resize_to_layers(image)
		
	''' Setup layer of the original image for difference calculation.  '''
	original.mode = DIFFERENCE_MODE

	''' Determine colors to use.  '''
	colors = list(list_of_colors(pdb.gimp_image_get_layer_by_name(image, "Color Map")))

	''' Create layer for the approximated image.  '''
	approximated = pdb.gimp_image_get_layer_by_name(image, "Approximated Image")
	if approximated == None:
		approximated = pdb.gimp_layer_new(image, image_new_width, image_new_height, RGB_IMAGE, "Approximated Image", 100, NORMAL_MODE)  # DIFFERENCE_MODE SUBTRACT_MODE
		pdb.gimp_image_insert_layer(image, approximated, None, 2)

	''' Match tiles to original colors.  '''
	if optimizer == "Simple":
		solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)

	''' Search for a sub-optimal solution with a genetic algorithm.  '''
	if optimizer == "Genetic Algorithm":
		solution = genetic_algorithm(original, approximated, colors, x_tiles, y_tiles, tile_side_length,
		        					 number_of_generations, population_size, crossover_rate, mutation_rate)

	''' Draw solution tiles.  '''
	draw_solution_tiles(approximated, solution, x_tiles, y_tiles, tile_side_length)

	''' Numbering tiles.  '''
	if solution_numbering == TRUE:
		draw_tiles_numbering(approximated, colors, solution, x_tiles, y_tiles, tile_side_length)

	''' Create layer for tiles statistics.  '''
	statistics = pdb.gimp_image_get_layer_by_name(image, "Tiles Statistics")
	
	''' Draw tiles statistics.  '''
	if solution_statistics == TRUE:
		if statistics == None:
			statistics = pdb.gimp_layer_new(image, 10 * x_tiles * tile_side_length, 10 * len(colors) * tile_side_length, RGB_IMAGE, "Tiles Statistics", 100, NORMAL_MODE)
			pdb.gimp_image_insert_layer(image, statistics, None, 3)
			pdb.gimp_image_resize_to_layers(image)
		draw_solution_statistics(statistics, colors, solution, x_tiles, y_tiles, tile_side_length)


register(
	"python_fu_image_to_tiles",
	"Raster image to tiles convertor plug-in.",
	"When run this plug-in converts a raster image in to tiles image.",
	"Todor Balabanov",
	"Velbazhd Software LLC\nGPLv3 License",
	"2021",
	"<Image>/Image/Custom/Image to Tiles Converter",
	"RGB*",
	[
		# (PF_IMAGE, "image", "Input Image", None),
		# (PF_DRAWABLE, "drawable", "Input Drawable", None),
		(PF_INT32, "number_of_tiles", "Desired Number of Tiles", 1),
		(PF_RADIO, "optimizer", "Optimizer", "Simple", (("Simple", "Simple"), ("Genetic Algorithm", "Genetic Algorithm"))),
		(PF_INT32, "number_of_generations", "Number of Genetic Algorithm Generations", 0),
		(PF_INT32, "population_size", "Genetic Algorithm Population Size", 3),
		(PF_FLOAT, "crossover_rate", "Genetic Algorithm Crossover Rate", 0.95),
		(PF_FLOAT, "mutation_rate", "Genetic Algorithm Mutation Rate", 0.01),
		(PF_BOOL, "solution_numbering", "Numbering of the Result Solution", FALSE),
		(PF_BOOL, "solution_statistics", "Statistics of the Result Solution", FALSE),
		(PF_BOOL, "image_resize", "Image Resize to Fit Exact Tiles", TRUE),
	],
	[],
	plugin_main,
)
 
main()
