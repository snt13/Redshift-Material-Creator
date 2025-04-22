import c4d
import maxon
import os
import re
import shutil
from c4d import gui, storage

# --------------------------------------------------
# Helper: Extract identifier from filename using a given keyword
# --------------------------------------------------
def extract_identifier(file_name, keyword):
    base = os.path.splitext(file_name)[0]
    cleaned = base.replace("_", "").lower()
    keyword_clean = keyword.lower().replace("_", "")
    pattern = re.compile(r'^(.*)' + re.escape(keyword_clean) + r'(.*)$')
    match = pattern.match(cleaned)
    if match:
        before = match.group(1).strip()
        after = match.group(2).strip()
        return after if after else before
    return None

# --------------------------------------------------
# Helper: Recursively gather all objects under a root
# --------------------------------------------------
def get_all_objects(obj):
    result = []
    while obj:
        result.append(obj)
        result += get_all_objects(obj.GetDown())
        obj = obj.GetNext()
    return result

# --------------------------------------------------
# Material Creation Function (with Game Asset ColorSplitters)
# --------------------------------------------------
def create_redshift_material(file_paths):
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        return None

    c4d.CallCommand(1040254, 1012)  # Redshift Material Presets
    mat = doc.GetActiveMaterial()
    if not mat:
        return None
    mat.SetName(file_paths.get("materialName", "RS Material"))

    node_material = mat.GetNodeMaterialReference()
    if node_material is None:
        return None

    graph = node_material.CreateDefaultGraph(
        maxon.Id("com.redshift3d.redshift4c4d.class.nodespace")
    )
    if graph is None or graph.IsNullValue():
        return None

    # Find StandardMaterial and Output nodes
    std_nodes = []
    maxon.GraphModelHelper.FindNodesByAssetId(
        graph,
        maxon.Id("com.redshift3d.redshift4c4d.nodes.core.standardmaterial"),
        True, std_nodes
    )
    if not std_nodes:
        return None
    std_node = std_nodes[0]

    output_nodes = []
    maxon.GraphModelHelper.FindNodesByAssetId(
        graph,
        maxon.Id("com.redshift3d.redshift4c4d.node.output"),
        True, output_nodes
    )
    if not output_nodes:
        return None
    output_node = output_nodes[0]

    # Node IDs
    texture_sampler_id = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.texturesampler")
    color_correct_id   = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection")
    bump_map_id        = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.bumpmap")
    displacement_id    = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.displacement")
    ramp_id            = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rsramp")
    split_id           = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rscolorsplitter")

    channels    = ["BaseColor", "Roughness", "Normal", "Displacement", "Opacity", "Metalness"]
    game_asset  = file_paths.get("gameAsset", False)
    texture_nodes = {}

    with graph.BeginTransaction() as tr:
        try:
            # 1) Create TextureSampler nodes
            for ch in channels:
                path = file_paths.get(ch)
                if path:
                    tn = graph.AddChild("", texture_sampler_id, maxon.DataDictionary())
                    texture_nodes[ch] = tn
                    inp = tn.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.tex0"
                    )
                    if inp:
                        if ch in ("Normal", "Displacement"):
                            cs = inp.FindChild("colorspace")
                            cs and cs.SetDefaultValue("RS_INPUT_COLORSPACE_RAW")
                        p = inp.FindChild("path")
                        p and p.SetDefaultValue(maxon.Url(path))
                else:
                    texture_nodes[ch] = None

            # 2) BaseColor → ColorCorrection → (AO?) → standard.base_color
            if texture_nodes["BaseColor"]:
                cc = graph.AddChild("", color_correct_id, maxon.DataDictionary())
                outc = texture_nodes["BaseColor"].GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                )
                inc = cc.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.input"
                )
                outc and inc and outc.Connect(inc)
                outcc = cc.GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.outcolor"
                )
                base_in = std_node.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.base_color"
                )
                if file_paths.get("ao") and outcc and base_in:
                    ao = graph.AddChild(
                        "", maxon.Id("com.redshift3d.redshift4c4d.nodes.core.ambientocclusion"),
                        maxon.DataDictionary()
                    )
                    ao_in = ao.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.ambientocclusion.bright"
                    )
                    ao_out = ao.GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.ambientocclusion.out"
                    )
                    outcc.Connect(ao_in)
                    ao_out.Connect(base_in)
                elif outcc and base_in:
                    outcc.Connect(base_in)

            # 3) Roughness → [Splitter?] → Ramp → standard.refl_roughness
            if texture_nodes["Roughness"]:
                if game_asset:
                    sp_r = graph.AddChild("", split_id, maxon.DataDictionary())
                    rout = texture_nodes["Roughness"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                    )
                    rin = sp_r.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rscolorsplitter.input"
                    )
                    rout and rin and rout.Connect(rin)
                    rout_out = sp_r.GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rscolorsplitter.outr"
                    )
                    ramp = graph.AddChild("", ramp_id, maxon.DataDictionary())
                    ramp_in = ramp.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rsramp.input"
                    )
                    rout_out and ramp_in and rout_out.Connect(ramp_in)
                    ramp_out = ramp.GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rsramp.outcolor"
                    )
                    rough_in = std_node.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.refl_roughness"
                    )
                    ramp_out and rough_in and ramp_out.Connect(rough_in)
                else:
                    ramp = graph.AddChild("", ramp_id, maxon.DataDictionary())
                    rout = texture_nodes["Roughness"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                    )
                    ramp_in = ramp.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rsramp.input"
                    )
                    rout and ramp_in and rout.Connect(ramp_in)
                    ramp_out = ramp.GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rsramp.outcolor"
                    )
                    rough_in = std_node.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.refl_roughness"
                    )
                    ramp_out and rough_in and ramp_out.Connect(rough_in)

            # 4) Normal → Bump → standard.bump_input
            if texture_nodes["Normal"]:
                bm = graph.AddChild("", bump_map_id, maxon.DataDictionary())
                bm.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.bumpmap.inputtype"
                ).SetDefaultValue(maxon.Int32(1))
                n_out = texture_nodes["Normal"].GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                )
                n_inp = bm.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.bumpmap.input"
                )
                n_out and n_inp and n_out.Connect(n_inp)
                n_out2 = bm.GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.bumpmap.out"
                )
                bump_std = std_node.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.bump_input"
                )
                n_out2 and bump_std and n_out2.Connect(bump_std)

            # 5) Displacement → output.displacement
            if texture_nodes["Displacement"]:
                dp = graph.AddChild("", displacement_id, maxon.DataDictionary())
                d_out = texture_nodes["Displacement"].GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                )
                d_inp = dp.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.displacement.texmap"
                )
                d_out and d_inp and d_out.Connect(d_inp)
                d_out2 = dp.GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.displacement.out"
                )
                od = output_node.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.node.output.displacement"
                )
                d_out2 and od and d_out2.Connect(od)

            # 6) Opacity → [Splitter?] → standard.opacity_color
            if texture_nodes["Opacity"]:
                if game_asset:
                    sp_o = graph.AddChild("", split_id, maxon.DataDictionary())
                    o_out = texture_nodes["Opacity"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                    )
                    o_inp = sp_o.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rscolorsplitter.input"
                    )
                    o_out and o_inp and o_out.Connect(o_inp)
                    o_r = sp_o.GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rscolorsplitter.outr"
                    )
                    std_o = std_node.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.opacity_color"
                    )
                    o_r and std_o and o_r.Connect(std_o)
                else:
                    o_out = texture_nodes["Opacity"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                    )
                    std_o = std_node.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.opacity_color"
                    )
                    o_out and std_o and o_out.Connect(std_o)

            # 7) Metalness → standard.metalness
            if texture_nodes["Metalness"]:
                m_out = texture_nodes["Metalness"].GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor"
                )
                m_inp = std_node.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.metalness"
                )
                m_out and m_inp and m_out.Connect(m_inp)

            tr.Commit()
        except Exception as e:
            tr.Rollback()
            print(f"Error creating nodes: {e}")

    c4d.EventAdd()
    return mat

