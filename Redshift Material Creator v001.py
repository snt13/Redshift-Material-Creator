"""
Material Creator v001
Developed by isintan kursun with the assistance of ChatGPT.
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
"""

import c4d
import maxon
import os
from c4d import gui, storage

# --------------------------------------------------
# Helper functions for object processing
# --------------------------------------------------
def get_all_objects(obj):
    """Recursively returns a list of all objects in the hierarchy starting at obj."""
    result = []
    while obj:
        result.append(obj)
        result += get_all_objects(obj.GetDown())
        obj = obj.GetNext()
    return result

def assign_material_recursive(obj, material):
    """Recursively assigns the material to obj and its children using a texture tag with UVW projection."""
    if obj is None:
        return
    tag = obj.MakeTag(c4d.Ttexture)
    if tag:
        tag[c4d.TEXTURETAG_MATERIAL] = material
        tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
    child = obj.GetDown()
    while child:
        assign_material_recursive(child, material)
        child = child.GetNext()

# --------------------------------------------------
# Material Creation Function (Conditional Node Creation)
# --------------------------------------------------
def create_redshift_material(file_paths):
    """
    Creates a Redshift Standard Material and conditionally creates node chains for each texture channel.
    Only channels with a provided file path (checkbox enabled) are processed.
    """
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        return None

    # Create a Redshift Standard Material using the preset command.
    c4d.CallCommand(1040254, 1012)
    mat = doc.GetActiveMaterial()
    if not mat:
        return None
    material_name = file_paths.get("materialName", "New_Redshift_Material")
    mat.SetName(material_name)

    node_material = mat.GetNodeMaterialReference()
    if node_material is None:
        return None

    rs_node_space_id = maxon.Id("com.redshift3d.redshift4c4d.class.nodespace")
    graph = node_material.CreateDefaultGraph(rs_node_space_id)
    if graph is None or graph.IsNullValue():
        return None

    # Retrieve the Standard Material node.
    standard_material_node = None
    result = []
    maxon.GraphModelHelper.FindNodesByAssetId(
        graph, 
        maxon.Id("com.redshift3d.redshift4c4d.nodes.core.standardmaterial"), 
        True, 
        result
    )
    if result:
        standard_material_node = result[0]
    else:
        return None

    # Retrieve the Output node.
    output_node = None
    output_result = []
    maxon.GraphModelHelper.FindNodesByAssetId(
        graph,
        maxon.Id("com.redshift3d.redshift4c4d.node.output"),
        True,
        output_result
    )
    if output_result:
        output_node = output_result[0]
    else:
        return None

    # Node IDs for the different types of nodes.
    texture_sampler_id = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.texturesampler")
    color_correct_id   = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection")
    bump_map_id        = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.bumpmap")
    displacement_id    = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.displacement")
    ramp_id            = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rsramp")

    # Begin a single transaction for all modifications.
    with graph.BeginTransaction() as transaction:
        try:
            # --- BaseColor Chain ---
            if file_paths.get("BaseColor"):
                base_tex = graph.AddChild("", texture_sampler_id, maxon.DataDictionary())
                if not base_tex.IsNullValue():
                    tex0 = base_tex.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.tex0")
                    if tex0:
                        path_port = tex0.FindChild("path")
                        if path_port:
                            path_port.SetDefaultValue(maxon.Url(file_paths["BaseColor"]))
                    color_correct_node = graph.AddChild("", color_correct_id, maxon.DataDictionary())
                    if not color_correct_node.IsNullValue():
                        out_color = base_tex.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                        cc_input = color_correct_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.input")
                        if out_color and cc_input:
                            out_color.Connect(cc_input)
                        cc_output = color_correct_node.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.outcolor")
                        base_color_input = standard_material_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.standardmaterial.base_color")
                        if cc_output and base_color_input:
                            cc_output.Connect(base_color_input)
            # --- Roughness Chain ---
            if file_paths.get("Roughness"):
                rough_tex = graph.AddChild("", texture_sampler_id, maxon.DataDictionary())
                if not rough_tex.IsNullValue():
                    tex0 = rough_tex.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.tex0")
                    if tex0:
                        path_port = tex0.FindChild("path")
                        if path_port:
                            path_port.SetDefaultValue(maxon.Url(file_paths["Roughness"]))
                    ramp_node = graph.AddChild("", ramp_id, maxon.DataDictionary())
                    if not ramp_node.IsNullValue():
                        out_color = rough_tex.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                        ramp_input = ramp_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rsramp.input")
                        if out_color and ramp_input:
                            out_color.Connect(ramp_input)
                        ramp_output = ramp_node.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rsramp.outcolor")
                        refl_input = standard_material_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.standardmaterial.refl_roughness")
                        if ramp_output and refl_input:
                            ramp_output.Connect(refl_input)
            # --- Normal Chain ---
            if file_paths.get("Normal"):
                normal_tex = graph.AddChild("", texture_sampler_id, maxon.DataDictionary())
                if not normal_tex.IsNullValue():
                    tex0 = normal_tex.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.tex0")
                    if tex0:
                        colorspace = tex0.FindChild("colorspace")
                        if colorspace:
                            colorspace.SetDefaultValue("RS_INPUT_COLORSPACE_RAW")
                        path_port = tex0.FindChild("path")
                        if path_port:
                            path_port.SetDefaultValue(maxon.Url(file_paths["Normal"]))
                    bump_node = graph.AddChild("", bump_map_id, maxon.DataDictionary())
                    if not bump_node.IsNullValue():
                        input_map_type = bump_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.inputtype")
                        if input_map_type:
                            input_map_type.SetDefaultValue(maxon.Int32(1))
                        out_color = normal_tex.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                        bump_input = bump_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.input")
                        if out_color and bump_input:
                            out_color.Connect(bump_input)
                        bump_output = bump_node.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.out")
                        bump_std_input = standard_material_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.standardmaterial.bump_input")
                        if bump_output and bump_std_input:
                            bump_output.Connect(bump_std_input)
            # --- Displacement Chain ---
            if file_paths.get("Displacement"):
                disp_tex = graph.AddChild("", texture_sampler_id, maxon.DataDictionary())
                if not disp_tex.IsNullValue():
                    tex0 = disp_tex.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.tex0")
                    if tex0:
                        colorspace = tex0.FindChild("colorspace")
                        if colorspace:
                            colorspace.SetDefaultValue("RS_INPUT_COLORSPACE_RAW")
                        path_port = tex0.FindChild("path")
                        if path_port:
                            path_port.SetDefaultValue(maxon.Url(file_paths["Displacement"]))
                    disp_node = graph.AddChild("", displacement_id, maxon.DataDictionary())
                    if not disp_node.IsNullValue():
                        out_color = disp_tex.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                        disp_input = disp_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.displacement.texmap")
                        if out_color and disp_input:
                            out_color.Connect(disp_input)
                        disp_output = disp_node.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.displacement.out")
                        output_disp_input = output_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.node.output.displacement")
                        if disp_output and output_disp_input:
                            disp_output.Connect(output_disp_input)
            transaction.Commit()
        except Exception as e:
            transaction.Rollback()
            print(f"Error creating nodes: {e}")
    c4d.EventAdd()
    return mat

