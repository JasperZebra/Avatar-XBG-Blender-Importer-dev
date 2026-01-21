bl_info = {
    "name": "XBG Importer",
    "author": "Quiet Joker",
    "version": (2, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > XBG Import",
    "description": "Import XBG models from James Cameron's Avatar The Game",
    "category": "Import-Export",
}
import bpy,os
from .modules.import_xbg import XBGBlenderImporter
from .modules.export_xbg import XBGExporter
from .modules.debug import VerboseLogger
class XBGAddonPreferences(bpy.types.AddonPreferences):
    bl_idname=__name__
    data_folder:bpy.props.StringProperty(name="Data Folder",description="Path to the game's Data folder",default="",subtype='DIR_PATH')
    def draw(self,ctx):self.layout.prop(self,"data_folder")
class XBGImportSettings(bpy.types.PropertyGroup):
    load_textures:bpy.props.BoolProperty(name="Load Textures",description="Automatically load and setup textures from XBM material files",default=True)
    load_hd_textures:bpy.props.BoolProperty(name="Load HD Textures",description="Use high-resolution _mip0 texture variants when available",default=True)
class XBGExportSettings(bpy.types.PropertyGroup):
    auto_scale_to_bounds:bpy.props.BoolProperty(name="Auto-Scale to Fit Bounds",description="Automatically scale mesh to fit within XBG format limits",default=False)
    show_scale_info:bpy.props.BoolProperty(name="Show Scale Information",description="Display scaling requirements",default=True)
    ignore_format_limits:bpy.props.BoolProperty(name="Ignore Format Limits (DANGEROUS)",description="Export raw values without clamping - may corrupt model!",default=False)
    override_game_scale:bpy.props.BoolProperty(name="Override Game Scale",description="Write a new scale value to the PMCP chunk",default=False)
    target_game_scale:bpy.props.FloatProperty(name="New Scale Value",description="The new PMCP multiplier",default=1.0,precision=6,min=0.000001)
class XBGDebugSettings(bpy.types.PropertyGroup):
    verbose_logging:bpy.props.BoolProperty(name="Verbose Logging",description="Print detailed debug information to console (bones, chunks, transforms, etc.)",default=False)
    show_file_info:bpy.props.BoolProperty(name="Show File Info",description="Display XBG file chunk information in the panel",default=False)
    show_format_bounds:bpy.props.BoolProperty(name="Show XBG Format Bounds",description="Display the 16-bit coordinate limit as a lattice box",default=False)
    show_bounding_box:bpy.props.BoolProperty(name="Show Bounding Boxes",description="Visualize bounding boxes from XOBB chunks",default=False)
    show_bounding_sphere:bpy.props.BoolProperty(name="Show Bounding Spheres",description="Visualize bounding spheres from HPSB chunks",default=False)
    bounds_display_type:bpy.props.EnumProperty(name="Display Type",description="How to display bounding volumes",items=[('WIRE','Wire','Display as wireframe'),('SOLID','Solid','Display as solid with transparency'),('LATTICE','Lattice','Display as lattice modifier on box')],default='WIRE')
    flip_normals:bpy.props.BoolProperty(name="Flip Normals",description="Flip all face normals after import (fixes inverted normals)",default=True)
    separate_primitives:bpy.props.BoolProperty(name="Separate Primitives",description="Create separate mesh objects for each primitive chunk instead of joining them",default=False)
    use_xml_assembly:bpy.props.BoolProperty(name="Use XML Assembly",description="Search for and use XML files to properly assemble parts using bone transforms",default=False)
    auto_smooth_normals:bpy.props.BoolProperty(name="Auto Smooth Normals",description="Automatically apply smooth shading after import",default=True)
    merge_distance:bpy.props.FloatProperty(name="Merge Distance",description="Distance threshold for merging duplicate vertices",default=0.0001,min=0.0,max=1.0,precision=4)
    import_xbt_as_dds:bpy.props.BoolProperty(name="Import XBT as DDS",description="Import XBT textures as DDS files instead of PNG. WARNING: DDS format will cause texture painting corruption! Use PNG (default) for texture painting",default=False)
    # Store file info data
    file_info_data:bpy.props.StringProperty(name="File Info Data",default="")
class XBG_OT_Import(bpy.types.Operator):
    bl_idname="import_scene.xbg_model";bl_label="Import XBG";bl_options={'REGISTER','UNDO'}
    filepath:bpy.props.StringProperty(subtype="FILE_PATH");files:bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement);directory:bpy.props.StringProperty(subtype="DIR_PATH")
    import_mesh_only:bpy.props.BoolProperty(name="Import Mesh Only",description="Skip skeleton import and rigging",default=False)
    import_all_lods:bpy.props.BoolProperty(name="Import All LODs",description="Import all Level of Details found in file",default=False)
    lod_level:bpy.props.IntProperty(name="LOD Level",default=0,min=0)
    def invoke(self,ctx,ev):ctx.window_manager.fileselect_add(self);return{'RUNNING_MODAL'}
    def execute(self,ctx):
        s,ds,p=ctx.scene.xbg_settings,ctx.scene.xbg_debug_settings,ctx.preferences.addons[__name__].preferences;VerboseLogger.enabled=ds.verbose_logging
        df,lt,lhd=p.data_folder,s.load_textures,s.load_hd_textures
        lt and not df and(self.report({'WARNING'},"Data folder not set - textures will not be loaded"),setattr(self,'load_textures',False))
        imp=XBGBlenderImporter();tl=-1 if self.import_all_lods else self.lod_level
        fs=[];self.files and[fs.append(os.path.join(self.directory,f.name)) for f in self.files if f.name.lower().endswith(".xbg")] or(self.filepath.lower().endswith(".xbg") and fs.append(self.filepath))
        fs or(self.report({'ERROR'},"No valid .xbg files selected"),({'CANCELLED'}))
        ic=0
        if ds.import_xbt_as_dds:
            self.report({'WARNING'},"DDS Import Mode enabled - Texture painting will be corrupted! Use PNG mode for texture painting.")
        for fp in fs:
            try:
                imp.load(ctx,fp,tl,self.import_mesh_only,df,lt,lhd,ds.flip_normals,ds.use_xml_assembly,ds.separate_primitives,ds.show_format_bounds,ds.import_xbt_as_dds)
                ic+=1
            except Exception as e:
                self.report({'WARNING'},f"Failed to import {os.path.basename(fp)}: {str(e)}")
        
        if ic>0:
            self.report({'INFO'},f"Imported {ic} XBG file(s)")
            return{'FINISHED'}
        else:
            self.report({'ERROR'},"No files were imported successfully")
            return{'CANCELLED'}
