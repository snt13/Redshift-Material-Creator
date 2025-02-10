"""
Material Creator v001
Developed by isintan kursun with the assistance of ChatGPT.
This script scans a selected folder for texture files for each channel 
(BaseColor, Roughness, Normal, Displacement) using case‐ and underscore‐insensitive matching.
For each enabled channel the script uses the custom search text (entered in the corresponding textbox)
to look for files whose names contain that keyword and then extracts an identifier from each file by taking
the portion of the filename (after removing underscores and lowercasing) that comes before the keyword.
After collecting matches for each channel, if a channel has only one match, its key is forced to a common value (""), 
so that if all channels have a single file, they are grouped into one complete texture set.
For every identifier (or the common identifier "") found in any of the enabled channels, a Redshift Standard Material is created 
(with the material name suffixed by the identifier if non‐empty). If a channel is enabled but no matching file is found,
that channel is simply omitted and the material is built without that texture.
If the "Import 3D Model" option is enabled, the script merges the 3D objects from the folder without assigning any material.
If you close the dialog without clicking "Create Material", no material is created.
"""

import c4d
import maxon
import os
import re
from c4d import gui, storage

# --------------------------------------------------
# Helper: Extract identifier from filename using a given keyword
# --------------------------------------------------
def extract_identifier(file_name, keyword):
    """
    Given a file name and a keyword (from the custom search text), remove the extension and underscores,
    convert to lowercase, and then find the keyword within it.
    If found, return the substring that comes before the keyword (this will be used as the identifier);
    otherwise return None.
    """
    base = os.path.splitext(file_name)[0]
    file_norm = base.replace("_", "").lower()
    keyword_norm = keyword.lower().replace("_", "")
    idx = file_norm.find(keyword_norm)
    if idx != -1:
        return file_norm[:idx].strip()  # Identifier is what comes before the keyword.
    return None

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

# (Material assignment to objects is not performed in this version.)

