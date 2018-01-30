from .BaseView import BaseView
from ..utils import ContextDecorator as _cm
from pathlib import Path

import PyQt5.QtWidgets as qt
from PyQt5 import QtCore
Qt = QtCore.Qt

class NewDocumentBatch(BaseView):
	def __init__(self, controller, parent, *args, **kwargs):
		super().__init__(controller, qt.QDialog, parent.window, *args, **kwargs)

		dialog = self.window
		dialog.setWindowTitle("New transaction")

		self._data = {key:qt.QLineEdit() for key in ('title', 'invoice')}
		self._data['recipient'] = qt.QComboBox()
		self.documents = None

		with _cm(self._data['recipient']) as cbox:
			cbox.setModel(controller.address_book)
			cbox.setInsertPolicy(cbox.NoInsert)
			cbox.setView(qt.QTreeView())

		with _cm(qt.QVBoxLayout(dialog)) as vbox:
			with _cm(qt.QFormLayout()) as form:
				vbox.addLayout(form)

				form.addRow(qt.QLabel('Receipient'), self._data['recipient'])
				form.addRow(qt.QLabel('Invoice number'), self._data['title'])

				with _cm(qt.QWidget()) as invdata:
					with _cm(qt.QHBoxLayout(invdata)) as hbox:
						hbox.setContentsMargins(0,0,0,0)
						hbox.addWidget(self._data['invoice'])
						browse = qt.QPushButton("Browse...")
						browse.clicked.connect(self.select_invoice)
						hbox.addWidget(browse)
					form.addRow(qt.QLabel('Invoice data'), invdata)

			with _cm(qt.QGroupBox('Documents')) as group:
				vbox.addWidget(group, 1)
				with _cm(qt.QVBoxLayout(group)) as vbox:
					hbox = qt.QHBoxLayout()
					vbox.addLayout(hbox)
					with _cm(qt.QPushButton("Add...")) as button:
						hbox.addWidget(button)
						button.clicked.connect(self.add_document)
					with _cm(qt.QPushButton("Remove")) as button:
						hbox.addWidget(button)
						button.clicked.connect(self.remove_document)
					hbox.addStretch(1)

					docs = qt.QTreeWidget()
					self.documents = docs
					docs.setHeaderLabels(('Name', 'Location'))
					vbox.addWidget(docs)

			with _cm(qt.QDialogButtonBox) as QDBB:
				qdbb = QDBB(QDBB.Ok | QDBB.Cancel)
			vbox.addWidget(qdbb)
			qdbb.accepted.connect(self.accept)
			qdbb.rejected.connect(dialog.reject)

		dialog.exec()

	def add_document(self):
		files, filter_ = qt.QFileDialog.getOpenFileNames(self.window)
		paths = [Path(f) for f in files]
		items = (qt.QTreeWidgetItem((path.name, str(path))) for path in paths)
		self.documents.addTopLevelItems(items)

	def remove_document(self):
		root = self.documents.invisibleRootItem()
		for i in self.documents.selectedItems():
			root.removeChild(i)

	def select_invoice(self):
		file_, filter_ = qt.QFileDialog.getOpenFileName(self.window)
		self._data['invoice'].setText(file_)

	def accept(self):
		# Process user input
		cbox = self._data['recipient']
		receiver = cbox.model().index(cbox.currentIndex(), 1)
		receiver = cbox.model().data(receiver)

		docbatch = {
			'title': self._data['title'].text(),
			'receiver': receiver,
		}

		invoice = self._data['invoice'].text()
		invoice = Path(invoice) if len(invoice) else None

		docs = []
		for i in range(self.documents.topLevelItemCount()):
			item = self.documents.topLevelItem(i)
			path = item.data(1, Qt.DisplayRole)
			path = Path(path)
			docs.append({'path': path})

		res, msg = self.controller.create_document_batch(invoice, docbatch, docs)
		if res:
			self.window.accept()
		else:
			qt.QMessageBox.warning(self.window, None, msg)
