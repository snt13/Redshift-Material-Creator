# C4D-Redshift Material Creator


RUN THE SCRIPT

Run Script inside of the Cinema 4D Run script command.


Material Creator v001
This script creates a Redshift Standard Material in Cinema 4D based on user input.
For each texture channel (BaseColor, Roughness, Normal, Displacement), if the checkbox is enabled
(i.e. a file path is provided), then a texture sampler node and its corresponding processing chain
are created and connected:
  - BaseColor: Texture Sampler → ColorCorrect → Standard Material (base_color)
  - Roughness: Texture Sampler → Ramp → Standard Material (refl_roughness)
  - Normal:    Texture Sampler → Bump Map → Standard Material (bump_input)
  - Displacement: Texture Sampler → Displacement → Output node (displacement)
If the dialog is closed without clicking "Create Material", no material is created.
Additionally, 3D objects (.fbx/.obj) in the selected folder can be imported and assigned the created material.
