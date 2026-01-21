import xml.etree.ElementTree as ET,os,mathutils
try:
    from .debug import VerboseLogger as vlog
except:
    class vlog:
        @staticmethod
        def log(m):pass
        @staticmethod
        def log_bone(*a):pass
        @staticmethod
        def log_bone_world_transform(*a):pass
        @staticmethod
        def log_xml_bone(*a):pass
class Bone:
    __slots__=('name','parent_id','local_rotation_quat','local_position','local_matrix','world_matrix')
    def __init__(self):self.name=None;self.parent_id=None;self.local_rotation_quat=None;self.local_position=[0,0,0];self.local_matrix=None;self.world_matrix=None
class Skeleton:
    def __init__(self):self.bones=[]
    def add_bone(self,bone):self.bones.append(bone)
    def get_bone_count(self):return len(self.bones)
    def compute_bone_transforms(self):
        vlog.log("\n=== COMPUTING BONE TRANSFORMS ===")
        for i,bone in enumerate(self.bones):
            if bone.local_rotation_quat is None:continue
            rot_matrix=bone.local_rotation_quat.to_matrix().to_4x4();pos_matrix=mathutils.Matrix.Translation(bone.local_position);bone.local_matrix=pos_matrix@rot_matrix
            if bone.parent_id is not None and 0<=bone.parent_id<len(self.bones):
                parent=self.bones[bone.parent_id]
                bone.world_matrix=parent.world_matrix@bone.local_matrix if parent.world_matrix is not None else bone.local_matrix
            else:bone.world_matrix=bone.local_matrix
            if bone.world_matrix:vlog.log_bone_world_transform(i,bone.name,tuple(bone.world_matrix.translation))
class XMLBoneData:
    def __init__(self,name,position,rotation,parent=None):self.name=name;self.position=position;self.rotation=rotation;self.parent=parent
def quaternion_from_xbg_data(qd):return mathutils.Quaternion((qd[3],qd[0],qd[1],qd[2])) if len(qd)>=4 else mathutils.Quaternion()
def parse_skeleton_chunk(g,skeleton):
    w=g.i(3);bone_count=w[2]
    vlog.log(f"\n=== EDON CHUNK (Skeleton) ===\nBone Count: {bone_count}")
    for m in range(bone_count):
        bone=Bone();g.b(4);w=g.i(3)
        quat_data=g.f(4);bone.local_rotation_quat=quaternion_from_xbg_data(quat_data)
        pos_data=g.f(3);bone.local_position=list(pos_data)
        g.f(3);g.i(1);g.f(1);g.i(1)
        name_len=g.i(1)[0];bone.name=g.word(name_len)[-25:];bone.parent_id=w[2];g.b(1)
        vlog.log_bone(m,bone.name,bone.parent_id,pos_data,quat_data)
        skeleton.add_bone(bone)
    skeleton.compute_bone_transforms()
class XMLSkeletonParser:
    @staticmethod
    def find_xml_file(xbg_filepath):
        base_path=os.path.splitext(xbg_filepath)[0];xml_path=base_path+'.xml'
        if os.path.exists(xml_path):vlog.log(f"\n{'='*60}\nFound XML file: {xml_path}\n{'='*60}");return xml_path
        return None
    @staticmethod
    def parse_xml_skeleton(xml_filepath):
        try:
            tree=ET.parse(xml_filepath);root=tree.getroot()
            bones={};mesh_to_bone={};mesh_index_to_bone={};mesh_index_to_name={}
            descriptor=root.find('.//descriptor')
            if descriptor is None:return bones,mesh_to_bone,mesh_index_to_bone,mesh_index_to_name
            graphic_component=descriptor.find(".//component[@class='GraphicComponent']")
            if graphic_component is not None:
                vlog.log("\n=== XML MESH-TO-BONE MAPPINGS ===")
                for obj in graphic_component.findall('object'):
                    mesh_name=obj.get('meshName');bone_name=obj.get('boneName');mesh_index=obj.get('index')
                    if mesh_name and bone_name:mesh_to_bone[mesh_name.upper()]=bone_name;vlog.log(f"  {mesh_name} → {bone_name}")
                    if mesh_index is not None and bone_name:
                        try:idx=int(mesh_index);mesh_index_to_bone[idx]=bone_name;mesh_index_to_name[idx]=mesh_name if mesh_name else None
                        except:pass
            skeleton=graphic_component.find('.//skeleton') if graphic_component else None
            if skeleton is None:return bones,mesh_to_bone,mesh_index_to_bone,mesh_index_to_name
            vlog.log(f"\n=== XML SKELETON PARSING ===")
            def parse_bone(bone_elem,parent_name=None):
                name=bone_elem.get('name')
                if not name:return
                pos_str=bone_elem.get('pos','0,0,0');pos=tuple(float(x) for x in pos_str.split(','))
                rot_str=bone_elem.get('rot','1,0,0,0');rot=tuple(float(x) for x in rot_str.split(','))
                bones[name]=XMLBoneData(name,pos,rot,parent_name);vlog.log_xml_bone(name,pos,rot,parent_name)
                for child_bone in bone_elem.findall('bone'):parse_bone(child_bone,name)
            for bone_elem in skeleton.findall('bone'):parse_bone(bone_elem,None)
            vlog.log(f"\nTotal XML bones: {len(bones)}")
            return bones,mesh_to_bone,mesh_index_to_bone,mesh_index_to_name
        except:return {},{},{},{}
