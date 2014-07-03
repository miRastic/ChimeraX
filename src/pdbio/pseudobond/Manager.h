// vim: set expandtab ts=4 sw=4:
#ifndef pseudobonds_Manager
#define pseudobonds_Manager

#include <map>
#include <memory>
#include <string>

#include "Group.h"

namespace pseudobond {

//classes
template <class Grp_Class>
class Base_Manager {
protected:
    mutable std::map<std::string, Grp_Class*>  _groups;
public:
    virtual  ~Base_Manager() { for (auto i: _groups) delete i.second; }
    virtual Grp_Class*  get_group(const std::string& name, bool create = false) const = 0;
    Grp_Class*  get_group(const char* name, bool create = false) const {
        return get_group(std::string(name), create);
    }
};

template <class Grp_Class>
class Global_Manager: public Base_Manager<Grp_Class> {
private:
    static Global_Manager  _manager;
public:
    virtual Grp_Class*  get_group(const std::string& name, bool create = false) const;
    virtual  ~Global_Manager() {};
    static Global_Manager&  manager() { return _manager; }
};

template <class Owner, class Grp_Class>
class Owned_Manager: public Base_Manager<Grp_Class> {
protected:
    Owner*  _owner;
public:
    virtual Grp_Class*  get_group(const std::string& name,
            bool create = false) const;
    Owned_Manager(Owner* owner): _owner(owner) {}
    virtual  ~Owned_Manager() {};
};

// methods
template <class Owner, class Grp_Class>
Grp_Class*
Owned_Manager<Owner, Grp_Class>::get_group(const std::string& name, bool create) const
{
    auto gmi = this->_groups.find(name);
    if (gmi != this->_groups.end())
        return (*gmi).second;

    if (!create)
        return nullptr;

    Grp_Class* grp = new Grp_Class(name, this->_owner);
    this->_groups[name] = grp;
    return grp;
}

template <class Grp_Class>
Grp_Class*
Global_Manager<Grp_Class>::get_group(const std::string& name, bool create) const
{
    auto gmi = this->_groups.find(name);
    if (gmi != this->_groups.end())
        return (*gmi).second;

    if (!create)
        return nullptr;

    Grp_Class* grp = new Grp_Class(name);
    this->_groups[name] = grp;
    return grp;
}

}  // namespace pseudobond

#endif  // pseudobonds_Manager
