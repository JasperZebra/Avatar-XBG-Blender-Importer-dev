import struct

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


# ============================================================
# FEATURE 1: VertexFlags - Complete 13-bit bitmask (V4.0 VERIFIED)
# Verified formats: 0x0BCA (32-byte static), 0x0BDA (40-byte skinned)
# ============================================================
class VertexFlags:
    POS_FLOAT  = 0x0001   # Position: float32 (12 bytes)
    POS_INT16  = 0x0002   # Position: int16   (8 bytes, most common)
    POS_HALF   = 0x0004   # Position: float16 (8 bytes)
    UV0        = 0x0008   # UV channel 0:  2x int16 (4 bytes)
    BONE_WTS1  = 0x0010   # Bone weights 1: 4x uint8 + 4x uint8 (8 bytes)
    BONE_WTS2  = 0x0020   # Bone weights 2: 4x uint8 + 4x uint8 (8 bytes)
    NORMAL     = 0x0040   # Normal:   3x int8 + pad (4 bytes)
    COLOR      = 0x0080   # RGBA:     4x uint8 (4 bytes)
    TANGENT    = 0x0100   # Tangent:  3x int8 + pad (4 bytes)
    BINORMAL   = 0x0200   # Binormal: 3x int8 + pad (4 bytes)
    UNK_400    = 0x0400   # Unknown:  3x int8 + pad (4 bytes)
    UV1        = 0x0800   # UV channel 1:  2x int16 (4 bytes)
    UV2        = 0x1000   # UV channel 2:  2x int16 (4 bytes)

    FORMAT_0BCA = 0x0BCA  # Static mesh  - verified 32 bytes
    FORMAT_0BDA = 0x0BDA  # Skinned mesh - verified 40 bytes

    # Component ordering within the stride (V4.0 VERIFIED order):
    # Position → UV0 → UV1 → UV2 → BoneWts1 → BoneWts2 → Normal
    #          → Color → Tangent → Binormal → Unk400
    COMPONENT_ORDER = [
        ('POS_FLOAT',  POS_FLOAT,  12, 'pos_float'),
        ('POS_INT16',  POS_INT16,   8, 'pos_int16'),
        ('POS_HALF',   POS_HALF,    8, 'pos_half'),
        ('UV0',        UV0,         4, 'uv0'),
        ('UV1',        UV1,         4, 'uv1'),
        ('UV2',        UV2,         4, 'uv2'),
        ('BONE_WTS1',  BONE_WTS1,   8, 'bone_wts1'),
        ('BONE_WTS2',  BONE_WTS2,   8, 'bone_wts2'),
        ('NORMAL',     NORMAL,      4, 'normal'),
        ('COLOR',      COLOR,       4, 'color'),
        ('TANGENT',    TANGENT,     4, 'tangent'),
        ('BINORMAL',   BINORMAL,    4, 'binormal'),
        ('UNK_400',    UNK_400,     4, 'unk400'),
    ]

    @staticmethod
    def has_skinning(flags):
        return bool(flags & VertexFlags.BONE_WTS1)

    @staticmethod
    def calculate_stride(flags):
        """Calculate vertex stride from flags and return component offsets dict.
        Returns (stride, offsets) where offsets maps name -> byte_offset.
        """
        # Position flags are mutually exclusive — use only the first set one
        stride = 0
        offsets = {}
        pos_handled = False
        for name, flag, size, key in VertexFlags.COMPONENT_ORDER:
            is_pos = flag in (VertexFlags.POS_FLOAT, VertexFlags.POS_INT16, VertexFlags.POS_HALF)
            if is_pos:
                if pos_handled:
                    continue  # skip other pos flags
                if not (flags & flag):
                    continue
                pos_handled = True
            else:
                if not (flags & flag):
                    continue
            offsets[key] = stride
            stride += size
        return stride, offsets

    @staticmethod
    def validate(flags, actual_stride):
        """Check stride matches and log any issues."""
        calc, _ = VertexFlags.calculate_stride(flags)
        if calc != actual_stride:
            vlog.log(f"  WARNING: Stride mismatch! flags=0x{flags:04X} calc={calc} actual={actual_stride}")
            return False
        return True
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
    __slots__=('vert_pos_list','vert_uv_list','vert_uv1_list','vert_uv2_list','vert_color_list',
               'primitives','mat_list_info','skin_weight_list','skin_indice_list',
               'vert_count','face_count','vert_stride','vert_format_flags',
               'vert_section_offset','indice_section_offset',
               'lod_level','part_number','sub_part_index','vb_index',
               'xobb_chunk_offset','hpsb_chunk_offset','name_index')
    def __init__(self):
        self.vert_pos_list=[];self.vert_uv_list=[];self.vert_uv1_list=[];self.vert_uv2_list=[];self.vert_color_list=[]
        self.primitives=[];self.mat_list_info=[];self.skin_weight_list=[];self.skin_indice_list=[]
        self.vert_count=0;self.face_count=0;self.vert_stride=0;self.vert_format_flags=0
        self.vert_section_offset=0;self.indice_section_offset=0
        self.lod_level=0;self.part_number=0;self.sub_part_index=-1;self.vb_index=0
        self.xobb_chunk_offset=0;self.hpsb_chunk_offset=0;self.name_index=-1
    def add_primitive(self,indices,mat_idx,mat_name):prim=MeshPrimitive();prim.indices=indices;prim.material_index=mat_idx;prim.material_name=mat_name;self.primitives.append(prim)
    def has_skinning(self):return bool(self.vert_format_flags & VertexFlags.BONE_WTS1)
