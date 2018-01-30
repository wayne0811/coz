#!/usr/bin/python
import sys
sys.path.insert(0,"./packages.zip")
from mvc.controllers.Main import Main

app = Main(sys.argv)
sys.exit(app.run())
