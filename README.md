# C4D-Redshift Material Creator


RUN THE SCRIPT

Run Script inside of the Cinema 4D Run script command.


Material Creator v001

This script scans a selected folder for texture files for each channel 
(BaseColor, Roughness, Normal, Displacement) using case‑ and underscore‑insensitive matching.
For each enabled channel the script looks for files whose names contain the search text and then 
extracts a common identifier by removing underscores and the channel keyword from the file name.
For every identifier that appears in any of the enabled channels, a Redshift Standard Material is created 
(with the material name suffixed by the identifier if non‑empty). Channels for which no matching file is found 
will be left out (and the material will be created without that texture).
If the "Import 3D Model" option is enabled, the script simply merges the 3D objects from the folder 
without assigning any material.
If you close the dialog without clicking "Create Material", no material is created.
