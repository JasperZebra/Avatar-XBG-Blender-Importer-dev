import bpy,bmesh,math,mathutils
class VerboseLogger:
    enabled=False
    _p=staticmethod(print)
    @staticmethod
    def log(m):VerboseLogger.enabled and VerboseLogger._p(m)
    @staticmethod
    def log_chunk(c,o,s):VerboseLogger.enabled and VerboseLogger._p(f"\n{'='*60}\nCHUNK FOUND: {c}\n  Offset: {o} (0x{o:08X})\n  Size: {s} bytes\n{'='*60}")
    @staticmethod
    def log_pmcp(sc,u):VerboseLogger.enabled and VerboseLogger._p(f"\nPMCP CHUNK DETAILS:\n  Position Scale: {sc}\n  Unknown Value: {u}\n  16-bit range: -32768 to 32767\n  World coordinate range: {-32768*sc:.3f} to {32767*sc:.3f}")
    @staticmethod
    def log_pmcu(t,s):VerboseLogger.enabled and VerboseLogger._p(f"\nPMCU CHUNK DETAILS:\n  UV Translation: {t}\n  UV Scale: {s}")
    @staticmethod
    def log_bone(i,n,p,po,r):VerboseLogger.enabled and VerboseLogger._p(f"\n  BONE {i}: {n}\n    Parent ID: {p}\n    Local Position: ({po[0]:.6f}, {po[1]:.6f}, {po[2]:.6f})\n    Local Rotation (quat x,y,z,w): ({r[0]:.6f}, {r[1]:.6f}, {r[2]:.6f}, {r[3]:.6f})")
    @staticmethod
    def log_bone_world_transform(i,n,w):VerboseLogger.enabled and VerboseLogger._p(f"    World Position: ({w[0]:.6f}, {w[1]:.6f}, {w[2]:.6f})")
    @staticmethod
    def log_mesh_header(l,v,f,s):
        si="✓ Skinning data present (stride=40)" if s==40 else f"✗ No skinning data (stride={s}, expected 40)"
        VerboseLogger.enabled and VerboseLogger._p(f"\n  MESH LOD {l}:\n    Vertex Count: {v}\n    Face Count: {f}\n    Vertex Stride: {s} bytes\n    {si}")
    @staticmethod
    def log_material(i,n,p):VerboseLogger.enabled and VerboseLogger._p(f"\n  MATERIAL {i}: {n}\n    Path: {p}")
    @staticmethod
    def log_submesh(l,i,m,b,f):VerboseLogger.enabled and VerboseLogger._p(f"\n    SUBMESH LOD{l}_{i}:\n      Material ID: {m}\n      Bones in Palette: {b}\n      Face Count: {f}")
    @staticmethod
    def log_xml_bone(n,p,r,pa):
        pi=f"\n    Parent: {pa}" if pa else ""
        VerboseLogger.enabled and VerboseLogger._p(f"\n  XML BONE: {n}\n    Position: ({p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f})\n    Rotation (w,x,y,z): ({r[0]:.6f}, {r[1]:.6f}, {r[2]:.6f}, {r[3]:.6f}){pi}")
    @staticmethod
    def log_bounds(bmi,bma,sc,sr):VerboseLogger.enabled and VerboseLogger._p(f"\nBOUNDING VOLUMES:\n  Box Min: ({bmi[0]:.3f}, {bmi[1]:.3f}, {bmi[2]:.3f})\n  Box Max: ({bma[0]:.3f}, {bma[1]:.3f}, {bma[2]:.3f})\n  Sphere Center: ({sc[0]:.3f}, {sc[1]:.3f}, {sc[2]:.3f})\n  Sphere Radius: {sr:.3f}")
def auto_smooth_normals(objs):
    VerboseLogger.log("\n=== AUTO SMOOTH NORMALS ===")
    for obj in objs:
        if obj.type!='MESH':continue
        for poly in obj.data.polygons:poly.use_smooth=True
        VerboseLogger.log(f"  ✓ Applied smooth shading to: {obj.name}")
