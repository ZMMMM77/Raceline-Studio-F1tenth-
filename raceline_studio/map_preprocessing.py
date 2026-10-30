"""Diagnostic layers for map-only imports; never change the collision raster."""
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from matplotlib import colormaps


def save_layers(map_data, directory):
    mask=map_data.extraction_free
    Image.fromarray(np.where(mask,254,0).astype(np.uint8)).save(directory/'extraction_mask.png')
    changes=np.asarray(map_data.image.convert('RGB')).copy()
    changes[mask & ~map_data.free]=[66,211,173]
    changes[~mask & map_data.free]=[255,171,102]
    Image.fromarray(changes).save(directory/'extraction_changes.png')
    # Exterior rooms must not dominate the color scale of the selected track.
    track_mask=map_data.extraction_track_free
    distance=distance_transform_edt(track_mask)*map_data.resolution
    maximum=float(distance.max())
    rgb=(colormaps['viridis'](distance/max(maximum,1e-9))[...,:3]*255).astype(np.uint8)
    rgb[~track_mask]=[19,30,44]
    Image.fromarray(rgb).save(directory/'distance_field.png')
    map_data.cleanup_info['distance_field_max_m']=maximum
    return {'cleaned':'extraction_mask.png','changes':'extraction_changes.png','distance':'distance_field.png'}
