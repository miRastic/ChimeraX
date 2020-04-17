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

# Define SUBDIRS with a list of subdirectories to make
# before including this file.  The convolutions below
# enable parallel makes across subdirectories.
#
# The targets are all, install, clean, and test.

ifdef NO_SUBDIR_INSTALL
install:
else
ifdef TWO_PASS_INSTALL
DEPS_SUBDIR_INSTALL = $(SUBDIRS:=.dep-install)
.PHONY: $(DEPS_SUBDIR_INSTALL)
NO_DEPS_SUBDIR_INSTALL = $(SUBDIRS:=.nodep-install)
.PHONY: $(NO_DEPS_SUBDIR_INSTALL)
nodeps-install: $(NO_DEPS_SUBDIR_INSTALL)
$(NO_DEPS_SUBDIR_INSTALL):
	$(MAKE) -C $(subst .nodep-install,,$@) DEVEL_ARGS="noDeps true" install
deps-install: $(DEPS_SUBDIR_INSTALL)
$(DEPS_SUBDIR_INSTALL):
	$(MAKE) -C $(subst .dep-install,,$@) install
install:
	$(MAKE) nodeps-install
	$(MAKE) -j 1 deps-install
else
SUBDIR_INSTALL = $(SUBDIRS:=.install)
.PHONY: $(SUBDIR_INSTALL)
install: $(SUBDIR_INSTALL)
$(SUBDIR_INSTALL):
	$(MAKE) -C $(subst .install,,$@) install
endif
endif

ifdef NO_SUBDIR_CLEAN
clean:
else
SUBDIR_CLEAN = $(SUBDIRS:=.clean)
.PHONY: $(SUBDIR_CLEAN)
clean: $(SUBDIR_CLEAN)
$(SUBDIR_CLEAN):
	$(MAKE) -C $(subst .clean,,$@) clean
endif

ifdef NO_SUBDIR_TEST
test:
else
SUBDIR_TEST = $(SUBDIRS:=.test)
.PHONY: $(SUBDIR_TEST)
test: $(SUBDIR_TEST)
$(SUBDIR_TEST):
	$(MAKE) -C $(subst .test,,$@) test
endif

ifdef SUBDIR_SYNC
SUBDIR_SYNC = $(SUBDIRS:=.sync)
.PHONY: $(SUBDIR_SYNC)
sync: $(SUBDIR_SYNC)
$(SUBDIR_SYNC):
	$(MAKE) -C $(subst .sync,,$@) sync
else
sync:
endif
