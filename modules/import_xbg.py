import bpy,math,mathutils,os
from .binary import BinaryReader
from .skeleton import Skeleton,XMLSkeletonParser,parse_skeleton_chunk
from .mesh import Mesh,parse_mesh_vertices,parse_sdol_chunk,parse_dnks_chunk
from .bounds import parse_xobb,parse_hpsb
from .uv import apply_uv_coordinates
from .weights import apply_vertex_weights,remap_skin_indices
from .materials import XBMParser
from .nodes import BlenderMaterialSetup
from .xbt import XBTConverter
from .debug import VerboseLogger as vlog,create_format_bounds_lattice,create_bounding_visualizations,flip_normals as dbg_flip,auto_smooth_normals,display_file_info
class XBGData:
    def __init__(self):self.skeleton=Skeleton();self.meshes=[];self.sub_mesh_list=[];self.materials=[];self.lod_count=0;self.vert_pos_scale=1.0;self.uv_trans=0.0;self.uv_scale=1.0;self.bounding_boxes=[];self.bounding_spheres=[];self.chunks=[]
class XBGParser:
    def __init__(self,fn):self.filename=fn;self.data=XBGData()
    def parse(self,lod=0):
        vlog.log(f"\n{'='*60}\nPARSING XBG FILE: {os.path.basename(self.filename)}\n{'='*60}")
        with BinaryReader(self.filename) as g:
            g.word(4);cc=g.i(7)[6];vlog.log(f"\nFile Header:\n  Chunk Count: {cc}")
            for m in range(cc):
                back=g.tell();chunk=g.word(4);ci=g.i(2);cs=ci[1];self.data.chunks.append((chunk,back,cs));vlog.log_chunk(chunk,back,cs)
                if chunk=='PMCP':g.i(2);unk,self.data.vert_pos_scale=g.f(2);vlog.log_pmcp(self.data.vert_pos_scale,unk)
                elif chunk=='PMCU':g.i(2);self.data.uv_trans,self.data.uv_scale=g.f(2);vlog.log_pmcu(self.data.uv_trans,self.data.uv_scale)
                elif chunk=='EDON':parse_skeleton_chunk(g,self.data.skeleton)
                elif chunk=='DIKS':g.i(2);self.data.lod_count=g.i(1)[0];vlog.log(f"\n=== DIKS CHUNK ===\nLOD Count: {self.data.lod_count}");[g.H(2) or g.B(4) for _ in range(self.data.lod_count)]
                elif chunk=='LTMR':
                    w=g.i(4);mc=w[2];vlog.log(f"\n=== LTMR CHUNK (Materials) ===\nMaterial Count: {mc}")
                    for m in range(mc):nl=g.i(1)[0];mf=g.word(nl);sn=mf.split('/')[-1].replace('.mat','') or f"Material_{m}";self.data.materials.append(sn);vlog.log_material(m,sn,mf);g.b(1)
                elif chunk=='SDOL':parse_sdol_chunk(g,self.data.meshes)
                elif chunk=='DNKS':self.data.sub_mesh_list=parse_dnks_chunk(g,self.data.lod_count)
                elif chunk=='XOBB':
                    bbox=parse_xobb(g,ci[1])
                    if bbox:self.data.bounding_boxes.append(bbox);[setattr(mesh,'xobb_chunk_offset',back) for mesh in self.data.meshes]
                elif chunk=='HPSB':
                    sphere=parse_hpsb(g,ci[1])
                    if sphere:self.data.bounding_spheres.append(sphere);[setattr(mesh,'hpsb_chunk_offset',back) for mesh in self.data.meshes]
                g.seek(back+ci[1])
            self._filter_lod(lod);self._process_mesh_vertices(g);self._remap_skin_indices(g);self._process_mesh_faces(g)
        vlog.log(f"\n{'='*60}\nPARSING COMPLETE\n{'='*60}\n");return self.data
    def _filter_lod(self,lod):
        if lod==-1:vlog.log("\nImporting ALL LODs");return
        if 0<=lod<len(self.data.meshes):vlog.log(f"\nImporting LOD {lod} only");self.data.meshes=[self.data.meshes[lod]]
        elif self.data.meshes:vlog.log(f"\nDefaulting to LOD 0");self.data.meshes=[self.data.meshes[0]]
    def _process_mesh_vertices(self,g):[parse_mesh_vertices(g,mesh,self.data.vert_pos_scale,self.data.uv_trans,self.data.uv_scale) for mesh in self.data.meshes]
    def _remap_skin_indices(self,g):[remap_skin_indices(mesh,self.data.sub_mesh_list) for mesh in self.data.meshes]
    def _process_mesh_faces(self,g):
        vlog.log(f"\n=== PROCESSING MESH FACES ===")
        for mesh in self.data.meshes:
            for info in mesh.mat_list_info:
                lg,si=info[1],info[2]
                if lg<len(self.data.sub_mesh_list) and si<len(self.data.sub_mesh_list[lg]):
                    sm=self.data.sub_mesh_list[lg][si];mid=sm.header_data[0];mn=self.data.materials[mid] if mid<len(self.data.materials) else f"Material_{mid}"
                    if sm.face_count>0:
                        g.seek(mesh.indice_section_offset+info[3]*2);idx=[]
                        for _ in range(sm.face_count):
                            try:fi=g.H(3);65535 not in fi and idx.extend(fi)
                            except:break
                        idx and mesh.add_primitive(idx,mid,mn) or vlog.log(f"  LOD{mesh.lod_level} Material '{mn}': {len(idx)//3} triangles")
