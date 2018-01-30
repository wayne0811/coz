from contextlib import contextmanager
from .BaseView import BaseView
from ..utils import ContextDecorator as _cm
import logging

import PyQt5.QtWidgets as qt
from PyQt5 import QtCore
from PyQt5 import QtGui
Qt = QtCore.Qt

import sys
def excepthook(etype, value, tracebackobj):
	import traceback
	traceback.print_exception(etype, value, tracebackobj)
	msg = '{}:\n{}'.format(etype.__name__, str(value))
	qt.QMessageBox.critical(None, None, msg)
sys.excepthook = excepthook

class DocumentBatchMasterDetail(qt.QSplitter):
	def __init__(self, parent, view, datasource, *args, **kwargs):
		super().__init__(Qt.Horizontal, *args, **kwargs)
		self.view = view

		self.master = DocumentBatchMaster(self, datasource)

		self.detail = DocumentBatchDetail(self, self.master)

		self.setSizes((100, 200))

class DocumentBatchMaster(qt.QTreeView):
	def __init__(self, parent, datasource, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)

		self.setModel(datasource)
		self._actions = []

		columns = ('Title', 'Date')
		for i in range(self.model().columnCount()):
			if self.model().headerData(i, Qt.Horizontal, Qt.DisplayRole) not in columns:
				self.hideColumn(i)

		self.initContextMenu()

	@property
	def view(self): return self.parentWidget().view

	def initContextMenu(self):
		act_download = qt.QAction("Save as...")
		act_download.triggered.connect(self.download_docbatch)
		self.addAction(act_download)
		self.setContextMenuPolicy(Qt.ActionsContextMenu)

		# Must manually store QAction somewhere, otherwise it disappears from actions() list when scope expires
		self._actions.append(act_download)

	def download_docbatch(self):
		dir_ = qt.QFileDialog.getExistingDirectory(self)
		subdir = self.view.controller.download_docbatch(self.model(), self.currentIndex(), dir_)
		qt.QMessageBox.information(self, None, 'Files downloaded to {}'.format(subdir))

class DocumentBatchDetail(qt.QWidget):
	def __init__(self, parent, master, *args, **kwargs):
		super().__init__(parent, *args, **kwargs)

		self._actions = []
		self.master = master

		vbox = qt.QVBoxLayout(self)
		vbox.setContentsMargins(0,0,0,0)

		frame = qt.QGroupBox('Details')
		vbox.addWidget(frame)

		labels = qt.QFormLayout(frame)
		mapper = qt.QDataWidgetMapper(self)
		mapper.setModel(master.model())

		col_titles = {'FromAlias':'From', 'ToAlias':'To'}
		for text in ('FromAlias', 'ToAlias', 'Title', 'Date', 'IPFS', 'Hash'):
			left = qt.QLabel(col_titles.get(text, text) + ':')
			right = qt.QLabel('')
			right.setTextInteractionFlags(Qt.TextSelectableByMouse)
			labels.addRow(left, right)
			section = mapper.model().findColumn(text)
			if section is not None:
				mapper.addMapping(right, section, b'text')

		master.selectionModel().currentRowChanged.connect(mapper.setCurrentModelIndex)

		docs_tree = qt.QTreeView()
		docs_tree.setModel(master.model().document_model)
		vbox.addWidget(docs_tree)

		master.selectionModel().currentRowChanged.connect(master.model().setCurrentDocumentBatch)

		self.initContextMenu(docs_tree)

	@property
	def view(self): return self.parentWidget().view

	def initContextMenu(self, widget):
		act_download = qt.QAction("Save as...")
		act_download.triggered.connect(lambda : self.download_document(widget))
		widget.addAction(act_download)
		widget.setContextMenuPolicy(Qt.ActionsContextMenu)

		# Must manually store QAction somewhere, otherwise it disappears from actions() list when scope expires
		self._actions.append(act_download)

	def download_document(self, widget):
		model = widget.model()
		index = widget.currentIndex()
		index_master = self.master.currentIndex()
		file_, filter_ = qt.QFileDialog.getSaveFileName(self, directory=model.getFileName(index))
		if file_:
			self.view.controller.download_document(self.master.model(), index_master, index, file_)
			qt.QMessageBox.information(self, None, 'File downloaded to {}'.format(file_))

