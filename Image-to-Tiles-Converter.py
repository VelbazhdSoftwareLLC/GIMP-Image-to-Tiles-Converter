#!/usr/bin/python
 
from gimpfu import *
from math import sqrt, ceil

def dimensions_as_tiles(width, height, tiles):
	tile_area = width * height / tiles

	tile_side = ceil(sqrt( tile_area ))

	width_in_tiles = ceil(width / tile_side)
	height_in_tiles = ceil(height / tile_side)

	return (width_in_tiles, height_in_tiles, tile_side)

def image_setup(x, y, length):
	return (x*y, x*length, y*length)

def plugin_main(image, drawable, number_of_tiles):
	''' Calculate dimensions as number of tiles and tiles size. '''
	(x_tiles, y_tiles, tile_side_length) = dimensions_as_tiles(image.width, image.height, number_of_tiles)
	#gimp.message( "".join(str((number_of_tiles, x_tiles, y_tiles, tile_side_length))) )

	''' Calculate image resize parameters. '''
	(number_of_tiles, image_new_width, image_new_height) = image_setup(x_tiles, y_tiles, tile_side_length)
	#gimp.message( "".join(str((number_of_tiles, image.width, image.height, image_new_width, image_new_height))) )

	''' Resize image.  '''
	pdb.gimp_context_set_interpolation(INTERPOLATION_LANCZOS)
	pdb.gimp_image_scale(image, image_new_width, image_new_height)
 
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
