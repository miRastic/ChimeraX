# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

def bumps(session, volume, center = None, max_radius = None, base_area = 10.0, height = 1.0,
          marker_radius = 1.0, color = (100,200,100,255), name = 'bumps', all_extrema = False):
    '''
    Find protrusions on T-cells in 3d light microscopy.

    Algorithm finds points on contour surface whose distance from a center point is locally maximal
    then extends to neighbor grid points inside the surface as long as the border area (ie protrusion
    base area) is less than a specified value.  Protrusions of sufficient height are marked.  A marker
    closer to the center and within another protrusion is not marked.

    Parameters
    ----------
    volume : Volume
        Map to find protrusions on.  Highest surface contour level used.
    center : Center
        Point which is the cell center for finding radial protrusions.
    max_radius : float or None
        How far out from center to look for protrusions.
    base_area : float
        Area of base of protrusion.  Protrusion is extended inward until this
        area is attained and that defines the protrusion height.
    height : float
        Minimum height of a protrusion to be marked.
    marker_radius : float
        Size of marker spheres to place at protrusion tips.
    color : uint8 4-tuple
        Color of markers.  Default light green.
    name : string
        Name of created marker model. Default "bumps".
    all_extrema : bool
        Whether to mark all radial extrema even if the don't meet the protrusion height minimum.
        Markers within another protrusion are colored yellow, ones that never attain the specified
        protrusion base_area (often smal disconnected density blobs) are colored pink, markers
        on protrusions that are too short are colored blue.
    '''

    c = center.scene_coordinates()
    r, ijk = radial_extrema(volume, c, max_radius)
    size_hvc = protrusion_sizes(r, ijk, volume.data, base_area, log = session.logger)

    if all_extrema:
        from numpy import arange
        keep = arange(len(ijk))
    else:
        keep = [i for i,(h,v,con) in enumerate(size_hvc) if h and con and h > height]
    xyz = volume.data.ijk_to_xyz_transform * ijk[keep]
    colors = marker_colors([size_hvc[i] for i in keep], height, color)
    create_markers(session, xyz, marker_radius, colors, name)

    msg = 'Found %d bumps, minimum height %.3g, base area %.3g' % (len(xyz), height, base_area)
    session.logger.status(msg, log=True)
    
def register_bumps_command(logger):

    from chimerax.core.commands import CmdDesc, register, CenterArg, FloatArg, Color8Arg, StringArg, BoolArg
    from chimerax.core.map import MapArg

    desc = CmdDesc(
        required = [('volume', MapArg)],
        keyword = [('center', CenterArg),
                   ('max_radius', FloatArg),
                   ('base_area', FloatArg),
                   ('height', FloatArg),
                   ('marker_radius', FloatArg),
                   ('color', Color8Arg),
                   ('name', StringArg),
                   ('all_extrema', BoolArg),],
        required_arguments = ['center'],
        synopsis = 'Mark protrusions in 3D image data'
    )
    register('bumps', desc, bumps, logger=logger)

def radial_extrema(volume, center_point, max_radius):
    level = max(volume.surface_levels)
    m = volume.full_matrix()
    d = volume.data
    r = radius_map(d, center_point)
    r *= (m >= level)
    rmax = local_maxima(r)
    if max_radius is not None:
        rmax *= (rmax <= max_radius)
    from numpy import array
    ijk = array(rmax.nonzero()[::-1]).transpose()
    return r, ijk

def protrusion_sizes(r, ijk, data, base_area, log = None):
    covered = set()
    rval = r[ijk[:,2],ijk[:,1],ijk[:,0]]
    from numpy import argsort
    ro = argsort(rval)[::-1]
    sizes = [None]*len(ro)
    for c,o in enumerate(ro):
        p = ijk[o]
        if tuple(p) in covered:
            h = v = None
        else:
            voxel_volume = data.step[0]*data.step[1]*data.step[2]
            from math import pow
            voxel_area = pow(voxel_volume, 2/3)
            base_count = base_area / voxel_area
            h, v, con, reached = protrusion_height(r, p, base_count)
            covered.update(reached)
            v *= voxel_volume
        sizes[o] = (h,v,con)
        if c % 10 == 0 and log is not None:
            log.status('Protrusion height %d of %d' % (c, len(ijk)))
    return sizes

