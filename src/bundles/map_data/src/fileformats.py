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

# -----------------------------------------------------------------------------
# Python readers for array file formats.
#
class MapFileFormat:
  def __init__(self, description, name, prefixes, suffixes, *,
               writable = False, writer_options = (), batch = False, allow_directory = False):
    self.description = description
    self.name = name
    self.prefixes = prefixes
    self.suffixes = suffixes
    self.writable = writable
    self.writer_options = writer_options
    self.batch = batch
    self.allow_directory = allow_directory

  @property
  def open_func(self):
    module_name = self.name
    module = __import__(module_name, globals(), level = 1)
    return module.open

  @property
  def save_func(self):
    if not self.writable:
      return None
    module_name = self.name
    module = __import__(module_name, globals(), level = 1)
    return module.save
    
# -----------------------------------------------------------------------------
# File description, file reader module name, file prefixes, and file suffixes.
#
file_formats = [
  MapFileFormat('Amira mesh', 'amira', ['amira'], ['am']),
  MapFileFormat('APBS potential', 'apbs', ['apbs'], ['dx']),
  MapFileFormat('BRIX density map', 'dsn6', ['dsn6'], ['brix'], writable = True),
  MapFileFormat('CCP4 density map', 'ccp4', ['ccp4'], ['ccp4','map']),
  MapFileFormat('Chimera map', 'cmap', ['cmap'], ['cmap', 'cmp'], writable = True,
                writer_options = ('chunk_shapes', 'append', 'compress', 'multigrid')),
  MapFileFormat('CNS or XPLOR density map', 'xplor', ['xplor'], ['cns','xplor']),
  MapFileFormat('DelPhi or GRASP potential', 'delphi', ['delphi'], ['phi']),
  MapFileFormat('DeltaVision map', 'deltavision', ['dv'], ['dv']),
  MapFileFormat('DSN6 density map', 'dsn6', ['dsn6'], ['omap']),
  MapFileFormat('DOCK scoring grid', 'dock', ['dock'], ['bmp','cnt','nrg']),
  MapFileFormat('EMAN HDF map', 'emanhdf', ['emanhdf'], ['hdf', 'h5']),
  MapFileFormat('Gaussian cube grid', 'gaussian', ['cube'], ['cube','cub']),
  MapFileFormat('gOpenMol grid', 'gopenmol', ['gopenmol'], ['plt']),
  MapFileFormat('Image stack', 'imagestack', ['images'], ['tif', 'tiff', 'png', 'pgm'], batch = True),
  MapFileFormat('Imaris map', 'ims', ['ims'], ['ims']),
  MapFileFormat('IMOD map', 'imod', ['imodmap'], ['rec']),
  MapFileFormat('MacMolPlt grid', 'macmolplt', ['macmolplt'], ['mmp']),
  MapFileFormat('MRC density map', 'mrc', ['mrc'], ['mrc'], writable = True),
  MapFileFormat('NetCDF generic array', 'netcdf', ['netcdf'], ['nc']),
  MapFileFormat('Priism microscope image', 'priism', ['priism'], ['xyzw', 'xyzt']),
  MapFileFormat('PROFEC free energy grid', 'profec', ['profec'], ['profec']),
  MapFileFormat('Purdue image format', 'pif', ['pif'], ['pif']),
  MapFileFormat('SITUS map file', 'situs', ['situs'], ['sit','situs']),
  MapFileFormat('SPIDER volume data', 'spider', ['spider'], ['spi','vol']),
  MapFileFormat('TOM toolbox EM density map', 'tom_em', ['tom_em'], ['em']),
  MapFileFormat('UHBD grid, binary', 'uhbd', ['uhbd'], ['grd']),
  ]
  
# -----------------------------------------------------------------------------
# The electrostatics file types are opened using a surface colormapping tool
# instead of displaying a contour surface.
#
electrostatics_types = ('apbs', 'delphi', 'uhbd')

# -----------------------------------------------------------------------------
#
class UnknownFileType(Exception):

  def __init__(self, path):

    self.path = path
    Exception.__init__(self)
    
  def __str__(self):

    return suffix_warning([self.path])

# -----------------------------------------------------------------------------
#
class FileFormatError(Exception):
  pass
  
# -----------------------------------------------------------------------------
#
def suffix_warning(paths):

  path_string = ' '.join(paths)

  if len(paths) > 1:
    pluralize = 'es'
  else:
    pluralize = ''
    
  suffixes = sum([f.suffixes for f in file_formats], [])
  suffix_string = ' '.join(['.'+s for s in suffixes])

  prefixes = sum([f.prefixes for s in file_formats], [])
  prefix_string = ' '.join([s+':' for s in prefixes])
  
  msg = ('Warning: Unrecognized file suffix%s for %s.\n' %
         (pluralize, path_string) +
         '\tKnown suffixes: %s\n' % suffix_string +
         '\tYou can specify the file type by prepending one of\n' +
         '\t%s\n' % prefix_string +
         '\tto the file name (eg. mrc:mydata).\n')
  return msg
  
