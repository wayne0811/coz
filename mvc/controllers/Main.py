from ..views.Main import Main as MainView
from ..models import DocumentBatch, AddressBook
from ..utils import Account, NEM, Storage
import logging
import ipfsapi
import PyQt5

logging.basicConfig(level=logging.DEBUG)

class Main():
	def __init__(self, argv):
		self.app = PyQt5.QtWidgets.QApplication(argv)

		self.docbatch_model_send = DocumentBatch.DocumentBatchModel()
		self.docbatch_model_recv = DocumentBatch.DocumentBatchModel()
		self.docbatch_model_send.alias_func = self.get_alias
		self.docbatch_model_recv.alias_func = self.get_alias

		self.address_book = AddressBook.AddressBookModel()

		self.nem = NEM()
		self.view = None
		self.account = Account()

		self.load_addressbook_storage()

		self.view = MainView(self)

		self.init_ipfs()

	@property
	def account_label(self):
		label = self.account.label
		return self.account.address if label is None else label
	@account_label.setter
	def account_label(self, value):
		self.account.set_label(value or None)
		self.account_label_updated()

	def account_label_updated(self):
		if self.view:
			self.view.update(account=True)
			self.refresh_docbatch_aliases()

	def update_address_book(self):
		self.address_book.storage.save()
		self.refresh_docbatch_aliases()

	def refresh_docbatch_aliases(self):
		self.docbatch_model_send.refresh_aliases()
		self.docbatch_model_recv.refresh_aliases()

	def get_alias(self, addr):
		if addr == self.account.address:
			alias = self.account_label
		else:
			alias = self.address_book.getAlias(addr)
			alias = addr if alias is None else alias
		return alias

	def init_config_dir(self):
		from pathlib import Path
		config_dir = Path('./.config') # Todo: use XDG
		config_dir.mkdir(exist_ok=True)
		return config_dir

	def load_addressbook_storage(self):
		import shelve
		storage_dir = self.init_config_dir()
		addrbook = shelve.open(str(storage_dir / 'addrbook.db'))
		self.address_book.storage.set_shelve(addrbook, 'entries')
		self.address_book.storage.load()

	def load_account_storage(self):
		import shelve
		storage_dir = self.init_config_dir()
		account = shelve.open(str(storage_dir / '{}.db'.format(self.account.address)))

		self.account.storage.set_shelve(account, 'label')
		self.account.storage.load()

		self.docbatch_model_send.storage.set_shelve(account, 'txs_out')
		self.docbatch_model_send.clear()
		self.docbatch_model_send.storage.load()
		self.docbatch_model_recv.storage.set_shelve(account, 'txs_in')
		self.docbatch_model_recv.clear()
		self.docbatch_model_recv.storage.load()

	def run(self):
		return self.app.exec_()

	def load_privkey(self, path):
		old = self.account.address
		privkey = open(str(path)).readline().strip()
		self.account.storage.close()
		self.account = Account.from_privkey(privkey, self.nem)

		if old != self.account.address:
			self.load_account_storage()
			self.account_label_updated()

	def init_ipfs(self):
		try:
			self.ipfs = ipfsapi.connect('127.0.0.1', 5001)
		except ipfsapi.exceptions.ConnectionError as e:
			logging.warning(e)
			self.ipfs = None

		self.view.set_ipfs_ok(self.ipfs is not None)

	def get_incoming_transactions(self):
		txs = self.account.get_incoming_transactions(self.nem)
		dbs = []
		model = self.docbatch_model_recv
		hash_column = model.findColumn('Hash')
		skip_txs = set(model.index(r, hash_column).data() for r in range(model.rowCount()))
		for tx in txs['data']:
			if tx['meta']['hash']['data'] in skip_txs: continue
			db = DocumentBatch.DocumentBatch.from_transaction(self.account, tx, self.nem, self.ipfs)
			dbs.append(db)

		model.appendData(dbs)
		date_column = model.findColumn('Date')
		model.sort(date_column, PyQt5.QtCore.Qt.DescendingOrder)
		model.storage.save()

	def create_document_batch(self, invoice, kwargs, documents=[]):
		db = DocumentBatch.DocumentBatch(sender=self.account.address, **kwargs)

		for d_kwargs in documents:
			d = DocumentBatch.Document(**d_kwargs)
			db.add_document(d)

		recv_pubkey = self.nem.find_pubkey_from_address(db.receiver)
		if recv_pubkey:
			acc_recv = Account.from_pubkey(recv_pubkey, self.nem)
			db.upload(self.account, acc_recv, self.nem, self.ipfs, invoice)

			model = self.docbatch_model_send
			model.appendData([db])
			date_column = model.findColumn('Date')
			model.sort(date_column, PyQt5.QtCore.Qt.DescendingOrder)
			model.storage.save()
			return True, None
		else:
			return False, "Recipient pubkey not found"

	def download_docbatch(self, model, index, dest):
		return model.download_docbatch(index, dest, self.ipfs)

	def download_document(self, model, index1, index2, dest):
		model.download_document(index1, index2, dest, self.ipfs)

	def _debug(self):
		from pathlib import Path
		docbatch = {
			'title': '123',
			'receiver': 'TBOHNY6V7FXUEC5PCWZMDXE4RMJEPRJQP7F4PIYC',
		}
		invoice = Path('../data/invoice.csv')
		docs = [{'path':Path('../data/test1.txt')}]
		self.create_document_batch(invoice, docbatch, docs)