# --------------------------------------------------
# UI Dialog for File Selection & Texture Search
# --------------------------------------------------
class MyDialog(gui.GeDialog):
    MATERIAL_NAME_INPUT = 1005
    FOLDER_INPUT = 1002
    SELECT_FOLDER_BUTTON = 1003
    IMPORT_3D_MODEL_CHECKBOX = 4001  # Import 3D Model checkbox
    CREATE_MATERIAL_BUTTON = 1001

    # Only four textures (AO removed)
    CHECKBOX_IDS = {
        "BaseColor": 2001,
        "Roughness": 2003,
        "Normal": 2004,
        "Displacement": 2005
    }
    TEXTBOX_IDS = {
        "BaseColor": 3001,
        "Roughness": 3003,
        "Normal": 3004,
        "Displacement": 3005
    }

    def CreateLayout(self):
        self.SetTitle("Material Creator v001")
        self.GroupBegin(9000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(9001, c4d.BFH_LEFT, name="Material Name:")
        self.AddEditText(self.MATERIAL_NAME_INPUT, c4d.BFH_SCALEFIT, 250, 15)
        self.GroupEnd()
        self.GroupBegin(1000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddEditText(self.FOLDER_INPUT, c4d.BFH_SCALEFIT, 300, 15)
        self.AddButton(self.SELECT_FOLDER_BUTTON, c4d.BFH_RIGHT, 100, 15, "Select Folder")
        self.GroupEnd()
        texture_names = ["BaseColor", "Roughness", "Normal", "Displacement"]
        self.GroupBegin(5000, c4d.BFH_SCALEFIT, 1, len(texture_names) * 2)
        for name in texture_names:
            self.GroupBegin(6000 + self.CHECKBOX_IDS[name], c4d.BFH_SCALEFIT, 2, 1)
            self.AddCheckbox(self.CHECKBOX_IDS[name], c4d.BFH_LEFT, 20, 15, name)
            self.AddEditText(self.TEXTBOX_IDS[name], c4d.BFH_SCALEFIT, 300, 15)
            self.GroupEnd()
        self.GroupEnd()
        self.AddCheckbox(self.IMPORT_3D_MODEL_CHECKBOX, c4d.BFH_LEFT, 140, 15, "Import 3D Model")
        self.AddButton(self.CREATE_MATERIAL_BUTTON, c4d.BFH_CENTER, 120, 15, "Create Material")
        return True

    def InitValues(self):
        self.SetString(self.FOLDER_INPUT, "")
        self.SetString(self.MATERIAL_NAME_INPUT, "New_Redshift_Material")
        default_texts = {
            "BaseColor": "BaseColor",
            "Roughness": "Roughness",
            "Normal": "Normal",
            "Displacement": "Displacement"
        }
        for name, checkbox_id in self.CHECKBOX_IDS.items():
            is_checked = True  # All textures enabled by default.
            self.SetBool(checkbox_id, is_checked)
            self.SetString(self.TEXTBOX_IDS[name], default_texts[name])
            self.Enable(self.TEXTBOX_IDS[name], not is_checked)
        self.SetBool(self.IMPORT_3D_MODEL_CHECKBOX, False)
        self.result = None
        return True

    def Command(self, id, msg):
        if id == self.SELECT_FOLDER_BUTTON:
            folder_path = storage.LoadDialog(title="Select a Folder", flags=c4d.FILESELECT_DIRECTORY)
            if folder_path:
                self.SetString(self.FOLDER_INPUT, folder_path)
        for name, checkbox_id in self.CHECKBOX_IDS.items():
            if id == checkbox_id:
                is_checked = self.GetBool(checkbox_id)
                self.Enable(self.TEXTBOX_IDS[name], not is_checked)
        if id == self.CREATE_MATERIAL_BUTTON:
            selected_folder = self.GetString(self.FOLDER_INPUT).strip()
            if not selected_folder or not os.path.exists(selected_folder):
                gui.MessageDialog("Please select a valid folder.")
                return True
            found_files = {}
            for texture in ["BaseColor", "Roughness", "Normal", "Displacement"]:
                checkbox_id = self.CHECKBOX_IDS[texture]
                if self.GetBool(checkbox_id):
                    search_text = self.GetString(self.TEXTBOX_IDS[texture]).strip()
                    found_file = None
                    for file_name in os.listdir(selected_folder):
                        if search_text.lower() in file_name.lower():
                            found_file = os.path.join(selected_folder, file_name)
                            break
                    found_files[texture] = found_file
                else:
                    found_files[texture] = None
            found_files["materialName"] = self.GetString(self.MATERIAL_NAME_INPUT).strip()
            found_files["folder"] = self.GetString(self.FOLDER_INPUT).strip()
            found_files["importObject"] = self.GetBool(self.IMPORT_3D_MODEL_CHECKBOX)
            print("\n✅ Found File Paths:")
            for key, value in found_files.items():
                print(f"{key}: {value}")
            self.result = found_files
            self.Close()
        return True

def main():
    dlg = MyDialog()
    dlg.Open(dlgtype=c4d.DLG_TYPE_MODAL, defaultw=400, defaulth=300)
    file_paths = dlg.result
    if file_paths is None:
        return  # User closed the dialog without clicking Create Material
    doc = c4d.documents.GetActiveDocument()
    material = create_redshift_material(file_paths)
    if file_paths.get("importObject") and file_paths.get("folder"):
        folder = file_paths.get("folder")
        old_objects = []
        first_obj = doc.GetFirstObject()
        if first_obj:
            old_objects = get_all_objects(first_obj)
        object_files = []
        for fname in os.listdir(folder):
            if fname.lower().endswith(('.fbx', '.obj')):
                object_files.append(os.path.join(folder, fname))
        if object_files:
            for fpath in object_files:
                c4d.documents.MergeDocument(doc, fpath, c4d.SCENEFILTER_OBJECTS)
            c4d.EventAdd()
            new_objects = []
            first_obj = doc.GetFirstObject()
            if first_obj:
                new_objects = get_all_objects(first_obj)
            new_imported = [obj for obj in new_objects if obj not in old_objects]
            for obj in new_imported:
                assign_material_recursive(obj, material)
            c4d.EventAdd()

if __name__ == "__main__":
    main()
