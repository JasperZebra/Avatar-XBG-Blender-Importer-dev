import bpy, struct, os, math, mathutils
from .bounds import clamp_to_16bit
from .mesh import VertexFlags


class XBGExporter:
    def calculate_required_scale(self,obj,pos_scale,import_mesh_only=False):
        mesh=obj.data;obj_rotation=obj.rotation_euler.copy()
        if import_mesh_only and abs(obj_rotation.z-math.radians(180))<0.01:z_rot_inv=mathutils.Matrix.Rotation(-math.radians(180),4,'Z')
        elif abs(obj_rotation.z)>0.01:z_rot_inv=mathutils.Matrix.Rotation(-obj_rotation.z,4,'Z')
        else:z_rot_inv=mathutils.Matrix.Identity(4)
        max_value=32767;inv_scale=1.0/pos_scale;max_x=max_y=max_z=0
        for vertex in mesh.vertices:
            local_co=vertex.co;rotated_co=z_rot_inv@mathutils.Vector((local_co.x,local_co.y,local_co.z,1.0))
            px=abs(int(rotated_co.x*inv_scale));py=abs(int(rotated_co.y*inv_scale));pz=abs(int(rotated_co.z*inv_scale))
            max_x=max(max_x,px);max_y=max(max_y,py);max_z=max(max_z,pz)
        max_coord=max(max_x,max_y,max_z)
        if max_coord>max_value:
            scale_factor=max_value/max_coord;axis="X" if max_coord==max_x else ("Y" if max_coord==max_y else "Z")
            return True,scale_factor,f"{axis} axis: {max_coord} (limit: {max_value})"
        return False,1.0,"All coordinates within bounds"
    
    def export(self,context,obj,output_path,auto_scale=False,show_scale_info=True,ignore_limits=False):
        """Export single mesh or all meshes from the same XBG file"""
        if "xbg_data" not in obj:
            return {'CANCELLED'},"Selected object is not an imported XBG mesh (missing metadata)."
        
        meta=obj["xbg_data"].to_dict()
        original_path=meta["filepath"]
        
        if not os.path.exists(original_path):
            return {'CANCELLED'},f"Original XBG file not found at: {original_path}"
        
        # Find all meshes from the same XBG file
        all_meshes_to_export = []
        for scene_obj in context.scene.objects:
            if scene_obj.type == 'MESH' and "xbg_data" in scene_obj:
                obj_meta = scene_obj["xbg_data"].to_dict()
                if obj_meta.get("filepath") == original_path:
                    all_meshes_to_export.append(scene_obj)
        
        if not all_meshes_to_export:
            return {'CANCELLED'},"No valid meshes found to export"
        
        print(f"\n{'='*60}")
        print(f"EXPORTING {len(all_meshes_to_export)} MESH(ES) TO: {os.path.basename(original_path)}")
        print(f"{'='*60}\n")
        
        # Load original file
        with open(original_path,'rb') as f:
            file_data=bytearray(f.read())
        
        # Handle PMCP override if enabled
        using_pmcp_override = context.scene.xbg_export_settings.override_game_scale
        new_scale = None  # None = use original pos_scale for vertex encoding
        if using_pmcp_override:
            new_scale = context.scene.xbg_export_settings.target_game_scale
            try:
                offset = 4
                header_ints = struct.unpack_from('<7i', file_data, offset)
                chunk_count = header_ints[6]
                offset += 28
                for _ in range(chunk_count):
                    chunk_sig = file_data[offset:offset+4].decode('utf-8', 'ignore')
                    chunk_info = struct.unpack_from('<ii', file_data, offset+4)
                    chunk_size = chunk_info[1]
                    if chunk_sig == 'PMCP':
                        struct.pack_into('<f', file_data, offset + 4 + 8 + 8 + 4, new_scale)
                        print(f"Updated PMCP scale to {new_scale:.6f}")
                        break
                    offset += chunk_size
            except Exception as e:
                print(f"Warning: Could not update PMCP scale: {e}")
        
        # Export each mesh, passing new_scale so vertices are re-encoded with the
        # correct scale when PMCP override is active (Bug fix #7)
        total_clamped = 0
        for export_obj in all_meshes_to_export:
            clamped = self._export_single_mesh(context, export_obj, file_data, auto_scale, ignore_limits, new_scale)
            total_clamped += clamped
        
        # Write output file
        try:
            with open(output_path,'wb') as f_out:
                f_out.write(file_data)
            
            msg = f"Successfully exported {len(all_meshes_to_export)} mesh(es) to {output_path}"
            if using_pmcp_override:
                msg += f" (PMCP scale updated)"
            if total_clamped > 0:
                msg += f" (Warning: {total_clamped} vertices clamped across all meshes)"
            
            print(f"\n{'='*60}")
            print(f"EXPORT COMPLETE")
            print(f"{'='*60}\n")
            
            return {'FINISHED'}, msg
        except Exception as e:
            return {'CANCELLED'}, f"Failed to write file: {str(e)}"
    
    def _export_single_mesh(self, context, obj, file_data, auto_scale=False, ignore_limits=False, override_scale=None):
        """Export a single mesh's data to the file buffer.
        override_scale: when PMCP scale was changed, pass the new scale here so vertex
        positions are re-encoded against the new multiplier (Bug fix #7).
        """
        mesh = obj.data
        meta = obj["xbg_data"].to_dict()

        print(f"Exporting: {obj.name}")

        # Get vertex mapping (if compaction was used during import)
        vertex_mapping_raw = meta.get("vertex_mapping", None)
        original_vert_count = meta["vert_count"]

        # Convert string keys back to integers (Blender stores dict keys as strings)
        vertex_mapping = None
        if vertex_mapping_raw:
            vertex_mapping = {int(k): v for k, v in vertex_mapping_raw.items()}

        if vertex_mapping:
            print(f"  Using vertex mapping: {len(mesh.vertices)} vertices -> {original_vert_count} file positions")
            if len(mesh.vertices) != len(vertex_mapping):
                print(f"  WARNING: Vertex count mismatch ({len(mesh.vertices)} vs {len(vertex_mapping)} mapped), skipping")
                return 0
        else:
            if len(mesh.vertices) != original_vert_count:
                print(f"  WARNING: Vertex count mismatch ({len(mesh.vertices)} vs {original_vert_count}), skipping")
                return 0

        pos_scale = meta["pos_scale"]
        import_mesh_only = meta.get("import_mesh_only", False)

        # Bug fix #7: when PMCP scale is overridden, encode vertices with the NEW scale
        # so the game sees geometrically correct positions under the new multiplier.
        if override_scale is not None:
            effective_pos_scale = override_scale
            apply_scale = 1.0  # No geometric rescale needed; re-encoding handles it
        else:
            effective_pos_scale = pos_scale
            needs_scaling, required_scale, _ = self.calculate_required_scale(obj, pos_scale, import_mesh_only)
            apply_scale = required_scale if (needs_scaling and auto_scale) else 1.0

        # Get UV parameters
        uv_trans = meta["uv_trans"]
        uv_scale_raw = meta["uv_scale"]
        if isinstance(uv_scale_raw, (list, tuple)):
            uv_scale = uv_scale_raw[1] if len(uv_scale_raw) > 1 else uv_scale_raw[0]
        else:
            uv_scale = uv_scale_raw

        vert_offset = meta["vert_offset"]
        vert_stride = meta["vert_stride"]
        xobb_offset = meta.get("xobb_offset", 0)
        hpsb_offset = meta.get("hpsb_offset", 0)

        # Bug fix #4: use stored vertex format flags to compute correct UV + normal offsets
        vert_format_flags = meta.get("vert_format_flags", 0)
        if vert_format_flags:
            _, comp_offsets = VertexFlags.calculate_stride(vert_format_flags)
            uv0_byte_offset   = comp_offsets.get('uv0', 8)    # fallback: int16 pos = 8 bytes
            normal_byte_offset = comp_offsets.get('normal', None)
            has_normal = bool(vert_format_flags & VertexFlags.NORMAL)
        else:
            # Legacy fallback for meshes imported before vert_format_flags was stored
            uv0_byte_offset    = 8      # correct for all known 0x0BCA/0x0BDA formats
            normal_byte_offset = None
            has_normal         = False

        # Calculate rotation matrix
        obj_rotation = obj.rotation_euler.copy()
        if import_mesh_only and abs(obj_rotation.z - math.radians(180)) < 0.01:
            z_rot_inv = mathutils.Matrix.Rotation(-math.radians(180), 4, 'Z')
        elif abs(obj_rotation.z) > 0.01:
            z_rot_inv = mathutils.Matrix.Rotation(-obj_rotation.z, 4, 'Z')
        else:
            z_rot_inv = mathutils.Matrix.Identity(4)

        # Collect and average UVs per vertex
        uv_layer = mesh.uv_layers.active if mesh.uv_layers.active else None
        vert_uv_map = {}
        if uv_layer:
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    vert_idx = mesh.loops[loop_index].vertex_index
                    uv_coord = uv_layer.data[loop_index].uv
                    if vert_idx not in vert_uv_map:
                        vert_uv_map[vert_idx] = []
                    vert_uv_map[vert_idx].append((uv_coord.x, uv_coord.y))
            averaged_uvs = {
                vi: (
                    sum(u[0] for u in ul) / len(ul),
                    sum(u[1] for u in ul) / len(ul)
                )
                for vi, ul in vert_uv_map.items()
            }
        else:
            averaged_uvs = {}

        # Export vertex data
        clamped_count = 0
        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')
        inv_pos_scale = 1.0 / effective_pos_scale

        for v_idx, vertex in enumerate(mesh.vertices):
            original_idx = vertex_mapping[v_idx] if vertex_mapping else v_idx
            byte_off = vert_offset + (original_idx * vert_stride)

            local_co = vertex.co
            rotated_co = z_rot_inv @ mathutils.Vector((local_co.x, local_co.y, local_co.z, 1.0))
            fx, fy, fz = rotated_co.x, rotated_co.y, rotated_co.z

            if apply_scale != 1.0:
                fx *= apply_scale
                fy *= apply_scale
                fz *= apply_scale

            min_x = min(min_x, fx)
            min_y = min(min_y, fy)
            min_z = min(min_z, fz)
            max_x = max(max_x, fx)
            max_y = max(max_y, fy)
            max_z = max(max_z, fz)

            px_raw = int(fx * inv_pos_scale)
            py_raw = int(fy * inv_pos_scale)
            pz_raw = int(fz * inv_pos_scale)

            if ignore_limits:
                px = px_raw & 0xFFFF
                py = py_raw & 0xFFFF
                pz = pz_raw & 0xFFFF
                if px > 32767: px -= 65536
                if py > 32767: py -= 65536
                if pz > 32767: pz -= 65536
            else:
                px = clamp_to_16bit(px_raw)
                py = clamp_to_16bit(py_raw)
                pz = clamp_to_16bit(pz_raw)
                if px != px_raw or py != py_raw or pz != pz_raw:
                    clamped_count += 1

            struct.pack_into('<hhh', file_data, byte_off, px, py, pz)

            # UV0 — use dynamic offset (Bug fix #4: was hardcoded to +8)
            if v_idx in averaged_uvs:
                u_float, v_float_raw = averaged_uvs[v_idx]
                v_float = 1.0 - v_float_raw
                u_short = clamp_to_16bit(int((u_float - uv_trans) / uv_scale))
                v_short = clamp_to_16bit(int((v_float - uv_trans) / uv_scale))
                struct.pack_into('<hh', file_data, byte_off + uv0_byte_offset, u_short, v_short)

            # Normals — recalculate from Blender geometry and encode as int8 (Feature)
            if has_normal and normal_byte_offset is not None:
                vnorm = vertex.normal
                rot_n = z_rot_inv @ mathutils.Vector((vnorm.x, vnorm.y, vnorm.z, 0.0))
                nv = mathutils.Vector((rot_n.x, rot_n.y, rot_n.z))
                nl = nv.length
                if nl > 0.0001:
                    nv /= nl
                nx = max(-127, min(127, int(nv.x * 127)))
                ny = max(-127, min(127, int(nv.y * 127)))
                nz = max(-127, min(127, int(nv.z * 127)))
                struct.pack_into('<bbb', file_data, byte_off + normal_byte_offset, nx, ny, nz)

        # Update bounding box
        if xobb_offset > 0:
            try:
                struct.pack_into('<ffffff', file_data, xobb_offset + 20,
                                 min_x, min_y, min_z, max_x, max_y, max_z)
            except Exception:
                pass

        # Update bounding sphere
        if hpsb_offset > 0:
            try:
                center_x = (min_x + max_x) * 0.5
                center_y = (min_y + max_y) * 0.5
                center_z = (min_z + max_z) * 0.5
                radius = 0.0
                for vertex in mesh.vertices:
                    local_co = vertex.co
                    rotated_co = z_rot_inv @ mathutils.Vector((local_co.x, local_co.y, local_co.z, 1.0))
                    dx = rotated_co.x - center_x
                    dy = rotated_co.y - center_y
                    dz = rotated_co.z - center_z
                    radius = max(radius, (dx*dx + dy*dy + dz*dz)**0.5)
                struct.pack_into('<ffff', file_data, hpsb_offset + 20,
                                 center_x, center_y, center_z, radius)
            except Exception:
                pass

        status = []
        if clamped_count > 0:
            status.append(f"{clamped_count} vertices clamped")
        else:
            status.append("all vertices within bounds")
        if has_normal and normal_byte_offset is not None:
            status.append("normals exported")
        print(f"  ✓ {', '.join(status)}")

        return clamped_count
