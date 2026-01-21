import bpy,os
from bpy_extras.image_utils import load_image
from .materials import XBMMaterialData
from .xbt import XBTConverter
class BlenderMaterialSetup:
    @staticmethod
    def setup_material(mat,xbm_data,data_folder,load_hd_textures=True,import_as_dds=False):
        if not mat.use_nodes:mat.use_nodes=True
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        bsdf=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
        if not bsdf:bsdf=nodes.new('ShaderNodeBsdfPrincipled');bsdf.location=(0,0)
        output=next((n for n in nodes if n.type=='OUTPUT_MATERIAL'),None)
        if not output:output=nodes.new('ShaderNodeOutputMaterial');output.location=(300,0)
        if not bsdf.outputs['BSDF'].links:links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
        tex_y_offset=300;needs_tiling=(xbm_data.diffuse_tiling!=1.0 or xbm_data.specular_tiling!=1.0 or xbm_data.normal_tiling!=1.0)
        tex_coord=None;mapping_nodes={}
        if needs_tiling:
            tex_coord=nodes.new('ShaderNodeTexCoord');tex_coord.location=(-1200,0)
            for tex_type,tiling in [('diffuse',xbm_data.diffuse_tiling),('specular',xbm_data.specular_tiling),('normal',xbm_data.normal_tiling)]:
                if tiling!=1.0:mapping=nodes.new('ShaderNodeMapping');mapping.location=(-1000,tex_y_offset);mapping.inputs['Scale'].default_value=(tiling,tiling,1.0);links.new(tex_coord.outputs['UV'],mapping.inputs['Vector']);mapping_nodes[tex_type]=mapping;tex_y_offset-=200
        tex_y_offset=300
        if 'diffuse' in xbm_data.textures:tex_y_offset=BlenderMaterialSetup._setup_diffuse(nodes,links,bsdf,xbm_data.textures['diffuse'],data_folder,mapping_nodes.get('diffuse'),tex_y_offset,load_hd_textures,import_as_dds)
        if 'specular' in xbm_data.textures:tex_y_offset=BlenderMaterialSetup._setup_specular(nodes,links,bsdf,xbm_data.textures['specular'],data_folder,mapping_nodes.get('specular'),tex_y_offset,load_hd_textures,import_as_dds)
        if 'normal' in xbm_data.textures:tex_y_offset=BlenderMaterialSetup._setup_normal(nodes,links,bsdf,xbm_data.textures['normal'],data_folder,mapping_nodes.get('normal'),tex_y_offset,load_hd_textures,import_as_dds)
        if 'bio' in xbm_data.textures:
            use_color_multiply=False
            if xbm_data.illumination_color:r,g,b=xbm_data.illumination_color;is_black=(abs(r)<0.01 and abs(g)<0.01 and abs(b)<0.01);is_white=(abs(r-1.0)<0.01 and abs(g-1.0)<0.01 and abs(b-1.0)<0.01);use_color_multiply=not (is_black or is_white)
            tex_y_offset=BlenderMaterialSetup._setup_bio_emission(nodes,links,bsdf,xbm_data.textures['bio'],xbm_data.illumination_color if use_color_multiply else None,data_folder,tex_y_offset,load_hd_textures,import_as_dds)
    @staticmethod
    def _load_texture_node(nodes,texture_path,data_folder,location,non_color=False,load_hd_textures=True,import_as_dds=False):
        actual_path=XBTConverter.find_mip0_variant(texture_path,data_folder) if load_hd_textures else texture_path
        actual_path=actual_path if actual_path else texture_path
        full_path=os.path.join(data_folder,actual_path.replace('\\',os.sep).replace('/',os.sep))
        if not os.path.exists(full_path):return None
        texture_file_path=XBTConverter.get_temp_texture_path(full_path,import_as_dds)
        if not texture_file_path:return None
        # Determine actual format from the file path
        actual_ext=os.path.splitext(texture_file_path)[1].lower()
        base_name=os.path.splitext(os.path.basename(texture_path))[0]
        # Use the actual extension of the converted file
        img_name=f"{base_name}{actual_ext}"
        img=bpy.data.images.get(img_name)
        if not img:
            try:
                # Use load_image utility which handles conversions properly
                img=load_image(texture_file_path,check_existing=False)
                if img:
                    img.name=img_name
                    img.pack()
                    non_color and setattr(img.colorspace_settings,'name','Non-Color')
                else:
                    return None
            except Exception as e:
                print(f"Failed to load texture {img_name}: {e}")
                return None
        tex_node=nodes.new('ShaderNodeTexImage');tex_node.location=location;tex_node.image=img
        return tex_node
    @staticmethod
    def _setup_diffuse(nodes,links,bsdf,texture_path,data_folder,mapping_node,y_offset,load_hd_textures=True,import_as_dds=False):
        tex_node=BlenderMaterialSetup._load_texture_node(nodes,texture_path,data_folder,(-600,y_offset),non_color=False,load_hd_textures=load_hd_textures,import_as_dds=import_as_dds)
        if tex_node:
            if mapping_node:links.new(mapping_node.outputs['Vector'],tex_node.inputs['Vector'])
            links.new(tex_node.outputs['Color'],bsdf.inputs['Base Color']);links.new(tex_node.outputs['Alpha'],bsdf.inputs['Alpha'])
        return y_offset-300
    @staticmethod
    def _setup_specular(nodes,links,bsdf,texture_path,data_folder,mapping_node,y_offset,load_hd_textures=True,import_as_dds=False):
        tex_node=BlenderMaterialSetup._load_texture_node(nodes,texture_path,data_folder,(-600,y_offset),non_color=True,load_hd_textures=load_hd_textures,import_as_dds=import_as_dds)
        if tex_node:
            if mapping_node:links.new(mapping_node.outputs['Vector'],tex_node.inputs['Vector'])
            if 'IOR Level' in bsdf.inputs:links.new(tex_node.outputs['Color'],bsdf.inputs['IOR Level'])
            elif 'Specular IOR Level' in bsdf.inputs:links.new(tex_node.outputs['Color'],bsdf.inputs['Specular IOR Level'])
            elif 'Specular' in bsdf.inputs:links.new(tex_node.outputs['Color'],bsdf.inputs['Specular'])
        return y_offset-300
    @staticmethod
    def _setup_normal(nodes,links,bsdf,texture_path,data_folder,mapping_node,y_offset,load_hd_textures=True,import_as_dds=False):
        tex_node=BlenderMaterialSetup._load_texture_node(nodes,texture_path,data_folder,(-900,y_offset),non_color=True,load_hd_textures=load_hd_textures,import_as_dds=import_as_dds)
        if tex_node:
            if mapping_node:links.new(mapping_node.outputs['Vector'],tex_node.inputs['Vector'])
            try:combine_node=nodes.new('ShaderNodeCombineColor')
            except:combine_node=nodes.new('ShaderNodeCombineRGB')
            combine_node.location=(-600,y_offset);links.new(tex_node.outputs['Color'],combine_node.inputs[1]);links.new(tex_node.outputs['Alpha'],combine_node.inputs[0]);combine_node.inputs[2].default_value=1.0
            normal_map=nodes.new('ShaderNodeNormalMap');normal_map.location=(-300,y_offset);normal_map.inputs['Strength'].default_value=1.0
            links.new(combine_node.outputs[0],normal_map.inputs['Color']);links.new(normal_map.outputs['Normal'],bsdf.inputs['Normal'])
        return y_offset-400
    @staticmethod
    def _setup_bio_emission(nodes,links,bsdf,texture_path,illumination_color,data_folder,y_offset,load_hd_textures=True,import_as_dds=False):
        tex_node=BlenderMaterialSetup._load_texture_node(nodes,texture_path,data_folder,(-600,y_offset),non_color=False,load_hd_textures=load_hd_textures,import_as_dds=import_as_dds)
        if tex_node:
            if illumination_color:
                try:multiply_node=nodes.new('ShaderNodeMix');multiply_node.data_type='RGBA';multiply_node.blend_type='MULTIPLY';multiply_node.inputs['Factor'].default_value=1.0
                except:multiply_node=nodes.new('ShaderNodeMixRGB');multiply_node.blend_type='MULTIPLY';multiply_node.inputs['Fac'].default_value=1.0
                multiply_node.location=(-300,y_offset)
                if 'A' in multiply_node.inputs:links.new(tex_node.outputs['Color'],multiply_node.inputs['A'])
                elif 'Color1' in multiply_node.inputs:links.new(tex_node.outputs['Color'],multiply_node.inputs['Color1'])
                else:links.new(tex_node.outputs['Color'],multiply_node.inputs[6])
                if 'B' in multiply_node.inputs:multiply_node.inputs['B'].default_value=(*illumination_color,1.0)
                elif 'Color2' in multiply_node.inputs:multiply_node.inputs['Color2'].default_value=(*illumination_color,1.0)
                else:multiply_node.inputs[7].default_value=(*illumination_color,1.0)
                output_socket=multiply_node.outputs['Result'] if 'Result' in multiply_node.outputs else multiply_node.outputs['Color'] if 'Color' in multiply_node.outputs else multiply_node.outputs[0]
                if 'Emission Color' in bsdf.inputs:links.new(output_socket,bsdf.inputs['Emission Color'])
                elif 'Emission' in bsdf.inputs:links.new(output_socket,bsdf.inputs['Emission'])
            else:
                if 'Emission Color' in bsdf.inputs:links.new(tex_node.outputs['Color'],bsdf.inputs['Emission Color'])
                elif 'Emission' in bsdf.inputs:links.new(tex_node.outputs['Color'],bsdf.inputs['Emission'])
            if 'Emission Strength' in bsdf.inputs:bsdf.inputs['Emission Strength'].default_value=1.0
        return y_offset-300
