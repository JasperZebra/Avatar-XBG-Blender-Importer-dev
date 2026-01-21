def apply_uv_coordinates(mesh_data, mesh):
    if not mesh.vert_uv_list:return
    uv_layer = mesh_data.uv_layers.new(name="UVMap")
    for loop in mesh_data.loops:
        if loop.vertex_index < len(mesh.vert_uv_list):
            uv_layer.data[loop.index].uv = mesh.vert_uv_list[loop.vertex_index]
def flip_mesh_normals(mesh_objects):
    import bmesh
    for obj in mesh_objects:
        if obj.type != 'MESH':continue
        me = obj.data;bm = bmesh.new();bm.from_mesh(me)
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(me);bm.free();me.update()
