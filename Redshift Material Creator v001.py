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
# Helper functions for object processing
# --------------------------------------------------
def get_all_objects(obj):
    result = []
    while obj:
        result.append(obj)
        result += get_all_objects(obj.GetDown())
        obj = obj.GetNext()
    return result

# --------------------------------------------------
# Material Creation Function (Conditional Node Creation)
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

    rs_node_space_id = maxon.Id("com.redshift3d.redshift4c4d.class.nodespace")
    graph = node_material.CreateDefaultGraph(rs_node_space_id)
    if graph is None or graph.IsNullValue():
        return None

    # Find Standard Material and Output nodes
    standard_material_node = None
    result = []
    maxon.GraphModelHelper.FindNodesByAssetId(
        graph,
        maxon.Id("com.redshift3d.redshift4c4d.nodes.core.standardmaterial"),
        True, result
    )
    if result:
        standard_material_node = result[0]
    else:
        return None

    output_node = None
    output_result = []
    maxon.GraphModelHelper.FindNodesByAssetId(
        graph,
        maxon.Id("com.redshift3d.redshift4c4d.node.output"),
        True, output_result
    )
    if output_result:
        output_node = output_result[0]
    else:
        return None

    # Node IDs
    texture_sampler_id = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.texturesampler")
    color_correct_id   = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection")
    bump_map_id        = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.bumpmap")
    displacement_id    = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.displacement")
    ramp_id            = maxon.Id("com.redshift3d.redshift4c4d.nodes.core.rsramp")

    with graph.BeginTransaction() as transaction:
        try:
            channels = ["BaseColor", "Roughness", "Normal", "Displacement", "Opacity"]
            texture_nodes = {}
            # create texture samplers for all enabled channels
            for ch in channels:
                if file_paths.get(ch):
                    tex = graph.AddChild("", texture_sampler_id, maxon.DataDictionary())
                    if not tex.IsNullValue():
                        texture_nodes[ch] = tex
                        inp = tex.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.texturesampler.tex0")
                        if inp:
                            # RAW colorspace for Normal/Displacement
                            if ch in ["Normal", "Displacement"]:
                                cs = inp.FindChild("colorspace")
                                if cs:
                                    cs.SetDefaultValue("RS_INPUT_COLORSPACE_RAW")
                            path = inp.FindChild("path")
                            if path:
                                path.SetDefaultValue(maxon.Url(file_paths[ch]))
                    else:
                        texture_nodes[ch] = None
                else:
                    texture_nodes[ch] = None

            # BaseColor → ColorCorrection → (AO?) → Standard.base_color
            if texture_nodes.get("BaseColor"):
                cc = graph.AddChild("", color_correct_id, maxon.DataDictionary())
                if not cc.IsNullValue():
                    outc = texture_nodes["BaseColor"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                    inc = cc.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.input")
                    if outc and inc:
                        outc.Connect(inc)
                    outcc = cc.GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.rscolorcorrection.outcolor")
                    base_in = standard_material_node.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.base_color")
                    if outcc and base_in:
                        if file_paths.get("ao"):
                            ao = graph.AddChild("", maxon.Id("com.redshift3d.redshift4c4d.nodes.core.ambientocclusion"), maxon.DataDictionary())
                            if not ao.IsNullValue():
                                br = ao.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.ambientocclusion.bright")
                                if br:
                                    outcc.Connect(br)
                                ao_out = ao.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.ambientocclusion.out")
                                if ao_out:
                                    ao_out.Connect(base_in)
                        else:
                            outcc.Connect(base_in)

            # Roughness → Ramp → Standard.refl_roughness
            if texture_nodes.get("Roughness"):
                rp = graph.AddChild("", ramp_id, maxon.DataDictionary())
                if not rp.IsNullValue():
                    outc = texture_nodes["Roughness"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                    inp = rp.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rsramp.input")
                    if outc and inp:
                        outc.Connect(inp)
                    outp = rp.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.rsramp.outcolor")
                    rin = standard_material_node.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.refl_roughness")
                    if outp and rin:
                        outp.Connect(rin)

            # Normal → Bump → Standard.bump_input
            if texture_nodes.get("Normal"):
                bm = graph.AddChild("", bump_map_id, maxon.DataDictionary())
                if not bm.IsNullValue():
                    imt = bm.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.inputtype")
                    if imt:
                        imt.SetDefaultValue(maxon.Int32(1))
                    outc = texture_nodes["Normal"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                    inp = bm.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.input")
                    if outc and inp:
                        outc.Connect(inp)
                    outb = bm.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.bumpmap.out")
                    bin = standard_material_node.GetInputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.bump_input")
                    if outb and bin:
                        outb.Connect(bin)

            # Displacement → Output.displacement
            if texture_nodes.get("Displacement"):
                dp = graph.AddChild("", displacement_id, maxon.DataDictionary())
                if not dp.IsNullValue():
                    outc = texture_nodes["Displacement"].GetOutputs().FindChild(
                        "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                    inp = dp.GetInputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.displacement.texmap")
                    if outc and inp:
                        outc.Connect(inp)
                    outd = dp.GetOutputs().FindChild("com.redshift3d.redshift4c4d.nodes.core.displacement.out")
                    od = output_node.GetInputs().FindChild("com.redshift3d.redshift4c4d.node.output.displacement")
                    if outd and od:
                        outd.Connect(od)

            # Opacity → Standard.opacity_color
            if texture_nodes.get("Opacity"):
                outc = texture_nodes["Opacity"].GetOutputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.texturesampler.outcolor")
                op = standard_material_node.GetInputs().FindChild(
                    "com.redshift3d.redshift4c4d.nodes.core.standardmaterial.opacity_color")
                if outc and op:
                    outc.Connect(op)

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
    MATERIAL_NAME_INPUT    = 1005
    FOLDER_INPUT           = 1002
    SELECT_FOLDER_BUTTON   = 1003
    IMPORT_3D_MODEL_CHECKBOX = 4001
    AO_CHECKBOX            = 4002
    COPY_TEXTURES_CHECKBOX = 4003
    CREATE_MATERIAL_BUTTON = 1001
    PREVIEW_MATERIAL_BUTTON = 1006

    CHECKBOX_IDS = {
        "BaseColor":   2001,
        "Roughness":   2003,
        "Normal":      2004,
        "Displacement":2005,
        "Opacity":     2006
    }
    TEXTBOX_IDS = {
        "BaseColor":   3001,
        "Roughness":   3003,
        "Normal":      3004,
        "Displacement":3005,
        "Opacity":     3006
    }

    def CreateLayout(self):
        self.SetTitle("Redshift Material Creator")

        # Material Name
        self.GroupBegin(9000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(9001, c4d.BFH_LEFT, name="Material Name:")
        self.AddEditText(self.MATERIAL_NAME_INPUT, c4d.BFH_SCALEFIT, 250, 15)
        self.GroupEnd()

        # Folder Picker
        self.GroupBegin(1000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddEditText(self.FOLDER_INPUT, c4d.BFH_SCALEFIT, 300, 15)
        self.AddButton(self.SELECT_FOLDER_BUTTON, c4d.BFH_RIGHT, 100, 15, "Select Folder")
        self.GroupEnd()

        # Texture Channels
        channels = ["BaseColor", "Roughness", "Normal", "Displacement", "Opacity"]
        self.GroupBegin(5000, c4d.BFH_SCALEFIT, 1, len(channels)*2)
        for ch in channels:
            self.GroupBegin(6000 + self.CHECKBOX_IDS[ch], c4d.BFH_SCALEFIT, 2, 1)
            self.AddCheckbox(self.CHECKBOX_IDS[ch], c4d.BFH_LEFT, 20, 15, ch)
            self.AddEditText(self.TEXTBOX_IDS[ch], c4d.BFH_SCALEFIT, 300, 15)
            self.GroupEnd()
        self.GroupEnd()

        # Extra Options
        self.GroupBegin(8000, c4d.BFH_LEFT, 3, 1)
        self.AddCheckbox(self.IMPORT_3D_MODEL_CHECKBOX, c4d.BFH_LEFT, 165, 15, "Import 3D Model")
        self.AddCheckbox(self.AO_CHECKBOX, c4d.BFH_LEFT, 55, 15, "AO")
        self.AddCheckbox(self.COPY_TEXTURES_CHECKBOX, c4d.BFH_LEFT, 100, 15, "Copy Textures")
        self.GroupEnd()

        # Buttons
        self.GroupBegin(9001, c4d.BFH_CENTER, 2, 1)
        self.AddButton(self.CREATE_MATERIAL_BUTTON, c4d.BFH_CENTER, 120, 15, "Create Material")
        self.AddButton(self.PREVIEW_MATERIAL_BUTTON, c4d.BFH_CENTER, 120, 15, "Preview Materials")
        self.GroupEnd()
        return True

    def InitValues(self):
        self.SetString(self.FOLDER_INPUT, "")
        self.SetString(self.MATERIAL_NAME_INPUT, "RS Material")
        default_texts = {
            "BaseColor":   "BaseColor, Albedo",
            "Roughness":   "Roughness, Rough",
            "Normal":      "Normal, Nrm",
            "Displacement":"Displacement, Height",
            "Opacity":     "Opacity, Alpha"
        }
        for ch, cb in self.CHECKBOX_IDS.items():
            self.SetBool(cb, True)
            self.SetString(self.TEXTBOX_IDS[ch], default_texts[ch])
            self.Enable(self.TEXTBOX_IDS[ch], True)

        self.SetBool(self.IMPORT_3D_MODEL_CHECKBOX, False)
        self.SetBool(self.AO_CHECKBOX, False)
        self.SetBool(self.COPY_TEXTURES_CHECKBOX, False)
        self.result = None
        return True

    def Command(self, id, msg):
        if id == self.SELECT_FOLDER_BUTTON:
            path = storage.LoadDialog(title="Select a Folder", flags=c4d.FILESELECT_DIRECTORY)
            if path:
                self.SetString(self.FOLDER_INPUT, path)

        # Preview
        if id == self.PREVIEW_MATERIAL_BUTTON:
            folder = self.GetString(self.FOLDER_INPUT).strip()
            if not folder or not os.path.exists(folder):
                gui.MessageDialog("Please select a valid folder.")
                return True

            channels = list(self.CHECKBOX_IDS.keys())
            files = {ch: {} for ch in channels}
            for fn in os.listdir(folder):
                lower = fn.lower().replace("_", "")
                for ch in channels:
                    if self.GetBool(self.CHECKBOX_IDS[ch]):
                        kws = [k.strip() for k in self.GetString(self.TEXTBOX_IDS[ch]).split(',')]
                        for kw in kws:
                            if kw.lower().replace("_","") in lower:
                                ident = extract_identifier(fn, kw) or ""
                                files[ch][ident] = os.path.join(folder, fn)
                                break

            # single matches → empty id
            for ch in channels:
                if len(files[ch]) == 1:
                    v = next(iter(files[ch].values()))
                    files[ch] = {"": v}

            ids = set()
            for ch in channels:
                if files[ch]:
                    ids |= set(files[ch].keys())
            if not ids:
                gui.MessageDialog("No texture files found.")
                return True

            text = ""
            base = self.GetString(self.MATERIAL_NAME_INPUT).strip()
            for ident in ids:
                name = f"{base}_{ident}" if ident else base
                text += f"Material: {name}\n"
                for ch in channels:
                    if files[ch].get(ident):
                        text += f"  {ch}: {os.path.basename(files[ch][ident])}\n"
                text += "\n"
            gui.MessageDialog(text)

        # Create
        if id == self.CREATE_MATERIAL_BUTTON:
            folder = self.GetString(self.FOLDER_INPUT).strip()
            if not folder or not os.path.exists(folder):
                gui.MessageDialog("Please select a valid folder.")
                return True

            channels = list(self.CHECKBOX_IDS.keys())
            files = {ch: {} for ch in channels}
            for fn in os.listdir(folder):
                lower = fn.lower().replace("_", "")
                for ch in channels:
                    if self.GetBool(self.CHECKBOX_IDS[ch]):
                        kws = [k.strip() for k in self.GetString(self.TEXTBOX_IDS[ch]).split(',')]
                        for kw in kws:
                            if kw.lower().replace("_","") in lower:
                                ident = extract_identifier(fn, kw) or ""
                                files[ch][ident] = os.path.join(folder, fn)
                                break

            for ch in channels:
                if len(files[ch]) == 1:
                    v = next(iter(files[ch].values()))
                    files[ch] = {"": v}

            ids = set()
            for ch in channels:
                if files[ch]:
                    ids |= set(files[ch].keys())
            if not ids:
                gui.MessageDialog("No texture files found.")
                return True

            sets = {}
            base = self.GetString(self.MATERIAL_NAME_INPUT).strip()
            for ident in ids:
                ms = {ch: files[ch].get(ident) if self.GetBool(self.CHECKBOX_IDS[ch]) else None for ch in channels}
                ms["materialName"] = f"{base}_{ident}" if ident else base
                ms["ao"] = self.GetBool(self.AO_CHECKBOX)
                sets[ident] = ms

            self.result = {
                "materialSets": sets,
                "folder": folder,
                "importObject": self.GetBool(self.IMPORT_3D_MODEL_CHECKBOX),
                "copyTextures": self.GetBool(self.COPY_TEXTURES_CHECKBOX),
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
    if file_paths is None:
        return

    doc = c4d.documents.GetActiveDocument()
    sets = file_paths["materialSets"]

    # Copy textures
    if file_paths["copyTextures"]:
        proj = doc.GetDocumentPath() or file_paths["folder"]
        texd = os.path.join(proj, "tex")
        if not os.path.exists(texd):
            os.makedirs(texd)
        for ms in sets.values():
            for ch in ["BaseColor","Roughness","Normal","Displacement","Opacity"]:
                if ms.get(ch):
                    src = ms[ch]
                    dst = os.path.join(texd, os.path.basename(src))
                    try:
                        shutil.copy2(src, dst)
                        ms[ch] = dst
                    except Exception as e:
                        print("Copy error:", e)

    # Create materials
    created = {}
    for ident, ms in sets.items():
        m = create_redshift_material(ms)
        if m:
            created[ident] = m

    # Import & assign
    if file_paths["importObject"]:
        fld = file_paths["folder"]
        old = get_all_objects(doc.GetFirstObject()) if doc.GetFirstObject() else []
        for fn in os.listdir(fld):
            if fn.lower().endswith(('.fbx','.obj')):
                c4d.documents.MergeDocument(doc, os.path.join(fld, fn), c4d.SCENEFILTER_OBJECTS)

        new = get_all_objects(doc.GetFirstObject()) if doc.GetFirstObject() else []
        added = [o for o in new if o not in old]
        for obj in added:
            for mat in created.values():
                tag = c4d.BaseTag(c4d.Ttexture)
                tag[c4d.TEXTURETAG_MATERIAL] = mat
                obj.InsertTag(tag)

        c4d.EventAdd()

if __name__ == "__main__":
    main()
