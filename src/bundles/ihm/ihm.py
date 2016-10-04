# vim: set expandtab shiftwidth=4 softtabstop=4:

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

"""
ihm: Integrative Hybrid Model file format support
=================================================
"""
def read_ihm(session, filename, name, *args, load_linked_files = True, **kw):
    """Read an integrative hybrid models file creating sphere models and restraint models

    :param filename: either the name of a file or a file-like object

    Extra arguments are ignored.
    """

    if hasattr(filename, 'read'):
        # Got a stream
        stream = filename
        filename = stream.name
        stream.close()

    from os.path import basename, splitext
    name = splitext(basename(filename))[0]
    from chimerax.core.models import Model
    ihm_model = Model(name, session)

    table_names = ['ihm_struct_assembly', 'ihm_model_list', 'ihm_sphere_obj_site', 'ihm_cross_link_restraint',
                   'ihm_ensemble_info', 'ihm_gaussian_obj_ensemble', 'ihm_dataset_other']
    from chimerax.core.atomic import mmcif
    table_list = mmcif.get_mmcif_tables(filename, table_names)
    tables = dict(zip(table_names, table_list))

    acomp = assembly_components(tables['ihm_struct_assembly'])
    
    gmodels = make_model_groups(session, tables['ihm_model_list'])
    for g in gmodels[1:]:
        g.display = False	# Only show first group.
    ihm_model.add(gmodels)
    
    smodels = make_sphere_models(session, tables['ihm_sphere_obj_site'], gmodels, acomp)

    xlinks = []
    xlink_table = tables['ihm_cross_link_restraint']
    if xlink_table is not None:
        xlinks = make_crosslink_pseudobonds(session, xlink_table, smodels)

    pgrids = []
    ensembles_table = tables['ihm_ensemble_info']
    gaussian_table = tables['ihm_gaussian_obj_ensemble']
    if ensembles_table is not None and gaussian_table is not None:
        pgrids = make_probability_grids(session, ensembles_table, gaussian_table, gmodels)

    lmodels = []
    datasets_table = tables['ihm_dataset_other']
    if datasets_table and load_linked_files:
        lmodels = read_linked_datasets(session, datasets_table, gmodels, acomp)
        if lmodels:
            from chimerax.core.models import Model
            comp_group = Model('Comparative models', session)
            comp_group.add(lmodels)
            ihm_model.add([comp_group])
        
    msg = ('Opened IHM file %s containing %d model groups, %d sphere models, %d distance restraints, %d ensemble distributions, %d linked models' %
           (filename, len(gmodels), len(smodels), len(xlinks), len(pgrids), len(lmodels)))
    return [ihm_model], msg

# -----------------------------------------------------------------------------
#
class Assembly:
    def __init__(self, assembly_id, entity_id, entity_description, asym_id, seq_beg, seq_end):
        self.assembly_id = assembly_id
        self.entity_id = entity_id
        self.entity_description = entity_description
        self.asym_id = asym_id
        self.seq_begin = seq_beg
        self.seq_end = seq_end

# -----------------------------------------------------------------------------
#
def assembly_components(ihm_struct_assembly_table):
    sa_fields = [
        'assembly_id',
        'entity_description',
        'entity_id',
        'asym_id',
        'seq_id_begin',
        'seq_id_end']
    sa = ihm_struct_assembly_table.fields(sa_fields)
    acomp = [Assembly(aid, eid, edesc, asym_id, seq_beg, seq_end)
             for aid, edesc, eid, asym_id, seq_beg, seq_end in sa]
    return acomp
    
# -----------------------------------------------------------------------------
#
def make_model_groups(session, ihm_model_list_table):
    ml_fields = [
        'model_id',
        'model_group_id',
        'model_group_name',]
    ml = ihm_model_list_table.fields(ml_fields)
    gm = {}
    for mid, gid, gname in ml:
        gm.setdefault((gid, gname), []).append(mid)
    models = []
    from chimerax.core.models import Model
    for (gid, gname), mid_list in gm.items():
        m = Model(gname, session)
        m.ihm_group_id = gid
        m.ihm_model_ids = mid_list
        models.append(m)
    models.sort(key = lambda m: m.ihm_group_id)
    return models

# -----------------------------------------------------------------------------
#
def make_sphere_models(session, spheres_obj_site, group_models, acomp):

    sos_fields = [
        'seq_id_begin',
        'seq_id_end',
        'asym_id',
        'cartn_x',
        'cartn_y',
        'cartn_z',
        'object_radius',
        'model_id']
    spheres = spheres_obj_site.fields(sos_fields)
    mspheres = {}
    for seq_beg, seq_end, asym_id, x, y, z, radius, model_id in spheres:
        sb, se = int(seq_beg), int(seq_end)
        xyz = float(x), float(y), float(z)
        r = float(radius)
        mspheres.setdefault(model_id, {}).setdefault(asym_id, []).append((sb,se,xyz,r))

    aname = {a.asym_id:a.entity_description for a in acomp}
    smodels = []
    for mid, asym_spheres in mspheres.items():
        sm = SphereModel(mid, session)
        smodels.append(sm)
        models = [SphereAsymModel(session, aname[asym_id], asym_id, mid, slist)
                  for asym_id, slist in asym_spheres.items()]
        models.sort(key = lambda m: m.asym_id)
        sm.add_asym_models(models)
    smodels.sort(key = lambda m: m.ihm_model_id)
    for sm in smodels[1:]:
        sm.display = False

    # Add sphere models to group
    gmodel = {id:g for g in group_models for id in g.ihm_model_ids}
    for m in smodels:
        gmodel[m.ihm_model_id].add([m])

    return smodels