class XBG_OT_QuickSetScale(bpy.types.Operator):
    bl_idname="xbg.quick_set_scale";bl_label="Set Scale";value:bpy.props.FloatProperty()
    def execute(self,ctx):ctx.scene.xbg_export_settings.target_game_scale=self.value;return{'FINISHED'}
class XBG_OT_MergeAllMeshes(bpy.types.Operator):
    bl_idname="xbg.merge_all_meshes";bl_label="Merge All Meshes";bl_options={'REGISTER','UNDO'}
    def execute(self,ctx):
        from .modules.debug import merge_duplicate_vertices
        ds=ctx.scene.xbg_debug_settings
        objs=[o for o in ctx.scene.objects if o.type=='MESH']
        if not objs:
            self.report({'WARNING'},"No meshes in scene")
            return{'CANCELLED'}
        merge_duplicate_vertices(objs,ds.merge_distance)
        self.report({'INFO'},f"Merged vertices on {len(objs)} mesh(es)")
        return{'FINISHED'}
class XBG_OT_MergeSelectedMesh(bpy.types.Operator):
    bl_idname="xbg.merge_selected_mesh";bl_label="Merge Selected Mesh";bl_options={'REGISTER','UNDO'}
    def execute(self,ctx):
        from .modules.debug import merge_duplicate_vertices
        ds=ctx.scene.xbg_debug_settings
        obj=ctx.active_object
        if not obj or obj.type!='MESH':
            self.report({'ERROR'},"No mesh selected")
            return{'CANCELLED'}
        merge_duplicate_vertices([obj],ds.merge_distance)
        self.report({'INFO'},f"Merged vertices on {obj.name}")
        return{'FINISHED'}