def radius_map(data, center_point):
    # Compute radius map.
    from numpy import indices, float32, sqrt
    i = indices(data.size[::-1], dtype = float32)
    cijk = data.xyz_to_ijk(center_point)
    step = data.step
    for a in (0,1,2):
        i[a] -= cijk[2-a]
        i[a] *= step[2-a]
    i *= i
    r2 = i.sum(axis=0)
    r = sqrt(r2)
    return r

def local_maxima(a):
    ac = a.copy()
    ksz,jsz,isz = a.shape
    #dirs = ((1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1))	# 6 principal axes directions
    # Use 26 nearest neighbor directions.
    dirs = [(i,j,k) for i in (-1,0,1) for j in (-1,0,1) for k in (-1,0,1) if i != 0 or j != 0 or k != 0]
    for i,j,k in dirs:
        is1,is2 = (slice(0,isz-i),slice(i,isz)) if i >= 0 else (slice(-i,isz),slice(0,isz+i))
        js1,js2 = (slice(0,jsz-j),slice(j,jsz)) if j >= 0 else (slice(-j,jsz),slice(0,jsz+j))
        ks1,ks2 = (slice(0,ksz-k),slice(k,ksz)) if k >= 0 else (slice(-k,ksz),slice(0,ksz+k))
        ac[ks1,js1,is1] *= (a[ks1,js1,is1] > a[ks2,js2,is2])
    return ac

def marker_colors(size_hvc, height, normal_color):
    colors = []
    for h,v,con in size_hvc:
        if h is None:
            color = (255,255,0,255)  # Covered by another peak
        elif not con:
            color = (255,100,100,255)  # Not connected to cell
        elif h < height:
            color = (0,0,255,255)    # Too short
        else:
            color = normal_color
        colors.append(color)
    return colors

def create_markers(session, xyz, radius, colors, name):
    if len(xyz) == 0:
        return None
    from chimerax.markers import MarkerSet
    m = MarkerSet(session, name)
    for i,(p,rgba) in enumerate(zip(xyz,colors)):
        m.create_marker(p, rgba, radius, i)
    session.models.add([m])
    return m

def protrusion_height(a, start, base_count):
    s = tuple(start)
    r0 = a[s[2],s[1],s[0]]
    hmax = 0
    border = [(0,s)]
    reached = set()
    reached.add(s)
    prot = set()	# Points that are part of protrusion.
    fill = set()	# Watershed spill points
    bounds = (a.shape[2], a.shape[1], a.shape[0])
    volume = 0
    from heapq import heappop, heappush
    while border and len(border) <= base_count:
        h, b = heappop(border)
        if h >= hmax:
            hmax = h
            volume += 1
            prot.add(b)
            if fill:
                # Only add watershed spill points if the filled basin
                # can be added before base_count is reached.
                prot.update(fill)
                volume += len(fill)
                fill.clear()
        else:
            fill.add(b)
        for s in neighbors(b, bounds):
            if s not in reached:
                reached.add(s)
                r = a[s[2],s[1],s[0]]
                if r > 0:
                    heappush(border, (r0-r,s))
    con = (len(border) > 0)
    return hmax, volume, con, prot

def neighbors(ijk, ijk_max):
    i0,j0,k0 = ijk
    isz,jsz,ksz = ijk_max
    n = [(i0+i,j0+j,k0+k) for i in (-1,0,1) for j in (-1,0,1) for k in (-1,0,1)
         if ((i != 0 or j != 0 or k != 0)
             and k0+k>=0 and j0+j>=0 and i0+i>=0
             and k0+k<ksz and j0+j<jsz and i0+i<isz)]
    return n
    