# -----------------------------------------------------------------------------
#
def make_crosslink_pseudobonds(session, xlink_restraint, smodels,
                               radius = 1.0,
                               color = (0,255,0,255),		# Green
                               long_color = (255,0,0,255)):	# Red

    xlink_fields = [
        'asym_id_1',
        'seq_id_1',
        'asym_id_2',
        'seq_id_2',
        'type',
        'distance_threshold'
        ]
    xlink_rows = xlink_restraint.fields(xlink_fields)
    xlinks = {}
    for asym_id_1, seq_id_1, asym_id_2, seq_id_2, type, distance_threshold in xlink_rows:
        xl = ((asym_id_1, int(seq_id_1)), (asym_id_2, int(seq_id_2)), float(distance_threshold))
        xlinks.setdefault(type, []).append(xl)

    if not xlinks:
        return xlinks
    
    for sm in smodels:
        pbgs = []
        for type, xl in xlinks.items():
            xname = '%d %s crosslinks %s' % (len(xl), type, sm.ihm_model_id)
            g = session.pb_manager.get_group(xname)
            # g.name = xname
            pbgs.append(g)
            for (asym1, seq1), (asym2, seq2), d in xl:
                m1, m2 = sm.asym_model(asym1), sm.asym_model(asym2)
                s1, s2 = m1.residue_sphere(seq1), m2.residue_sphere(seq2)
                if s1 and s2 and s1 is not s2:
                    b = g.new_pseudobond(s1, s2)
                    b.color = long_color if b.length > d else color
                    b.radius = radius
                    b.halfbond = False
                    b.restraint_distance = d
        sm.add(pbgs)

    return xlinks

# -----------------------------------------------------------------------------
#
def make_probability_grids(session, ensemble_table, gaussian_table, group_models,
                           level = 0.2, opacity = 0.5):
    '''Level sets surface threshold so that fraction of mass is outside the surface.'''

    ensemble_fields = ['ensemble_id', 'model_group_id', 'num_ensemble_models']
    ens = ensemble_table.fields(ensemble_fields)
    ens_group = {id:(gid,int(n)) for id, gid, n in ens}
    
    gauss_fields = ['asym_id',
                   'mean_cartn_x',
                   'mean_cartn_y',
                   'mean_cartn_z',
                   'weight',
                   'covariance_matrix[1][1]',
                   'covariance_matrix[1][2]',
                   'covariance_matrix[1][3]',
                   'covariance_matrix[2][1]',
                   'covariance_matrix[2][2]',
                   'covariance_matrix[2][3]',
                   'covariance_matrix[3][1]',
                   'covariance_matrix[3][2]',
                   'covariance_matrix[3][3]',
                   'ensemble_id']
    cov = {}	# Map model_id to dictionary mapping asym id to list of (weight,center,covariance) triples
    gauss_rows = gaussian_table.fields(gauss_fields)
    from numpy import array, float64
    for asym_id, x, y, z, w, c11, c12, c13, c21, c22, c23, c31, c32, c33, eid in gauss_rows:
        center = array((float(x), float(y), float(z)), float64)
        weight = float(w)
        covar = array(((float(c11),float(c12),float(c13)),
                       (float(c21),float(c22),float(c23)),
                       (float(c31),float(c32),float(c33))), float64)
        cov.setdefault(eid, {}).setdefault(asym_id, []).append((weight, center, covar))

    # Compute probability volume models
    pmods = []
    gmodel = {id:g for g in group_models for id in g.ihm_model_ids}
    from chimerax.core.models import Model
    from chimerax.core.map import volume_from_grid_data
    from chimerax.core.atomic.colors import chain_rgba
    first_model_id = min(cov.keys())
    for ensemble_id, asym_gaussians in cov.items():
        gid, n = ens_group[ensemble_id]
        m = Model('Ensemble %s of %d models' % (ensemble_id, n), session)
        gmodel[gid].add([m])
        pmods.append(m)
        for asym_id in sorted(asym_gaussians.keys()):
            g = probability_grid(asym_gaussians[asym_id])
            g.name = '%s Gaussians' % asym_id
            g.rgba = chain_rgba(asym_id)[:3] + (opacity,)
            v = volume_from_grid_data(g, session, show_data = False,
                                      open_model = False, show_dialog = False)
            v.initialize_thresholds()
            ms = v.matrix_value_statistics()
            vlev = ms.mass_rank_data_value(level)
            v.set_parameters(surface_levels = [vlev])
            v.show()
            m.add([v])

    return pmods