def merge_duplicate_vertices(objs,dist):
    VerboseLogger.log(f"\n=== MERGE DUPLICATE VERTICES ===\nMerge Distance: {dist:.6f}")
    tb=ta=0
    for obj in objs:
        if obj.type!='MESH':continue
        me=obj.data;vb=len(me.vertices);tb+=vb
        bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=dist)
        bm.to_mesh(me);bm.free();me.update()
        va=len(me.vertices);ta+=va
        if va<vb:VerboseLogger.log(f"  {obj.name}: {vb} → {va} (-{vb-va})")
    VerboseLogger.log(f"\nTotal vertices removed: {tb-ta}")
def flip_normals(objs):
    VerboseLogger.log("\n=== FLIP NORMALS ===")
    for obj in objs:
        if obj.type!='MESH':continue
        me=obj.data;bm=bmesh.new();bm.from_mesh(me);bmesh.ops.reverse_faces(bm,faces=bm.faces[:])
        bm.to_mesh(me);bm.free();me.update()
        VerboseLogger.log(f"  ✓ Flipped normals: {obj.name}")
def create_format_bounds_lattice(ctx,ps,name="XBG_Format_Bounds"):
    mc=-32768*ps;Mc=32767*ps;cx=cy=cz=(mc+Mc)/2;dim=Mc-mc
    ld=bpy.data.lattices.new(name);ld.points_u=ld.points_v=ld.points_w=2
    lo=bpy.data.objects.new(name,ld);ctx.collection.objects.link(lo)
    lo.location=(cx,cy,cz);lo.scale=(dim,dim,dim);lo.show_in_front=True
    VerboseLogger.log(f"\n=== XBG FORMAT BOUNDS LATTICE ===\n16-bit range: -32768 to 32767\nPosition scale: {ps}\nWorld coordinate range: {mc:.3f} to {Mc:.3f}\nTotal dimension: {dim:.3f}\n⚠ WARNING: Vertices outside this box will be clamped during export!")
    return lo
def create_bounding_box_visualization(ctx,bbox,idx,dt):
    c=[(bbox.min[0]+bbox.max[0])/2,(bbox.min[1]+bbox.max[1])/2,(bbox.min[2]+bbox.max[2])/2]
    d=[bbox.max[0]-bbox.min[0],bbox.max[1]-bbox.min[1],bbox.max[2]-bbox.min[2]]
    if dt=='LATTICE':
        ld=bpy.data.lattices.new(f"BBoxLattice_LOD{idx}");ld.points_u=ld.points_v=ld.points_w=2
        lo=bpy.data.objects.new(f"BoundingBox_LOD{idx}",ld);ctx.collection.objects.link(lo)
        lo.location=c;lo.scale=[di/2 for di in d];return lo
    else:
        bpy.ops.mesh.primitive_cube_add(size=1,location=c);bo=ctx.active_object
        bo.name=f"BoundingBox_LOD{idx}";bo.scale=[di/2 for di in d]
        if dt=='WIRE':bo.display_type='WIRE'
        elif dt=='SOLID':
            mat=bpy.data.materials.new(name=f"BBox_Mat_LOD{idx}");mat.use_nodes=True
            bsdf=mat.node_tree.nodes.get('Principled BSDF')
            if bsdf:bsdf.inputs['Alpha'].default_value=0.3;bsdf.inputs['Base Color'].default_value=(0,1,0,1)
            mat.blend_method='BLEND';bo.data.materials.append(mat)
        return bo
def create_bounding_sphere_visualization(ctx,sphere,idx,dt):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=sphere.radius,location=sphere.center,segments=32,ring_count=16)
    so=ctx.active_object;so.name=f"BoundingSphere_LOD{idx}"
    if dt=='WIRE' or dt=='LATTICE':so.display_type='WIRE'
    elif dt=='SOLID':
        mat=bpy.data.materials.new(name=f"BSphere_Mat_LOD{idx}");mat.use_nodes=True
        bsdf=mat.node_tree.nodes.get('Principled BSDF')
        if bsdf:bsdf.inputs['Alpha'].default_value=0.3;bsdf.inputs['Base Color'].default_value=(1,0,0,1)
        mat.blend_method='BLEND';so.data.materials.append(mat)
    return so
