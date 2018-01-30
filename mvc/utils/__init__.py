from contextlib import contextmanager
import jsonrpyc
from subprocess import Popen, PIPE
import base64
from functools import lru_cache

@contextmanager
def ContextDecorator(obj): yield obj

class Storage():
	def __init__(self, load_func, save_func):
		self.load_func = load_func
		self.save_func = save_func
		self.shelve = None

	def set_shelve(self, shelve, key):
		self.shelve = shelve
		self.key = key

	@property
	def data(self):
		return self.shelve[self.key]
	@data.setter
	def data(self, newdata):
		self.shelve[self.key] = newdata
	@data.deleter
	def data(self):
		del self.shelve[self.key]

	@property
	def initialized(self):
		return self.shelve is not None
	@property
	def has_data(self):
		return self.initialized and self.key in self.shelve

	def load_unsafe(self): self.load_func(self.data)
	def load(self):
		if self.has_data:
			self.load_unsafe()
	def load_default(self, default):
		if self.has_data:
			self.load()
		else:
			self.load_func(default)

	def save(self):
		self.data = self.save_func()

	def reset(self):
		if self.has_data: del self.data

	def close(self):
		if self.initialized:
			self.shelve.close()

class Account():

	@classmethod
	def from_privkey(cls, privkey, nem):
		pubkey = nem.privkey_to_pubkey(privkey)
		acc = cls.from_pubkey(pubkey, nem)
		acc.privkey = privkey
		return acc

	@classmethod
	def from_pubkey(cls, pubkey, nem):
		acc = cls()
		acc.pubkey = pubkey
		acc.address = nem.pubkey_to_address(pubkey)
		return acc

	def __init__(self):
		self.label = None
		self.pubkey = None
		self.privkey = None
		self.address = None
		self.storage = Storage(lambda v: self.__setattr__('label', v), lambda: self.label)

	def get_incoming_transactions(self, nem):
		return nem.get_incoming_transactions(self.address)

	def send_transfer_transaction(self, nem, amount, message):
		assert(self.privkey)
		return nem.send_transfer_transaction(self.privkey, self.address, amount, message, block=1)

	def set_label(self, label):
		self.label = label
		if self.storage.initialized:
			self.storage.save()

class NEM():

	def __init__(self):
		proc = Popen(["node", "./node/coz"], stdin=PIPE, stdout=PIPE, universal_newlines=True)
		self.proc = proc
		self.rpc = jsonrpyc.RPC(stdout=proc.stdin, stdin=proc.stdout)
		# First message must have id>0 or it is treated as notification. Node json-rpc-server-stream bug?
		self.rpc._i = 0

	@lru_cache()
	def privkey_to_pubkey(self, privkey):
		params = {'privkey': privkey}
		return self.rpc('privkey-to-pubkey', kwargs=params, block=0.1)

	@lru_cache()
	def pubkey_to_address(self, pubkey):
		params = {'pubkey': pubkey}
		return self.rpc('pubkey-to-address', kwargs=params, block=0.1)

	def find_pubkey_from_address(self, address):
		params = {'address': address}
		txs = self.rpc('get-outgoing-transactions', kwargs=params, block=0.1)
		if len(txs.get('data',[])):
			tx = txs['data'][0]
			pubkey = tx['transaction']['signer']
			return pubkey

		return None

	def get_incoming_transactions(self, address):
		params = {'address': address}
		return self.rpc('get-incoming-transactions', kwargs=params, block=1)

	def send_transfer_transaction(self, privkey, address, amount, message, recv_pubkey=None, callback=None, block=0):
		params = {
			'address': address,
			'message': message,
			'privkey': privkey,
		}
		if recv_pubkey:
			params['recv_pubkey'] = recv_pubkey

		return self.rpc('send-transfer-transaction', kwargs=params, callback=callback, block=block)

	@staticmethod
	def encrypt_subproc(privkey, pubkey, msg, encrypt=True):
		from subprocess import Popen, PIPE
		proc = Popen(["node", "./node/encrypt", "encrypt" if encrypt else "decrypt"], stdin=PIPE, stdout=PIPE, universal_newlines=True)
		input_ = '\n'.join([privkey, pubkey, msg])
		return proc.communicate(input_)

	def encrypt(self, privkey, pubkey, payload):
		out, err = self.encrypt_subproc(privkey, pubkey, payload, True)
		if out:
			return bytes.fromhex(out)

	def decrypt(self, privkey, pubkey, payload):
		from binascii import hexlify
		payload = hexlify(payload).decode()
		out, err = self.encrypt_subproc(privkey, pubkey, payload, False)
		if out:
			return bytes.fromhex(out)