# --------------------------------------------------
# Material Creation Function (Conditional Node Creation)
# --------------------------------------------------
def create_redshift_material(file_paths):
    """
    Creates a Redshift Standard Material and conditionally creates node chains for each enabled channel.
    Expects file_paths with keys:
      "BaseColor", "Roughness", "Normal", "Displacement", "materialName", "folder", "importObject"
    Only channels with a provided file path (non-None) are processed.
    """
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        return None

    c4d.CallCommand(1040254, 1012)  # Redshift Material Presets
    mat = doc.GetActiveMaterial()
    if not mat:
        return None
    mat.SetName(file_paths.get("materialName", "New_Redshift_Material"))

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
    maxon.GraphModelHelper.FindNodesByAssetId(graph,
        maxon.Id("com.redshift3d.redshift4c4d.nodes.core.standardmaterial"),
        True, result)
    if result:
        standard_material_node = result[0]
    else:
        return None

    # Retrieve the Output node.
    output_node = None
    output_result = []
    maxon.GraphModelHelper.FindNodesByAssetId(graph,
        maxon.Id("com.redshift3d.redshift4c4d.node.output"),
        True, output_result)
    if output_result:
        output_node = output_result[0]
    else:
        return None

    # Define node IDs.
    texture_sampler_id = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.texturesampler")
    color_correct_id   = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection")
    bump_map_id        = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.bumpmap")
    displacement_id    = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.displacement")
    ramp_id            = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rsramp")

    with graph.BeginTransaction() as transaction:
        try:
            channels = ["BaseColor", "Roughness", "Normal", "Displacement"]
            texture_nodes = {}
            for ch in channels:
                if file_paths.get(ch):
                    tex_node = graph.AddChild("", texture_sampler_id, maxon.DataDictionary())
                    if not tex_node.IsNullValue():
                        texture_nodes[ch] = tex_node
                        tex0_input = tex_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.tex0")
                        if tex0_input:
                            if ch in ["Normal", "Displacement"]:
                                colorspace_port = tex0_input.FindChild("colorspace")
                                if colorspace_port:
                                    colorspace_port.SetDefaultValue("RS_INPUT_COLORSPACE_RAW")
                            path_port = tex0_input.FindChild("path")
                            if path_port:
                                path_port.SetDefaultValue(maxon.Url(file_paths[ch]))
                    else:
                        texture_nodes[ch] = None
                else:
                    texture_nodes[ch] = None

            # Create additional nodes only for channels that have a texture.
            if texture_nodes.get("BaseColor"):
                cc_node = graph.AddChild("", color_correct_id, maxon.DataDictionary())
                if cc_node and not cc_node.IsNullValue():
                    out_color = texture_nodes["BaseColor"].GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                    cc_input = cc_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.input")
                    if out_color and cc_input:
                        out_color.Connect(cc_input)
                    cc_output = cc_node.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.outcolor")
                    base_color_input = standard_material_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.standardmaterial.base_color")
                    if cc_output and base_color_input:
                        cc_output.Connect(base_color_input)
            if texture_nodes.get("Roughness"):
                ramp_node_inst = graph.AddChild("", ramp_id, maxon.DataDictionary())
                if ramp_node_inst and not ramp_node_inst.IsNullValue():
                    out_color = texture_nodes["Roughness"].GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                    ramp_input = ramp_node_inst.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rsramp.input")
                    if out_color and ramp_input:
                        out_color.Connect(ramp_input)
                    ramp_output = ramp_node_inst.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rsramp.outcolor")
                    refl_input = standard_material_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.standardmaterial.refl_roughness")
                    if ramp_output and refl_input:
                        ramp_output.Connect(refl_input)
            if texture_nodes.get("Normal"):
                bump_node = graph.AddChild("", bump_map_id, maxon.DataDictionary())
                if bump_node and not bump_node.IsNullValue():
                    input_map_type = bump_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.inputtype")
                    if input_map_type:
                        input_map_type.SetDefaultValue(maxon.Int32(1))
                    out_color = texture_nodes["Normal"].GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                    bump_input = bump_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.input")
                    if out_color and bump_input:
                        out_color.Connect(bump_input)
                    bump_output = bump_node.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.out")
                    bump_std_input = standard_material_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.standardmaterial.bump_input")
                    if bump_output and bump_std_input:
                        bump_output.Connect(bump_std_input)
            if texture_nodes.get("Displacement"):
                disp_node = graph.AddChild("", displacement_id, maxon.DataDictionary())
                if disp_node and not disp_node.IsNullValue():
                    out_color = texture_nodes["Displacement"].GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
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
        channels = ["BaseColor", "Roughness", "Normal", "Displacement"]
        self.GroupBegin(5000, c4d.BFH_SCALEFIT, 1, len(channels) * 2)
        for ch in channels:
            self.GroupBegin(6000 + self.CHECKBOX_IDS[ch], c4d.BFH_SCALEFIT, 2, 1)
            self.AddCheckbox(self.CHECKBOX_IDS[ch], c4d.BFH_LEFT, 20, 15, ch)
            self.AddEditText(self.TEXTBOX_IDS[ch], c4d.BFH_SCALEFIT, 300, 15)
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
        for ch, checkbox_id in self.CHECKBOX_IDS.items():
            is_checked = True
            self.SetBool(checkbox_id, is_checked)
            self.SetString(self.TEXTBOX_IDS[ch], default_texts[ch])
            self.Enable(self.TEXTBOX_IDS[ch], not is_checked)
        self.SetBool(self.IMPORT_3D_MODEL_CHECKBOX, False)
        self.result = None
        return True

    def Command(self, id, msg):
        if id == self.SELECT_FOLDER_BUTTON:
            folder_path = storage.LoadDialog(title="Select a Folder", flags=c4d.FILESELECT_DIRECTORY)
            if folder_path:
                self.SetString(self.FOLDER_INPUT, folder_path)
        for ch, checkbox_id in self.CHECKBOX_IDS.items():
            if id == checkbox_id:
                is_checked = self.GetBool(checkbox_id)
                self.Enable(self.TEXTBOX_IDS[ch], not is_checked)
        if id == self.CREATE_MATERIAL_BUTTON:
            selected_folder = self.GetString(self.FOLDER_INPUT).strip()
            if not selected_folder or not os.path.exists(selected_folder):
                gui.MessageDialog("Please select a valid folder.")
                return True

            channels = ["BaseColor", "Roughness", "Normal", "Displacement"]
            channel_files = { ch: {} for ch in channels }
            for file_name in os.listdir(selected_folder):
                for ch in channels:
                    if self.GetBool(self.CHECKBOX_IDS[ch]):
                        # Use the custom text entered in the textbox as the search keyword.
                        custom_keyword = self.GetString(self.TEXTBOX_IDS[ch]).strip()
                        keyword = custom_keyword.lower().replace("_", "")
                        file_name_clean = file_name.lower().replace("_", "")
                        if keyword in file_name_clean:
                            ident = extract_identifier(file_name, custom_keyword)
                            if ident is None:
                                # If no identifier could be extracted, use an empty string.
                                ident = ""
                            channel_files[ch][ident] = os.path.join(selected_folder, file_name)
            # If a channel has only one match, force its identifier to "" so it groups with others.
            for ch in channels:
                if len(channel_files[ch]) == 1:
                    if channel_files[ch]:
                        value = next(iter(channel_files[ch].values()))
                        channel_files[ch] = {"": value}
            # Grouping: use the union of identifiers across enabled channels.
            grouping_channels = [ch for ch in channels if self.GetBool(self.CHECKBOX_IDS[ch]) and len(channel_files[ch]) > 0]
            all_ids = set()
            for ch in grouping_channels:
                all_ids = all_ids.union(set(channel_files[ch].keys()))
            common_ids = all_ids
            if not common_ids:
                gui.MessageDialog("No texture files found for the enabled channels.")
                return True

            materialSets = {}
            base_material_name = self.GetString(self.MATERIAL_NAME_INPUT).strip()
            for ident in common_ids:
                ms = {}
                for ch in channels:
                    if self.GetBool(self.CHECKBOX_IDS[ch]):
                        ms[ch] = channel_files[ch].get(ident, None)
                    else:
                        ms[ch] = None
                if ident:
                    ms["materialName"] = base_material_name + "_" + ident
                else:
                    ms["materialName"] = base_material_name
                materialSets[ident] = ms

            found_files = {}
            found_files["materialSets"] = materialSets
            found_files["folder"] = selected_folder
            found_files["importObject"] = self.GetBool(self.IMPORT_3D_MODEL_CHECKBOX)

            print("\n✅ Found Material Sets:")
            for ident, ms in materialSets.items():
                print(f"Identifier '{ident}':")
                for ch in channels:
                    print(f"  {ch}: {ms.get(ch)}")
                print(f"  Material Name: {ms.get('materialName')}")
            self.result = found_files
            self.Close()
        return True

# --------------------------------------------------
# Main Entry Point
# --------------------------------------------------
def main():
    dlg = MyDialog()
    dlg.Open(dlgtype=c4d.DLG_TYPE_MODAL, defaultw=400, defaulth=300)
    file_paths = dlg.result
    if file_paths is None:
        return  # User closed the dialog without clicking Create Material
    doc = c4d.documents.GetActiveDocument()

    materialSets = file_paths.get("materialSets", {})
    created_materials = {}
    for ident, ms in materialSets.items():
        mat = create_redshift_material(ms)
        if mat:
            created_materials[ident] = mat

    if file_paths.get("importObject") and file_paths.get("folder"):
        folder = file_paths["folder"]
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
        c4d.EventAdd()

if __name__ == "__main__":
    main()
