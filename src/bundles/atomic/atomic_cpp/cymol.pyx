# distutils: language=c++
#cython: language_level=3, boundscheck=False, auto_pickle=False 
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


cimport cydecl
import collections
from tinyarray import array, zeros
from cython.operator import dereference
from ctypes import c_void_p, byref
cimport cython

IF UNAME_SYSNAME == "Windows":
    ctypedef long long ptr_type
ELSE:
    ctypedef long ptr_type

cdef const char * _translate_struct_cat(cydecl.StructCat cat):
    if cat == cydecl.StructCat.Main:
        return "main"
    if cat == cydecl.StructCat.Solvent:
        return "solvent"
    if cat == cydecl.StructCat.Ligand:
        return "ligand"
    if cat == cydecl.StructCat.Ions:
        return "ions"
    raise ValueError("Unknown structure category")

cdef class CyAtom:
    '''Base class for Atom, and is present only for performance reasons.'''
    cdef cydecl.Atom *cpp_atom
    cdef cydecl.bool _deleted

    SPHERE_STYLE, BALL_STYLE, STICK_STYLE = range(3)
    HIDE_RIBBON = 0x1
    HIDE_ISOLDE = 0x2
    HIDE_NUCLEOTIDE = 0x4
    BBE_MIN, BBE_RIBBON, BBE_MAX = range(3)

    _idatm_tuple = collections.namedtuple('idatm', ['geometry', 'substituents', 'description'])
    _idatm_tuple.geometry.__doc__ = "arrangement of bonds; 0: no bonds; 1: one bond;" \
        " 2: linear; 3: planar; 4: tetrahedral"
    _idatm_tuple.substituents.__doc__ = "number of bond partners"
    _idatm_tuple.description.__doc__ = "text description of atom type"
    _non_const_map = cydecl.Atom.get_idatm_info_map()
    idatm_info_map = { idatm_type.decode():
        _idatm_tuple(info['geometry'], info['substituents'], info['description'].decode())
        for idatm_type, info in _non_const_map.items()
    }

    def __cinit__(self, ptr_type ptr_val):
        self.cpp_atom = <cydecl.Atom *>ptr_val
        self._deleted = False


    # possibly long-term hack for interoperation with ctypes
    def __delattr__(self, name):
        if name == "_c_pointer" or name == "_c_pointer_ref":
            self._deleted = True
        else:
            super().__delattr__(name)
    @property
    def cpp_pointer(self):
        return int(<ptr_type>self.cpp_atom)
    @property
    def _c_pointer(self):
        return c_void_p(self.cpp_pointer)
    @property
    def _c_pointer_ref(self):
        return byref(self._c_pointer)

    def __hash__(self):
        return id(self)

    def __lt__(self, other):
        # for sorting (objects of the same type)
        if self.residue == other.residue:
            return self.name < other.name \
                if self.name != other.name else self.serial_number < other.serial_number
        return self.residue < other.residue

    def __str__(self):
        "Supported API.  Allow Atoms to be used directly in print() statements"
        return self.string()

    # properties...

    @property
    def alt_loc(self):
        "Supported API. Alternate location indicator"
        return chr(self.cpp_atom.alt_loc())

    @alt_loc.setter
    def alt_loc(self, loc):
        "For switching between existing alt locs;"
        " use 'set_alt_loc' method for creating alt locs"
        if len(loc) != 1:
            raise ValueError("Alt loc must be single character, not '%s'" % loc)
        self.cpp_atom.set_alt_loc(ord(loc[0]))

    @property
    def alt_locs(self):
        alt_locs = self.cpp_atom.alt_locs()
        return [chr(loc) for loc in alt_locs]

    @property
    def aniso_u(self):
        "Supported API. Anisotropic temperature factors,"
        " returns 3x3 array of float or None.  Read only."
        c_arr = self.cpp_atom.aniso_u()
        if c_arr:
            arr = dereference(c_arr)
            a00 = arr[0]
            a01 = arr[1]
            a02 = arr[2]
            a11 = arr[3]
            a12 = arr[4]
            a22 = arr[5]
            return array([[a00, a01, a02], [a01, a11, a12], [a02, a12, a22]])
        return None

    @property
    def aniso_u6(self):
        "Get anisotropic temperature factors as a 6 element float array"
        " containing (u11, u22, u33, u12, u13, u23) or None."
        c_arr = self.cpp_atom.aniso_u()
        if c_arr:
            return array(dereference(c_arr))
        return None

    @aniso_u6.setter
    def aniso_u6(self, u6):
        "Set anisotropic temperature factors as a 6 element float array"
        " representing the unique elements of the symmetrix matrix"
        " containing (u11, u22, u33, u12, u13, u23)."
        if len(u6) != 6:
            raise ValueError("aniso_u6 array isn't length 6")
        self.cpp_atom.set_aniso_u(u6[0], u6[1], u6[2], u6[3], u6[4], u6[5])

    @property
    def bfactor(self):
        "Supported API. B-factor, floating point value."
        return self.cpp_atom.bfactor()

    @bfactor.setter
    def bfactor(self, bf):
        self.cpp_atom.set_bfactor(bf)

    @property
    def bonds(self):
        "Supported API. Bonds connected to this atom"
        " as a list of :py:class:`Bond` objects. Read only."
        # work around non-const-correct code by using temporary...
        bonds = self.cpp_atom.bonds()
        from . import Bond
        return [Bond.c_ptr_to_py_inst(<ptr_type>b) for b in bonds]

    @property
    def color(self):
        "Supported API. Color RGBA length 4 sequence/array. Values in range 0-255"
        color = self.cpp_atom.color()
        return array([color.r, color.g, color.b, color.a])

    @color.setter
    @cython.boundscheck(False)  # turn off bounds checking
    @cython.wraparound(False)  # turn off negative index wrapping
    def color(self, rgba):
        if len(rgba) != 4:
            raise ValueError("Atom.color = rgba: 'rgba' must be length 4")
        self.cpp_atom.set_color(rgba[0], rgba[1], rgba[2], rgba[3])

    @property
    def coord(self):
        "Supported API. Coordinates from the current coordinate set (or alt loc) as a"
        " length 3 sequence/array, float values.  See get_coord method for other"
        " coordsets / alt locs.  See scene_coord for coordinates after rotations and"
        " translations."
        crd = self.cpp_atom.coord()
        return array((crd[0], crd[1], crd[2]))

    @coord.setter
    @cython.boundscheck(False)  # turn off bounds checking
    @cython.wraparound(False)  # turn off negative index wrapping
    def coord(self, xyz):
        if len(xyz) != 3:
            raise ValueError("set_coord(xyz): 'xyz' must be length 3")
        self.cpp_atom.set_coord(cydecl.Point(xyz[0], xyz[1], xyz[2]))

    @property
    def coord_index(self):
        "Supported API. Coordinate index of atom in coordinate set."
        return self.cpp_atom.coord_index()

    @property
    def default_radius(self):
        "Supported API. Default atom radius. Read only."
        return self.cpp_atom.default_radius()

    @property
    def deleted(self):
        "Supported API. Has the C++ side been deleted?"
        return self._deleted

    @property
    def display(self):
        "Supported API. Whether to display the atom. Boolean value."
        return self.cpp_atom.display()

    @display.setter
    def display(self, cydecl.bool disp):
        self.cpp_atom.set_display(disp)

    @property
    def display_radius(self):
        dm = self.draw_mode
        if dm == CyAtom.SPHERE_STYLE:
            return self.radius
        if dm == CyAtom.BALL_STYLE:
            return self.radius * self.structure.ball_scale
        if dm == CyAtom.STICK_STYLE:
            return self.cpp_atom.maximum_bond_radius(self.structure.bond_radius)
        raise ValueError("Unknown draw mode")

    @property
    def draw_mode(self):
        "Supported API. Controls how the atom is depicted.\n\nPossible values:\n\n"
        "SPHERE_STYLE\n"
        "    Use full atom radius\n\n"
        "BALL_STYLE\n"
        "    Use reduced atom radius, but larger than bond radius\n\n"
        "STICK_STYLE\n"
        "    Match bond radius"
        return self.cpp_atom.draw_mode()

    @draw_mode.setter
    def draw_mode(self, int dm):
        self.cpp_atom.set_draw_mode(<cydecl.DrawMode>dm)

    @property
    def element(self):
        "Supported API. :class:`Element` corresponding to the atom's chemical element"
        return self.cpp_atom.element().py_instance(True)

    @property
    def hide(self):
        "Supported API. Whether atom is hidden (overrides display).  Integer bitmask."
        "\n\nPossible values:\n\n"
        "HIDE_RIBBON\n"
        "    Hide mask for backbone atoms in ribbon.\n"
        "HIDE_ISOLDE\n"
        "    Hide mask for backbone atoms for ISOLDE.\n"
        "HIDE_NUCLEOTIDE\n"
        "    Hide mask for sidechain atoms in nucleotides.\n"
        return self.cpp_atom.hide()

    @hide.setter
    def hide(self, int hide_bits):
        self.cpp_atom.set_hide(hide_bits)

    @property
    def idatm_type(self):
        '''Supported API. Atom's <a href="help:user/atomtypes.html">IDATM type</a>'''
        return self.cpp_atom.idatm_type().decode()

    @idatm_type.setter
    def idatm_type(self, idatm_type):
        string_type = "" if idatm_type is None else idatm_type
        self.cpp_atom.set_idatm_type(string_type.encode())

    @property
    def is_ribose(self):
        "Whether this atom is part of an nucleic acid ribose moiety. Read only."
        return self.cpp_atom.is_ribose()

    @property
    def is_side_connector(self):
        "Whether this atom is connects the side chain to the backbone, e.g. CA/ribose."
        " Read only."
        return self.cpp_atom.is_side_connector()

    @property
    def is_side_chain(self):
        "Whether this atom is part of an amino/nucleic acid sidechain."
        " Includes atoms needed to connect to backbone (CA/ribose)."
        " is_side_only property excludes those. Read only."
        return self.cpp_atom.is_side_chain(False)

    @property
    def is_side_only(self):
        "Whether this atom is part of an amino/nucleic acid sidechain."
        "  Does not include atoms needed to connect to backbone (CA/ribose)."
        "  is_side_chain property includes those.  Read only."
        return self.cpp_atom.is_side_chain(True)

    @property
    def name(self):
        "Supported API. Atom name. Maximum length 4 characters."
        return self.cpp_atom.name().decode()

    @name.setter
    def name(self, new_name):
        self.cpp_atom.set_name(new_name.encode())

    @property
    def neighbors(self):
        "Supported API. :class:`.Atom`\\ s connnected to this atom directly by one bond."
        " Read only."
        # work around Cython not always generating const-correct code
        tmp = <cydecl.vector[cydecl.Atom*]>self.cpp_atom.neighbors()
        return [nb.py_instance(True) for nb in tmp]

    @property
    def num_bonds(self):
        "Supported API. Number of bonds connected to this atom. Read only."
        return self.cpp_atom.bonds().size()

    @property
    def num_explicit_bonds(self):
        "Supported API. Number of bonds and missing-structure pseudobonds"
        " connected to this atom. Read only."
        return self.cpp_atom.num_explicit_bonds()

    @property
    def occupancy(self):
        "Supported API. Occupancy, floating point value."
        return self.cpp_atom.occupancy()

    @occupancy.setter
    def occupancy(self, new_occ):
        self.cpp_atom.set_occupancy(new_occ)

    @property
    def radius(self):
        "Supported API. Radius of atom."
        return self.cpp_atom.radius()

    @radius.setter
    def radius(self, new_rad):
        self.cpp_atom.set_radius(new_rad)

    @property
    def residue(self):
        "Supported API. :class:`Residue` the atom belongs to. Read only."
        return self.cpp_atom.residue().py_instance(True)

    @property
    def ribbon_coord(self):
        return self.structure.ribbon_coord(self)

    @property
    def scene_coord(self):
        "Supported API. Atom center coordinates in the global scene coordinate system."
        " This accounts for the :class:`Drawing` positions for the hierarchy "
        " of models this atom belongs to."
        crd = self.cpp_atom.scene_coord()
        return array((crd[0], crd[1], crd[2]))

    @scene_coord.setter
    def scene_coord(self, xyz):
        self.coord = self.structure.scene_position.inverse() * xyz

    @property
    def selected(self):
        "Supported API. Whether the atom is selected."
        return self.cpp_atom.selected()

    @selected.setter
    def selected(self, new_sel):
        self.cpp_atom.set_selected(new_sel)

    @property
    def serial_number(self):
        "Supported API. Atom serial number from input file."
        return self.cpp_atom.serial_number()

    @serial_number.setter
    def serial_number(self, new_sn):
        self.cpp_atom.set_serial_number(new_sn)

    @property
    def session(self):
        "Session that this Atom is in"
        return self.structure.session

    @property
    def structure(self):
        "Supported API. :class:`.AtomicStructure` the atom belongs to"
        return self.cpp_atom.structure().py_instance(True)

    @property
    def structure_category(self):
        "Supported API. Whether atom is ligand, ion, etc. Read only."
        return _translate_struct_cat(self.cpp_atom.structure_category()).decode()

    @property
    def visible(self):
        "Supported API. Whether atom is displayed and not hidden."
        return self.cpp_atom.visible()

    # instance methods...

    @property
    def atomspec(self):
        return self.string(style="command")

    def clear_hide_bits(self, bit_mask):
        '''Set the hide bits 'off' that are 'on' in "bitmask"'''
        " and leave others unchanged. Opposite of set_hide_bits()"
        self.cpp_atom.clear_hide_bits(bit_mask)

    def connects_to(self, CyAtom atom):
        "Supported API. Whether this atom is directly bonded to a specified atom."
        return self.cpp_atom.connects_to(atom.cpp_atom)

    def delete(self):
        "Supported API. Delete this Atom from it's Structure"
        self.cpp_atom.structure().delete_atom(self.cpp_atom)

    def get_altloc_coord(self, loc):
        "Supported API.  Like the 'coord' property, but uses the given altloc"
        " (character) rather than the current altloc."
        if self.has_alt_loc(loc):
            crd = self.cpp_atom.coord(ord(loc[0]))
            return array((crd[0], crd[1], crd[2]))
        raise ValueError("Atom %s has no altloc %s" % (self, loc))

    def get_altloc_scene_coord(self, loc):
        "Supported API.  Like the 'scene_coord' property, but uses the given altloc"
        " (character) rather than the current altloc."
        return self.structure.scene_position * self.get_altloc_coord(loc)

    def get_coordset_coord(self, cs_id):
        "Supported API.  Like the 'coord' property, but uses the given coordset ID"
        " (integer) rather than the current coordset."
        cdef cydecl.CoordSet* cs = self.cpp_atom.structure().find_coord_set(cs_id)
        if not cs:
            raise ValueError("No such coordset ID: %d" % cs_id)
        crd = self.cpp_atom.coord(cs)
        return array((crd[0], crd[1], crd[2]))

    def get_coordset_scene_coord(self, cs_id):
        "Supported API.  Like the 'scene_coord' property, but uses the given coordset ID"
        " (integer) rather than the current coordset."
        return self.structure.scene_position * self.get_coordset_coord(cs_id)

    def has_alt_loc(self, loc):
        "Supported API. Does this Atom have an alt loc with the given letter?"
        if len(loc) != 1:
            raise ValueError("Alt loc must be single character, not '%s'" % loc)
        return self.cpp_atom.has_alt_loc(ord(loc[0]))

    def is_backbone(self, bb_extent=CyAtom.BBE_MAX):
        "Supported API. Whether this Atom is considered backbone,"
        " given the 'extent' criteria. "
        "\n\nPossible 'extent' values are:\n\n"
        "BBE_MIN\n"
        "    Only the atoms needed to connect the residue chain (and their hydrogens)"
        "BBE_MAX\n"
        "    All non-sidechain atoms"
        "BBE_RIBBON\n"
        "    The backbone atoms that a ribbon depiction hides"
        return self.cpp_atom.is_backbone(<cydecl.BackboneExtent>bb_extent)

    def rings(self, cross_residues=False, all_size_threshold=0):
        '''Return :class:`.Rings` collection of rings this Atom participates in.

        If 'cross_residues' is False, then rings that cross residue boundaries are not
        included.  If 'all_size_threshold' is zero, then return only minimal rings, of
        any size.  If it is greater than zero, then return all rings not larger than the
        given value.

        The returned rings are quite emphemeral, and shouldn't be cached or otherwise
        retained for long term use.  They may only live until the next call to rings()
        [from anywhere, including C++].
        '''
        # work around non-const-correct code by using temporary...
        ring_ptrs = self.cpp_atom.rings(cross_residues, all_size_threshold)
        from chimerax.core.atomic.molarray import Rings
        import numpy
        return Rings(numpy.array([<ptr_type>r for r in ring_ptrs], dtype=numpy.uintp))

    def set_alt_loc(self, loc, create):
        "Normally used to create alt locs. "
        "The 'alt_loc' property is used to switch between existing alt locs."
        self.cpp_atom.set_alt_loc(ord(loc[0]), create, False)

    @cython.boundscheck(False)  # turn off bounds checking
    @cython.wraparound(False)  # turn off negative index wrapping
    def set_coord(self, xyz, int cs_id):
        cdef int size = xyz.shape[0]
        if size != 3:
            raise ValueError('setcoord(xyz, cs_id): "xyz" must by numpy array of dimension 1x3')
        cdef cydecl.CoordSet* cs = self.cpp_atom.structure().find_coord_set(cs_id)
        if not cs:
            raise ValueError("No such coordset ID: %d" % cs_id)
        self.cpp_atom.set_coord(cydecl.Point(xyz[0], xyz[1], xyz[2]), cs)

    def set_hide_bits(self, bit_mask):
        '''Set the hide bits 'on' that are 'on' in "bitmask"'''
        " and leave others unchanged. Opposite of clear_hide_bits()"
        self.cpp_atom.set_hide_bits(bit_mask)

    def string(self, atom_only = False, style = None, relative_to=None):
        "Supported API.  Get text representation of Atom"
        " (also used by __str__ for printing)"
        if style == None:
            from chimerax.core.core_settings import settings
            style = settings.atomspec_contents
        if relative_to:
            if self.residue == relative_to.residue:
                return self.string(atom_only=True, style=style)
            if self.structure == relative_to.structure:
                # tautology for bonds, but this func is conscripted by pseudobonds, so test...
                if style.startswith('serial'):
                    return self.string(atom_only=True, style=style)
                chain_str = "" if  self.residue.chain_id == relative_to.residue.chain_id \
                    else '/' + self.residue.chain_id + (' ' if style.startswith("simple") else "")
                res_str = self.residue.string(residue_only=True)
                atom_str = self.string(atom_only=True, style=style)
                joiner = "" if res_str.startswith(":") else " "
                return chain_str + res_str + joiner + atom_str
        if style.startswith("simple"):
            atom_str = self.name
        elif style.startswith("command"):
            atom_str = '@' + self.name
        else:
            atom_str = str(self.serial_number)
        if atom_only:
            return atom_str
        if not style.startswith('simple'):
            return '%s%s' % (self.residue.string(style=style), atom_str)
        return '%s %s' % (self.residue.string(style=style), atom_str)

    def use_default_radius(self):
        "Supported API.  If an atom's radius has previously been explicitly set,"
        " this call will revert it to using the default radius"
        self.cpp_atom.use_default_radius()

    # static methods...

    @staticmethod
    def c_ptr_to_existing_py_inst(ptr_type ptr_val):
        return (<cydecl.Atom *>ptr_val).py_instance(False)

    @staticmethod
    def c_ptr_to_py_inst(ptr_type ptr_val):
        return (<cydecl.Atom *>ptr_val).py_instance(True)

    @staticmethod
    def set_py_class(klass):
        cydecl.Atom.set_py_class(klass)

