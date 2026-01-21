def apply_vertex_weights(obj, armature_obj, mesh, verbose=False):
    if not armature_obj or not mesh.skin_indice_list or not mesh.skin_weight_list:
        return
    bone_names = [b.name for b in armature_obj.data.bones]
    v_groups = {name: obj.vertex_groups.new(name=name) for name in bone_names}
    for v_idx, (indices, weights) in enumerate(zip(mesh.skin_indice_list, mesh.skin_weight_list)):
        for b_idx_idx, b_id in enumerate(indices):
            weight = weights[b_idx_idx] / 255.0
            if weight > 0.0 and b_id < len(bone_names) and bone_names[b_id] in v_groups:
                v_groups[bone_names[b_id]].add([v_idx], weight, 'REPLACE')
def remap_skin_indices(mesh, sub_mesh_list):
    if not mesh.skin_indice_list or not mesh.mat_list_info:return
    vert_id_start = 0
    for info in mesh.mat_list_info:
        lod_grp, sub_idx = info[1], info[2]
        if lod_grp < len(sub_mesh_list):
            submesh = sub_mesh_list[lod_grp][sub_idx] if sub_idx < len(sub_mesh_list[lod_grp]) else None
            if submesh:
                count = submesh.header_data[5];palette = submesh.bone_data
                end = min(vert_id_start + count, len(mesh.skin_indice_list))
                for v_idx in range(vert_id_start, end):
                    mesh.skin_indice_list[v_idx] = tuple((palette[r] if r < len(palette) and palette[r] != -1 else 0) for r in mesh.skin_indice_list[v_idx])
                vert_id_start += count