class SubMesh:
    __slots__=('header_data','bone_data','face_count')
    def __init__(self):self.header_data=[];self.bone_data=[];self.face_count=0
    def get_face_count(self):return self.header_data[1] if len(self.header_data)>1 else 0
def parse_mesh_vertices(g, mesh, vps, uvt, uvs):
    """Parse vertex buffer using a single bulk read + struct.unpack_from offsets.

    Replaces the previous per-vertex per-component approach (many tiny reads) with:
      1. One g.raw(count * stride) call to pull the whole vertex buffer into memory.
      2. struct.unpack_from at pre-computed byte offsets for each component.

    This eliminates O(count * num_components) file reads and format-string allocations,
    typically yielding a 4-8× speedup on the parse stage for large meshes.
    """
    flags  = mesh.vert_format_flags
    stride = mesh.vert_stride
    count  = mesh.vert_count

    VertexFlags.validate(flags, stride)

    has_uv0       = bool(flags & VertexFlags.UV0)
    has_uv1       = bool(flags & VertexFlags.UV1)
    has_uv2       = bool(flags & VertexFlags.UV2)
    has_bone      = bool(flags & VertexFlags.BONE_WTS1)
    has_col       = bool(flags & VertexFlags.COLOR)
    has_pos_float = bool(flags & VertexFlags.POS_FLOAT)

    vlog.log(f"\n=== PARSING VERTICES (LOD {mesh.lod_level}) ==="
             f"\nOffset: {mesh.vert_section_offset}  Count: {count}  Stride: {stride}"
             f"\nFlags: 0x{flags:04X}  UV0:{has_uv0} UV1:{has_uv1} UV2:{has_uv2}"
             f"  Skinned:{has_bone} Color:{has_col}")

    # Pre-compute component byte offsets once (avoids repeated calculate_stride calls)
    _, comp_off = VertexFlags.calculate_stride(flags)
    pos_off = comp_off.get('pos_float' if has_pos_float else 'pos_int16', 0)
    uv0_off = comp_off.get('uv0')
    uv1_off = comp_off.get('uv1')
    uv2_off = comp_off.get('uv2')
    bwt_off = comp_off.get('bone_wts1')
    col_off = comp_off.get('color')

    pos_fmt = '<3f' if has_pos_float else '<3h'

    # ── Single bulk read ──────────────────────────────────────────────────────
    g.seek(mesh.vert_section_offset)
    buf = g.raw(count * stride)  # one system call instead of count×components calls
    # ─────────────────────────────────────────────────────────────────────────

    # Local aliases — avoids repeated global/attribute lookups in the hot loop
    unpack_from = struct.unpack_from
    append_pos  = mesh.vert_pos_list.append
    append_uv   = mesh.vert_uv_list.append
    append_uv1  = mesh.vert_uv1_list.append
    append_uv2  = mesh.vert_uv2_list.append
    append_wt   = mesh.skin_weight_list.append
    append_si   = mesh.skin_indice_list.append
    append_col  = mesh.vert_color_list.append

    for v in range(count):
        base = v * stride

        # --- Position ---
        p = unpack_from(pos_fmt, buf, base + pos_off)
        append_pos([p[0] * vps, p[1] * vps, p[2] * vps])

        # --- UV0 ---
        if has_uv0:
            u, vr = unpack_from('<2h', buf, base + uv0_off)
            append_uv([uvt + u * uvs, 1.0 - (uvt + vr * uvs)])

        # --- UV1 ---
        if has_uv1:
            r1 = unpack_from('<2h', buf, base + uv1_off)
            if r1[0] != -32768 or r1[1] != -32768:
                append_uv1([uvt + r1[0] * uvs, 1.0 - (uvt + r1[1] * uvs)])
            else:
                append_uv1(None)  # sentinel: unused channel

        # --- UV2 ---
        if has_uv2:
            r2 = unpack_from('<2h', buf, base + uv2_off)
            if r2[0] != -32768 or r2[1] != -32768:
                append_uv2([uvt + r2[0] * uvs, 1.0 - (uvt + r2[1] * uvs)])
            else:
                append_uv2(None)

        # --- Bone weights (4 × uint8) then indices (4 × uint8) ---
        if has_bone:
            append_wt(unpack_from('<4B', buf, base + bwt_off))
            append_si(unpack_from('<4B', buf, base + bwt_off + 4))

        # --- Color (RGBA 4 × uint8) ---
        if has_col:
            append_col(unpack_from('<4B', buf, base + col_off))

        # Note: Normal, Tangent, Binormal, UNK_400 are read-at-import-time skipped;
        # offsets are stored in metadata for export-time normal re-encoding.

    vlog.log(f"Parsed {len(mesh.vert_pos_list)} vertices"
             + (f"  skinning:{len(mesh.skin_weight_list)}" if mesh.skin_weight_list else "")
             + (f"  colors:{len(mesh.vert_color_list)}"    if mesh.vert_color_list  else "")
             + (f"  uv1:{len(mesh.vert_uv1_list)}"         if mesh.vert_uv1_list    else ""))
