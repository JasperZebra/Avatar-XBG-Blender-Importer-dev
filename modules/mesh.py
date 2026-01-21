try:
    from .debug import VerboseLogger as vlog
except:
    class vlog:
        @staticmethod
        def log(m):pass
        @staticmethod
        def log_mesh_header(*a):pass
        @staticmethod
        def log_submesh(*a):pass
class Vector:
    __slots__=('x','y','z')
    def __init__(self,x=0,y=0,z=0):
        if isinstance(x,(list,tuple)) and len(x)>=3:self.x,self.y,self.z=x[0],x[1],x[2]
        else:self.x,self.y,self.z=x,y,z
    def __mul__(self,s):return Vector(self.x*s,self.y*s,self.z*s)
    def to_list(self):return [self.x,self.y,self.z]
class MeshPrimitive:
    __slots__=('indices','material_index','material_name')
    def __init__(self):self.indices=[];self.material_index=0;self.material_name="Default"
class Mesh:
    __slots__=('vert_pos_list','vert_uv_list','primitives','mat_list_info','skin_weight_list','skin_indice_list','vert_count','face_count','vert_stride','vert_section_offset','indice_section_offset','lod_level','xobb_chunk_offset','hpsb_chunk_offset')
    def __init__(self):
        self.vert_pos_list=[];self.vert_uv_list=[];self.primitives=[];self.mat_list_info=[];self.skin_weight_list=[];self.skin_indice_list=[]
        self.vert_count=0;self.face_count=0;self.vert_stride=0;self.vert_section_offset=0;self.indice_section_offset=0;self.lod_level=0;self.xobb_chunk_offset=0;self.hpsb_chunk_offset=0
    def add_primitive(self,indices,mat_idx,mat_name):prim=MeshPrimitive();prim.indices=indices;prim.material_index=mat_idx;prim.material_name=mat_name;self.primitives.append(prim)
class SubMesh:
    __slots__=('header_data','bone_data','face_count')
    def __init__(self):self.header_data=[];self.bone_data=[];self.face_count=0
    def get_face_count(self):return self.header_data[1] if len(self.header_data)>1 else 0
def parse_mesh_vertices(g,mesh,vps,uvt,uvs):
    g.seek(mesh.vert_section_offset)
    vlog.log(f"\n=== PARSING VERTICES (LOD {mesh.lod_level}) ===\nVertex Section Offset: {mesh.vert_section_offset}\nVertex Count: {mesh.vert_count}\nVertex Stride: {mesh.vert_stride} bytes")
    for m in range(mesh.vert_count):
        tm=g.tell();pos_data=g.h(3);pos=Vector(pos_data)*vps;mesh.vert_pos_list.append(pos.to_list())
        g.h(1);u=uvt+g.h(1)[0]*uvs;v=uvt+g.h(1)[0]*uvs;mesh.vert_uv_list.append([u,1.0-v])
        g.seek(4,1)
        if mesh.vert_stride==40:mesh.skin_weight_list.append(g.B(4));mesh.skin_indice_list.append(g.B(4))
        g.seek(tm+mesh.vert_stride)
    vlog.log(f"Parsed {len(mesh.vert_pos_list)} vertices")
    if mesh.skin_weight_list:vlog.log(f"  With skinning data: {len(mesh.skin_weight_list)} weight sets")
def parse_sdol_chunk(g,meshes):
    g.i(2);lod_count=g.i(1)[0]
    vlog.log(f"\n=== SDOL CHUNK (Mesh LODs) ===\nLOD Count: {lod_count}")
    for m in range(lod_count):
        mesh=Mesh();mesh.lod_level=m;w=g.i(6);mesh.face_count=w[1];mesh.vert_count=w[4];mesh.vert_stride=w[3]
        vlog.log_mesh_header(m,mesh.vert_count,mesh.face_count,mesh.vert_stride)
        count=g.i(1)[0];mesh.mat_list_info=[g.i(7) for _ in range(count)]
        vert_section_size=g.I(1)[0];g.seekpad(16);mesh.vert_section_offset=g.tell();vlog.log(f"    Vertex Section: offset={mesh.vert_section_offset}, size={vert_section_size}");g.seek(mesh.vert_section_offset+vert_section_size)
        indice_section_size=g.I(1)[0];g.seekpad(16);mesh.indice_section_offset=g.tell();vlog.log(f"    Index Section: offset={mesh.indice_section_offset}, size={indice_section_size}");g.seek(mesh.indice_section_offset+indice_section_size*2)
        meshes.append(mesh)
def parse_dnks_chunk(g,lod_count):
    g.i(2);g.word(4);g.i(4);sub_mesh_list=[]
    if lod_count==0:vlog.log("Found DNKS chunk but LOD count is 0, skipping");return sub_mesh_list
    vlog.log(f"\n=== DNKS CHUNK (Skinning) ===\nProcessing {lod_count} LOD levels")
    for n in range(lod_count):
        lod_submeshes=[];mat_count=g.i(1)[0];vlog.log(f"\n  LOD {n}: {mat_count} submeshes")
        for m in range(mat_count):
            submesh=SubMesh();submesh.header_data=list(g.H(7));submesh.bone_data=list(g.h(48));submesh.face_count=submesh.get_face_count()
            valid_bones=sum(1 for b in submesh.bone_data if b!=-1);mat_id=submesh.header_data[0]
            vlog.log_submesh(n,m,mat_id,valid_bones,submesh.face_count)
            lod_submeshes.append(submesh)
        sub_mesh_list.append(lod_submeshes)
    return sub_mesh_list