cdef class Element:
    '''A chemical element having a name, number, mass, and other physical properties.'''
    cdef cydecl.Element *cpp_element

    NUM_SUPPORTED_ELEMENTS = cydecl.Element.AS.NUM_SUPPORTED_ELEMENTS

    def __cinit__(self, ptr_type ptr_val):
        self.cpp_element = <cydecl.Element *>ptr_val

    def __init__(self, ptr_val):
        if not isinstance(ptr_val, int) or ptr_val < 256:
            raise ValueError("Do not use Element constructor directly;"
                " use Element.get_element method to get an Element instance")

    # possibly long-term hack for interoperation with ctypes
    def __delattr__(self, name):
        if name == "_c_pointer" or name == "_c_pointer_ref":
            self._deleted = True
        else:
            super().__delattr__(name)
    @property
    def cpp_pointer(self):
        return int(<ptr_type>self.cpp_element)
    @property
    def _c_pointer(self):
        return c_void_p(self.cpp_pointer)
    @property
    def _c_pointer_ref(self):
        return byref(self._c_pointer)

    @property
    def has_custom_attrs(self):
        return False

    @property
    def is_alkali_metal(self):
        "Supported API. Is atom an alkali metal?  Read only"
        return self.cpp_element.is_alkali_metal()

    @property
    def is_halogen(self):
        "Supported API. Is atom a halogen?  Read only"
        return self.cpp_element.is_halogen()

    @property
    def is_metal(self):
        "Supported API. Is atom a metal?  Read only"
        return self.cpp_element.is_metal()

    @property
    def is_noble_gas(self):
        "Supported API. Is atom a noble gas?  Read only"
        return self.cpp_element.is_noble_gas()

    @property
    def mass(self):
        "Supported API. Atomic mass, taken from"
        " http://en.wikipedia.org/wiki/List_of_elements_by_atomic_weight.  Read only."
        return self.cpp_element.mass()

    @property
    def name(self):
        "Supported API. Atomic symbol.  Read only"
        return self.cpp_element.name().decode()

    names = { sym.decode() for sym in cydecl.Element.names() }
    '''Set of known element names'''

    @property
    def number(self):
        "Supported API. Atomic number.  Read only"
        return self.cpp_element.number()

    @property
    def valence(self):
        "Supported API. Electronic valence number, for example 7 for chlorine. Read only"
        return self.cpp_element.valence()

    def __str__(self):
        # make printing easier
        return self.name

    @staticmethod
    cdef float _bond_length(ptr_type e1, ptr_type e2):
        return cydecl.Element.bond_length(
            dereference(<cydecl.Element*>e1), dereference(<cydecl.Element*>e2))

    @staticmethod
    def bond_length(e1, e2):
        "Supported API. Standard single-bond length between two elements."
        " Arguments can be element instances, atomic numbers, or element names"
        if not isinstance(e1, Element):
            e1 = Element.get_element(e1)
        if not isinstance(e2, Element):
            e2 = Element.get_element(e2)
        return Element._bond_length(e1.cpp_pointer, e2.cpp_pointer)

    @staticmethod
    cdef float _bond_radius(ptr_type e):
        return cydecl.Element.bond_radius(dereference(<cydecl.Element*>e))

    @staticmethod
    def bond_radius(e):
        "Supported API. Standard single-bond 'radius'"
        " (the amount this element would contribute to bond length)."
        " Argument can be an element instance, atomic number, or element name"
        if not isinstance(e, Element):
            e = Element.get_element(e)
        return Element._bond_radius(e.cpp_pointer)

    @staticmethod
    def c_ptr_to_existing_py_inst(ptr_type ptr_val):
        return (<cydecl.Element *>ptr_val).py_instance(False)

    @staticmethod
    def c_ptr_to_py_inst(ptr_type ptr_val):
        return (<cydecl.Element *>ptr_val).py_instance(True)

    @staticmethod
    cdef const cydecl.Element* _string_to_cpp_element(const char* ident):
        return &cydecl.Element.get_named_element(ident)

    @staticmethod
    cdef const cydecl.Element* _int_to_cpp_element(int ident):
        return &cydecl.Element.get_element(ident)

    @staticmethod
    def get_element(ident):
        "Supported API.  Given an atomic symbol or atomic number, return the"
        " corresponding Element instance."
        cdef const cydecl.Element* ele_ptr
        if isinstance(ident, int):
            ele_ptr = Element._int_to_cpp_element(ident)
        else:
            ele_ptr = Element._string_to_cpp_element(ident.encode())
        return ele_ptr.py_instance(True)

    names = set(cydecl.Element.names())

