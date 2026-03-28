import xml.etree.ElementTree as ET
import os
import mathutils

try:
    from .debug import VerboseLogger as vlog
except:
    class vlog:
        @staticmethod
        def log(m): pass
        @staticmethod
        def log_bone(*a): pass
        @staticmethod
        def log_bone_world_transform(*a): pass
        @staticmethod
        def log_xml_bone(*a): pass


class Bone:
    __slots__ = ('name', 'parent_id', 'local_rotation_quat', 'local_position', 'local_matrix', 'world_matrix', 'bind_matrix', 'mb2o_index')
    
    def __init__(self):
        self.name = None
        self.parent_id = None
        self.local_rotation_quat = None
        self.local_position = [0, 0, 0]
        self.local_matrix = None
        self.world_matrix = None
        self.bind_matrix = None  # MB2O inverse bind matrix
        self.mb2o_index = None  # Index into MB2O array


class Skeleton:
    def __init__(self):
        self.bones = []
        self.bone_to_mb2o_map = {}  # Maps bone_id → MB2O index
    
    def add_bone(self, bone):
        self.bones.append(bone)
    
    def get_bone_count(self):
        return len(self.bones)
    
    def compute_bone_transforms(self):
        vlog.log("\n=== COMPUTING BONE TRANSFORMS ===")
        for i, bone in enumerate(self.bones):
            if bone.local_rotation_quat is None:
                continue
            
            rot_matrix = bone.local_rotation_quat.to_matrix().to_4x4()
            pos_matrix = mathutils.Matrix.Translation(bone.local_position)
            bone.local_matrix = pos_matrix @ rot_matrix
            
            if bone.parent_id is not None and 0 <= bone.parent_id < len(self.bones):
                parent = self.bones[bone.parent_id]
                bone.world_matrix = parent.world_matrix @ bone.local_matrix if parent.world_matrix is not None else bone.local_matrix
            else:
                bone.world_matrix = bone.local_matrix
            
            if bone.world_matrix:
                vlog.log_bone_world_transform(i, bone.name, tuple(bone.world_matrix.translation))
    
    def build_mb2o_mapping(self, sub_mesh_list):
        """Build mapping of bone IDs to MB2O indices based on DNKS data
        
        MB2O contains inverse bind matrices for bones used in skinning.
        The order matches the unique bones collected from DNKS bone palettes.
        """
        vlog.log(f"\n=== BUILDING MB2O BONE MAPPING ===")
        
        # Collect all unique bones from all LODs in DNKS
        unique_bones = []
        seen_bones = set()
        
        for lod_idx, lod_submeshes in enumerate(sub_mesh_list):
            for submesh in lod_submeshes:
                for bone_id in submesh.bone_data:
                    if bone_id != -1 and bone_id not in seen_bones:
                        unique_bones.append(bone_id)
                        seen_bones.add(bone_id)
        
        # Create mapping: bone_id → MB2O index
        for mb2o_idx, bone_id in enumerate(unique_bones):
            self.bone_to_mb2o_map[bone_id] = mb2o_idx
            if bone_id < len(self.bones):
                self.bones[bone_id].mb2o_index = mb2o_idx
        
        vlog.log(f"  Found {len(unique_bones)} bones used in skinning")
        vlog.log(f"  MB2O mapping: {self.bone_to_mb2o_map}")
        
        return unique_bones
    
    def apply_bind_matrices(self, bind_matrices, sub_mesh_list):
        """Apply MB2O bind matrices with correct bone mapping
        
        CRITICAL: MB2O matrices are NOT indexed by bone ID!
        They're indexed by the order bones appear in DNKS bone palettes.
        """
        vlog.log(f"\n=== APPLYING MB2O BIND MATRICES ===")
        vlog.log(f"  MB2O matrices available: {len(bind_matrices)}")
        
        # Build the bone → MB2O index mapping from DNKS
        unique_bones = self.build_mb2o_mapping(sub_mesh_list)
        
        if len(bind_matrices) != len(unique_bones):
            vlog.log(f"  WARNING: MB2O count ({len(bind_matrices)}) != unique bones ({len(unique_bones)})")
        
        # Apply MB2O matrices to the correct bones
        for bone_id, mb2o_idx in self.bone_to_mb2o_map.items():
            if mb2o_idx < len(bind_matrices) and bone_id < len(self.bones):
                bone = self.bones[bone_id]
                bone.bind_matrix = bind_matrices[mb2o_idx]
                
                # For visualization: we could override world_matrix, but that breaks the hierarchy
                # Instead, store it separately and use it during skinning
                vlog.log(f"  Bone {bone_id} ({bone.name}): MB2O[{mb2o_idx}] applied")
        
        # Bones without MB2O data keep their EDON world transforms
        bones_without_mb2o = [i for i in range(len(self.bones)) if i not in self.bone_to_mb2o_map]
        if bones_without_mb2o:
            vlog.log(f"  {len(bones_without_mb2o)} bones have no MB2O data (using EDON transforms)")


class XMLBoneData:
    def __init__(self, name, position, rotation, parent=None):
        self.name = name
        self.position = position
        self.rotation = rotation
        self.parent = parent


def quaternion_from_xbg_data(qd):
    return mathutils.Quaternion((qd[3], qd[0], qd[1], qd[2])) if len(qd) >= 4 else mathutils.Quaternion()


