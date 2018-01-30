from ..utils import Storage
from PyQt5 import QtCore
Qt = QtCore.Qt

class AddressBookModel(QtCore.QAbstractTableModel):
	_headers = (
		('Name', ),
		('Address', ),
	)

	def __init__(self, parent=None):
		super().__init__(parent)

		self._data = []
		self.storage = Storage(self.loadDataDump, self.dumpData)

	def rowCount(self, parent=None):
		return len(self._data)

	def columnCount(self, parent=None):
		return len(self._headers)

	def data(self, index, role=Qt.DisplayRole):
		if role in (Qt.DisplayRole, Qt.EditRole):
			entry = self._data[index.row()]
			return entry[index.column()]

		return QtCore.QVariant()

	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			header, = self._headers[section]
			return header

		return QtCore.QVariant()

	def setData(self, index, value, role = Qt.EditRole):
		if role == Qt.EditRole:

			entry = list(self._data[index.row()])
			entry[index.column()] = value
			self._data[index.row()] = tuple(entry)

			self.dataChanged.emit(index, index)

			return True

		return False

	def flags(self, index):
		return super().flags(index) | Qt.ItemIsEditable

	def getAlias(self, addr):
		entries = {address:alias for alias, address in self._data}
		return entries.get(addr, None)

	def insertRows(self, position, rows, index=QtCore.QModelIndex()):
		self.beginInsertRows(index, position, position+rows-1)
		self._data[position:position] = [('', '')] * rows
		self.endInsertRows()
		return True

	def removeRows(self, position, rows, index=QtCore.QModelIndex()):
		self.beginRemoveRows(index, position, position+rows-1)
		del self._data[position:position+rows]
		self.endRemoveRows()
		return True

	def loadDataDump(self, data):
		self.beginResetModel()
		self._data = [tuple(d) for d in data]
		self.endResetModel()

	def dumpData(self):
		return [
			tuple(self.index(row, col).data() for col in range(self.columnCount())) \
			for row in range(self.rowCount())
		]

	def sort(self, column, order):
		pass
