from PyQt5.QtWidgets import QMainWindow

class BaseView():
	def __init__(self, controller, qt_class=QMainWindow, *args, **kwargs):
		self.controller = controller
		self.window = qt_class(*args, **kwargs)
