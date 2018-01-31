from pathlib import Path
import datetime
import time
import logging
from ..utils import Storage
from PyQt5.QtCore import (
	QAbstractTableModel,
	QModelIndex,
	Qt,
	QVariant
)

class EncryptionMethods():
# TODO: Stream data instead of storing in memory
	class Base():
		def __init__(self, key=None):
			self.key = None

		@classmethod
		def genkey(cls):
			return None

	class Dummy(Base):
		def encrypt(self, data):
			return data

		def decrypt(self, data):
			return data

	class AES(Base):
		import os, pyaes

		def __init__(self, key=None):
			self.key = key or self.genkey()
			self.mode = self.pyaes.AESModeOfOperationCTR(self.key)

		@classmethod
		def genkey(cls):
			return cls.os.urandom(32)

		def encrypt(self, data):
			return self.mode.encrypt(data)

		def decrypt(self, data):
			return self.mode.decrypt(data)

class Document():
	def __init__(self, path, name=None):
		self.path = Path(path)
		self.name = name if name else self.path.name
		self.hash = ''

	def upload(self, ipfs, encrypt_cls, key):
		import io
		enc = encrypt_cls(key)
		data = io.BytesIO(enc.encrypt(self.path.open('rb').read()))
		res = ipfs.add(data)
		logging.debug(res)
		self.hash = res['Hash']

		return self.hash, enc.key

	def download(self, dest, ipfs, encrypt_cls, key):
		if not ipfs: raise ValueError

		data = ipfs.cat(self.hash)
		data = encrypt_cls(key).decrypt(data)
		open(dest, 'wb').write(data)

