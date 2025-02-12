# C4D-Redshift Material Creator


RUN THE SCRIPT

Run Script inside of the Cinema 4D Run script command.


Redshift Material Creator is a Cinema 4D Python script that automates building Redshift materials from texture files in a chosen folder. It searches for BaseColor, Roughness, Normal, and Displacement textures using user-defined keywords, extracts an identifier from each filename, and sets up a complete node-based Redshift material for each texture set. Additionally, it can optionally:

Import 3D models from the same folder,
Copy textures to a “tex” subfolder of the Cinema 4D project,
Add an Ambient Occlusion node to the BaseColor chain.
This streamlines texturing workflows by eliminating manual node creation and ensuring that all relevant textures are discovered, named, and linked automatically.