class XBG_OT_Export(bpy.types.Operator):
    bl_idname="export_scene.xbg_inject";bl_label="Export XBG (Inject)";bl_options={'REGISTER','UNDO'};filepath:bpy.props.StringProperty(subtype="FILE_PATH")
    def invoke(self,ctx,ev):obj=ctx.active_object;obj and"xbg_data"in obj and setattr(self,'filepath',obj["xbg_data"]["filepath"]);ctx.window_manager.fileselect_add(self);return{'RUNNING_MODAL'}
    def execute(self,ctx):
        obj=ctx.active_object;obj or(self.report({'ERROR'},"No active object selected"),({'CANCELLED'}))
        ds,es=ctx.scene.xbg_debug_settings,ctx.scene.xbg_export_settings;VerboseLogger.enabled=ds.verbose_logging
        if"xbg_data"in obj:
            from .modules.debug import analyze_export_scale
            m=obj["xbg_data"].to_dict();analyze_export_scale(obj,m.get("pos_scale",1.0),m.get("import_mesh_only",False))
        exp=XBGExporter();st,msg=exp.export(ctx,obj,self.filepath,es.auto_scale_to_bounds,es.show_scale_info,es.ignore_format_limits)
        st=={'FINISHED'}and(self.report({'INFO'},msg),{'FINISHED'})or(self.report({'ERROR'},msg),{'CANCELLED'});return st
class XBG_PT_Panel(bpy.types.Panel):
    bl_label="XBG Import";bl_idname="OBJECT_PT_xbg_import";bl_space_type='VIEW_3D';bl_region_type='UI';bl_category="XBG Import"
    def draw(self,ctx):
        l,s,p=self.layout,ctx.scene.xbg_settings,ctx.preferences.addons[__name__].preferences
        b=l.box();b.label(text="Game Data Folder:",icon='FILE_FOLDER');b.prop(p,"data_folder",text="")
        b=l.box();b.label(text="Import Options:",icon='PREFERENCES');b.prop(s,"load_textures");r=b.row();r.enabled=s.load_textures;r.prop(s,"load_hd_textures")
        l.separator();r=l.row();r.scale_y=1.5;r.operator("import_scene.xbg_model",icon='IMPORT')
        l.separator();b=l.box();b.label(text="Export (Re-Inject):",icon='EXPORT');obj,es=ctx.active_object,ctx.scene.xbg_export_settings
        if obj and"xbg_data"in obj:
            b.label(text=f"Linked: {os.path.basename(obj['xbg_data']['filepath'])}",icon='LINKED')
            m=obj["xbg_data"].to_dict();ps,imo=m.get("pos_scale",1.0),m.get("import_mesh_only",False)
            exp=XBGExporter();ns,rs,si=exp.calculate_required_scale(obj,ps,imo)
            if not es.override_game_scale:
                ib=b.box()
                if ns:ib.alert=True;ib.label(text="⚠ MESH EXCEEDS FORMAT BOUNDS",icon='ERROR');ib.label(text=f"Exceeded: {si}");ib.separator();es.ignore_format_limits and ib.label(text="IGNORE LIMITS ENABLED!",icon='ERROR')or(es.auto_scale_to_bounds and(ib.label(text="Will auto-scale to fit:",icon='INFO'),ib.label(text=f"  Scale: {rs:.6f}"))or ib.label(text="Vertices will be CLAMPED!",icon='CANCEL'))
                else:ib.label(text="✓ Mesh fits within bounds",icon='CHECKMARK')
            sb=b.box();sb.label(text="Export Options:",icon='SETTINGS');sb.prop(es,"auto_scale_to_bounds");sb.prop(es,"show_scale_info");sb.separator();sb.label(text=f"Current Scale: {m['pos_scale']:.6f}",icon='LINENUMBERS_ON');sb.prop(es,"override_game_scale")
            if es.override_game_scale:r=sb.row();r.prop(es,"target_game_scale");r=sb.row(align=True);op=r.operator("xbg.quick_set_scale",text="x2");op.value=m['pos_scale']*2;op=r.operator("xbg.quick_set_scale",text="x0.5");op.value=m['pos_scale']*0.5
            sb.separator();dr=sb.row();dr.alert=True;dr.prop(es,"ignore_format_limits");r=b.row();r.scale_y=1.3;r.operator("export_scene.xbg_inject",text="Inject Mesh Data",icon='EXPORT')
        else:b.label(text="Select an imported XBG mesh",icon='INFO');b.enabled=False