class Main(BaseView):
	class Signals(QtCore.QObject):
		addressChanged = QtCore.pyqtSignal(str)
		accountValidityChanged = QtCore.pyqtSignal(bool)
		dbSendValidityChanged = QtCore.pyqtSignal(bool)
		dbRecvValidityChanged = QtCore.pyqtSignal(bool)

	def __init__(self, controller, *args, **kwargs):
		super().__init__(controller, qt.QMainWindow, *args, **kwargs)
		root = self.window
		root.resize(800, 500)
		root.setWindowTitle("CoZ")

		self.signals = self.Signals()

		menubar = root.menuBar()
		with _cm(menubar.addMenu('File')) as file_:

			with _cm(qt.QAction('Load private key...', root)) as act:
				act.setShortcut('Ctrl+O')
				act.setIcon(QtGui.QIcon.fromTheme('document-open'))
				act.triggered.connect(self.load_privkey)
				file_.addAction(act)

			with _cm(qt.QAction('Set account name...', root)) as act:
				act.triggered.connect(self.change_account_label)
				self.signals.accountValidityChanged.connect(act.setEnabled)
				file_.addAction(act)

			with _cm(qt.QAction('Exit', root)) as act:
				act.setShortcut('Ctrl+Q')
				act.setIcon(QtGui.QIcon.fromTheme('application-exit'))
				act.setStatusTip('Exit application')
				act.triggered.connect(qt.qApp.quit)
				file_.addAction(act)

		with _cm(menubar.addMenu('Tools')) as tools:
			with _cm(qt.QAction('Address book...', root)) as act:
				act.setIcon(QtGui.QIcon.fromTheme('x-office-address-book'))
				act.triggered.connect(self.address_book)
				tools.addAction(act)

		with _cm(menubar.addMenu('Debug')) as debug:

			with _cm(qt.QAction('Send test transaction', root)) as act:
				act.triggered.connect(controller._debug)
				debug.addAction(act)

			with _cm(qt.QAction('Reconnect IPFS', root)) as act:
				act.triggered.connect(controller.init_ipfs)
				debug.addAction(act)

			with _cm(debug.addMenu('Reset storage')) as menu:
				reset_send = menu.addAction('Send')
				reset_send.triggered.connect(controller.docbatch_model_send.clear)
				reset_recv = menu.addAction('Receive')
				reset_recv.triggered.connect(controller.docbatch_model_recv.clear)
				reset_both = menu.addAction('Both')
				reset_both.triggered.connect(reset_send.trigger)
				reset_both.triggered.connect(reset_recv.trigger)

		# Tabs
		with _cm(qt.QTabWidget(root)) as tabs:
			tab_send = qt.QWidget()
			self.tab_send = tab_send
			tab_recv = qt.QWidget()
			self.tab_recv = tab_recv

			with _cm(tab_send) as tab:
				vbox = qt.QVBoxLayout()

				label = qt.QLabel("Account:")
				vbox.addWidget(label)
				self.signals.addressChanged.connect(label.setText)
				label.setTextInteractionFlags(Qt.TextSelectableByMouse)

				hbox = qt.QHBoxLayout()
				with _cm(qt.QPushButton("New...")) as button:
					button.setIcon(QtGui.QIcon.fromTheme('document-new'))
					hbox.addWidget(button)
					button.clicked.connect(self.new_document_batch)
					self.signals.accountValidityChanged.connect(button.setEnabled)
				with _cm(qt.QPushButton("Download...")) as button:
					button_download = button
					button.setIcon(QtGui.QIcon.fromTheme('document-save'))
					hbox.addWidget(button)
					self.signals.dbSendValidityChanged.connect(button.setEnabled)

				hbox.addStretch(1)

				#ttk.Label(f, text="([x] new files found)").grid(row=0, column=1)

				vbox.addLayout(hbox)
				dbmd = DocumentBatchMasterDetail(None, self, controller.docbatch_model_send)
				dbmd.master.selectionModel().currentRowChanged.connect(lambda idx: self.update(docbatch_send=idx))
				button_download.clicked.connect(dbmd.master.download_docbatch)
				vbox.addWidget(dbmd, 1)

				tab.setLayout(vbox)

			with _cm(tab_recv) as tab:
				vbox = qt.QVBoxLayout()

				label = qt.QLabel("Account:")
				vbox.addWidget(label)
				self.signals.addressChanged.connect(label.setText)
				label.setTextInteractionFlags(Qt.TextSelectableByMouse)

				hbox = qt.QHBoxLayout()
				with _cm(qt.QPushButton("Refresh")) as button:
					button.setIcon(QtGui.QIcon.fromTheme('view-refresh'))
					hbox.addWidget(button)
					button.clicked.connect(controller.get_incoming_transactions)
					self.signals.accountValidityChanged.connect(button.setEnabled)
				with _cm(qt.QPushButton("Download...")) as button:
					button_download = button
					button.setIcon(QtGui.QIcon.fromTheme('document-save'))
					hbox.addWidget(button)
					self.signals.dbRecvValidityChanged.connect(button.setEnabled)
				with _cm(qt.QPushButton("Reject")) as button:
					button.setIcon(QtGui.QIcon.fromTheme('process-stop'))
					hbox.addWidget(button)
					button.clicked.connect(self.docbatch_reject)
					self.signals.dbRecvValidityChanged.connect(button.setEnabled)
				with _cm(qt.QPushButton("Approve")) as button:
					button.setIcon(QtGui.QIcon.fromTheme('mail-reply-sender'))
					hbox.addWidget(button)
					button.clicked.connect(self.docbatch_accept)
					self.signals.dbRecvValidityChanged.connect(button.setEnabled)
				hbox.addStretch(1)

				vbox.addLayout(hbox)
				dbmd = DocumentBatchMasterDetail(None, self, controller.docbatch_model_recv)
				dbmd.master.selectionModel().currentRowChanged.connect(lambda idx: self.update(docbatch_recv=idx))
				button_download.clicked.connect(dbmd.master.download_docbatch)
				vbox.addWidget(dbmd, 1)
				tab.setLayout(vbox)

			tabs.addTab(tab_send, QtGui.QIcon.fromTheme('go-up'), "Send")
			tabs.addTab(tab_recv, QtGui.QIcon.fromTheme('go-down'), "Receive")
			root.setCentralWidget(tabs)

		self.update(True, QtCore.QModelIndex(), QtCore.QModelIndex())

		root.show()

	def new_document_batch(self):
		from .NewDocumentBatch import NewDocumentBatch
		view = NewDocumentBatch(self.controller, self)

	def address_book(self):
		from .AddressBook import AddressBook
		view = AddressBook(self.controller, self)
		self.controller.update_address_book()

	def load_privkey(self):
		file_, filter_ = qt.QFileDialog.getOpenFileName(self.window)
		if file_:
			self.controller.load_privkey(file_)
			qt.QMessageBox.information(self.window, None, 'Loaded NEM account: {}'.format(self.controller.account.address))

	def change_account_label(self):
		acc_label, ok = qt.QInputDialog.getText(self.window, 'Set account name', 'Account name', text=self.controller.account.label)
		if ok:
			self.controller.account_label = acc_label

	def update(self, account=False, docbatch_send=False, docbatch_recv=False):
		if account:
			self.signals.addressChanged.emit("Account: {}".format(self.controller.account_label))
			valid = bool(self.controller.account.privkey)
			self.signals.accountValidityChanged.emit(valid)

		def update_docbatch(index, signal):
			valid = index.isValid()
			if valid:
				db = index.data(Qt.UserRole)
				valid = valid and bool(db.tx_hash) and bool(db.ipfs_hash)
			signal.emit(valid)
		if docbatch_send: update_docbatch(docbatch_send, self.signals.dbSendValidityChanged)
		if docbatch_recv: update_docbatch(docbatch_recv, self.signals.dbRecvValidityChanged)

	def docbatch_accept(self):
		b = qt.QMessageBox.question(self.window, 'Accept invoice', 'This will broadcast a transaction to indicate acceptance of the selected invoice and documents. This cannot be undone. Continue?')
		if b == qt.QMessageBox.Yes:
			self.not_implemented()
	def docbatch_reject(self):
		b = qt.QMessageBox.question(self.window, 'Reject invoice', 'This will broadcast a transaction to indicate rejection of the selected invoice and documents. This cannot be undone. Continue?')
		if b == qt.QMessageBox.Yes:
			self.not_implemented()
	def not_implemented(self):
		logging.warning('This functionality is not implemented')

	def set_ipfs_ok(self, status):
		pass
