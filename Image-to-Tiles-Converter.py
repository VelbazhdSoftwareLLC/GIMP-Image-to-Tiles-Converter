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


def radnom_tiles(image, layer, colors, columns, rows, side):
	for x in range(0, int(columns)):
		for y in range(0, int(rows)):
			pdb.gimp_image_select_rectangle(image, 2, x * side, y * side, side, side)
			pdb.gimp_context_set_background(random.choice(colors))
			pdb.gimp_edit_fill(layer, 1)


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

	''' Determine colors to use.  '''
	colors = list(list_of_colors(image.layers[1]))
	# gimp.message( "".join(str(colors)) )

	''' Create layer for the resulting image.  '''
	approximated = pdb.gimp_layer_new(image, image.width, image.height, RGB_IMAGE, "Approximated Image", 100, NORMAL_MODE)  # DIFFERENCE_MODE SUBTRACT_MODE
	pdb.gimp_image_insert_layer(image, approximated, None, 2)

	''' Draw random tiles.  '''
	radnom_tiles(image, approximated, colors, x_tiles, y_tiles, tile_side_length)


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
