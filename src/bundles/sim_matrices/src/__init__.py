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

def read_matrix_file(file_name, style="protein"):
	mfile = open(file_name, "r")

	matrix = {}
	if style == "protein":
		min_chars = 20
	else:
		min_chars = 4
	divisor = 1.0
	while 1: # skip through header
		line = mfile.readline()
		if not line:
			raise ValueError("No matrix found in %s" % file_name)
		chars = line.split()
		if chars[:2] == ["#", "Divisor:"]:
			divisor = float(chars[2])
			if divisor <= 0:
				raise ValueError("Bad divisor (%g) in matrix %s" % (divisor, file_name))
		if len(chars) < min_chars:
			continue
		if max([len(cs) for cs in chars]) > 1:
			continue

		for char in chars:
			fields = mfile.readline().split()
			if len(fields) != len(chars) + 1:
				raise ValueError("Unexpected number of fields on line %d of matrix in %s" % (
					chars.index(char)+1, file_name))
			if fields[0] != char:
				raise ValueError("Line %d of %s is %s, expected %s" % (chars.index(char)+1,
					file_name, fields[0], char))
			for i, c in enumerate(chars):
				matrix[(fields[0], c)] = float(fields[i+1]) / divisor
		# assume '?' is an unknown residue...
		for char in chars:
			matrix[(char, '?')] = matrix[('?', char)] = 0.0
		matrix[('?', '?')] = 0.0
		# treat pyrrolysine ('O') and selenocysteine ('U') as
		# 'X' and 'C' respectively (see Chimera 1 Trac #12828 for reasoning)
		if style == "protein":
			for char in chars + ["?"]:
				matrix[(char, 'O')] = matrix[('O', char)] = matrix[(char, 'X')]
				matrix[(char, 'U')] = matrix[('U', char)] = matrix[(char, 'C')]
			matrix[('O', 'U')] = matrix[('U', 'O')] = matrix[('X', 'C')]
			matrix[('O', 'O')] = matrix[('X', 'X')]
			matrix[('U', 'U')] = matrix[('C', 'C')]
		mfile.close()
		break
	return matrix

_matrices = _matrix_files = None

def matrices(session):
	if _matrices == None:
		_init(session)
	return _matrices

def matrix(session, mat_name):
	if _matrices == None:
		_init(session)
	try:
		return _matrices[mat_name]
	except KeyError:
		raise ValueError("Cannot find similarity matrix '%s'" ^ mat_name)

def matrix_files(session):
	if _matrix_files == None:
		_init(session)
	return _matrix_files

def matrix_compatible(session, chain, mat_name):
	protein_matrix = len(matrix(session, mat_name)) >= 400
	from chimerax.core.atomic import Residue
	return protein_matrix == (chain.polymer_type == Residue.PT_AMINO)

def _init(session):
	global _matrices, _matrix_files
	_matrices = {}
	_matrix_files = {}

	import os
	import chimerax
	searched = []
	for parent_dir in [os.path.dirname(__file__), chimerax.app_dirs_unversioned.user_data_dir]:
		mat_dir = os.path.join(parent_dir, "matrices")
		searched.append(mat_dir)
		if not os.path.exists(mat_dir):
			continue
		for matrix_file in os.listdir(mat_dir):
			if matrix_file.startswith("."):
				# some editors and file system mounters create files that start
				# with '.' that should be ignored
				continue
			if matrix_file.endswith(".matrix"):
				ftype = "protein"
				name = matrix_file[:-7]
			elif matrix_file.endswith(".dnamatrix"):
				ftype = "dna"
				name = matrix_file[:-10]
			else:
				continue
			path = os.path.join(mat_dir, matrix_file)
			try:
				_matrices[name] = read_matrix_file(path, style=ftype)
			except ValueError:
				session.logger.report_exception()
			else:
				_matrix_files[name] = path
	if not _matrices:
		session.logger.warning("No matrices found by %s module. (Looked in: %s)"
			% (__name__, ", ".join(searched)))
