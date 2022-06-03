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

from chimerax.core.tools import ToolInstance
from chimerax.core.errors import UserError
from chimerax.core.settings import Settings
from Qt.QtCore import Qt

class DouseSettings(Settings):
    AUTO_SAVE = {
        "show_hbonds": True,
    }

class DouseResultsViewer(ToolInstance):
    def __init__(self, session, tool_name, orig_model=None, douse_model=None, compared_waters=None):
        # if 'model' is None, we are being restored from a session and _finalize_init() will be called later
        super().__init__(session, tool_name)
        self.settings = DouseSettings(session, tool_name)
        if douse_model is None:
            return
        self._finalize_init(orig_model, douse_model, compared_waters)

    def _finalize_init(self, orig_model, douse_model, compared_waters, *, from_session=False):
        self.orig_model = orig_model
        self.douse_model = douse_model
        self.compared_waters = [x.__class__(sorted(x)) for x in compared_waters] if compared_waters else None
        from chimerax.core.models import REMOVE_MODELS
        self.handlers = [self.session.triggers.add_handler(REMOVE_MODELS, self._models_removed_cb)]

        from chimerax.ui import MainToolWindow
        self.tool_window = MainToolWindow(self, close_destroys=False, statusbar=False)
        parent = self.tool_window.ui_area

        from Qt.QtWidgets import QHBoxLayout, QButtonGroup, QVBoxLayout, QRadioButton, QCheckBox
        from Qt.QtWidgets import QPushButton, QLabel, QToolButton
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        parent.setLayout(layout)
        if self.compared_waters:
            # we kept the input waters
            self.radio_group = QButtonGroup(parent)
            self.radio_group.buttonClicked.connect(self._update_residues)
            self.button_layout = but_layout = QVBoxLayout()
            layout.addLayout(but_layout)
            self.douse_only_button = QRadioButton(parent)
            self.radio_group.addButton(self.douse_only_button)
            but_layout.addWidget(self.douse_only_button)
            self.in_common_button = QRadioButton(parent)
            self.radio_group.addButton(self.in_common_button)
            but_layout.addWidget(self.in_common_button)
            self.original_only_button = QRadioButton(parent)
            self.radio_group.addButton(self.original_only_button)
            but_layout.addWidget(self.original_only_button)
            self._update_button_texts()
            self.douse_only_button.setChecked(True)
            self.filter_residues = self.compared_waters[1]
        else:
            # didn't keep the input waters
            self.radio_group = None
            from .douse import _water_residues
            self.filter_residues = sorted(_water_residues(self.douse_model))
        self.filter_model = self.douse_model
        from chimerax.atomic.widgets import ResidueListWidget
        self.res_list = ResidueListWidget(self.session, filter_func=self._filter_residues)
        if from_session:
            # Complicated code to avoid having the residue list callback change
            # the restored session state:  after one frame drawn look for a new
            # frame where there aren't changes pending, then hook up callback.
            # Three handlers are involved because "frame drawn" is not called
            # if "new frame" has nothing to draw.
            cb_info = []
            def new_frame_handler(*args, ses=self.session, cb_info=cb_info,
                    signal=self.res_list.value_changed, handler=self._res_sel_cb):
                if ses.change_tracker.changed:
                    from chimerax.atomic import get_triggers
                    get_triggers().add_handler("changes done", cb_info[0])
                else:
                    signal.connect(handler)
                from chimerax.core.triggerset import DEREGISTER
                return DEREGISTER
            def changes_done_handler(*args, ses=self.session):
                ses.triggers.add_handler("new frame", new_frame_handler)
                from chimerax.core.triggerset import DEREGISTER
                return DEREGISTER
            cb_info.append(changes_done_handler)
            def frame_drawn_handler(*args, ses=self.session):
                ses.triggers.add_handler("new frame", new_frame_handler)
                from chimerax.core.triggerset import DEREGISTER
                return DEREGISTER
            self.session.triggers.add_handler("frame drawn", frame_drawn_handler)
        else:
            self.res_list.value_changed.connect(self._res_sel_cb)
        layout.addWidget(self.res_list)

        self.hbond_groups = {}
        controls_layout = QVBoxLayout()
        hbonds_layout = QVBoxLayout()
        hbonds_layout.setSpacing(1)
        self.show_hbonds = check = QCheckBox("Show hydrogen bonds")
        check.setChecked(self.settings.show_hbonds)
        check.clicked.connect(self._show_hbonds_cb)
        hbonds_layout.addWidget(check)
        disclosure_layout = QHBoxLayout()
        self.params_arrow = QToolButton()
        self.params_arrow.setArrowType(Qt.RightArrow)
        self.params_arrow.setMaximumSize(16, 16)
        self.params_arrow.clicked.connect(self._hb_disclosure_cb)
        disclosure_layout.addWidget(self.params_arrow, alignment=Qt.AlignRight)
        disclosure_layout.addWidget(QLabel(" H-Bond Parameters"), alignment=Qt.AlignLeft)
        disclosure_layout.addStretch(1)
        hbonds_layout.addLayout(disclosure_layout)
        from chimerax.hbonds.gui import HBondsGUI
        self.hb_gui = HBondsGUI(self.session, settings_name="Douse H-bonds", compact=True, inter_model=False,
            show_bond_restrict=False, show_inter_model=False, show_intra_model=False, show_intra_mol=False,
            show_intra_res=False, show_log=False, show_model_restrict=False, show_retain_current=False,
            show_reveal=False, show_salt_only=False, show_save_file=False, show_select=False)
        self.hb_gui.layout().setContentsMargins(0,0,0,0)
        self.hb_gui.setHidden(True)
        hbonds_layout.addWidget(self.hb_gui)
        hb_apply_layout = QHBoxLayout()
        hb_apply_layout.addStretch(1)
        self.hb_apply_but = apply_but = QPushButton("Apply")
        self.hb_apply_but.setHidden(True)
        apply_but.clicked.connect(self._update_hbonds)
        hb_apply_layout.addWidget(apply_but)
        self.hb_apply_label = QLabel("above parameters")
        self.hb_apply_label.setHidden(True)
        hb_apply_layout.addWidget(self.hb_apply_label)
        hb_apply_layout.addStretch(1)
        hbonds_layout.addLayout(hb_apply_layout)
        controls_layout.addLayout(hbonds_layout)
        if not from_session and self.settings.show_hbonds:
            self._show_hbonds_cb(True)
        delete_layout = QHBoxLayout()
        but = QPushButton("Delete")
        but.clicked.connect(self._delete_waters)
        delete_layout.addWidget(but, alignment=Qt.AlignRight)
        delete_layout.addWidget(QLabel("chosen water(s)"), alignment=Qt.AlignLeft)
        controls_layout.addLayout(delete_layout)
        layout.addLayout(controls_layout)

        self.tool_window.manage('side')

    def delete(self):
        for handler in self.handlers:
            handler.remove()
        self.orig_model = self.douse_model = None
        super().delete()

    @classmethod
    def restore_snapshot(cls, session, data):
        inst = super().restore_snapshot(session, data['ToolInstance'])
        inst._finalize_init(data['orig_model'], data['douse_model'], data['compared_waters'],
            from_session=True)
        if data['radio info']:
            for but in inst.radio_group.buttons():
                if but.text() == data['radio info']:
                    but.setChecked(True)
                    inst._update_residues()
                    break
        if data['water']:
            inst.res_list.blockSignals(True)
            inst.res_list.value = data['water']
            inst.res_list.blockSignals(False)
        inst.settings.show_hbonds = data['show hbonds']
        inst.show_hbonds.setChecked(data['show hbonds'])
        return inst

    SESSION_SAVE = True

    def take_snapshot(self, session, flags):
        data = {
            'ToolInstance': ToolInstance.take_snapshot(self, session, flags),
            'compared_waters': self.compared_waters,
            'douse_model': self.douse_model,
            'orig_model': self.orig_model,
            'radio info': self.radio_group.checkedButton().text() if self.radio_group else None,
            'show hbonds': self.settings.show_hbonds,
            'version': 1,
            'water': self.res_list.value,
        }
        return data

    def _delete_waters(self):
        waters = self.res_list.value
        if not waters:
            raise UserError("No waters chosen")
        if len(waters) > 1:
            from chimerax.ui.ask import ask
            if ask(self.session, "Really delete %d waters?" % len(waters),
                    default="no", title="Delete waters") == "no":
                return
        from chimerax.atomic import Residues
        Residues(waters).atoms.delete()

    def _filter_residues(self, r):
        return r.structure == self.filter_model and r in self.filter_residues

    def _hb_disclosure_cb(self, *args):
        is_hidden = self.hb_gui.isHidden()
        self.params_arrow.setArrowType(Qt.DownArrow if is_hidden else Qt.RightArrow)
        self.hb_gui.setHidden(not is_hidden)
        self.hb_apply_but.setHidden(not is_hidden)
        self.hb_apply_label.setHidden(not is_hidden)

    def _make_hb_group(self):
        model = self.filter_model
        all_input, douse_only, douse_in_common, input_in_common = self.compared_waters
        if self.radio_group:
            checked_button = self.radio_group.checkedButton()
            text = checked_button.text()
            left_paren = text.index('(')
            name = text[:left_paren] + " H-bonds"
            if checked_button == self.douse_only_button:
                waters = douse_only
            elif checked_button == self.original_only_button:
                waters = all_input - input_in_common
            else:
                waters = douse_in_common
        else:
            waters = douse_only
            name = "Douse H-bonds"
        cmd_name, spec, args = self.hb_gui.get_command()
        from chimerax.atomic import concise_residue_spec
        spec = concise_residue_spec(self.session, waters)
        from chimerax.core.commands import run, StringArg
        run(self.session, '%s %s %s restrict any name %s' % (cmd_name, spec, args, StringArg.unparse(name)))
        return model.pseudobond_group(name, create_type="per coordset")

    def _models_removed_cb(self, trig_name, trig_data):
        if self.douse_model in trig_data:
            self.delete()
        elif self.orig_model in trig_data:
            self.douse_only_button.setChecked(True)
            self._update_residues()
            self.tool_window.ui_area.layout().removeItem(self.button_layout)

    def _res_sel_cb(self):
        selected = self.res_list.value
        if not selected:
            cmd = "~select; view %s" % self.douse_model.atomspec
        else:
            if selected[0].structure.display:
                base_cmd = ""
            else:
                base_cmd = "show %s models; " % selected[0].structure.atomspec
            from chimerax.atomic import concise_residue_spec
            spec = concise_residue_spec(self.session, selected)
            cmd = base_cmd + f"select {spec}; disp {spec} :<4; view {spec} @<4"
        from chimerax.core.commands import run
        run(self.session, cmd)

    def _show_hbonds_cb(self, checked):
        self.settings.show_hbonds = checked
        for group in self.hbond_groups.values():
            group.display = False
        if checked:
            group_key = self.radio_group.checkedButton() if self.radio_group else None
            try:
                group = self.hbond_groups[group_key]
            except KeyError:
                self.hbond_groups[group_key] = group = self._make_hb_group()
            group.display = True

    def _update_button_texts(self):
        all_input, douse_only, douse_in_common, input_in_common = self.compared_waters
        self.douse_only_button.setText("Douse only (%d)" % len(douse_only))
        self.in_common_button.setText("In common (%d)" % len(input_in_common))
        self.original_only_button.setText("Input only (%d)" % len(all_input - input_in_common))

    def _update_hbonds(self):
        group_key = self.radio_group.checkedButton() \
            if (self.radio_group and self.settings.show_hbonds) else None
        self.session.models.close([group for key, group in self.hbond_groups.items() if key != group_key])
        if self.settings.show_hbonds:
            self.hbond_groups[group_key] = self._make_hb_group()

    def _update_residues(self):
        all_input, douse_only, douse_in_common, input_in_common = self.compared_waters
        checked = self.radio_group.checkedButton()
        if checked == self.douse_only_button:
            self.filter_model = self.douse_model
            self.filter_residues = douse_only
        elif checked == self.original_only_button:
            self.filter_model = self.orig_model
            self.filter_residues = all_input - input_in_common
        else:
            self.filter_model = self.orig_model
            self.filter_residues = input_in_common
        if self.show_hbonds.isChecked():
            self._show_hbonds_cb(True)
        self.res_list.refresh()