class DocumentBatch():
	def __init__(self, title, sender=None, receiver=None):
		self.title = title
		self.timestamp = int(time.time())
		self.documents = []
		self.tx_hash = None
		self.ipfs_hash = None

		self.sender = sender
		self.receiver = receiver

	@property
	def localtime(self):
		dt = datetime.datetime.fromtimestamp(self.timestamp)
		return str(dt)

	def add_document(self, doc):
		self.documents.append(doc)

	def upload(self, acc_send, acc_recv, nem, ipfs, invoice, encrypt=True):
		assert(self.sender == acc_send.address)
		assert(self.receiver == acc_recv.address)

		# Upload documents
		ipfs_files = ipfs.object_new('unixfs-dir')
		enc_class = EncryptionMethods.AES if encrypt else EncryptionMethods.Dummy
		enc_key = enc_class.genkey()
		for d in self.documents:
			d.upload(ipfs, enc_class, enc_key)
			ipfs_files = ipfs.object_patch_add_link(ipfs_files['Hash'], d.name, d.hash)

		ipfs.pin_add(ipfs_files['Hash'])
		for d in self.documents:
			ipfs.pin_rm(d.hash)

		# Root directory
		ipfs_root = ipfs.object_new('unixfs-dir')
		ipfs_root = ipfs.object_patch_add_link(ipfs_root['Hash'], 'files', ipfs_files['Hash'])
		ipfs.pin_update(ipfs_files['Hash'], ipfs_root['Hash'], unpin=True)

		import io
		def add_link_data(root, name, data):
			res = ipfs.add(io.BytesIO(data), pin=False)
			new = ipfs.object_patch_add_link(root['Hash'], name, res['Hash'])
			ipfs.pin_update(root['Hash'], new['Hash'], unpin=True)
			#ipfs.pin_rm(res['Hash'])
			return new

		# Add metadata
		ipfs_root = add_link_data(ipfs_root, 'title', self.title.encode())
		if encrypt:
			# TODO: encrypt AES key using NEM keypair before uploading
			ipfs_root = add_link_data(ipfs_root, 'key', enc_key)
		if invoice:
			data = invoice.open('rb').read()
			data = enc_class(enc_key).encrypt(data)
			ipfs_root = add_link_data(ipfs_root, 'invoice', data)

		logging.debug(ipfs_root['Hash'])

		# Send transfer transaction
		pubkey = acc_recv.pubkey if encrypt else None
		tx = nem.send_transfer_transaction(acc_send.privkey, self.receiver, 0, ipfs_root['Hash'], recv_pubkey=pubkey, block=1)
		logging.debug(tx)

		self.tx_hash = tx['transactionHash']['data']
		self.ipfs_hash = ipfs_root['Hash']

		return tx

	@classmethod
	def get_ipfs_hash(cls, acc_recv, tx, nem):
		assert(tx['transaction']['recipient'] == acc_recv.address)

		msg = tx['transaction']['message']['payload']
		msg = bytes.fromhex(msg)
		# Decode transaction message
		if tx['transaction']['message']['type'] == 2:
			msg = nem.decrypt(acc_recv.privkey, tx['transaction']['signer'], msg)
		msg = msg.decode()

		tx_hash = tx['meta']['hash']['data']
		if msg.startswith('Q'):
			return msg
		else:
			logging.warning('{}: message "{}" not recognized'.format(tx_hash, msg))

		return None

	@classmethod
	def _get_metadata(cls, _hash, ipfs):

		# Return list of links within a directory
		def parse_ipfs(ipfs, _hash):
			files = ipfs.ls(_hash)
			msg = [(f['Name'], f['Hash']) for f in files['Objects'][0]['Links']]
			return msg

		root = dict(parse_ipfs(ipfs, _hash))
		root['files'] = parse_ipfs(ipfs, root['files'])

		# Check for required fields
		for key in ('title', 'invoice'):
			root[key]

		return root

	def get_metadata(self, ipfs):
		return self._get_metadata(self.ipfs_hash, ipfs)

	@classmethod
	def from_metadata(cls, nem, ipfs, tx, ipfs_hash, meta):
		db = DocumentBatch('', sender=nem.pubkey_to_address(tx['transaction']['signer']), receiver=tx['transaction']['recipient'])
		nemesis_block = 1427587585
		db.timestamp = nemesis_block + int(tx['transaction']['timeStamp'])
		db.tx_hash = tx['meta']['hash']['data']
		db.ipfs_hash = ipfs_hash
		if meta:
			db.title = ipfs.cat(meta['title']).decode()
			for name, _hash in meta['files']:
				d = Document('', name)
				d.hash = _hash
				db.add_document(d)
		return db

	@classmethod
	def from_transaction(cls, acc_recv, tx, nem, ipfs):
		_hash = None
		try:
			_hash = cls.get_ipfs_hash(acc_recv, tx, nem)
			metadata = cls._get_metadata(_hash, ipfs)
		except Exception as e:
			logging.error('Error when parsing transaction {}:'.format(tx['meta']['hash']['data']))
			import traceback
			traceback.print_exc()
			metadata = None

		db = cls.from_metadata(nem, ipfs, tx, _hash, metadata)
		return db

	def download(self, ipfs, destination):
		if not ipfs: raise ValueError

		destination = Path(destination)

		# Generate a new folder by adding a numeric suffix
		suffix_num = None
		while True:
			suffix = '_{}'.format(suffix_num) if suffix_num else ''
			subdir = destination / ('{}_{}'.format(self.title, self.tx_hash) + suffix)
			logging.debug(str(subdir))
			if subdir.exists():
				suffix_num = suffix_num+1 if suffix_num else 1
			else:
				break
		subdir.mkdir()
		# Download files
		ipfs.get(self.ipfs_hash + '/files', filepath=str(subdir)+'/')

		metadata = self.get_metadata(ipfs)
		# Todo: include name of invoice file in metadata
		open(str(subdir / 'invoice.csv'), 'wb').write(ipfs.cat(self.ipfs_hash + '/invoice'))

		def decrypt_inplace(method, key, file_):
			data = open(file_, 'rb').read()
			data = method(key).decrypt(data)
			open(file_, 'wb').write(data)

		enc_key = metadata.get('key')
		if enc_key:
			enc_key = ipfs.cat(self.ipfs_hash + '/key')
			method = EncryptionMethods.AES
			for path in [subdir/'invoice.csv'] + [subdir/'files'/n for n,h in metadata['files']]:
				path = str(path)
				decrypt_inplace(method, enc_key, path)

		return str(subdir)

