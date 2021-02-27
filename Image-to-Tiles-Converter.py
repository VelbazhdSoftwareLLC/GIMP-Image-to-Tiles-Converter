#!/usr/bin/python

import random
from gimpfu import *
from math import sqrt, ceil
from array import array


def dimensions_as_tiles(width, height, tiles):
	tile_area = width * height / tiles

	tile_side = ceil(sqrt(tile_area))

	width_in_tiles = ceil(width / tile_side)
	height_in_tiles = ceil(height / tile_side)

	return (width_in_tiles, height_in_tiles, tile_side)


def image_setup(x, y, length):
	return (x * y, x * length, y * length)


def list_of_colors(layer):
	colors = set()
	for y in range(layer.height):
		for x in range(layer.width):
			colors.add(layer.get_pixel(x, y))
	return colors


def draw_random_tiles(layer, colors, columns, rows, side):
	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
			pdb.gimp_context_set_background(random.choice(colors))
			pdb.gimp_edit_fill(layer, 1)

	pdb.gimp_selection_none(layer.image)


def average_color(layer):
		r, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_RED, 0, 1)
		g, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_GREEN, 0, 1)
		b, _, _, _, _, _ = pdb.gimp_drawable_histogram(layer, HISTOGRAM_BLUE, 0, 1)
		return (int(r), int(g), int(b))


def match_color(colors, average):
	result = colors[0]
	min = sqrt((result[0] - average[0]) ** 2 + (result[1] - average[1]) ** 2 + (result[2] - average[2]) ** 2)

	for candidate in colors:
		distance = sqrt((candidate[0] - average[0]) ** 2 + (candidate[1] - average[1]) ** 2 + (candidate[2] - average[2]) ** 2)
		if distance < min:
			result = candidate
			min = distance

	return result


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


def draw_solution_tiles(layer, solution, columns, rows, side):
	i = 0

	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(layer.image, 2, x * side, y * side, side, side)
			pdb.gimp_context_set_background(solution[i])
			pdb.gimp_edit_fill(layer, 1)
			i += 1

	pdb.gimp_selection_none(layer.image)


def draw_tiles_numbering(layer, colors, solution, columns, rows, side):
	i = 0

	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_context_set_foreground((255 - solution[i][0], 255 - solution[i][1], 255 - solution[i][2]))
			pdb.gimp_text_fontname(layer.image, layer, x * side, y * side, str(colors.index(solution[i]) + 1), 2, 0, int(side / 3), 0, "Sans")
			i += 1

	pdb.gimp_image_remove_layer(layer.image, pdb.gimp_text_fontname(layer.image, layer, 0, 0, "", 2, 1, 1, 0, "Sans"))


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


def plugin_main(image, drawable, number_of_tiles=1, number_of_generations=0, population_size=3, crossover_rate=1.0, mutation_rate=0.0,
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
	solution = match_tiles(original, colors, x_tiles, y_tiles, tile_side_length)

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
		(PF_INT32, "number_of_generations", "Number of Genetic Algorithm Generations", 0),
		(PF_INT32, "population_size", "Genetic Algorithm Population Size", 3),
		(PF_FLOAT, "crossover_rate", "Genetic Algorithm Crossover Rate", 1.0),
		(PF_FLOAT, "mutation_rate", "Genetic Algorithm Mutation Rate", 0.0),
		(PF_BOOL, "solution_numbering", "Numbering of the Result Solution", FALSE),
		(PF_BOOL, "solution_statistics", "Statistics of the Result Solution", FALSE),
		(PF_BOOL, "image_resize", "Image Resize to Fit Exact Tiles", TRUE),
	],
	[],
	plugin_main,
)
 
main()