# -----------------------------------------------------------------------------
#
def open_file(path, file_type = None, log = None, verbose = False):

  if file_type is None:
    p = path if isinstance(path, str) else path[0]
    file_type = file_type_from_suffix(p)
    if file_type is None:
      file_type, path = file_type_from_colon_specifier(p)
      if file_type is None:
        raise UnknownFileType(p)

  fmt = file_format_by_name(file_type)
  open_func = fmt.open_func

  apath = absolute_path(path) if isinstance(path,str) else [absolute_path(p) for p in path]

  kw = {}
  from inspect import getargspec
  if log is not None and 'log' in getargspec(open_func).args:
    kw['log'] = log
  if verbose:
    if 'verbose' in getargspec(open_func).args:
      kw['verbose'] = verbose
  try:
    if fmt.batch or isinstance(apath,str):
      data = open_func(apath, **kw)
    else:
      data = []
      for p in apath:
        data.extend(open_func(p, **kw))
  except SyntaxError as value:
    raise FileFormatError(value)
  
  return data

# -----------------------------------------------------------------------------
#
def file_type_from_suffix(path):
    
  for ff in file_formats:
    for suffix in ff.suffixes:
      if has_suffix(path, suffix):
        return mname
  return None

# -----------------------------------------------------------------------------
#
def file_type_from_colon_specifier(path):

  try:
    colon_position = path.rindex(':')
  except ValueError:
    return None, path
  
  first_part = path[:colon_position]
  last_part = path[colon_position+1:]

  module_names = [ff.name for ff in file_formats]
  if last_part in module_names:
    return last_part, first_part

  return None, path

# -----------------------------------------------------------------------------
#
def file_format_by_name(name):
  for ff in file_formats:
    if ff.name == name:
      return ff
  raise ValueError('Unknown map file format %s' % file_type)

# -----------------------------------------------------------------------------
#
def has_suffix(path, suffix):

  parts = path.split('.')
  if len(parts) >= 2:
    return parts[-1] == suffix
  return 0

# -----------------------------------------------------------------------------
# Path can be a tuple of paths.
#
def absolute_path(path):

  from os.path import abspath
  if isinstance(path, (tuple, list)):
    apath = tuple([abspath(p) for p in path])
  elif isinstance(path, str) and len(path) > 0:
    apath = abspath(path)
  else:
    apath = path
  return apath
  
# -----------------------------------------------------------------------------
#
def file_writer(path, format = None):

  if format is None:
    for ff in file_formats:
      for suffix in ff.suffixes:
        if path.endswith('.' + suffix):
          return ff
  else:
    for ff in file_formats:
      if format == ff.name or format == ff.description:
        return ff
  return None
  
# -----------------------------------------------------------------------------
#
def save_map_command(cmdname, args, session):

    from chimerax.core.commands.parse import path_arg, volumes_arg, parse_arguments
    req_args = (('path', path_arg),
                ('maps', volumes_arg),
                )
    opt_args = ()
    kw_args = ()

    kw = parse_arguments(cmdname, args, session, req_args, opt_args, kw_args)
    kw['session'] = session
    vlist = kw['maps']
    kw['grids'] = [v.data for v in vlist]
    kw.pop('maps')

    save_grid_data(**kw)

    # Set file icon image on Mac
    from chimerax.core.files import fileicon
    fileicon.set_file_icon(kw['path'], session, models = vlist)

    session.file_history.add_entry(kw['path'], models = vlist)
 
# -----------------------------------------------------------------------------
#
def save_grid_data(grids, path, session, format = None, options = {}):

  import os.path
  path = os.path.expanduser(path)
  
  ff = file_writer(path, format)
  if ff is None:
    raise ValueError('Unknown format "%s"' % (format or path))

  badopt = [k for k in options.keys() if not k in ff.writer_options]
  if badopt:
    raise ValueError(('Unsupported options for format %s: %s'
                      % (ff.name, ' ,'.join(badopt))))

  from .griddata import GridData
  if isinstance(grids, GridData):
    glist = [grids]
  else:
    glist = grids

  if len(glist) > 1 and not ('multigrid' in ff.writer_options):
    from chimerax.core.errors import UserError
    raise UserError('Cannot write multiple volumes using format %s' % ff.name)

  # Use a temporary file if a source file is being overwritten.
  tpath = path
  if not ('append' in options):
    if matching_grid_path(glist, path):
      from tempfile import mkstemp
      f, tpath = mkstemp(ff.suffixes[0])
      from os import close, remove
      close(f)
      remove(tpath)  # Want new file to have normal, not secure, permissions.

  g = glist[0]
  from os.path import basename
  operation = 'Writing %s to %s' % (g.name, basename(path))
  from .progress import ProgressReporter
  p = ProgressReporter(operation, g.size, g.value_type.itemsize,
                       message = session.logger.status)
  if 'multigrid' in ff.writer_options:
    garg = glist
  else:
    garg = g
  ff.save_func(garg, tpath, options = options, progress = p)

  if tpath != path:
    import os, os.path, shutil
    if os.path.exists(path):
      os.remove(path)
    shutil.move(tpath, path)

  # Update path in grid data object.
  for g in glist:
    g.set_path(path, ff.name)

  from os.path import basename
  p.message('Wrote file %s' % basename(path))

  return format
  
# -----------------------------------------------------------------------------
#
def matching_grid_path(glist, path):

  from os.path import realpath
  rp = realpath(path)
  for g in glist:
    for gp in grid_paths(g):
      if realpath(gp) == rp:
        return True
  return False
  
# -----------------------------------------------------------------------------
#
def grid_paths(g):

  if isinstance(g.path, str):
    gpaths = [g.path]
  else:
    gpaths = g.path
  return gpaths