# -----------------------------------------------------------------------------
#
def probability_grid(wcc, voxel_size = 5, cutoff_sigmas = 3):
    # Find bounding box for probability distribution
    from chimerax.core.geometry import Bounds, union_bounds
    from math import sqrt, ceil
    bounds = []
    for weight, center, covar in wcc:
        sigmas = [sqrt(covar[a,a]) for a in range(3)]
        xyz_min = [x-s for x,s in zip(center,sigmas)]
        xyz_max = [x+s for x,s in zip(center,sigmas)]
        bounds.append(Bounds(xyz_min, xyz_max))
    b = union_bounds(bounds)
    isize,jsize,ksize = [int(ceil(s  / voxel_size)) for s in b.size()]
    from numpy import zeros, float32, array
    a = zeros((ksize,jsize,isize), float32)
    xyz0 = b.xyz_min
    vsize = array((voxel_size, voxel_size, voxel_size), float32)

    # Add Gaussians to probability distribution
    for weight, center, covar in wcc:
        acenter = (center - xyz0) / vsize
        cov = covar.copy()
        cov *= 1/(voxel_size*voxel_size)
        add_gaussian(weight, acenter, cov, a)

    from chimerax.core.map.data import Array_Grid_Data
    g = Array_Grid_Data(a, origin = xyz0, step = vsize)
    return g

# -----------------------------------------------------------------------------
#
def add_gaussian(weight, center, covar, array):

    from numpy import linalg
    cinv = linalg.inv(covar)
    d = linalg.det(covar)
    from math import pow, sqrt, pi
    s = weight * pow(2*pi, -1.5) / sqrt(d)	# Normalization to sum 1.
    covariance_sum(cinv, center, s, array)

# -----------------------------------------------------------------------------
#
def covariance_sum(cinv, center, s, array):
    from numpy import dot
    from math import exp
    ksize, jsize, isize = array.shape
    i0,j0,k0 = center
    for k in range(ksize):
        for j in range(jsize):
            for i in range(isize):
                v = (i-i0, j-j0, k-k0)
                array[k,j,i] += s*exp(-0.5*dot(v, dot(cinv, v)))

from chimerax.core.map import covariance_sum

# -----------------------------------------------------------------------------
#
def read_linked_datasets(session, datasets_table, gmodels, acomp):
    '''Read linked data from ihm_dataset_other table'''
    lmodels = []
    fields = ['data_type', 'doi', 'content_filename']
    for data_type, doi, content_filename in datasets_table.fields(fields):
        if data_type == 'Comparative model' and content_filename.endswith('.pdb'):
            from .doi_fetch import fetch_doi_archive_file
            pdbf = fetch_doi_archive_file(session, doi, content_filename)
            from os.path import basename
            name = basename(content_filename)
            from chimerax.core.atomic.pdb import open_pdb
            models, msg = open_pdb(session, pdbf, name, smart_initial_display = False)
            from numpy import random, uint8
            color = random.randint(128,255,(4,),uint8)
            color[3] = 255
            for m in models:
                r = m.residues
                r.ribbon_colors = color
                r.ribbon_displays = True
                a = m.atoms
                a.colors = color
                a.displays = False
            pdbf.close()
            lmodels.extend(models)
    return lmodels

# -----------------------------------------------------------------------------
#
def register():
    from chimerax.core import io
    from chimerax.core.atomic import structure
    io.register_format("Integrative Hybrid Model", structure.CATEGORY, (".ihm",), ("ihm",),
                       open_func=read_ihm)


# -----------------------------------------------------------------------------
#
from chimerax.core.models import Model
class SphereModel(Model):
    def __init__(self, model_id, session):
        Model.__init__(self, 'Sphere model %s' % model_id, session)
        self.ihm_model_id = model_id
        self._asym_models = {}

    def add_asym_models(self, models):
        Model.add(self, models)
        am = self._asym_models
        for m in models:
            am[m.asym_id] = m

    def asym_model(self, asym_id):
        return self._asym_models.get(asym_id)
    
# -----------------------------------------------------------------------------
#
from chimerax.core.atomic import Structure
class SphereAsymModel(Structure):
    def __init__(self, session, name, asym_id, model_id, sphere_list):
        Structure.__init__(self, session, name = name, smart_initial_display = False)

        self.ihm_model_id = model_id
        self.asym_id = asym_id
        self._res_sphere = rs = {}	# res_num -> sphere atom
        
        from chimerax.core.atomic.colors import chain_rgba8
        color = chain_rgba8(asym_id)
        for (sb,se,xyz,r) in sphere_list:
            aname = ''
            a = self.new_atom(aname, 'H')
            a.coord = xyz
            a.radius = r
            a.draw_mode = a.SPHERE_STYLE
            a.color = color
            rname = '%d' % (se-sb+1)
            r = self.new_residue(rname, asym_id, sb)
            r.add_atom(a)
            for s in range(sb, se+1):
                rs[s] = a
        self.new_atoms()

    def residue_sphere(self, res_num):
        return self._res_sphere.get(res_num)
    
