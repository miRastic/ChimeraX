// vim: set expandtab ts=4 sw=4:
#include "restmpl.h"

#include "TemplateCache.h"

namespace tmpl {

std::vector<Atom *>
Residue::template_assign(void (Atom::*assign_func)(const char *),
    const char *app, const char *template_dir, const char *extension) const
{
    return template_assign(tmpl_assigner(assign_func),
                        app, template_dir, extension);
}

std::vector<Atom *>
Residue::template_assign(void (*assign_func)(Atom *, const char *),
    const char *app, const char *template_dir, const char *extension) const
{
    return template_assign(tmpl_assigner(assign_func),
                        app, template_dir, extension);
}

// returns atoms that received assignments from the template.
// can throw exceptions if:
//     template syntax error: TA_TemplateSyntax
//    no template found: TA_NoTemplate
//    internal logic error: std::logic_error
std::vector<Atom *>
Residue::template_assign(tmpl_assigner assign,
    const char *app, const char *template_dir, const char *extension) const
{
    TemplateCache *tc = TemplateCache::template_cache();
    TemplateCache::AtomMap *am = tc->res_template(name(), app,
                            template_dir, extension);
    std::vector<Atom *> assigned;
    for (AtomsMap::const_iterator ai = _atoms.begin(); ai != _atoms.end(); ++ai) {
        const std::string& at_name = ai->first;
        Atom *a = ai->second;

        TemplateCache::AtomMap::iterator ami = am->find(at_name);
        if (ami == am->end())
            continue;
        
        std::string normType(ami->second.first);
        ConditionalTemplate *ct = ami->second.second;
        if (ct != NULL) {
            // assign conditional type if applicable
            bool cond_assigned = false;
            for (std::vector<CondInfo>::iterator cii =
            ct->conditions.begin(); cii != ct->conditions.end();
            ++cii) {
                CondInfo &ci = *cii;
                if (ci.op == ".") {
                      // is given atom terminal?
                    bool is_terminal = true;
                    AtomsMap::const_iterator opai = _atoms.find(ci.operand);
                    if (opai == _atoms.end())
                        continue;
                    Atom *opa = opai->second;
                    const Atom::BondsMap &bm = opa->bonds_map();
                    for (Atom::BondsMap::const_iterator abi =
                      bm.begin(); abi != bm.end(); ++abi) {
                        const Atom *bonded = abi->first;
                        if (bonded->residue()
                        != opa->residue()) {
                            is_terminal = false;
                            break;
                        }
                    }
                    if (is_terminal) {
                        cond_assigned = true;
                        if (ci.result != "-") {
                            assign(a, ci.result);
                            assigned.push_back(a);
                        }
                    }
                } else if (ci.op == "?") {
                      // does given atom exist in residue?
                    if (_atoms.find(ci.operand) != _atoms.end()) {
                        cond_assigned = true;
                        if (ci.result != "-") {
                            assign(a, ci.result);
                            assigned.push_back(a);
                        }
                    }
                } else {
                      throw std::logic_error(
                    "Legal template condition not implemented");
                }
                if (cond_assigned)
                    break;
            }
            if (cond_assigned)
                continue;
        }

        // assign normal type
        if (normType != "-") {
            assign(a, normType);
            assigned.push_back(a);
        }
    }
    return assigned;
}

void
Residue::add_atom(Atom *element)
{
    element->_residue = this;
    _atoms[element->name()] = element;
}

Atom *
Residue::find_atom(const std::string &index) const
{
    AtomsMap::const_iterator i = _atoms.find(index);
    if (i == _atoms.end())
        return NULL;
    return i->second;
}

Residue::Residue(Molecule *, const char *n): _name(n), _chief(0), _link(0) 
{
}

Residue::~Residue()
{
}

}  // namespace tmpl
