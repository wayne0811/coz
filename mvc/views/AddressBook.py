from .BaseView import BaseView
from ..utils import ContextDecorator as _cm

import PyQt5.QtWidgets as qt
from PyQt5 import QtCore
Qt = QtCore.Qt
from PyQt5 import QtGui

class NewAddress(qt.QDialog):
	def __init__(self, parent):
		super().__init__(parent)
		self.setWindowTitle("New alias")
		self.setMinimumWidth(400)

		vbox = qt.QVBoxLayout(self)
		form = qt.QFormLayout()
		vbox.addLayout(form)

		nonempty = QtCore.QRegExp(r'.{1,}')
		with _cm(qt.QLabel("Name")) as label:
			self._name = qt.QLineEdit()
			form.addRow(label, self._name)
			validator = QtGui.QRegExpValidator(nonempty, self)
			self._name.setValidator(validator)
			self._name.textEdited.connect(self.validate)

		with _cm(qt.QLabel("Address")) as label:
			self._address = qt.QLineEdit()
			form.addRow(label, self._address)
			validator = QtGui.QRegExpValidator(nonempty, self)
			self._address.setValidator(validator)
			self._address.textEdited.connect(self.validate)

		with _cm(qt.QDialogButtonBox) as QDBB:
			qdbb = QDBB(QDBB.Ok | QDBB.Cancel)
			self._ok = qdbb.button(QDBB.Ok)
		vbox.addWidget(qdbb)
		qdbb.accepted.connect(self.accept)
		qdbb.rejected.connect(self.reject)

		self.validate()

	def validate(self):
		feedbacks = []
		if not self._name.hasAcceptableInput():
			feedbacks.append("Name must not be blank")
		if not self._address.hasAcceptableInput():
			feedbacks.append("Invalid NEM address")

		button = self._ok
		button.setToolTip('\n'.join(feedbacks))
		valid = len(feedbacks) == 0
		button.setEnabled(valid)

		return valid

	def done(self, r):
		if not r or self.validate():
			super().done(r)

class AddressBook(BaseView):
	def __init__(self, controller, parent, *args, **kwargs):
		super().__init__(controller, qt.QDialog, parent.window, *args, **kwargs)

		dialog = self.window
		dialog.setWindowTitle("Address book")
		dialog.sizeHint = lambda : QtCore.QSize(600, 400)

		self.treeview = None

		with _cm(qt.QVBoxLayout(dialog)) as vbox:
			hbox = qt.QHBoxLayout()
			vbox.addLayout(hbox)
			with _cm(qt.QPushButton("Add...")) as button:
				hbox.addWidget(button)
				button.clicked.connect(self.add_address)
			with _cm(qt.QPushButton("Remove")) as button:
				hbox.addWidget(button)
				button.clicked.connect(self.remove_address)
			hbox.addStretch(1)

			addrs = qt.QTreeView()
			self.treeview = addrs
			addrs.setModel(controller.address_book)
			vbox.addWidget(addrs)

			with _cm(qt.QDialogButtonBox) as QDBB:
				qdbb = QDBB(QDBB.Close)
			vbox.addWidget(qdbb)
			qdbb.rejected.connect(self.on_close)

		dialog.exec_()

	def add_address(self):
		dialog = NewAddress(self.window)
		if(dialog.exec_()):
			model = self.treeview.model()
			row = model.rowCount()
			model.insertRow(row)
			model.setData(model.index(row, 0), dialog._name.text())
			model.setData(model.index(row, 1), dialog._address.text())

	def remove_address(self):
		indexes = self.treeview.selectedIndexes()
		rows = set(i.row() for i in indexes)
		for row in rows:
			self.treeview.model().removeRow(row)

	def on_close(self):
		self.window.reject()
		pass
