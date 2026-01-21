import struct,os,re
class XBMMaterialData:
    def __init__(self):self.textures={};self.illumination_color=None;self.diffuse_tiling=1.0;self.specular_tiling=1.0;self.normal_tiling=1.0
class XBMParser:
    @staticmethod
    def parse(fp,lhd=True):
        try:
            with open(fp,'rb') as f:data=f.read()
            result=XBMMaterialData()
            XBMParser._extract_textures(data,result);XBMParser._extract_illumination_color(data,result);XBMParser._extract_tiling(data,result);XBMParser._find_missing_textures(result,fp,lhd)
            return result
        except:return None
    @staticmethod
    def _extract_textures(data,result):
        found_textures={}
        for match in re.finditer(rb'graphics[/\\][^\x00]{10,200}\.xbt',data):
            try:
                path=match.group().decode('ascii',errors='ignore');basename=os.path.basename(path).lower();is_mip0='_mip0.xbt' in basename
                tex_type=None
                if '_d.xbt' in basename or '_d_mip0.xbt' in basename:tex_type='diffuse'
                elif '_n.xbt' in basename or '_n_mip0.xbt' in basename:tex_type='normal'
                elif '_s.xbt' in basename or '_s_mip0.xbt' in basename:tex_type='specular'
                elif '_m.xbt' in basename or '_m_mip0.xbt' in basename:tex_type='bio'
                if tex_type:
                    if tex_type not in found_textures:found_textures[tex_type]={'mip0':None,'regular':None}
                    found_textures[tex_type]['mip0' if is_mip0 else 'regular']=path
                else:result.textures[basename]=path
            except:continue
        for tex_type,versions in found_textures.items():result.textures[tex_type]=versions['mip0'] if versions['mip0'] else versions['regular'] if versions['regular'] else None
    @staticmethod
    def _extract_illumination_color(data,result):
        for term in [b'IlluminationColor1',b'illuminationcolor1']:
            pos=data.find(term)
            if pos!=-1:
                val_pos=pos+len(term)
                while val_pos<len(data) and data[val_pos]==0:val_pos+=1
                if val_pos+12<=len(data):
                    try:
                        r,g,b=struct.unpack('<f',data[val_pos:val_pos+4])[0],struct.unpack('<f',data[val_pos+4:val_pos+8])[0],struct.unpack('<f',data[val_pos+8:val_pos+12])[0]
                        max_val=max(r,g,b,1.0)
                        result.illumination_color=(r/max_val,g/max_val,b/max_val) if max_val>0 else (0.0,0.0,0.0)
                        return
                    except:pass
    @staticmethod
    def _extract_tiling(data,result):
        for search_term,attr_name in [(b'DiffuseTiling1','diffuse_tiling'),(b'SpecularTiling1','specular_tiling'),(b'NormalTiling1','normal_tiling')]:
            pos=data.find(search_term)
            if pos!=-1:
                val_pos=pos+len(search_term)
                while val_pos<len(data) and data[val_pos]==0:val_pos+=1
                if val_pos+4<=len(data):
                    try:
                        value=struct.unpack('<f',data[val_pos:val_pos+4])[0]
                        if 0.001<abs(value)<1000:setattr(result,attr_name,value)
                    except:pass
    @staticmethod
    def _find_missing_textures(result,xbm_filepath,lhd=True):
        xbm_dir=os.path.dirname(xbm_filepath);data_folder=xbm_dir
        while data_folder and not data_folder.endswith('Data'):
            parent=os.path.dirname(data_folder)
            if parent==data_folder:break
            data_folder=parent
        if not data_folder or not os.path.exists(data_folder):return
        reference_texture=None
        for tex_type in ['diffuse','normal','specular','bio']:
            if tex_type in result.textures:reference_texture=result.textures[tex_type];break
        if not reference_texture:return
        basename=os.path.basename(reference_texture).lower().replace('.xbt','')
        for suffix in ['_d','_n','_s','_m','_mip0']:
            if basename.endswith(suffix):basename=basename[:-len(suffix)];break
        texture_dir=os.path.dirname(reference_texture)
        texture_types=[('diffuse','_d.xbt','_d_mip0.xbt'),('normal','_n.xbt','_n_mip0.xbt'),('specular','_s.xbt','_s_mip0.xbt'),('bio','_m.xbt','_m_mip0.xbt')]
        for tex_type,suffix,mip0_suffix in texture_types:
            if tex_type in result.textures:
                current_path=result.textures[tex_type]
                if lhd and '_mip0.xbt' not in current_path.lower():
                    potential_path=texture_dir+'/'+basename+mip0_suffix
                    if os.path.exists(os.path.join(data_folder,potential_path.replace('\\',os.sep).replace('/',os.sep))):result.textures[tex_type]=potential_path
            else:
                if lhd:
                    mip0_path=texture_dir+'/'+basename+mip0_suffix
                    if os.path.exists(os.path.join(data_folder,mip0_path.replace('\\',os.sep).replace('/',os.sep))):result.textures[tex_type]=mip0_path;continue
                regular_path=texture_dir+'/'+basename+suffix
                if os.path.exists(os.path.join(data_folder,regular_path.replace('\\',os.sep).replace('/',os.sep))):result.textures[tex_type]=regular_path