def parse_sdol_chunk(g,meshes,lod_names={}):
    g.i(2);lod_count=g.i(1)[0]
    if lod_count==0:
        vlog.log("\n=== SDOL CHUNK ===\nSDOL lod_count=0, no data")
        return
    vlog.log(f"\n=== SDOL CHUNK (Mesh LODs) ===\nParsing {lod_count} LOD levels in SDOL...")
    mesh_dict={}
    # Loop through each LOD level
    for current_lod in range(lod_count):
        lod_dist=g.f(1)[0];vb_count=g.i(1)[0]
        # Read vertex buffer info
        vb_info=[]
        for vb in range(vb_count):
            vb_flags=g.i(1)[0];vb_stride=g.i(1)[0];vb_unk=g.i(1)[0];vb_offset=g.i(1)[0]
            vb_info.append((vb_flags,vb_stride,vb_offset))
        # Read submesh info
        submesh_count=g.i(1)[0];submesh_info=[]
        for sm in range(submesh_count):
            vb_idx=g.i(1)[0];lod_grp=g.i(1)[0];sub_idx=g.i(1)[0];idx_offset=g.i(1)[0];vert_marker=g.i(1)[0];unk1=g.i(1)[0];unk2=g.i(1)[0]
            submesh_info.append((vb_idx,lod_grp,sub_idx,idx_offset,vert_marker))
        submesh_data=[]
        for i in range(len(submesh_info)):
            vb_idx,lod_grp,sub_idx,idx_offset,vert_marker=submesh_info[i]
            if i+1<len(submesh_info):
                next_offset=submesh_info[i+1][3];idx_count=next_offset-idx_offset
            else:idx_count=-1
            submesh_data.append((vb_idx,lod_grp,sub_idx,idx_offset,idx_count))
        vert_section_size=g.I(1)[0];g.seekpad(16);vert_section_base=g.tell();g.seek(vert_section_base+vert_section_size)
        indice_section_size=g.I(1)[0];g.seekpad(16);indice_section_offset=g.tell();total_indices=indice_section_size;g.seek(indice_section_offset+indice_section_size*2)
        if submesh_data and submesh_data[-1][4]==-1:
            last=list(submesh_data[-1]);last[4]=total_indices-last[3];submesh_data[-1]=tuple(last)
        # Create meshes for this LOD level - one mesh per submesh
        for sm_idx,(vb_idx,lod_grp,sub_idx,idx_offset,idx_count) in enumerate(submesh_data):
            key=(current_lod,sm_idx)  # Unique per submesh
            mesh=Mesh()
            # CORRECTED: current_lod is the TRUE LOD level, sub_idx is the part number
            mesh.lod_level=current_lod;mesh.part_number=sub_idx;mesh.vb_index=vb_idx;mesh.indice_section_offset=indice_section_offset
            mesh.name_index=sm_idx  # CRITICAL: Use sm_idx (submesh index) for name lookup
            if vb_idx<len(vb_info):
                vb_flags,vb_stride,vb_offset=vb_info[vb_idx]
                mesh.vert_format_flags=vb_flags;mesh.vert_stride=vb_stride;mesh.vert_section_offset=vert_section_base+vb_offset
            # Each submesh gets its own mat_list_info entry
            mesh.mat_list_info.append((vb_idx,lod_grp,sub_idx,idx_offset,idx_count))
            mesh_dict[key]=mesh
        # Calculate vertex counts for meshes in this LOD
        for key,mesh in mesh_dict.items():
            if key[0]!=current_lod:continue  # Skip if not current LOD
            if mesh.vb_index<len(vb_info):
                vb_flags,vb_stride,vb_offset=vb_info[mesh.vb_index]
                if mesh.vb_index+1<len(vb_info):
                    next_offset=vb_info[mesh.vb_index+1][2];vb_size=next_offset-vb_offset
                else:vb_size=vert_section_size-vb_offset
                if vb_stride>0:mesh.vert_count=vb_size//vb_stride
                else:mesh.vert_count=0
            else:mesh.vert_count=0
    # Add all meshes to list
    for mesh in mesh_dict.values():meshes.append(mesh)
    # Detect and number sub-parts
    part_groups={}
    for mesh in mesh_dict.values():
        key=(mesh.lod_level,mesh.part_number)
        if key not in part_groups:part_groups[key]=[]
        part_groups[key].append(mesh)
    # If multiple meshes share the same (lod, part), they're sub-parts
    for key,ms in part_groups.items():
        if len(ms)>1:
            ms.sort(key=lambda m:m.vb_index)
            for i,mesh in enumerate(ms):mesh.sub_part_index=i
    # Group by LOD to show structure
    lods={}
    for m in mesh_dict.values():
        if m.lod_level not in lods:lods[m.lod_level]={}
        if m.part_number not in lods[m.lod_level]:lods[m.lod_level][m.part_number]=[]
        lods[m.lod_level][m.part_number].append(m)
    vlog.log("    Found structure:")
    for lod in sorted(lods.keys()):
        parts_info=[]
        for part in sorted(lods[lod].keys()):
            ms=lods[lod][part]
            if len(ms)==1:parts_info.append(f"P{part}")
            else:parts_info.append(f"P{part}({len(ms)} sub-parts)")
        # Use LOD name if available
        lod_display = lod_names.get(lod, [f"LOD{lod}"])[0] if lod in lod_names and lod_names[lod] else f"LOD{lod}"
        vlog.log(f"      {lod_display}: {', '.join(parts_info)}")
