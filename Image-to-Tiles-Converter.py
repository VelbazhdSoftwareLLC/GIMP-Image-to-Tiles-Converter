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


def draw_random_tiles(image, layer, colors, columns, rows, side):
	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(image, 2, x * side, y * side, side, side)
			pdb.gimp_context_set_background(random.choice(colors))
			pdb.gimp_edit_fill(layer, 1)

	pdb.gimp_selection_none(image)


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


def match_tiles(image, original, colors, columns, rows, side):
	matched = list()

	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(image, 2, x * side, y * side, side, side)
			average = average_color(original)
			corresponding = match_color(colors, average)
			matched.append(corresponding)

	pdb.gimp_selection_none(image)

	return matched


def draw_solution_tiles(image, layer, solution, columns, rows, side):
	i = 0

	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(image, 2, x * side, y * side, side, side)
			pdb.gimp_context_set_background(solution[i])
			pdb.gimp_edit_fill(layer, 1)
			i += 1

	pdb.gimp_selection_none(image)


def draw_tiles_numbering(image, layer, colors, solution, columns, rows, side):
	i = 0

	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_context_set_foreground((255 - solution[i][0], 255 - solution[i][1], 255 - solution[i][2]))
			pdb.gimp_text_fontname(image, layer, x * side, y * side, str(colors.index(solution[i]) + 1), 2, 0, int(side / 3), 0, "Sans")
			i += 1

	pdb.gimp_image_remove_layer(image, pdb.gimp_text_fontname(image, layer, 0, 0, "", 2, 1, 1, 0, "Sans"))


def plugin_main(image, drawable, number_of_tiles):
	''' Calculate dimensions as number of tiles and tiles size. '''
	(x_tiles, y_tiles, tile_side_length) = dimensions_as_tiles(image.width, image.height, number_of_tiles)
	# gimp.message( "".join(str((number_of_tiles, x_tiles, y_tiles, tile_side_length))) )

	''' Calculate image resize parameters. '''
	(number_of_tiles, image_new_width, image_new_height) = image_setup(x_tiles, y_tiles, tile_side_length)
	# gimp.message( "".join(str((number_of_tiles, image.width, image.height, image_new_width, image_new_height))) )

	''' Resize image.  '''
	pdb.gimp_context_set_interpolation(INTERPOLATION_LANCZOS)
	pdb.gimp_image_scale(image, image_new_width, image_new_height)

	''' Layer of the original image.  '''
	original = image.layers[0]

	''' Determine colors to use.  '''
	colors = list(list_of_colors(image.layers[1]))
	# gimp.message( "".join(str(colors)) )

	''' Create layer for the resulting image.  '''
	approximated = pdb.gimp_image_get_layer_by_name(image, "Approximated Image")
	if approximated == None:
		approximated = pdb.gimp_layer_new(image, image.width, image.height, RGB_IMAGE, "Approximated Image", 100, NORMAL_MODE)  # DIFFERENCE_MODE SUBTRACT_MODE
		pdb.gimp_image_insert_layer(image, approximated, None, 2)

	''' Draw random tiles.  '''
	# draw_random_tiles(image, approximated, colors, x_tiles, y_tiles, tile_side_length)

	''' Match tiles to original colors.  '''
	solution = match_tiles(image, original, colors, x_tiles, y_tiles, tile_side_length)
	# gimp.message("".join(str(solution)))

	''' Draw solution tiles.  '''
	draw_solution_tiles(image, approximated, solution, x_tiles, y_tiles, tile_side_length)

	''' Enumerate tiles.  '''
	# draw_tiles_numbering(image, approximated, colors, solution, x_tiles, y_tiles, tile_side_length)


register(
	"python_fu_image_to_tiles",
	"Raster image to tiles convertor plug-in.",
	"When run this plug-in converts a raster image in to tiles image.",
	"Todor Balabanov",
	"Velbazhd Software LLC\nGPLv3 License",
	"2021",
	"<Image>/Image/Custom/Image to Tiles Converter",
	"RGB",
	[
		(PF_INT32, "number_of_tiles", "Desired Number of Tiles", 1),
	],
	[],
	plugin_main,
)
 
main()