class XBG_PT_DebugPanel(bpy.types.Panel):
    bl_label="XBG Debug";bl_idname="OBJECT_PT_xbg_debug";bl_space_type='VIEW_3D';bl_region_type='UI';bl_category="XBG Import";bl_options={'DEFAULT_CLOSED'}
    def draw(self,ctx):
        l,ds=self.layout,ctx.scene.xbg_debug_settings
        b=l.box();b.label(text="Logging:",icon='CONSOLE');b.prop(ds,"verbose_logging");b.prop(ds,"show_file_info")
        if ds.show_file_info and ds.file_info_data:
            info_box=b.box()
            info_box.scale_y=0.8
            lines=ds.file_info_data.split('\n')
            for line in lines:
                if line.strip():
                    row=info_box.row()
                    row.alignment='LEFT'
                    row.label(text=line)
        b=l.box();b.label(text="Mesh Processing:",icon='MESH_DATA');b.prop(ds,"flip_normals");b.prop(ds,"separate_primitives")
        ds.separate_primitives and(i:=b.box(),i.label(text="Separate Primitives Mode:",icon='INFO'),i.label(text="Each primitive = separate object"),i.label(text="Creates individual mesh per chunk"))
        b.prop(ds,"use_xml_assembly")
        ds.use_xml_assembly and(i:=b.box(),i.label(text="XML Assembly:",icon='INFO'),i.label(text="Uses .xml files for bone transforms"),i.label(text="Properly positions weapon parts"))
        b.separator();b.prop(ds,"auto_smooth_normals");b.separator();b.label(text="Merge Vertices:",icon='AUTOMERGE_ON');b.prop(ds,"merge_distance");r=b.row(align=True);r.operator("xbg.merge_all_meshes",text="All Meshes");r.operator("xbg.merge_selected_mesh",text="Selected")
        l.separator();b=l.box();b.label(text="Texture Import:",icon='TEXTURE');b.prop(ds,"import_xbt_as_dds")
        if ds.import_xbt_as_dds:
            i=b.box();i.alert=True
            i.label(text="⚠ DDS Import Mode:",icon='ERROR')
            i.label(text="WARNING: Texture painting will be")
            i.label(text="corrupted with DDS format!")
            i.label(text="Use PNG (default) for painting.")
        l.separator();b=l.box();b.label(text="Format Bounds:",icon='SHADING_BBOX');b.prop(ds,"show_format_bounds")
        l.separator();b=l.box();b.label(text="Bounding Volumes:",icon='MESH_CUBE');b.prop(ds,"show_bounding_box");b.prop(ds,"show_bounding_sphere");(ds.show_bounding_box or ds.show_bounding_sphere)and b.prop(ds,"bounds_display_type")
classes=(XBGAddonPreferences,XBGImportSettings,XBGExportSettings,XBGDebugSettings,XBG_OT_Import,XBG_OT_QuickSetScale,XBG_OT_MergeAllMeshes,XBG_OT_MergeSelectedMesh,XBG_OT_Export,XBG_PT_Panel,XBG_PT_DebugPanel)
def register():[bpy.utils.register_class(c)for c in classes];bpy.types.Scene.xbg_settings=bpy.props.PointerProperty(type=XBGImportSettings);bpy.types.Scene.xbg_export_settings=bpy.props.PointerProperty(type=XBGExportSettings);bpy.types.Scene.xbg_debug_settings=bpy.props.PointerProperty(type=XBGDebugSettings)
def unregister():del bpy.types.Scene.xbg_settings;del bpy.types.Scene.xbg_export_settings;del bpy.types.Scene.xbg_debug_settings;[bpy.utils.unregister_class(c)for c in reversed(classes)]
if __name__=="__main__":register()
