def read_pseudobond_file(session, file, name, radius = 0.1, color = (255,0,255,255), as_ = None):
    lines = file.readlines()
    file.close()

    from . import pbgroup
    g = pbgroup.PseudoBondGroup(name)

    from .structure import AtomsArg
    for i, line in enumerate(lines):
        aspec1, aspec2 = line.decode('utf-8').split()[:2]
        a1, used, rest = AtomsArg.parse(aspec1, session)
        a2, used, rest = AtomsArg.parse(aspec2, session)
        for a, apsec in ((a1,aspec1), (a2,aspec2)):
            if len(a) != 1:
                raise SyntaxError('Line %d, got %d atoms for spec "%s", require exactly 1'
                                  % (i, len(a), aspec))
        b = g.new_pseudobond(a1[0], a2[0])
        b.color = color
        b.radius = radius
        b.halfbond = False

    g.update_graphics()

    return [g], 'Opened Pseudobonds %s, %d bonds' % (name, len(lines))

def register():
    from . import io
    io.register_format("Pseudobonds", io.GENERIC3D, (".pb",),
                       open_func = read_pseudobond_file)
