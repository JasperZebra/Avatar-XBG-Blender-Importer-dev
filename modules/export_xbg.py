import bpy,struct,os,math,mathutils
from .bounds import clamp_to_16bit
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
        if "xbg_data" not in obj:return {'CANCELLED'},"Selected object is not an imported XBG mesh (missing metadata)."
        meta=obj["xbg_data"].to_dict();original_path=meta["filepath"]
        if not os.path.exists(original_path):return {'CANCELLED'},f"Original XBG file not found at: {original_path}"
        mesh=obj.data
        if len(mesh.vertices)!=meta["vert_count"]:return {'CANCELLED'},f"Topology Error: Vertex count changed ({len(mesh.vertices)} vs {meta['vert_count']})"
        pos_scale=meta["pos_scale"];import_mesh_only=meta.get("import_mesh_only",False)
        using_pmcp_override=context.scene.xbg_export_settings.override_game_scale
        if using_pmcp_override:needs_scaling=False;required_scale=1.0;scale_info="Using PMCP scale override";apply_scale=1.0
        else:needs_scaling,required_scale,scale_info=self.calculate_required_scale(obj,pos_scale,import_mesh_only);apply_scale=1.0
        if needs_scaling and not using_pmcp_override:
            if ignore_limits:print(f"\n{'='*60}\nIGNORE FORMAT LIMITS ENABLED - EXPORTING INVALID DATA\n{'='*60}\n")
            elif auto_scale:apply_scale=required_scale;print(f"\n{'='*60}\nMESH EXCEEDS FORMAT BOUNDS - AUTO-SCALING ENABLED\n{'='*60}\n")
        with open(original_path,'rb') as f:file_data=bytearray(f.read())
        export_pos_scale=meta["pos_scale"]
        if context.scene.xbg_export_settings.override_game_scale:
            new_scale=context.scene.xbg_export_settings.target_game_scale;export_pos_scale=new_scale
            try:
                offset=4;header_ints=struct.unpack_from('<7i',file_data,offset);chunk_count=header_ints[6];offset+=28
                for _ in range(chunk_count):
                    chunk_sig=file_data[offset:offset+4].decode('utf-8','ignore');chunk_info=struct.unpack_from('<ii',file_data,offset+4);chunk_size=chunk_info[1]
                    if chunk_sig=='PMCP':struct.pack_into('<f',file_data,offset+4+8+8+4,new_scale);break
                    offset+=chunk_size
            except:pass
        uv_trans=meta["uv_trans"];uv_scale=meta["uv_scale"];vert_offset=meta["vert_offset"];vert_stride=meta["vert_stride"]
        xobb_offset=meta.get("xobb_offset",0);hpsb_offset=meta.get("hpsb_offset",0);obj_rotation=obj.rotation_euler.copy()
        if import_mesh_only and abs(obj_rotation.z-math.radians(180))<0.01:z_rot_inv=mathutils.Matrix.Rotation(-math.radians(180),4,'Z')
        elif abs(obj_rotation.z)>0.01:z_rot_inv=mathutils.Matrix.Rotation(-obj_rotation.z,4,'Z')
        else:z_rot_inv=mathutils.Matrix.Identity(4)
        uv_layer=mesh.uv_layers.active.data if mesh.uv_layers.active else None;vert_to_loop=[0]*len(mesh.vertices)
        for poly in mesh.polygons:
            for loop_index in poly.loop_indices:vert_to_loop[mesh.loops[loop_index].vertex_index]=loop_index
        clamped_count=0;min_x=min_y=min_z=float('inf');max_x=max_y=max_z=float('-inf');inv_pos_scale=1.0/pos_scale
        for v_idx,vertex in enumerate(mesh.vertices):
            offset=vert_offset+(v_idx*vert_stride);local_co=vertex.co
            rotated_co=z_rot_inv@mathutils.Vector((local_co.x,local_co.y,local_co.z,1.0))
            fx,fy,fz=rotated_co.x,rotated_co.y,rotated_co.z
            if apply_scale!=1.0:fx*=apply_scale;fy*=apply_scale;fz*=apply_scale
            min_x=min(min_x,fx);min_y=min(min_y,fy);min_z=min(min_z,fz);max_x=max(max_x,fx);max_y=max(max_y,fy);max_z=max(max_z,fz)
            px_raw=int(fx*inv_pos_scale);py_raw=int(fy*inv_pos_scale);pz_raw=int(fz*inv_pos_scale)
            if ignore_limits:
                px=px_raw&0xFFFF;py=py_raw&0xFFFF;pz=pz_raw&0xFFFF
                if px>32767:px-=65536
                if py>32767:py-=65536
                if pz>32767:pz-=65536
            else:
                px=clamp_to_16bit(px_raw);py=clamp_to_16bit(py_raw);pz=clamp_to_16bit(pz_raw)
                if px!=px_raw or py!=py_raw or pz!=pz_raw:clamped_count+=1
            struct.pack_into('<hhh',file_data,offset,px,py,pz)
            if uv_layer:
                loop_idx=vert_to_loop[v_idx];uv=uv_layer[loop_idx].uv;u_float=uv.x;v_float=1.0-uv.y
                u_short=clamp_to_16bit(int((u_float-uv_trans)/uv_scale));v_short=clamp_to_16bit(int((v_float-uv_trans)/uv_scale))
                struct.pack_into('<hh',file_data,offset+8,u_short,v_short)
        if xobb_offset>0:
            try:struct.pack_into('<ffffff',file_data,xobb_offset+20,min_x,min_y,min_z,max_x,max_y,max_z)
            except:pass
        if hpsb_offset>0:
            try:
                center_x=(min_x+max_x)*0.5;center_y=(min_y+max_y)*0.5;center_z=(min_z+max_z)*0.5;radius=0.0
                for vertex in mesh.vertices:
                    local_co=vertex.co;rotated_co=z_rot_inv@mathutils.Vector((local_co.x,local_co.y,local_co.z,1.0))
                    dx=rotated_co.x-center_x;dy=rotated_co.y-center_y;dz=rotated_co.z-center_z
                    radius=max(radius,(dx*dx+dy*dy+dz*dz)**0.5)
                struct.pack_into('<ffff',file_data,hpsb_offset+20,center_x,center_y,center_z,radius)
            except:pass
        try:
            with open(output_path,'wb') as f_out:f_out.write(file_data)
            msg=f"Successfully exported to {output_path}"
            if using_pmcp_override:msg+=f" (PMCP scale updated to {export_pos_scale:.6f})"
            elif ignore_limits and needs_scaling:msg+=f" (WARNING: Exported with invalid 16-bit values!)"
            elif clamped_count>0:msg+=f" (Warning: {clamped_count} vertices clamped)"
            elif apply_scale!=1.0:msg+=f" (Auto-scaled by {apply_scale:.4f}x)"
            return {'FINISHED'},msg
        except Exception as e:return {'CANCELLED'},f"Failed to write file: {str(e)}"