def parse_dnks_chunk(g, lod_count):
    """Parse DNKS chunk including LOD name entries and per-name bboxes.

    Returns: (sub_mesh_list, lod_names_dict, lod_name_bboxes)
      sub_mesh_list   : list-of-lists of SubMesh
      lod_names_dict  : {lod_index: [name, ...]}
      lod_name_bboxes : {lod_index: [(bbox_min, bbox_max, metric, name), ...]}
    """
    g.i(2); g.word(4); g.i(4); sub_mesh_list = []
    if lod_count == 0:
        vlog.log("Found DNKS chunk but LOD count is 0, skipping")
        return sub_mesh_list, {}, {}
    vlog.log(f"\n=== DNKS CHUNK (Skinning) ===\nProcessing {lod_count} LOD levels")
    for n in range(lod_count):
        lod_submeshes = []; mat_count = g.i(1)[0]
        vlog.log(f"\n  LOD {n}: {mat_count} submeshes")
        for m in range(mat_count):
            submesh = SubMesh()
            submesh.header_data = list(g.H(7))
            submesh.bone_data = list(g.h(48))
            submesh.face_count = submesh.get_face_count()
            valid_bones = sum(1 for b in submesh.bone_data if b != -1)
            mat_id = submesh.header_data[0]
            vlog.log_submesh(n, m, mat_id, valid_bones, submesh.face_count)
            lod_submeshes.append(submesh)
        sub_mesh_list.append(lod_submeshes)
    
    # ----------------------------------------------------------------
    # Parse LOD names and per-name bounding boxes
    # (all live inside the DNKS chunk per V4.0 spec)
    #
    # LOD name entry structure (V4.0 VERIFIED):
    #   +0x00  float[6]  BBox min/max (24 bytes)
    #   +0x18  float     Metric value  (4 bytes)
    #   +0x1C  int32     LOD index     (4 bytes)
    #   +0x20  int32     Reserved = 0  (4 bytes)
    #   +0x24  int32     String length (4 bytes)   ← pos in scan
    #   +0x28  char[]    Name string
    # ----------------------------------------------------------------
    lod_names_dict = {}
    lod_name_bboxes = {}  # {lod_idx: [(bbox_min, bbox_max, metric, name)]}

    try:
        vlog.log(f"\n=== LOD NAMES ===\nSearching inside DNKS chunk...")
        saved_pos = g.tell()
        lookahead_data = g.raw(65536)  # up to 64 KB
        g.seek(saved_pos)

        sdol_pos = lookahead_data.find(b'SDOL')
        if sdol_pos == -1:
            sdol_pos = len(lookahead_data)

        pos = 0
        name_entries = []

        while pos < sdol_pos - 20:
            try:
                if pos + 4 > len(lookahead_data):
                    break
                str_length = struct.unpack('<I', lookahead_data[pos:pos+4])[0]

                if not (5 <= str_length <= 100):
                    pos += 1; continue

                string_start = pos + 4
                if string_start + str_length > len(lookahead_data):
                    pos += 1; continue

                string_data = lookahead_data[string_start:string_start + str_length]
                if not all(32 <= b < 127 or b == 0 for b in string_data):
                    pos += 1; continue

                try:
                    name = string_data.split(b'\x00')[0].decode('ascii')
                except Exception:
                    pos += 1; continue

                if len(name) < 4:
                    pos += 1; continue

                # LOD index lives 8 bytes before str_length
                if pos < 8:
                    pos += 1; continue
                lod_index = struct.unpack('<I', lookahead_data[pos-8:pos-4])[0]
                if lod_index > lod_count + 10:
                    pos += 1; continue

                # Metric lives 12 bytes before str_length
                if pos < 12:
                    pos += 1; continue
                metric_value = struct.unpack('<f', lookahead_data[pos-12:pos-8])[0]

                # FEATURE 5: Bounding box lives 36 bytes before str_length
                # Structure: bbox_min(12) + bbox_max(12) + metric(4) + lod_idx(4) + reserved(4) + str_len
                bbox_min = bbox_max = None
                if pos >= 36:
                    try:
                        bbox_min = struct.unpack('<fff', lookahead_data[pos-36:pos-24])
                        bbox_max = struct.unpack('<fff', lookahead_data[pos-24:pos-12])
                        # Sanity: bbox values should be world-space floats
                        if not all(abs(v) < 100000 for v in bbox_min + bbox_max):
                            bbox_min = bbox_max = None
                    except Exception:
                        bbox_min = bbox_max = None

                entry = {
                    'offset': pos,
                    'lod_index': lod_index,
                    'name': name,
                    'metric': metric_value,
                    'length': str_length,
                    'bbox_min': bbox_min,
                    'bbox_max': bbox_max,
                }
                name_entries.append(entry)
                pos += 4 + str_length

            except Exception:
                pos += 1; continue

        # Organise into dicts
        for entry in name_entries:
            lod = entry['lod_index']
            name = entry['name']

            if lod not in lod_names_dict:
                lod_names_dict[lod] = []
            lod_names_dict[lod].append(name)

            # FEATURE 5: store per-name bbox
            if entry['bbox_min'] is not None:
                if lod not in lod_name_bboxes:
                    lod_name_bboxes[lod] = []
                lod_name_bboxes[lod].append(
                    (entry['bbox_min'], entry['bbox_max'], entry['metric'], name)
                )

        if name_entries:
            vlog.log(f"  Found {len(name_entries)} name entries")
            for lod in sorted(lod_names_dict.keys()):
                names = lod_names_dict[lod]
                vlog.log(f"  LOD {lod}: {len(names)} name(s)")
                for i, n in enumerate(names):
                    if i < 3 or len(names) <= 5:
                        vlog.log(f"    [{i}] {n}")
                    elif i == 3:
                        vlog.log(f"    ... ({len(names)-3} more)")
                        break
        else:
            vlog.log("  No LOD names found, using defaults")

    except Exception as e:
        vlog.log(f"  Could not read LOD names ({e}), using defaults")

    if not lod_names_dict:
        for lod in range(lod_count):
            lod_names_dict[lod] = [f"LOD{lod}"]

    return sub_mesh_list, lod_names_dict, lod_name_bboxes