class QTableModel(QAbstractTableModel):
	_headers = ()

	def __init__(self, parent=None):
		super().__init__(parent)

		self._data = []

	def rowCount(self, parent=None):
		return len(self._data)

	def columnCount(self, parent=None):
		return len(self._headers)

	def data(self, index, role=Qt.DisplayRole):
		if role in (Qt.DisplayRole, Qt.EditRole):
			header, func = self._headers[index.column()]
			data = self._data[index.row()]
			return func(self, data)
		elif role == Qt.UserRole:
			return self._data[index.row()]

		return QVariant()

	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			header, func = self._headers[section]
			return header

		return QVariant()

	def findColumn(self, header, role=Qt.DisplayRole):
		for i in range(self.columnCount()):
			if self.headerData(i, Qt.Horizontal, role) == header:
				return i
		return None

	def appendData(self, data):
		first = len(self._data)
		last = first + len(data) - 1
		self.beginInsertRows(QModelIndex(), first, last)
		self._data += data
		self.endInsertRows()

	def replaceData(self, data):
		self.beginResetModel()
		self._data[:] = data
		self.endResetModel()

	def clear(self):
		self.replaceData([])

	def sort(self, column, order=Qt.AscendingOrder):
		gen = iter(self.index(r, column) for r in range(self.rowCount()))
		indexes = sorted(gen, key=self.data, reverse=order!=Qt.AscendingOrder)
		newdata = [index.data(Qt.UserRole) for index in indexes]
		self.replaceData(newdata)

class DocumentModel(QTableModel):
	_headers = (
		('Name', lambda self, obj: obj.name),
		('Location', lambda self, obj: obj.path),
		('Hash', lambda self, obj: obj.hash),
	)

	def download_document(self, index, *args):
		doc = self._data[index.row()]
		doc.download(*args)

	def getFileName(self, index):
		doc = self._data[index.row()]
		return doc.name

class DocumentBatchModel(QTableModel):
	_headers = (
		('From', lambda self, obj: obj.sender),
		('FromAlias', lambda self, obj: self.alias_func(obj.sender)),
		('To', lambda self, obj: obj.receiver),
		('ToAlias', lambda self, obj: self.alias_func(obj.receiver)),
		('Title', lambda self, obj: obj.title),
		('Date', lambda self, obj: obj.localtime),
		('IPFS', lambda self, obj: obj.ipfs_hash),
		('Hash', lambda self, obj: obj.tx_hash),
	)

	def __init__(self, parent=None):
		super().__init__(parent)

		self.document_model = DocumentModel()
		self.alias_func = lambda addr: addr

		self.storage = Storage(self.replaceData, lambda : self._data)

	def setCurrentDocumentBatch(self, index):
		db = self._data[index.row()]
		self.document_model.replaceData(db.documents)

	def replaceData(self, data):
		super().replaceData(data)
		self.document_model.clear()

	def download_docbatch(self, index, dest, ipfs):
		db = self._data[index.row()]
		if db.ipfs_hash and db.tx_hash:
			return db.download(ipfs, dest)
		else:
			logging.warning('Invalid document batch')

	def download_document(self, index1, index2, dest, ipfs):
		db = self._data[index1.row()]
		metadata = db.get_metadata(ipfs)
		enc_key = metadata.get('key')
		enc_method = EncryptionMethods.Dummy
		if enc_key:
			enc_key = ipfs.cat(db.ipfs_hash + '/key')
			enc_method = EncryptionMethods.AES
		self.document_model.download_document(index2, dest, ipfs, enc_method, enc_key)

	def refresh_aliases(self):
		for col in ('FromAlias', 'ToAlias'):
			col = self.findColumn(col)
			index_start, index_end = [self.index(row, col) for row in (0, self.rowCount()-1)]
			self.dataChanged.emit(index_start, index_end)

def generate_data():
	docbatches = []

	for i in range(5):
		title = "Test {:d}".format(i+1)
		db = DocumentBatch(title)
		docbatches.append(db)
		db.tx_hash = "0xc0ffee"
		for j in range (3):
			name = "Document {:d}-{:d}".format(i+1, j+1)
			location = "C:\\"
			d = Document(location, name=name)
			d.hash = "0xdeadbeef"
			db.add_document(d)

	return docbatches
