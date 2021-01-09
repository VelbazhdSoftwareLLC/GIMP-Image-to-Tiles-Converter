#!/usr/bin/python
 
from gimpfu import *
 
def plugin_main(image, drawable, number_of_tiles):
	gimp.message("Hi all!")
 
register(
	"python_fu_image_to_tiles",
	"Raster image to tiles convertor plug-in.",
	"When run this plug-in converts a raster image in to tiles image.",
	"Todor Balabanov",
	"Velbazhd Software LLC\nGPLv3 License",
	"2021",
	"<Image>/Image/Custom/Image to Tiles Converter",
	"*",
	[
		(PF_INT32, "number_of_tiles", "Desired Number of Tiles", 1),
	],
	[],
	plugin_main,
)
 
main()