def create_bounding_visualizations(ctx,data,objs,sb,ss,dt):
    if sb and data.bounding_boxes:
        VerboseLogger.log("\n=== CREATING BOUNDING BOX VISUALIZATIONS ===")
        for i,bbox in enumerate(data.bounding_boxes):create_bounding_box_visualization(ctx,bbox,i,dt)
    if ss and data.bounding_spheres:
        VerboseLogger.log("\n=== CREATING BOUNDING SPHERE VISUALIZATIONS ===")
        for i,sphere in enumerate(data.bounding_spheres):create_bounding_sphere_visualization(ctx,sphere,i,dt)
def analyze_export_scale(obj,ps,imo):
    if not VerboseLogger.enabled:return
    VerboseLogger.log("\n"+"="*60+"\nEXPORT SCALE ANALYSIS\n"+"="*60)
    mesh=obj.data;rot=obj.rotation_euler.copy()
    if imo and abs(rot.z-math.radians(180))<0.01:zr=mathutils.Matrix.Rotation(-math.radians(180),4,'Z')
    elif abs(rot.z)>0.01:zr=mathutils.Matrix.Rotation(-rot.z,4,'Z')
    else:zr=mathutils.Matrix.Identity(4)
    mx=my=mz=0;mnx=mny=mnz=float('inf');Mx=My=Mz=float('-inf')
    for v in mesh.vertices:
        rc=zr@mathutils.Vector((v.co.x,v.co.y,v.co.z,1.0));fc=mathutils.Vector((rc.x,rc.y,rc.z))
        px=int(fc.x/ps);py=int(fc.y/ps);pz=int(fc.z/ps)
        mx=max(mx,abs(px));my=max(my,abs(py));mz=max(mz,abs(pz))
        mnx=min(mnx,fc.x);Mx=max(Mx,fc.x);mny=min(mny,fc.y);My=max(My,fc.y);mnz=min(mnz,fc.z);Mz=max(Mz,fc.z)
    mc=max(mx,my,mz);mv=32767
    VerboseLogger.log(f"\nPosition Scale: {ps}\n16-bit range: -32768 to {mv}\n\nWorld Space Bounds:\n  X: {mnx:.3f} to {Mx:.3f}\n  Y: {mny:.3f} to {My:.3f}\n  Z: {mnz:.3f} to {Mz:.3f}\n\n16-bit Integer Space (absolute max):\n  X: {mx} (limit: {mv})\n  Y: {my} (limit: {mv})\n  Z: {mz} (limit: {mv})")
    if mc>mv:
        sn=mv/mc
        VerboseLogger.log(f"\n⚠ EXCEEDS BOUNDS!\n  Exceeded by: {mc-mv}\n  Scale factor needed: {sn:.6f}\n  = Reduce to {sn*100:.2f}% of current size\n  = Scale down by {1/sn:.2f}x")
    else:
        VerboseLogger.log(f"\n✓ FITS WITHIN BOUNDS\n  Headroom: {mv-mc} units\n  Using {(mc/mv)*100:.2f}% of available range")
    VerboseLogger.log("="*60)