class XBGBlenderImporter:
    def load(self,ctx,fp,lod=0,imo=False,df="",lt=True,lhd=True,fn=True,uxa=True,sp=False,sfb=False,iad=False):
        vlog.log(f"\n{'#'*60}\n# XBG IMPORT STARTED\n# File: {os.path.basename(fp)}\n{'#'*60}")
        xb={};xm2b={};xmi2b={};xmi2n={}
        if uxa:
            xp=XMLSkeletonParser.find_xml_file(fp)
            if xp:
                xb,xm2b,xmi2b,xmi2n=XMLSkeletonParser.parse_xml_skeleton(xp)
        sp and vlog.log(f"\n*** SEPARATE PRIMITIVES MODE ENABLED ***")
        parser=XBGParser(fp);data=parser.parse(lod)
        # Always store file info, but only display if checkbox enabled
        file_info_str = display_file_info(data.chunks,os.path.basename(fp),fp)
        ctx.scene.xbg_debug_settings.file_info_data = file_info_str
        sfb and data.vert_pos_scale and create_format_bounds_lattice(ctx,data.vert_pos_scale)
        ao=None
        if not imo:
            ao=self.create_armature(data.skeleton,os.path.basename(fp))
        mos=self.create_meshes(data.meshes,ao,data.materials,imo,df,lt,lhd,xb,xm2b,xmi2b,xmi2n,sp,fp,data.vert_pos_scale,data.uv_trans,data.uv_scale,iad)
        fn and mos and dbg_flip(mos)
        ds=ctx.scene.xbg_debug_settings
        (ds.show_bounding_box or ds.show_bounding_sphere) and mos and create_bounding_visualizations(ctx,data,mos,ds.show_bounding_box,ds.show_bounding_sphere,ds.bounds_display_type)
        ds.auto_smooth_normals and mos and auto_smooth_normals(mos)
        XBTConverter.cleanup_temp_files();vlog.log(f"\n{'#'*60}\n# XBG IMPORT COMPLETE\n{'#'*60}\n");return {'FINISHED'}
    def create_armature(self,skel,nb):
        if skel.get_bone_count()==0:return None
        vlog.log(f"\n=== CREATING ARMATURE ===");an=f"{nb}_Armature";ad=bpy.data.armatures.new(an);ao=bpy.data.objects.new(an,ad)
        bpy.context.collection.objects.link(ao);bpy.context.view_layer.objects.active=ao;ao.rotation_euler=(0,0,math.radians(180));vlog.log(f"Armature rotation: (0, 0, 180°)")
        bpy.ops.object.mode_set(mode='EDIT');eb={}
        for i,bd in enumerate(skel.bones):
            bn=bd.name if bd.name else f"Bone_{i}";e=ad.edit_bones.new(bn);eb[i]=e
            e.head=mathutils.Vector(bd.world_matrix.translation) if bd.world_matrix else mathutils.Vector((0,0,0));e.tail=e.head+mathutils.Vector((0,0.5,0))
        for i,bd in enumerate(skel.bones):
            e=eb[i]
            if bd.parent_id is not None and bd.parent_id in eb:
                e.parent=eb[bd.parent_id]
                e.use_connect=False
            if bd.world_matrix:
                rot=bd.world_matrix.to_quaternion()
                off=mathutils.Vector((0,1,0))*0.5
                off.rotate(rot)
                e.tail=e.head+off
        bpy.ops.object.mode_set(mode='OBJECT');vlog.log(f"Created armature: {an}");return ao
    def create_meshes(self,meshes,ao,mns,imo=False,df="",lt=True,lhd=True,xb={},xm2b={},xmi2b={},xmi2n={},sp=False,fp="",vps=1.0,uvt=0.0,uvs=1.0,iad=False):
        vlog.log(f"\n=== CREATING BLENDER MESHES ===");co=[]
        for mi,mesh in enumerate(meshes):
            if not mesh.vert_pos_list:continue
            if sp:
                for pi,prim in enumerate(mesh.primitives):
                    mn=f"Mesh_LOD{mesh.lod_level}_{mi}_Prim{pi}";me=bpy.data.meshes.new(mn);obj=bpy.data.objects.new(mn,me);bpy.context.collection.objects.link(obj);co.append(obj)
                    obj["xbg_data"]={"filepath":fp,"vert_offset":mesh.vert_section_offset,"vert_stride":mesh.vert_stride,"vert_count":mesh.vert_count,"pos_scale":vps,"uv_trans":uvt,"uv_scale":uvs,"lod_level":mesh.lod_level,"import_mesh_only":imo,"xobb_offset":mesh.xobb_chunk_offset,"hpsb_offset":mesh.hpsb_chunk_offset}
                    imo and setattr(obj,'rotation_euler',(0,0,math.radians(180)))
                    if ao:obj.parent=ao;mod=obj.modifiers.new(name="Armature",type='ARMATURE');mod.object=ao
                    verts=mesh.vert_pos_list;faces=[(prim.indices[i],prim.indices[i+1],prim.indices[i+2]) for i in range(0,len(prim.indices),3) if i+2<len(prim.indices)]
                    mrn=prim.material_name;mat=bpy.data.materials.get(mrn) or bpy.data.materials.new(name=mrn);mat.use_nodes=True;obj.data.materials.append(mat)
                    me.from_pydata(verts,[],faces);me.update();apply_uv_coordinates(me,mesh);apply_vertex_weights(obj,ao,mesh,verbose=vlog.enabled)
                    lt and df and self.setup_material_textures([(mat,mrn)],df,lhd,iad);vlog.log(f"Created mesh: {mn} ({len(verts)} verts, {len(faces)} faces)")
            else:
                mn=f"Mesh_LOD{mesh.lod_level}_{mi}";me=bpy.data.meshes.new(mn);obj=bpy.data.objects.new(mn,me);bpy.context.collection.objects.link(obj);co.append(obj)
                obj["xbg_data"]={"filepath":fp,"vert_offset":mesh.vert_section_offset,"vert_stride":mesh.vert_stride,"vert_count":mesh.vert_count,"pos_scale":vps,"uv_trans":uvt,"uv_scale":uvs,"lod_level":mesh.lod_level,"import_mesh_only":imo,"xobb_offset":mesh.xobb_chunk_offset,"hpsb_offset":mesh.hpsb_chunk_offset}
                imo and setattr(obj,'rotation_euler',(0,0,math.radians(180)))
                if ao:obj.parent=ao;mod=obj.modifiers.new(name="Armature",type='ARMATURE');mod.object=ao
                verts=mesh.vert_pos_list;faces=[];mm={};m2s=[]
                for prim in mesh.primitives:midx=prim.material_index;midx not in mm and (mrn:=prim.material_name,mat:=bpy.data.materials.get(mrn) or bpy.data.materials.new(name=mrn),setattr(mat,'use_nodes',True),obj.data.materials.append(mat),mm.__setitem__(midx,len(obj.data.materials)-1),m2s.append((mat,mrn)));[faces.append((prim.indices[i],prim.indices[i+1],prim.indices[i+2])) for i in range(0,len(prim.indices),3) if i+2<len(prim.indices)]
                me.from_pydata(verts,[],faces);me.update();po=0
                for prim in mesh.primitives:bmi=mm.get(prim.material_index,0);nt=len(prim.indices)//3;[setattr(me.polygons[po+i],'material_index',bmi) for i in range(nt) if po+i<len(me.polygons)];po+=nt
                apply_uv_coordinates(me,mesh);apply_vertex_weights(obj,ao,mesh,verbose=vlog.enabled);lt and df and self.setup_material_textures(m2s,df,lhd,iad);vlog.log(f"Created mesh: {mn} ({len(verts)} verts, {len(faces)} faces)")
        return co
    def setup_material_textures(self,m2s,df,lhd=True,iad=False):
        mf=os.path.join(df,"graphics","_materials")
        for mat,mn in m2s:
            xfn=os.path.basename(mn)
            if not xfn.lower().endswith('.xbm'):
                xfn=xfn+'.xbm'
            xp=os.path.join(mf,xfn)
            if os.path.exists(xp):
                vlog.log(f"\nLoading XBM: {xfn}")
                xd=XBMParser.parse(xp,lhd)
                if xd:
                    BlenderMaterialSetup.setup_material(mat,xd,df,lhd,iad)