cydecl.Element.set_py_class(Element)

cdef class CyResidue:
    '''Base class for Residue, and is present only for performance reasons.'''
    cdef cydecl.Residue *cpp_res
    cdef cydecl.bool _deleted

    def __cinit__(self, ptr_type ptr_val):
        self.cpp_res = <cydecl.Residue *>ptr_val
        self._deleted = False

    # possibly long-term hack for interoperation with ctypes
    def __delattr__(self, name):
        if name == "_c_pointer" or name == "_c_pointer_ref":
            self._deleted = True
        else:
            super().__delattr__(name)
    @property
    def cpp_pointer(self):
        return int(<ptr_type>self.cpp_res)
    @property
    def _c_pointer(self):
        return c_void_p(self.cpp_pointer)
    @property
    def _c_pointer_ref(self):
        return byref(self._c_pointer)

    def __hash__(self):
        return id(self)

    def __lt__(self, other):
        # for sorting (objects of the same type)
        if self.structure != other.structure:
            return self.structure < other.structure

        if self.chain_id != other.chain_id:
            return self.chain_id < other.chain_id

        return self.number < other.number \
            if self.number != other.number else self.insertion_code < other.insertion_code

    def __str__(self):
        return self.string()


    # properties...

    @property
    def atoms(self):
        "Supported API. :class:`.Atoms` collection containing all atoms of the residue."
        from .molarray import Atoms
        import numpy
        # work around non-const-correct code by using temporary...
        atoms = self.cpp_res.atoms()
        return Atoms(numpy.array([<ptr_type>a for a in atoms], dtype=numpy.uintp))

    @property
    def atomspec(self):
        return self.string(style="command")

    @property
    def chain(self):
        "Supported API. :class:`.Chain` that this residue belongs to, if any. Read only."
        chain_ptr = self.cpp_res.chain()
        if chain_ptr:
            from chimerax.core.atomic import Chain
            chain = Chain.c_ptr_to_existing_py_inst(<ptr_type>chain_ptr)
            if chain:
                return chain
            return Chain(<ptr_type>chain_ptr)
        return None

    @property
    def chain_id(self):
        "Supported API. PDB chain identifier. Limited to 4 characters. Read only string."
        return self.cpp_res.chain_id().decode()

    @property
    def center(self):
        "Average of atom positions as a length 3 array, 64-bit float values."
        return sum([a.coord for a in self.atoms]) / self.num_atoms

    @property
    def deleted(self):
        "Supported API. Has the C++ side been deleted?"
        return self._deleted

    @property
    def description(self):
        '''Description of residue (if available) from HETNAM/HETSYN records or equivalent'''
        return getattr(self.structure, '_hetnam_descriptions', {}).get(self.name, None)

    @property
    def insertion_code(self):
        "Supported API. PDB residue insertion code. 1 character or empty string."
        code = chr(self.cpp_res.insertion_code())
        return "" if code == ' ' else code

    @insertion_code.setter
    def insertion_code(self, ic):
        if not ic:
            ic = ' '
        elif len(ic) != 1:
            raise ValueError("Insertion code must be single character, not '%s'" % ic)
        self.cpp_res.set_insertion_code(ord(ic[0]))

    @property
    def is_helix(self):
        "Supported API. Whether this residue belongs to a protein alpha helix. Boolean value. "
        return self.cpp_res.is_helix()

    @is_helix.setter
    def is_helix(self, val):
        self.cpp_res.set_is_helix(val)

    @property
    def is_strand(self):
        "Supported API. Whether this residue belongs to a protein beta sheet. Boolean value. "
        return self.cpp_res.is_strand()

    @is_strand.setter
    def is_strand(self, val):
        self.cpp_res.set_is_strand(val)

    @property
    def mmcif_chain_id(self):
        "mmCIF chain identifier. Limited to 4 characters. Read only string."
        return self.cpp_res.mmcif_chain_id().decode()

    @property
    def name(self):
        "Supported API. Residue name. Maximum length 4 characters."
        return self.cpp_res.name().decode()

    @name.setter
    def name(self, new_name):
        self.cpp_res.set_name(new_name.encode())

    @property
    def num_atoms(self):
        "Supported API. Number of atoms belonging to the residue. Read only."
        return self.cpp_res.atoms().size()

    @property
    def number(self):
        "Supported API. Integer sequence position number from input data file. Read only."
        return self.cpp_res.number()

    PT_NONE, PT_AMINO, PT_NUCLEIC = range(3)
    @property
    def polymer_type(self):
        '''Supported API.  Polymer type of residue. Values are:
            PT_NONE: not a polymeric residue
            PT_AMINO: amino acid
            PT_NUCLEIC: nucleotide
        (Access as Residue.PT_XXX)
        '''
        return self.cpp_res.polymer_type()

    @property
    def principal_atom(self):
        '''The 'chain trace' :class:`.Atom`\\ , if any.
        Normally returns the C4' from a nucleic acid since that is always present,
        but in the case of a P-only trace it returns the P.'''
        princ_ptr = self.cpp_res.principal_atom()
        if princ_ptr:
            return princ_ptr.py_instance(True)
        return None

    @property
    def ribbon_adjust(self):
        "Smoothness adjustment factor (no adjustment = 0 <= factor <= 1 = idealized)."
        return self.cpp_res.ribbon_adjust()

    @ribbon_adjust.setter
    def ribbon_adjust(self, ra):
        self.cpp_res.set_ribbon_adjust(ra)

    @property
    def ribbon_display(self):
        "Whether to display the residue as a ribbon/pipe/plank. Boolean value."
        return self.cpp_res.ribbon_display()

    @ribbon_display.setter
    def ribbon_display(self, rd):
        self.cpp_res.set_ribbon_display(rd)

    @property
    def ribbon_hide_backbone(self):
        "Whether a ribbon automatically hides the residue backbone atoms. Boolean value."
        return self.cpp_res.ribbon_hide_backbone()

    @ribbon_hide_backbone.setter
    def ribbon_hide_backbone(self, rhb):
        self.cpp_res.set_ribbon_hide_backbone(rhb)

    @property
    def ribbon_color(self):
        "Ribbon color RGBA length 4 sequence/array. Values in range 0-255"
        color = self.cpp_res.ribbon_color()
        return array([color.r, color.g, color.b, color.a])

    @ribbon_color.setter
    @cython.boundscheck(False)  # turn off bounds checking
    @cython.wraparound(False)  # turn off negative index wrapping
    def ribbon_color(self, rgba):
        if len(rgba) != 4:
            raise ValueError("Residue.ribbon_color = rgba: 'rgba' must be length 4")
        self.cpp_res.set_ribbon_color(rgba[0], rgba[1], rgba[2], rgba[3])

    @property
    def session(self):
        return self.structure.session

    @property
    def ss_id(self):
        "Secondary structure id number. Integer value."
        return self.cpp_res.ss_id()

    @ss_id.setter
    def ss_id(self, new_ss_id):
        self.cpp_res.set_ss_id(new_ss_id)

    SS_COIL, SS_HELIX, SS_STRAND = range(3)
    SS_SHEET = SS_STRAND
    @property
    def ss_type(self):
        "Supported API. Secondary structure type of residue. Integer value."
        " One of Residue.SS_COIL, Residue.SS_HELIX, Residue.SS_SHEET (a.k.a. SS_STRAND)"
        return self.cpp_res.ss_type()

    @ss_type.setter
    def ss_type(self, st):
        self.cpp_res.set_ss_type(st)

    @property
    def structure(self):
        "Supported API. ':class:`.AtomicStructure` that this residue belongs to. Read only."
        return self.cpp_res.structure().py_instance(True)

    water_res_names = set(["HOH", "WAT", "H2O", "D2O", "TIP3"])


    # instance methods...

    def add_atom(self, CyAtom atom):
        '''Supported API. Add the specified :class:`.Atom` to this residue.
        An atom can only belong to one residue, and all atoms
        must belong to a residue.'''
        self.cpp_res.add_atom(<cydecl.Atom*>atom.cpp_atom)

    def bonds_between(self, CyResidue other_res):
        "Supported API. Return the bonds between this residue and other_res as a Bonds collection."
        from .molarray import Bonds
        import numpy
        # work around non-const-correct code by using temporary...
        between = self.cpp_res.bonds_between(<cydecl.Residue*>other_res.cpp_res)
        return Bonds(numpy.array([<ptr_type>b for b in between], dtype=numpy.uintp))

    def connects_to(self, CyResidue other_res):
        "Supported API. Return True if this residue is connected by at least one bond "
        " (not pseudobond) to other_res"
        return self.cpp_res.connects_to(<cydecl.Residue*>other_res.cpp_res)

    def delete(self):
        "Supported API. Delete this Residue from it's Structure"
        self.cpp_res.structure().delete_atoms(self.cpp_res.atoms())

    def find_atom(self, atom_name):
        '''Supported API. Return the atom with the given name, or None if not found.\n'''
        '''If multiple atoms in the residue have that name, an arbitrary one that matches will'''
        ''' be returned.'''
        fa_ptr = self.cpp_res.find_atom(atom_name.encode())
        if fa_ptr:
            return fa_ptr.py_instance(True)
        return None

    def set_alt_loc(self, loc):
        "Set the appropiate atoms in the residue to the given (existing) alt loc"
        if not loc:
            loc = ' '
        self.cpp_res.set_alt_loc(ord(loc[0]))

    def string(self, residue_only = False, omit_structure = False, style = None):
        "Supported API.  Get text representation of Residue"
        if style == None:
            from chimerax.core.core_settings import settings
            style = settings.atomspec_contents
        ic = self.insertion_code
        if style.startswith("simple"):
            res_str = self.name + " " + str(self.number) + ic
        else:
            res_str = ":" + str(self.number) + ic
        chain_str = '/' + self.chain_id if not self.chain_id.isspace() else ""
        if residue_only:
            return res_str
        if omit_structure:
            return '%s %s' % (chain_str, res_str)
        from .structure import Structure
        if len([s for s in self.structure.session.models.list() if isinstance(s, Structure)]) > 1:
            struct_string = str(self.structure)
            if style.startswith("serial"):
                struct_string += " "
        else:
            struct_string = ""
        if style.startswith("simple"):
            return '%s%s %s' % (struct_string, chain_str, res_str)
        if style.startswith("command"):
            return struct_string + chain_str + res_str
        return struct_string


    # static methods...

    @staticmethod
    def add_standard_residue(res_name):
        cydecl.add_standard_residue(res_name)

    @staticmethod
    def c_ptr_to_existing_py_inst(ptr_type ptr_val):
        return (<cydecl.Residue *>ptr_val).py_instance(False)

    @staticmethod
    def c_ptr_to_py_inst(ptr_type ptr_val):
        return (<cydecl.Residue *>ptr_val).py_instance(True)

    @staticmethod
    def is_standard_residue(res_name):
        return cydecl.is_standard_residue(res_name)

    @staticmethod
    def remove_standard_residue(res_name):
        cydecl.remove_standard_residue(res_name)

    @staticmethod
    def set_py_class(klass):
        cydecl.Residue.set_py_class(klass)

    @staticmethod
    def set_templates_dir(tmpl_dir):
        cydecl.Residue.set_templates_dir(tmpl_dir.encode())