def display_file_info(chunks,fn,filepath=""):
    import struct
    
    # Helper functions to read binary data
    def read_int(data, pos):
        try:
            return struct.unpack('<I', data[pos:pos+4])[0]
        except:
            return 0
    
    def read_float(data, pos):
        try:
            return round(struct.unpack('<f', data[pos:pos+4])[0], 6)
        except:
            return 0.0
    
    def read_vector3(data, pos):
        try:
            x = read_float(data, pos)
            y = read_float(data, pos + 4)
            z = read_float(data, pos + 8)
            return (x, y, z)
        except:
            return (0.0, 0.0, 0.0)
    
    # Read the actual file data if filepath provided
    file_data = None
    file_size = 0
    if filepath:
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()
                file_size = len(file_data)
        except:
            pass
    
    # Chunk name mapping: Original -> (Display Name, Description)
    # Using full descriptive names since we have space on one line
    ci={
        "HSEM": ("Header", "File Header"),
        "PMCP": ("Vertex Scale", "Position Scaling"),
        "PMCU": ("UV Scale", "UV Coordinate Scaling"),
        "HPSB": ("Bounding Sphere", "Spherical Bounds"),
        "XOBB": ("Bounding Box", "Box Bounds"),
        "SDOL": ("LOD System", "Level of Detail"),
        "DOL": ("Mesh Data", "Loaded Geometry"),
        "EDON": ("Skeleton", "Bone Hierarchy"),
        "LTMR": ("Materials", "Material List"),
        "DNKS": ("Skinning", "Vertex Weights"),
        "DIKS": ("Bone Index", "Bone Metadata"),
        "MB2O": ("Mesh Object", "Mesh Definition"),
        "SULC": ("Clusters", "Mesh Clusters")
    }
    
    # Build comprehensive info string
    lines = []
    lines.append(f"File: {fn}")
    lines.append(f"Chunks: {len(chunks)}")
    lines.append("")
    
    # Parse each chunk and display inline with details on new lines
    for chunk_name, offset, size in chunks:
        rn, desc = ci.get(chunk_name, (chunk_name[::-1], "?"))
        
        # Display chunk header
        lines.append(f"{chunk_name}->{rn}:")
        
        # Read actual values for specific chunks
        if file_data and offset + 40 < len(file_data):
            if chunk_name == "LTMR":
                # LTMR: +20=material count (3rd int in array of 4)
                mat_count = read_int(file_data, offset + 20)
                lines.append(f"  Mats={mat_count}")
                    
            elif chunk_name == "EDON":
                # EDON: +20=bone count (3rd int in array)
                bone_count = read_int(file_data, offset + 20)
                lines.append(f"  Bones={bone_count}")
                
            elif chunk_name == "MB2O":
                # Just show the reversed name
                pass
                
            elif chunk_name == "DIKS":
                # DIKS: +20=LOD count
                lod_count = read_int(file_data, offset + 20)
                lines.append(f"  LODs={lod_count}")
                
            elif chunk_name == "DNKS":
                # Just show the reversed name
                pass
                    
            elif chunk_name == "SDOL":
                # SDOL Structure based on Structure.py:
                # After 'SDOL' signature (4 bytes)
                # +4: chunk_int1 (4 bytes)
                # +8: chunk_int2 (4 bytes)
                # +12: skip 2 ints (8 bytes)
                # +20: LOD count (4 bytes)
                # Then for each LOD:
                #   - Read 6 ints (LOD header)
                #   - [0] = distance (as float)
                #   - [1] = face_count
                #   - [3] = vert_stride
                #   - [4] = vert_count
                
                # Read LOD count at offset +20
                lod_count = read_int(file_data, offset + 20)
                lines.append(f"  LODs={lod_count}")
                
                # Parse each LOD distance
                # Start reading LOD data after: signature(4) + 2 ints(8) + 2 skip ints(8) + lod_count(4) = 24 bytes
                lod_pos = offset + 24
                
                for lod_idx in range(lod_count):
                    # Read the 6-integer LOD header
                    try:
                        lod_int0 = read_int(file_data, lod_pos)
                        lod_int1 = read_int(file_data, lod_pos + 4)
                        lod_int2 = read_int(file_data, lod_pos + 8)
                        vert_stride = read_int(file_data, lod_pos + 12)
                        vert_count = read_int(file_data, lod_pos + 16)
                        lod_int5 = read_int(file_data, lod_pos + 20)
                        
                        # Interpret header[0] as float - this is the LOD distance
                        import struct as st
                        distance = st.unpack('<f', st.pack('<I', lod_int0))[0]
                        
                        lines.append(f"  LOD{lod_idx}: Dist={distance:.1f} Verts={vert_count} Stride={vert_stride}")
                        
                        # Skip past this LOD's data to get to the next one
                        # This is complex - we'd need to parse material lists, vertex data, etc.
                        # For now, just show what we can read from the header
                        lod_pos += 24  # Skip the 6 ints we just read
                        
                        # Read material list count and skip it
                        if lod_pos + 4 < len(file_data):
                            mat_list_count = read_int(file_data, lod_pos)
                            lod_pos += 4 + (mat_list_count * 7 * 4)  # Skip material entries (7 ints each)
                            
                            # Read vertex section size and skip vertex data
                            if lod_pos + 4 < len(file_data):
                                vert_section_size = read_int(file_data, lod_pos)
                                lod_pos += 4
                                
                                # Align to 16-byte boundary
                                remainder = lod_pos % 16
                                if remainder != 0:
                                    lod_pos += 16 - remainder
                                
                                # Skip vertex data
                                lod_pos += vert_section_size
                                
                                # Read index section size and skip index data
                                if lod_pos + 4 < len(file_data):
                                    index_section_size = read_int(file_data, lod_pos)
                                    lod_pos += 4
                                    
                                    # Align to 16-byte boundary
                                    remainder = lod_pos % 16
                                    if remainder != 0:
                                        lod_pos += 16 - remainder
                                    
                                    # Skip index data (size * 2 because indices are 16-bit)
                                    lod_pos += index_section_size * 2
                    except:
                        # If we can't parse more LODs, break
                        break
                
            elif chunk_name == "XOBB":
                # XOBB: +20=min vector, +32=max vector
                min_vec = read_vector3(file_data, offset + 20)
                max_vec = read_vector3(file_data, offset + 32)
                dx = max_vec[0] - min_vec[0]
                dy = max_vec[1] - min_vec[1]
                dz = max_vec[2] - min_vec[2]
                volume = dx * dy * dz
                lines.append(f"  Vol={volume:.2f}")
                lines.append(f"  Min: ({min_vec[0]:.3f}, {min_vec[1]:.3f}, {min_vec[2]:.3f})")
                lines.append(f"  Max: ({max_vec[0]:.3f}, {max_vec[1]:.3f}, {max_vec[2]:.3f})")
                
            elif chunk_name == "HPSB":
                # HPSB: +20=center, +32=radius
                center = read_vector3(file_data, offset + 20)
                radius = read_float(file_data, offset + 32)
                volume = (4.0 / 3.0) * 3.14159 * (radius ** 3)
                lines.append(f"  R={radius:.3f}")
                lines.append(f"  Center: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
                lines.append(f"  Volume: {volume:.2f}")
                
            elif chunk_name == "DOL":
                # DOL = Currently loaded/imported mesh
                lines.append(f"  Imported Geometry")
                
            elif chunk_name == "PMCP":
                # PMCP: +20=unknown float, +24=vertex position scale
                chunk_int1 = read_int(file_data, offset + 4)
                chunk_int2 = read_int(file_data, offset + 8)
                skip_int1 = read_int(file_data, offset + 12)
                skip_int2 = read_int(file_data, offset + 16)
                float1 = read_float(file_data, offset + 20)
                vertex_scale = read_float(file_data, offset + 24)
                lines.append(f"  VertexScale: {vertex_scale:.9f}")
                lines.append(f"  ChunkInts: [{chunk_int1}, {chunk_int2}]")
                lines.append(f"  SkipInts: [{skip_int1}, {skip_int2}]")
                lines.append(f"  Float1(unk): {float1:.6f}")
                
            elif chunk_name == "PMCU":
                # PMCU: +20=UV translation, +24=UV scale
                chunk_int1 = read_int(file_data, offset + 4)
                chunk_int2 = read_int(file_data, offset + 8)
                skip_int1 = read_int(file_data, offset + 12)
                skip_int2 = read_int(file_data, offset + 16)
                uv_trans = read_float(file_data, offset + 20)
                uv_scale = read_float(file_data, offset + 24)
                lines.append(f"  Trans={uv_trans:.6f} Scale={uv_scale:.6f}")
                lines.append(f"  ChunkInts: [{chunk_int1}, {chunk_int2}]")
                lines.append(f"  SkipInts: [{skip_int1}, {skip_int2}]")
                lines.append(f"  UV_Trans: {uv_trans:.6f}")
                lines.append(f"  UV_Scale: {uv_scale:.6f}")
    
    lines.append("")
    lines.append(f"File Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    
    return "\n".join(lines)