def parse_skeleton_chunk(g, skeleton):
    w = g.i(3)
    bone_count = w[2]
    vlog.log(f"\n=== EDON CHUNK (Skeleton) ===\nBone Count: {bone_count}")
    
    for m in range(bone_count):
        bone = Bone()
        g.b(4)
        w = g.i(3)
        
        quat_data = g.f(4)
        bone.local_rotation_quat = quaternion_from_xbg_data(quat_data)
        
        pos_data = g.f(3)
        bone.local_position = list(pos_data)
        
        g.f(3)
        g.i(1)
        g.f(1)
        g.i(1)
        
        name_len = g.i(1)[0]
        bone.name = g.word(name_len)[-25:]
        bone.parent_id = w[2]
        g.b(1)
        
        vlog.log_bone(m, bone.name, bone.parent_id, pos_data, quat_data)
        skeleton.add_bone(bone)
    
    skeleton.compute_bone_transforms()


def parse_mb2o_chunk(g):
    """Parse MB2O chunk containing inverse bind matrices
    
    IMPORTANT: MB2O matrices are stored in COLUMN-MAJOR format!
    The matrices must be transposed when reading.
    """
    vlog.log("\n=== MB2O CHUNK (Bind Matrices) ===")
    
    g.i(2)  # Skip first two ints
    matrix_count = g.i(1)[0]
    vlog.log(f"  Reading {matrix_count} MB2O inverse bind matrices")
    
    matrices = []
    for i in range(matrix_count):
        # Read 16 floats for 4x4 matrix
        # CRITICAL: XBG stores matrices in COLUMN-MAJOR format!
        # File layout: [c0r0, c0r1, c0r2, c0r3, c1r0, c1r1, c1r2, c1r3, ...]
        #   where c = column, r = row
        matrix_data = g.f(16)
        
        # Convert from column-major to Blender's Matrix format
        # Blender Matrix constructor takes rows, so we transpose by reading columns as rows
        mat = mathutils.Matrix((
            (matrix_data[0], matrix_data[4], matrix_data[8],  matrix_data[12]),  # Row 0 from column data
            (matrix_data[1], matrix_data[5], matrix_data[9],  matrix_data[13]),  # Row 1 from column data
            (matrix_data[2], matrix_data[6], matrix_data[10], matrix_data[14]),  # Row 2 from column data
            (matrix_data[3], matrix_data[7], matrix_data[11], matrix_data[15])   # Row 3 from column data
        ))
        
        matrices.append(mat)
        
        if vlog.enabled and i < 3:  # Only log first 3 for brevity
            trans = mat.translation
            vlog.log(f"  Matrix {i}: Translation = ({trans.x:.3f}, {trans.y:.3f}, {trans.z:.3f})")
    
    vlog.log(f"  Successfully parsed {len(matrices)} MB2O inverse bind matrices")
    vlog.log(f"  Note: These are indexed by DNKS bone palette order, NOT bone ID!")
    return matrices


class XMLSkeletonParser:
    @staticmethod
    def find_xml_file(xbg_filepath):
        base_path = os.path.splitext(xbg_filepath)[0]
        xml_path = base_path + '.xml'
        if os.path.exists(xml_path):
            vlog.log(f"\n{'='*60}\nFound XML file: {xml_path}\n{'='*60}")
            return xml_path
        return None
    
    @staticmethod
    def parse_xml_skeleton(xml_filepath):
        try:
            tree = ET.parse(xml_filepath)
            root = tree.getroot()
            bones = {}
            mesh_to_bone = {}
            mesh_index_to_bone = {}
            mesh_index_to_name = {}
            
            descriptor = root.find('.//descriptor')
            if descriptor is None:
                return bones, mesh_to_bone, mesh_index_to_bone, mesh_index_to_name
            
            graphic_component = descriptor.find(".//component[@class='GraphicComponent']")
            if graphic_component is not None:
                vlog.log("\n=== XML MESH-TO-BONE MAPPINGS ===")
                for obj in graphic_component.findall('object'):
                    mesh_name = obj.get('meshName')
                    bone_name = obj.get('boneName')
                    mesh_index = obj.get('index')
                    
                    if mesh_name and bone_name:
                        mesh_to_bone[mesh_name.upper()] = bone_name
                        vlog.log(f"  {mesh_name} → {bone_name}")
                    
                    if mesh_index is not None and bone_name:
                        try:
                            idx = int(mesh_index)
                            mesh_index_to_bone[idx] = bone_name
                            mesh_index_to_name[idx] = mesh_name if mesh_name else None
                        except:
                            pass
            
            skeleton = graphic_component.find('.//skeleton') if graphic_component else None
            if skeleton is None:
                return bones, mesh_to_bone, mesh_index_to_bone, mesh_index_to_name
            
            vlog.log(f"\n=== XML SKELETON PARSING ===")
            
            def parse_bone(bone_elem, parent_name=None):
                name = bone_elem.get('name')
                if not name:
                    return
                
                pos_str = bone_elem.get('pos', '0,0,0')
                pos = tuple(float(x) for x in pos_str.split(','))
                
                rot_str = bone_elem.get('rot', '1,0,0,0')
                rot = tuple(float(x) for x in rot_str.split(','))
                
                bones[name] = XMLBoneData(name, pos, rot, parent_name)
                vlog.log_xml_bone(name, pos, rot, parent_name)
                
                for child_bone in bone_elem.findall('bone'):
                    parse_bone(child_bone, name)
            
            for bone_elem in skeleton.findall('bone'):
                parse_bone(bone_elem, None)
            
            vlog.log(f"\nTotal XML bones: {len(bones)}")
            return bones, mesh_to_bone, mesh_index_to_bone, mesh_index_to_name
        except:
            return {}, {}, {}, {}