# --------------------------------------------------
# UI Dialog for File Selection & Texture Search
# --------------------------------------------------
class MyDialog(gui.GeDialog):
    MATERIAL_NAME_INPUT       = 1005
    FOLDER_INPUT              = 1002
    SELECT_FOLDER_BUTTON      = 1003
    IMPORT_3D_MODEL_CHECKBOX  = 4001
    AO_CHECKBOX               = 4002
    COPY_TEXTURES_CHECKBOX    = 4003
    GAME_ASSET_CHECKBOX       = 4004
    CREATE_MATERIAL_BUTTON    = 1001
    PREVIEW_MATERIAL_BUTTON   = 1006

    CHECKBOX_IDS = {
        "BaseColor":    2001,
        "Metalness":    2007,
        "Roughness":    2003,
        "Opacity":      2006,
        "Normal":       2004,
        "Displacement": 2005
    }
    TEXTBOX_IDS = {
        "BaseColor":    3001,
        "Metalness":    3007,
        "Roughness":    3003,
        "Opacity":      3006,
        "Normal":       3004,
        "Displacement": 3005
    }

    def CreateLayout(self):
        self.SetTitle("Redshift Material Creator")

        # Material Name Row
        self.GroupBegin(9000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(9001, c4d.BFH_LEFT, name="Material Name:")
        self.AddEditText(self.MATERIAL_NAME_INPUT, c4d.BFH_SCALEFIT, 250, 15)
        self.GroupEnd()

        # Folder Selection Row
        self.GroupBegin(1000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddEditText(self.FOLDER_INPUT, c4d.BFH_SCALEFIT, 300, 15)
        self.AddButton(self.SELECT_FOLDER_BUTTON, c4d.BFH_RIGHT, 100, 15, "Select Folder")
        self.GroupEnd()

        # Texture Channels
        channels = list(self.CHECKBOX_IDS.keys())
        self.GroupBegin(5000, c4d.BFH_SCALEFIT, 1, len(channels)*2)
        for ch in channels:
            cb = self.CHECKBOX_IDS[ch]
            tb = self.TEXTBOX_IDS[ch]
            self.GroupBegin(6000+cb, c4d.BFH_SCALEFIT, 2, 1)
            self.AddCheckbox(cb, c4d.BFH_LEFT, 20, 15, ch)
            self.AddEditText(tb, c4d.BFH_SCALEFIT, 300, 15)
            self.GroupEnd()
        self.GroupEnd()

        # Additional Options
        self.GroupBegin(8000, c4d.BFH_LEFT, 4, 1)
        self.AddCheckbox(self.IMPORT_3D_MODEL_CHECKBOX, c4d.BFH_LEFT, 170, 15, "Import 3D Model")
        self.AddCheckbox(self.AO_CHECKBOX,              c4d.BFH_LEFT,  55, 15, "AO")
        self.AddCheckbox(self.COPY_TEXTURES_CHECKBOX,   c4d.BFH_LEFT, 150, 15, "Copy Textures")
        self.AddCheckbox(self.GAME_ASSET_CHECKBOX,      c4d.BFH_LEFT, 100, 15, "Game Asset")
        self.GroupEnd()

        # Material Buttons Row
        self.GroupBegin(9001, c4d.BFH_CENTER, 2, 1)
        self.AddButton(self.CREATE_MATERIAL_BUTTON,  c4d.BFH_CENTER, 120, 15, "Create Material")
        self.AddButton(self.PREVIEW_MATERIAL_BUTTON, c4d.BFH_CENTER, 120, 15, "Preview Materials")
        self.GroupEnd()

        return True

    def InitValues(self):
        self.SetString(self.FOLDER_INPUT, "")
        self.SetString(self.MATERIAL_NAME_INPUT, "RS Material")

        default_texts = {
            "BaseColor":    "BaseColor, Albedo",
            "Roughness":    "Roughness, Rough",
            "Normal":       "Normal, Nrm",
            "Displacement": "Displacement, Height",
            "Opacity":      "Opacity, Alpha",
            "Metalness":    "Metalness, Mtl"
        }

        for ch, cb in self.CHECKBOX_IDS.items():
            # Opacity and Metalness default to unchecked
            default_state = False if ch in ("Opacity", "Metalness") else True
            self.SetBool(cb, default_state)
            self.SetString(self.TEXTBOX_IDS[ch], default_texts[ch])
            self.Enable(self.TEXTBOX_IDS[ch], True)

        self.SetBool(self.IMPORT_3D_MODEL_CHECKBOX, False)
        self.SetBool(self.AO_CHECKBOX,              False)
        self.SetBool(self.COPY_TEXTURES_CHECKBOX,   False)
        self.SetBool(self.GAME_ASSET_CHECKBOX,      False)

        self.result = None
        return True

    def Command(self, id, msg):
        if id == self.SELECT_FOLDER_BUTTON:
            folder = storage.LoadDialog(title="Select a Folder", flags=c4d.FILESELECT_DIRECTORY)
            if folder:
                self.SetString(self.FOLDER_INPUT, folder)

        if id == self.PREVIEW_MATERIAL_BUTTON:
            folder = self.GetString(self.FOLDER_INPUT).strip()
            if not folder or not os.path.exists(folder):
                gui.MessageDialog("Please select a valid folder.")
                return True

            channels = list(self.CHECKBOX_IDS.keys())
            channel_files = {ch: {} for ch in channels}
            for fn in os.listdir(folder):
                low = fn.lower().replace("_", "")
                for ch in channels:
                    if self.GetBool(self.CHECKBOX_IDS[ch]):
                        kws = [k.strip() for k in self.GetString(self.TEXTBOX_IDS[ch]).split(',')]
                        for kw in kws:
                            if kw.lower().replace("_", "") in low:
                                ident = extract_identifier(fn, kw) or ""
                                channel_files[ch][ident] = os.path.join(folder, fn)
                                break

            for ch in channels:
                if len(channel_files[ch]) == 1:
                    val = next(iter(channel_files[ch].values()))
                    channel_files[ch] = {"": val}

            ids = set().union(*[set(channel_files[ch].keys()) for ch in channels])
            if not ids:
                gui.MessageDialog("No texture files found.")
                return True

            preview = ""
            base = self.GetString(self.MATERIAL_NAME_INPUT).strip()
            for ident in ids:
                name = f"{base}_{ident}" if ident else base
                preview += f"Material: {name}\n"
                for ch in channels:
                    if channel_files[ch].get(ident):
                        preview += f"  {ch}: {os.path.basename(channel_files[ch][ident])}\n"
                preview += "\n"

            gui.MessageDialog(preview)

        if id == self.CREATE_MATERIAL_BUTTON:
            folder = self.GetString(self.FOLDER_INPUT).strip()
            if not folder or not os.path.exists(folder):
                gui.MessageDialog("Please select a valid folder.")
                return True

            channels = list(self.CHECKBOX_IDS.keys())
            channel_files = {ch: {} for ch in channels}
            for fn in os.listdir(folder):
                low = fn.lower().replace("_", "")
                for ch in channels:
                    if self.GetBool(self.CHECKBOX_IDS[ch]):
                        kws = [k.strip() for k in self.GetString(self.TEXTBOX_IDS[ch]).split(',')]
                        for kw in kws:
                            if kw.lower().replace("_", "") in low:
                                ident = extract_identifier(fn, kw) or ""
                                channel_files[ch][ident] = os.path.join(folder, fn)
                                break

            for ch in channels:
                if len(channel_files[ch]) == 1:
                    val = next(iter(channel_files[ch].values()))
                    channel_files[ch] = {"": val}

            ids = set().union(*[set(channel_files[ch].keys()) for ch in channels])
            if not ids:
                gui.MessageDialog("No texture files found.")
                return True

            materialSets = {}
            base = self.GetString(self.MATERIAL_NAME_INPUT).strip()
            for ident in ids:
                ms = {ch: channel_files[ch].get(ident) if self.GetBool(self.CHECKBOX_IDS[ch]) else None
                      for ch in channels}
                ms["materialName"] = f"{base}_{ident}" if ident else base
                ms["ao"]           = self.GetBool(self.AO_CHECKBOX)
                ms["gameAsset"]    = self.GetBool(self.GAME_ASSET_CHECKBOX)
                materialSets[ident] = ms

            self.result = {
                "materialSets": materialSets,
                "folder":       folder,
                "importObject": self.GetBool(self.IMPORT_3D_MODEL_CHECKBOX),
                "copyTextures": self.GetBool(self.COPY_TEXTURES_CHECKBOX),
                "gameAsset":    self.GetBool(self.GAME_ASSET_CHECKBOX),
            }
            self.Close()

        return True

# --------------------------------------------------
# Main Entry Point
# --------------------------------------------------
def main():
    dlg = MyDialog()
    dlg.Open(dlgtype=c4d.DLG_TYPE_MODAL, defaultw=400, defaulth=300)
    file_paths = dlg.result
    if not file_paths:
        return

    doc = c4d.documents.GetActiveDocument()

    # Copy textures if requested
    if file_paths.get("copyTextures"):
        project_folder = doc.GetDocumentPath() or file_paths.get("folder")
        tex_folder = os.path.join(project_folder, "tex")
        if not os.path.exists(tex_folder):
            os.makedirs(tex_folder)
        for ident, ms in file_paths["materialSets"].items():
            for ch in ["BaseColor", "Roughness", "Normal", "Displacement", "Opacity", "Metalness"]:
                path = ms.get(ch)
                if path:
                    dst = os.path.join(tex_folder, os.path.basename(path))
                    try:
                        shutil.copy2(path, dst)
                        ms[ch] = dst
                    except Exception as e:
                        print("Error copying file:", e)

    # Create materials
    created_materials = {}
    for ident, ms in file_paths["materialSets"].items():
        ms["gameAsset"] = file_paths.get("gameAsset", False)
        mat = create_redshift_material(ms)
        if mat:
            created_materials[ident] = mat

    # Import models and assign materials
    if file_paths.get("importObject"):
        folder = file_paths["folder"]
        old_objs = get_all_objects(doc.GetFirstObject()) if doc.GetFirstObject() else []
        for fn in os.listdir(folder):
            if fn.lower().endswith(('.fbx', '.obj')):
                c4d.documents.MergeDocument(
                    doc, os.path.join(folder, fn), c4d.SCENEFILTER_OBJECTS
                )

        new_objs = get_all_objects(doc.GetFirstObject()) if doc.GetFirstObject() else []
        added = [o for o in new_objs if o not in old_objs]
        for obj in added:
            for mat in created_materials.values():
                tag = c4d.BaseTag(c4d.Ttexture)
                tag[c4d.TEXTURETAG_MATERIAL] = mat
                obj.InsertTag(tag)
        c4d.EventAdd()

if __name__ == "__main__":
    main()
