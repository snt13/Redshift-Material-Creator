# C4D-Redshift Material Creator


RUN THE SCRIPT

Run Script inside of the Cinema 4D Run script command.


Material Creator v001

This script scans a selected folder for texture files for each channel 
(BaseColor, Roughness, Normal, Displacement) using case‐ and underscore‐insensitive matching.
For each enabled channel the script uses the custom search text (entered in the corresponding textbox)
to look for files whose names contain one of the comma‐separated keywords, and then extracts an identifier from each file.
If a channel returns only one match, its identifier is forced to "" so that it groups with the others.
A Redshift Standard Material is then created for each identifier found (the material name is suffixed by the identifier if non‐empty).
If the "Import 3D Model" option is enabled, the script merges the 3D objects from the folder without assigning any material.
Additionally, if the AO checkbox is checked (ID 4002), an AO node is created and inserted into the BaseColor chain:
  • The Color Correct node’s OutColor is connected to the AO node’s “bright” input.
  • The AO node’s output is connected to the Standard Material’s base_color input.
If you close the dialog without clicking "Create Material", no material is created.
"""
