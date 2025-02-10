# C4D-Redshift Material Creator


RUN THE SCRIPT

Run Script inside of the Cinema 4D Run script command.


Material Creator v001

This script scans a selected folder for texture files for each channel (BaseColor, Roughness, Normal, Displacement)
using case‑ and underscore‑insensitive matching. It groups the files by a common identifier (the file name with the 
channel keyword removed) so that for every identifier common to all enabled channels a complete texture set exists.
For every complete set a Redshift Standard Material is created (with the material name suffixed by the identifier 
if non‑empty). If the "Import 3D Model" option is enabled, the script simply merges the 3D objects from the folder 
without assigning any material.
If you close the dialog without clicking "Create Material", no material is created.
