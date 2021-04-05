# -*- coding: utf-8 -*-
from PyQt5.QtCore import QVariant, pyqtSlot, QObject
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox, QApplication
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsField, QgsGeometry, QgsPoint
from qgis.gui import QgsMapToolEmitPoint
# from qgis.core import QgsFeature, QgsFeatureRequest

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .zds_erpts_integration_dialog import eRPTSIntegrationDialog
import os.path
from .zds_erpts_integration_config_dialog import zdseRPTSIntegrationConfig
from .zds_erpts_integration_tool_dialog import zdseRPTSIntegrationTool
import base64

class eRPTSIntegration:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'eRPTSIntegration_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&eRPTS Integration')
        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.dlg = eRPTSIntegrationDialog()
        self.dlg_config = zdseRPTSIntegrationConfig()
        self.dlg_tool = zdseRPTSIntegrationTool()
        self.first_start = None
        self.config_start = None
        self.tool_start = None
        self.db = None
        self.current_lot = None
        self.current_lot_id = None
        self.muncode = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26"]
        self.munname = ["AURORA", "BAYOG", "DIMATALING", "DINAS", "DUMALINAO", "DUMINGAG", "GUIPOS", "JOSEFINA", "KUMALARANG", "LABANGAN", "LAKEWOOD", "LAPUYAN", "MAHAYAG", "MARGOSATUBBIG", "MIDSALIP", "MOLAVE", "PITOGO", "RAMON MAGSAYSAY", "SAN MIGUEL", "SAN PABLO", "SOMINOT", "TABINA", "TAMBULIG", "TIGBAO", "TUKURAN", "VINCENZO SAGUN"]
        self.curcode = None
        self.curname = None
        self.barcode = []
        self.barname = []
        self.curbrgy = None
        self.dbstatus = None
        self.selected_lot = None
        self.temp_col_names = []
        self.curdlg = None
        self.data_match = []
        self.data_error = []
        self.selected_feat = []
        self.active_layer = None
        self.array_layer = []
        self.array_feats = []
        self.tmcr_brgy = None
        self.tmcr_ref = []
        self.skipped_lots = []

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('eRPTSIntegration', message)


    def add_action(
        self,
        icon_dialog_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_dialog_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_config_path = ':/plugins/zds_erpts_integration/img/zds_erpts_integration_config_icon.png'
        icon_dialog_path = ':/plugins/zds_erpts_integration/img/zds_erpts_integration_dialog_icon.png'
        icon_tool_path = ':/plugins/zds_erpts_integration/img/zds_erpts_integration_config_icon.png'
        self.add_action(
            icon_config_path,
            text=self.tr(u'eRPT Plugin Configuration'),
            callback=self.run_config,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_dialog_path,
            text=self.tr(u'eRPT System Integration'),
            callback=self.run,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_tool_path,
            text=self.tr(u'eRPT System Toolbox'),
            callback=self.run_tool,
            parent=self.iface.mainWindow())
        # will be set False in run()
        self.first_start = True
        self.config_start = True
        self.tool_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&eRPTS Integration'),
                action)
            self.iface.removeToolBarIcon(action)

    def connect(self, dlg):
        import MySQLdb as mdb
        DBHOST = dlg.input_host.text()
        DBUSER = dlg.input_user.text()
        DBPASS = dlg.input_pass.text()
        DBNAME = dlg.input_data.text()
        try:
            db = mdb.connect(DBHOST, DBUSER, DBPASS, DBNAME)
            print("Database Connected Successfully")
        except mdb.Error as e:
            print("Database Not Connected Successfully")

    def retrieve(self, lot):
        if lot:
            self.curdlg.tw_value.setRowCount(0)
            self.curdlg.tw_value.setColumnCount(0)
            cur = self.connect_to_db().cursor()
            cur.execute(self.get_query1("liblandinfoall", lot, self.curcode, self.curbrgy))
            row = cur.fetchall()
            c_row = len(row)
            self.curdlg.tw_data.setRowCount(0)
            self.curdlg.tw_data.setColumnCount(0)
            self.curdlg.tw_info.setRowCount(0)
            self.curdlg.tw_info.setColumnCount(0)
            if c_row > 0:
                c_col = len(row[0])
                twr1 = 0
                twr2 = 0
                self.curdlg.tw_data.setColumnCount(c_col)
                self.curdlg.tw_info.setColumnCount(c_col)
                columns = []
                for i in range(len(cur.description)):
                    columns.append(cur.description[i][0])
                self.curdlg.tw_data.setHorizontalHeaderLabels(columns)
                self.curdlg.tw_info.setHorizontalHeaderLabels(columns)
                for r in range(c_row):
                    if row[r][c_col-1] is None:
                        twr1 += 1
                        self.curdlg.tw_data.setRowCount(twr1)
                        for c in range(c_col):
                            item = QTableWidgetItem(str(row[r][c]))
                            self.curdlg.tw_data.setItem(twr1 - 1, c, item)
                    else:
                        twr2 += 1
                        self.curdlg.tw_info.setRowCount(twr2)
                        status = 0
                        if str(row[r][c_col-1]) == "CANCELLED":
                            status = 1
                        elif str(row[r][c_col-1]) == "SUBDIVISION":
                            status = 2
                        for c in range(c_col):
                            item = QTableWidgetItem(str(row[r][c]))
                            if status == 0:
                                item.setForeground(QBrush(QColor(169, 169, 169)))
                            elif status == 1:
                                item.setForeground(QBrush(QColor(255, 0, 0)))
                            elif status == 2:
                                item.setForeground(QBrush(QColor(0, 0, 255)))
                            self.curdlg.tw_info.setItem(twr2-1, c, item)

    def get_query1(self, query, lot, mun, bar):
        instance = self.get_query(query).replace("$lot", lot).replace("$mun", mun).replace("$bar", bar)
        return instance

    def get_query2(self, query, mun):
        instance = self.get_query(query).replace("$mun", mun)
        return instance

    def get_query3(self, query, mun, bar):
        instance = self.get_query(query).replace("$mun", mun).replace("$bar", bar)
        return instance

    def get_query4(self, query, mun, bar, filter):
        instance = self.get_query(query).replace("$mun", mun).replace("$bar", bar).replace("$filter", filter)
        return instance

    def get_query(self, query):
        stored_file = self.get_store_folder() + "/GIS DataBase/" + query + ".ini"
        content = ""
        if os.path.exists(stored_file):
            f = open(stored_file, "r")
            content = f.read()
            f.close()
        else:
            QMessageBox.information(None, "Query File", "Query file does not exist!")
        return content

    def connect_to_db(self):
        import MySQLdb as mdb
        DBHOST = self.db[0]
        DBUSER = self.db[1]
        DBPASS = self.db[2]
        DBNAME = self.db[3]
        try:
            db = mdb.connect(DBHOST, DBUSER, DBPASS, DBNAME)
            self.curcode = self.muncode[self.munname.index(self.db[3].replace("erptax_", "").replace("_", " ").upper())]
            self.curname = self.munname[self.munname.index(self.db[3].replace("erptax_", "").replace("_", " ").upper())]
            self.dbstatus = "CONNECTED TO:  [" + self.curcode + "] " + self.curname + " DATABASE"
            return db
        except mdb.Error as e:
            self.dbstatus = "Connection Failed!"

    def get_active_feature(self, field_name):
        layer = self.iface.activeLayer()
        current_lot = []
        for feat in layer.selectedFeatures():
            tmp_value = feat[field_name]
            tmp_id = feat.id()
            current_lot.append(str(tmp_id))
            current_lot.append(str(tmp_value))
        if len(current_lot) == 0:
            current_lot = ["", ""]
        return current_lot

    def main_get_data(self):
        self.curdlg = self.dlg
        lot = self.dlg.txt_field_value.text()
        if lot != "":
            index = self.dlg.cb_field_values.findText(lot, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.dlg.cb_field_values.setCurrentIndex(index)
                # self.current_lot = self.dlg.cb_field_values.currentText()
            self.retrieve(lot)
        if self.dlg.cb_field_brgys.currentText() != "":
            self.set_cache2(self.dlg.cb_field_brgys.currentText())
        curlot = self.get_active_feature("LOT_NO")
        self.dlg.lbl_lot.setText("[SHP] CURRENT LOT: [" + curlot[0] + "] " + curlot[1])
        self.main_show_feature_attr()

    def main_selected_feature(self):
        if self.can_proc():
            curlot = self.get_active_feature("LOT_NO")
            self.dlg.lbl_lot.setText("[SHP] CURRENT LOT: [" + curlot[0] + "] " + curlot[1])
            self.main_show_feature_attr()

    def tool_get_data(self):
        self.curdlg = self.dlg_tool
        self.get_selected_lots()
        self.retrieve(self.current_lot)
        self.dlg_tool.lbl_brgy.setText("[SHP] CURRENT LOT: " + self.current_lot + " [" + self.curcode + "][" + self.curbrgy + "]" )

    def main_attr_field(self):
        layer = self.iface.activeLayer()
        self.dlg.cb_field_names.clear()
        for field in layer.fields():
            self.dlg.cb_field_names.addItem(field.name())

    def main_selected_lot(self):
        self.current_lot = self.get_active_feature(self.dlg.cb_field_names.currentText())[1]
        if self.current_lot != "":
            index = self.dlg.cb_field_values.findText(self.current_lot, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.dlg.cb_field_values.setCurrentIndex(index)

    def get_lot_list(self):
        layer = self.iface.activeLayer()
        feat = []
        if self.can_proc():
            for feature in layer.getFeatures():
                feat.append(feature["LOT_NO"])
            feat.sort()
        return feat

    def can_proc(self, attr="LOT_NO"):
        layer = self.iface.activeLayer()
        attr_count = len(layer.fields().names())
        can_proc = False
        for x in range(attr_count):
            if layer.fields().names()[x] == attr:
                can_proc = True
        return can_proc

    def set_cache2(self, brgy):
        stored_file = self.get_store_folder() + "/GIS DataBase/cache2.ini"
        if os.path.exists(stored_file):
            f = open(stored_file, "w+")
            f.write("CURRENT_BRGY=" + brgy)
            f.close()
        else:
            QMessageBox.information(None, "Cache File", "Cache file does not exist!")

    def get_layer_name(self):
        layer = self.iface.activeLayer()
        brgy_name = layer.name().lower().split("section")[0].replace("_", " ").strip().upper()
        print("Current Layer's Barangay: " + brgy_name)
        return brgy_name

    def set_brgy(self):
        temp_name = self.get_layer_name().upper()
        print(temp_name)
        print(self.barname)
        index = self.barname.index(temp_name)
        if index >= 0:
            self.curbrgy = self.barcode[self.barname.index(temp_name)]
        return index

    def save_conn(self):
        import MySQLdb as mdb
        DBHOST = self.dlg_config.input_host.text()
        DBUSER = self.dlg_config.input_user.text()
        DBPASS = self.dlg_config.input_pass.text()
        DBNAME = self.dlg_config.input_data.currentText()
        try:
            db = mdb.connect(DBHOST, DBUSER, DBPASS, DBNAME)
            self.dlg_config.lbl_status.setText("Database successfully connected.")
            stored_file = self.get_store_folder() + "/GIS DataBase/config.ini"
            f = open(stored_file, "w+")
            enc = self.encrypt(DBHOST + ";" + DBUSER + ";" + DBPASS + ";" + DBNAME)
            f.write(enc.decode('utf-8'))
            f.close()
            self.set_cache1(self.dlg_config.input_data.currentText())
            self.dlg_config.close()
        except mdb.Error as e:
            self.dlg_config.lbl_status.setText("Database connection failed!")

    def open_conn(self):
        stored_file = self.get_store_folder() + "/GIS DataBase/config.ini"
        haspath = os.path.exists(stored_file)
        if haspath:
            f = open(stored_file, "r")
            if f.mode == "r":
                content = f.read()
                dec = self.decrypt(content)
                dec_str = dec.decode("utf-8")
                self.db = dec_str.split(";")
                self.curcode = self.muncode[self.munname.index(self.db[3].replace("erptax_", "").replace("_", " ").upper())]
                self.curname = self.munname[self.munname.index(self.db[3].replace("erptax_", "").replace("_", " ").upper())]
            f.close()
        return haspath

    def encrypt(self, data):
        data_bytes = data.encode("utf-8")
        enc_data = base64.b64encode(data_bytes)
        return enc_data

    def decrypt(self, data):
        data_bytes = data.encode("utf-8")
        dec_data = base64.b64decode(data_bytes)
        return dec_data

    def get_store_folder(self):
        import ctypes
        from ctypes.wintypes import MAX_PATH
        dll = ctypes.windll.shell32
        buf = ctypes.create_unicode_buffer(MAX_PATH + 1)
        if dll.SHGetSpecialFolderPathW(None, buf, 0x0005, False):
            return buf.value
        else:
            return "Failure!"

    def set_cache1(self, data):
        import MySQLdb as mdb
        DBHOST = self.db[0]
        DBUSER = self.db[1]
        DBPASS = self.db[2]
        DBNAME = self.db[3]
        try:
            db = mdb.connect(DBHOST, DBUSER, DBPASS, DBNAME)
            muncode = self.muncode[self.munname.index(data.replace("erptax_", "").replace("_", " ").upper())]
            cur = db.cursor()
            cur.execute(self.get_query2("libbarangay", muncode))
            row = cur.fetchall()
            c_row = len(row)
            if c_row > 0:
                brgys = ""
                codes = ""
                for r in range(c_row):
                    if r == 0:
                        brgys = brgys + row[r][1]
                        codes = codes + row[r][0]
                    else:
                        brgys = brgys + ";" + row[r][1]
                        codes = codes + ";" + row[r][0]
                stored_file = self.get_store_folder() + "/GIS DataBase/cache1.ini"
                if os.path.exists(stored_file):
                    f = open(stored_file, "w+")
                    f.write(brgys + "\n")
                    f.write(codes)
                    f.close()
                else:
                    QMessageBox.information(None, "Cache File", "Cache file does not exist!")
            print("[CONFIG] CONNECTED TO:  " + self.curname + " DATABASE")
            return db
        except mdb.Error as e:
            print("[Config] Connection Failed!")

    def get_brgy_list(self):
        stored_file = self.get_store_folder() + "/GIS DataBase/cache1.ini"
        if os.path.exists(stored_file):
            f = open(stored_file, "r")
            if f.mode == "r":
                contents = f.readlines()
                index = 0
                for content in contents:
                    if index == 0:
                        self.barname = content.replace("\n", "").split(";")
                    else:
                        self.barcode = content.split(";")
                    index += 1
                print(self.barname)
            f.close()
        else:
            QMessageBox.information(None, "Cache File", "Cache file does not exist!")

    def main_set_brgy(self):
        if len(self.barname) > 0:
            self.dlg.cb_field_brgys.clear()
            self.dlg.cb_tmcr_brgys.clear()
            self.dlg.cb_tmcr_brgys.addItem("ALL BRGYS")
            for brgy in self.barname:
                self.dlg.cb_field_brgys.addItem(brgy)
                self.dlg.cb_tmcr_brgys.addItem(brgy)
            self.dlg.cb_field_brgys.setCurrentIndex(self.set_brgy())
            self.dlg.cb_tmcr_brgys.setCurrentIndex(self.set_brgy() + 1)

    def tw_error_cell_click(self):
        modifiers = QApplication.keyboardModifiers()
        if self.dlg.tw_error.rowCount() > 0:
            items = self.dlg.tw_error.selectedItems()
            if len(items) > 0:
                self.selected_lot = str(items[0].text()).strip()
                if self.dlg.ch_auto_locate.isChecked():
                    self.get_feat_location()
                self.dlg.txt_field_value.setText(self.selected_lot)
                index = self.dlg.cb_field_values.findText(self.selected_lot, QtCore.Qt.MatchFixedString)
                if index >= 0:
                    self.dlg.cb_field_values.setCurrentIndex(index)
                if modifiers:
                    if self.dlg.cb_search.currentText() == "landinfo_pin":
                        if self.selected_lot.startswith("0"):
                            self.dlg.txt_search.setText(str(int(self.selected_lot)))
                        else:
                            self.dlg.txt_search.setText(self.selected_lot)
                    else:
                        self.dlg.txt_search.setText(self.selected_lot)
                    self.main_tmcr_search()


    def tw_match_cell_click(self):
        if self.dlg.tw_match.rowCount() > 0:
            items = self.dlg.tw_match.selectedItems()
            if len(items) > 0:
                self.selected_lot = str(items[0].text()).strip()
                if self.dlg.ch_auto_locate.isChecked():
                    self.get_feat_location()
                self.dlg.txt_field_value.setText(self.selected_lot)
                index = self.dlg.cb_field_values.findText(self.selected_lot, QtCore.Qt.MatchFixedString)
                if index >= 0:
                    self.dlg.cb_field_values.setCurrentIndex(index)

    def tw_attr_cell_click(self):
        for r in range(self.dlg.tw_error.rowCount()):
            twitem = self.dlg.tw_error.item(r, 0)
            twitem.setBackground(QBrush(QColor(255, 255, 255)))
        for r in range(self.dlg.tw_match.rowCount()):
            twitem = self.dlg.tw_match.item(r, 0)
            twitem.setBackground(QBrush(QColor(255, 255, 255)))
        if self.dlg.tw_attr.rowCount() > 0:
            items = self.dlg.tw_attr.selectedItems()
            if len(items) > 0:
                sought_str = str(items[0].text()).strip()
                match = self.dlg.tw_error.findItems(sought_str, QtCore.Qt.MatchFixedString)
                for m in match:
                    m.setBackground(QBrush(QColor(255, 0, 0)))
                match = self.dlg.tw_match.findItems(sought_str, QtCore.Qt.MatchFixedString)
                for m in match:
                    m.setBackground(QBrush(QColor(255, 0, 0)))

    def tw_feat_cell_click(self):
        modifiers = QApplication.keyboardModifiers()
        if self.can_proc():
            curlot = self.get_active_feature("LOT_NO")
            if modifiers:
                if self.dlg.cb_search.currentText() == "landinfo_pin":
                    if self.selected_lot.startswith("0"):
                        self.dlg.txt_search.setText(str(int(curlot[1])))
                    else:
                        self.dlg.txt_search.setText(curlot[1])
                else:
                    self.dlg.txt_search.setText(curlot[1])
                self.main_tmcr_search()

    def get_feat_location(self):
        if self.selected_lot is not None:
            layer = self.iface.activeLayer()
            selection = []
            layer.removeSelection()
            for feature in layer.getFeatures():
                lot = feature.attribute("LOT_NO")
                if lot == self.selected_lot:
                    selection.append(feature.id())
                    layer.select(selection)
            self.main_selected_feature()

    def main_lot_search(self):
        search_key = self.dlg.txt_search_lot.text()
        if search_key == "":
            self.dlg.tw_match.setRowCount(0)
            self.dlg.tw_match.setRowCount(len(self.data_match))
            row = 0
            for data in self.data_match:
                columns = len(data)
                for col in range(columns):
                    item = QTableWidgetItem(str(data[col]))
                    self.dlg.tw_match.setItem(row, col, item)
                row += 1
            self.dlg.tw_error.setRowCount(0)
            self.dlg.tw_error.setRowCount(len(self.data_error))
            row = 0
            for data in self.data_error:
                columns = len(data)
                for col in range(columns):
                    item = QTableWidgetItem(str(data[col]))
                    self.dlg.tw_error.setItem(row, col, item)
                row += 1
        else:
            result = []
            for data in self.data_match:
                if data[0].__contains__(search_key):
                    result.append(data)
            self.dlg.tw_match.setRowCount(0)
            self.dlg.tw_match.setRowCount(len(result))
            row = 0
            for res in result:
                columns = len(res)
                for col in range(columns):
                    item = QTableWidgetItem(str(res[col]))
                    self.dlg.tw_match.setItem(row, col, item)
                row += 1
            result.clear()
            for data in self.data_error:
                if data[0].__contains__(search_key):
                    result.append(data)
            self.dlg.tw_error.setRowCount(0)
            self.dlg.tw_error.setRowCount(len(result))
            row = 0
            for res in result:
                columns = len(res)
                for col in range(columns):
                    item = QTableWidgetItem(str(res[col]))
                    self.dlg.tw_error.setItem(row, col, item)
                row += 1

    def main_tmcr(self):
        self.show_progress(1)
        cur = self.connect_to_db().cursor()
        brgy = self.dlg.cb_tmcr_brgys.currentText()
        if brgy == "ALL BRGYS":
            self.main_tmcr_search()
        else:
            brgycode = self.barcode[self.barname.index(brgy)]
            self.tmcr_brgy = brgy
            self.tmcr_ref = []
            self.dlg.lbl_tmcr_ref.setText("TMCR Reference at: " + self.tmcr_brgy)
            if brgycode:
                cur.execute(self.get_query3("liblandinfo", self.curcode, brgycode))
                row = cur.fetchall()
                c_row = len(row)
                self.dlg.tw_tmcr.setRowCount(0)
                self.dlg.tw_tmcr.setColumnCount(0)
                self.dlg.cb_search.clear()
                if c_row > 0:
                    c_col = len(row[0])
                    twr = 0
                    self.dlg.tw_tmcr.setColumnCount(c_col)
                    columns = []
                    for i in range(len(cur.description)):
                        columns.append(cur.description[i][0])
                        self.dlg.cb_search.addItem(cur.description[i][0])
                    self.dlg.tw_tmcr.setHorizontalHeaderLabels(columns)
                    self.dlg.cb_search.addItem("Customize")
                    for r in range(c_row):
                        if str(row[r][c_col-1]) == "CANCELLED":
                            twr += 0
                        elif str(row[r][c_col-1]) == "DELETED":
                            twr += 0
                        else:
                            twr += 1
                            self.dlg.tw_tmcr.setRowCount(twr)
                            col = []
                            for c in range(c_col):
                                item = QTableWidgetItem(str(row[r][c]))
                                self.dlg.tw_tmcr.setItem(twr-1, c, item)
                                col.append(str(row[r][c]))
                            if len(col) > 0:
                                self.tmcr_ref.append(col)
                        self.show_progress(1)
            # if len(self.tmcr_ref) > 0:
            #     self.dlg.btn_search.setEnabled(True)
            # else:
            #     self.dlg.btn_search.setEnabled(False)
            self.hide_progress()

    def main_tmcr_search(self):
        self.show_progress(1)
        if self.dlg.cb_search.count() == 0:
            field = "landinfo_lot_no"
        else:
            field = self.dlg.cb_search.currentText()
        key = self.dlg.txt_search.text()
        cur = self.connect_to_db().cursor()
        brgy = self.dlg.cb_tmcr_brgys.currentText()
        if brgy == "ALL BRGYS":
            query = self.get_query4("liblandsearch", self.curcode, "", "AND " + field + " LIKE '%" + key + "%'")
        else:
            brgycode = self.barcode[self.barname.index(brgy)]
            query = self.get_query4("liblandsearch", self.curcode, "AND landinfo_barangay = '" + brgycode + "'",
                                    "AND " + field + " LIKE '%" + key + "%'")
        if field == "land_area":
            self.main_tmcr_area()
            self.show_progress(1)
        else:
            cur.execute(query)
            row = cur.fetchall()
            c_row = len(row)
            self.dlg.tw_tmcr.setRowCount(0)
            self.dlg.tw_tmcr.setColumnCount(0)
            if c_row > 0:
                c_col = len(row[0])
                twr = 0
                self.dlg.tw_tmcr.setColumnCount(c_col)
                columns = []
                for i in range(len(cur.description)):
                    columns.append(cur.description[i][0])
                self.dlg.tw_tmcr.setHorizontalHeaderLabels(columns)
                for r in range(c_row):
                    if str(row[r][c_col - 1]) == "CANCELLED":
                        twr += 0
                    elif str(row[r][c_col - 1]) == "DELETED":
                        twr += 0
                    else:
                        twr += 1
                        self.dlg.tw_tmcr.setRowCount(twr)
                        for c in range(c_col):
                            item = QTableWidgetItem(str(row[r][c]))
                            self.dlg.tw_tmcr.setItem(twr - 1, c, item)
                self.show_progress(1)
        self.hide_progress()

    def main_tmcr_area(self):
        land_area = self.dlg.txt_search.text()
        if self.dlg.cb_search.currentText() == "land_area":
            row = len(self.tmcr_ref)
            if row > 0:
                self.dlg.tw_tmcr.setRowCount(0)
                twr = 0
                for r in self.tmcr_ref:
                    # 4 is the index of land_area derived from tmcr column index
                    area = r[4]
                    if area is not None:
                        if str(area).__contains__(land_area):
                            twr += 1
                            self.dlg.tw_tmcr.setRowCount(twr)
                            col = len(r)
                            for c in range(col):
                                item = QTableWidgetItem(r[c])
                                self.dlg.tw_tmcr.setItem(twr - 1, c, item)

            else:
                QMessageBox.information(None, "TMCR Reference", "TMCR reference is empty!")


    def main_match(self):
        self.show_progress(1)
        layer = self.iface.activeLayer()
        field_list = []
        brgy_name = self.get_layer_name()
        if self.curbrgy is not None:
            self.dlg.lbl_brgy.setText("CURRENT BARANGAY:  [" + self.curbrgy + "] " + brgy_name)
        if self.barname.__contains__(brgy_name):
            self.curbrgy = self.barcode[self.barname.index(brgy_name)]
            hasNotes = self.can_proc("SH_NOTES")
            if self.can_proc():
                cur = self.connect_to_db().cursor()
                cur.execute(self.get_query3("libmatch", self.curcode, self.curbrgy))
                row = cur.fetchall()
                c_row = len(row)
                self.dlg.tw_match.setRowCount(0)
                if c_row > 0:
                    c_col = len(row[0])
                    twr1 = 0
                    columns = []
                    for i in range(len(cur.description)):
                        columns.append(cur.description[i][0])
                    self.dlg.tw_match.setHorizontalHeaderLabels(columns)
                    print("Pre-match values: " + str(layer.featureCount()))
                    for feature in layer.getFeatures():
                        lot = str(feature["LOT_NO"])
                        if hasNotes:
                            notes = str(feature["SH_NOTES"])
                            if notes.__contains__("REF@"):
                                twr1 += 1
                                self.dlg.tw_match.setRowCount(twr1)
                                item = QTableWidgetItem(lot)
                                self.dlg.tw_match.setItem(twr1 - 1, 0, item)
                                item = QTableWidgetItem(notes)
                                self.dlg.tw_match.setItem(twr1 - 1, 1, item)
                                item = QTableWidgetItem("Matched!")
                                self.dlg.tw_match.setItem(twr1 - 1, 2, item)
                            else:
                                field_list.append(lot)
                        else:
                            field_list.append(lot)
                    field_list.sort()
                    print("Post-match values [Process I]: " + str(len(field_list)))
                    for r in range(c_row):
                        existence = 0
                        if field_list.__contains__(str(row[r][0]).strip()):
                            for f in field_list:
                                if f == str(row[r][0]).strip():
                                    existence += 1
                        if existence == 1:
                            field_list.remove(str(row[r][0]))
                            twr1 += 1
                            self.dlg.tw_match.setRowCount(twr1)
                            for c in range(c_col):
                                item = QTableWidgetItem(str(row[r][c]))
                                self.dlg.tw_match.setItem(twr1 - 1, c, item)
                            item = QTableWidgetItem("Matched!")
                            self.dlg.tw_match.setItem(twr1 - 1, 2, item)
                        self.show_progress(1)
                    print("Post-match values [Process II]: " + str(len(field_list)))
                    print(field_list)
                    self.dlg.tw_error.setRowCount(0)
                    self.dlg.tw_error.setColumnCount(0)
                    if len(field_list) > 0:
                        query = None
                        for field in field_list:
                            if query is None:
                                query = self.get_query1("libduplicate", field, self.curcode, self.curbrgy)
                            else:
                                query += " UNION " + self.get_query1("libduplicate", field, self.curcode, self.curbrgy)
                        cur.execute(query)
                        row = cur.fetchall()
                        c_row = len(row)
                        self.dlg.tw_error.setRowCount(len(field_list))
                        if c_row == 0:
                            self.dlg.tw_error.setColumnCount(2)
                        else:
                            self.dlg.tw_error.setColumnCount(c_col)
                        c_count = 1
                        if c_row > 0:
                            c_col = len(row[0])
                            for r in range(c_row):
                                if field_list.__contains__(str(row[r][0]).strip()):
                                    field_list.remove(str(row[r][0]))
                                dup = str(row[r][1]).split("||")
                                lot = QTableWidgetItem(str(row[r][0]))
                                self.dlg.tw_error.setItem(r, 0, lot)
                                if len(dup) > c_count:
                                    c_count = len(dup)
                                    self.dlg.tw_error.setColumnCount(c_col + (c_count - 1))
                                    for c in range(c_count):
                                        item = QTableWidgetItem(dup[c].strip())
                                        self.dlg.tw_error.setItem(r, c+1, item)
                                else:
                                    for c in range(len(dup)):
                                        item = QTableWidgetItem(dup[c].strip())
                                        self.dlg.tw_error.setItem(r, c+1, item)
                        columns = []
                        for i in range(c_count + 1):
                            if i == 0:
                                columns.append("LOT_NO")
                            else:
                                columns.append("DUP" + str(i))
                        self.dlg.tw_error.setHorizontalHeaderLabels(columns)
                        if len(field_list) > 0:
                            rcount = 0
                            for field in field_list:
                                lot = QTableWidgetItem(field)
                                self.dlg.tw_error.setItem(c_row + rcount, 0, lot)
                                item = QTableWidgetItem("No record from current barangay.")
                                self.dlg.tw_error.setItem(c_row + rcount, 1, item)
                                rcount += 1
                        row_index = 0
                        removed = []
                        if len(self.skipped_lots) > 0:
                            for row in range(self.dlg.tw_error.rowCount()):
                                if self.skipped_lots.__contains__(self.dlg.tw_error.item(row, 0).text()):
                                    row_end_index = self.dlg.tw_error.rowCount()
                                    self.dlg.tw_error.insertRow(row_end_index)
                                    for i in range(self.dlg.tw_error.columnCount()):
                                        self.dlg.tw_error.setItem(row_end_index, i, self.dlg.tw_error.takeItem(row_index, i))
                                    removed.append(row_index)
                                row_index += 1
                            for c in range(len(removed) - 1, -1, -1):
                                self.dlg.tw_error.removeRow(removed[c])
                    if len(field_list) > 0:
                        print("Post-match values [Process III]: " + str(len(field_list)))
            self.hide_progress()
            self.main_cache_data()
        else:
            QMessageBox.information(None, "Invalid Layer Name", "Layer name is not a valid ERPT Barangay!")

    def main_cache_data(self):
        row = self.dlg.tw_match.rowCount()
        col = self.dlg.tw_match.columnCount()
        self.data_match.clear()
        for r in range(row):
            items = []
            for c in range(col):
                items.append(str(self.dlg.tw_match.item(r, c).text()))
            self.data_match.append(items)
        row = self.dlg.tw_error.rowCount()
        col = self.dlg.tw_error.columnCount()
        self.data_error.clear()
        for r in range(row):
            items = []
            for c in range(col):
                if self.dlg.tw_error.item(r, c) is not None:
                    items.append(str(self.dlg.tw_error.item(r, c).text()))
            self.data_error.append(items)

    def set_survey_nsd(self):
        if self.can_proc():
            layer = self.iface.activeLayer()
            feature = layer.selectedFeatures()
            provider = layer.dataProvider()
            selected = len(layer.selectedFeatures())
            if self.can_proc():
                if selected == 1:
                    item = self.curdlg.txt_nsd.text()
                    if item != "":
                        layer.startEditing()
                        attr_value = {layer.fields().indexFromName("SH_NSD"): item}
                        provider.changeAttributeValues({feature[0].id(): attr_value})
                        layer.commitChanges()
        else:
            QMessageBox.information(None, "Invalid Proc", "No valid data to process!")

    def set_clear_nsd(self):
        self.curdlg.txt_nsd.setText("")
        self.curdlg.txt_nsd.setFocus()

    def set_survey_nsp(self):
        if self.can_proc():
            layer = self.iface.activeLayer()
            feature = layer.selectedFeatures()
            provider = layer.dataProvider()
            selected = len(layer.selectedFeatures())
            if self.can_proc():
                if selected == 1:
                    item = self.curdlg.txt_nsp.text()
                    if item != "":
                        layer.startEditing()
                        attr_value = {layer.fields().indexFromName("SH_NSP"): item}
                        provider.changeAttributeValues({feature[0].id(): attr_value})
                        layer.commitChanges()
        else:
            QMessageBox.information(None, "Invalid Proc", "No valid data to process!")

    def set_clear_nsp(self):
        self.curdlg.txt_nsp.setText("")
        self.curdlg.txt_nsp.setFocus()

    def main_attr(self):
        self.dlg.tw_attr.setRowCount(0)
        self.dlg.tw_attr.setColumnCount(0)
        layer = self.iface.activeLayer()
        col = len(layer.fields().names())
        if self.can_proc():
            row = layer.featureCount()
            self.dlg.tw_attr.setRowCount(row)
            self.dlg.tw_attr.setColumnCount(col)
            features = layer.getFeatures()
            index = 0
            columns = []
            for i in range(col):
                columns.append(layer.fields().names()[i])
            self.dlg.tw_attr.setHorizontalHeaderLabels(columns)
            for f in features:
                for c in range(col):
                    if str(f.attributes()[c]) != "NULL":
                        attrib = QTableWidgetItem(str(f.attributes()[c]))
                        self.dlg.tw_attr.setItem(index, c, attrib)
                index += 1
        else:
            QMessageBox.information(None, "Invalid Proc", "No valid data to process!")

    def main_attr_trim(self):
        layer = self.iface.activeLayer()
        provider = layer.dataProvider()
        col = len(layer.fields().names())
        if self.can_proc():
            has_field = 0
            for c in range(col):
                field_name = layer.fields().names()[c]
                if field_name.startswith("ER_"):
                    has_field += 1
            if has_field == 0:
                default_columns = ["SH_LOT_NO", "SH_CONF", "SH_NSP", "SH_NOTES", "SH_AREA"]
                # SH_NSD: No subdivision data
                # SH_NSP: No subdivision plan
                del_fields = []
                for c in range(col):
                    field_name = layer.fields().names()[c]
                    relevant = False
                    if field_name.upper().__contains__("LOT"):
                        relevant = True
                    if field_name == "E_":
                        relevant = True
                    if field_name == "LOT_NO":
                        relevant = True
                    if field_name.startswith("SH_"):
                        relevant = True
                        if default_columns.__contains__(field_name):
                            default_columns.remove(field_name)
                    if not relevant:
                        print("kill: " + str(field_name))
                        del_fields.append(layer.fields().indexFromName(field_name))
                if len(del_fields) > 0:
                    provider.deleteAttributes(del_fields)
                    layer.updateFields()
                if len(default_columns) > 0:
                    for d in range(len(default_columns)):
                        col_name = default_columns[d]
                        provider.addAttributes([QgsField(col_name, QVariant.String)])
                features = layer.getFeatures()
                layer.updateFields()
                cur = self.connect_to_db().cursor()
                cur.execute(self.get_query3("libjoindata", self.curcode, self.curbrgy))
                row = cur.fetchall()
                c_row = len(row)
                if c_row > 0:
                    for c in range(len(cur.description)):
                        if c > 0:
                            col_name = cur.description[c][0]
                            provider.addAttributes([QgsField("E_" + str(col_name), QVariant.String, )])
                layer.updateFields()
        self.main_attr()

    def main_attr_copy(self):
        layer = self.iface.activeLayer()
        provider = layer.dataProvider()
        features = layer.getFeatures()
        layer.startEditing()
        for f in features:
            lot_no = f["LOT_NO"]
            if str(f["SH_LOT_NO"]) == "" or str(f["SH_LOT_NO"]) == "NULL":
                copy = layer.fields().indexFromName("SH_LOT_NO")
                attr_value = {copy: lot_no}
                provider.changeAttributeValues({f.id(): attr_value})
        layer.commitChanges()
        self.main_attr()

    def main_attr_join(self):
        self.temp_col_names = []
        if self.dlg.tw_attr.columnCount() > 0:
            if self.can_proc():
                layer = self.iface.activeLayer()
                provider = layer.dataProvider()
                cur = self.connect_to_db().cursor()
                cur.execute(self.get_query3("libjoindata", self.curcode, self.curbrgy))
                row = cur.fetchall()
                c_row = len(row)
                if c_row > 0:
                    c_col = len(row[0])
                    # for c in range(c_col):
                    #     print(str(cur.description[c][0]))
                    lots = []
                    data = []
                    arps = []
                    for r in range(c_row - 1, -1, -1):
                        if str(row[r][c_col - 1]).strip() == "CANCELLED":
                            print("REMOVED LOT NO.: " + str(row[r][0]) + " [" + str(row[r][c_col - 1]) + "]")
                        elif str(row[r][c_col - 1]).strip() == "DELETED":
                            print("REMOVED LOT NO.: " + str(row[r][0]) + " [" + str(row[r][c_col - 1]) + "]")
                        else:
                            lots.append(str(row[r][0]))
                            data.append(row[r])
                            arps.append(str(row[r][2]))
                    col = len(layer.fields().names())
                    start = 1
                    for c in range(col):
                        field_name = layer.fields().names()[c]
                        if start == 1:
                            if field_name.startswith("E_"):
                                start = c
                    if col > 5 and start > 1:
                        features = layer.getFeatures()
                        layer.startEditing()
                        col_count = len(cur.description)
                        for f in features:
                            lot_no = str(f["LOT_NO"])
                            ref_no = str(f["SH_NOTES"])
                            num = start
                            if ref_no.startswith("REF@"):
                                arp_no = ref_no.replace("REF@", "").strip()
                                for cc in range(col_count):
                                    if int(cc) > 0:
                                        if arps.__contains__(arp_no):
                                            index = arps.index(arp_no)
                                            attr_value = {num: str(data[index][cc])}
                                            provider.changeAttributeValues({f.id(): attr_value})
                                            num += 1
                            else:
                                for cc in range(col_count):
                                    if int(cc) > 0:
                                        if lots.__contains__(lot_no):
                                            index = lots.index(lot_no)
                                            attr_value = {num: str(data[index][cc])}
                                            provider.changeAttributeValues({f.id(): attr_value})
                                            num += 1
                        layer.commitChanges()
                        self.main_attr()
                    else:
                        QMessageBox.information(None, "Layer Attributes", "Relevant columns are required!")

    def main_show_feature_attr(self):
        layer = self.iface.activeLayer()
        selected = len(layer.selectedFeatures())
        self.dlg.tw_feature.setRowCount(0)
        if selected == 1:
            feat = layer.selectedFeatures()[0]
            col = len(layer.fields().names())
            # columns = []
            # columns.append("FIELDS")
            # columns.append("VALUES")
            self.dlg.tw_feature.setRowCount(col)
            for i in range(col):
                col_name = layer.fields().names()[i]
                item = feat[col_name]
                fld = QTableWidgetItem(col_name)
                val = QTableWidgetItem(str(item))
                fld.setBackground(QBrush(QColor(255, 255, 255)))
                val.setBackground(QBrush(QColor(255, 255, 255)))
                self.dlg.tw_feature.setItem(i, 0, fld)
                self.dlg.tw_feature.setItem(i, 1, val)
            # self.dlg.tw_feature.setHorizontalHeaderLabels(columns)

    def set_value(self, ref_only):
        curlot = self.get_active_feature("LOT_NO")
        if self.can_proc("SH_NOTES"):
            if self.curdlg.tw_tmcr.columnCount() > 0 and len(self.curdlg.tw_tmcr.selectedIndexes()) > 0:
                rowcount = len(self.curdlg.tw_tmcr.selectedIndexes()) / self.curdlg.tw_tmcr.columnCount()
                layer = self.iface.activeLayer()
                provider = layer.dataProvider()
                selected = len(layer.selectedFeatures())
                if selected == 1:
                    if rowcount > 0:
                        item = self.curdlg.tw_tmcr.selectedItems()
                        feat = layer.selectedFeatures()[0]
                        tmcr_data = []
                        # LOT_NO
                        tmcr_data.append(item[0].text())
                        # ARPNO
                        tmcr_data.append(item[2].text())
                        # NAME
                        tmcr_data.append(item[6].text())
                        layer.startEditing()
                        if ref_only == 0:
                            ref_val = "REF@" + tmcr_data[1]
                            attr_value = {layer.fields().indexFromName("SH_NOTES"): ref_val}
                            provider.changeAttributeValues({feat.id(): attr_value})
                        elif ref_only == 1:
                            lot_val = tmcr_data[2]
                            ref_val = "REF@" + tmcr_data[1]
                            attr_value = {layer.fields().indexFromName("LOT_NO"): lot_val}
                            provider.changeAttributeValues({feat.id(): attr_value})
                            attr_value = {layer.fields().indexFromName("SH_LOT_NO"): lot_val}
                            provider.changeAttributeValues({feat.id(): attr_value})
                            attr_value = {layer.fields().indexFromName("SH_NOTES"): ref_val}
                            provider.changeAttributeValues({feat.id(): attr_value})
                        elif ref_only == 2:
                            lot_val = tmcr_data[0]
                            attr_value = {layer.fields().indexFromName("LOT_NO"): lot_val}
                            provider.changeAttributeValues({feat.id(): attr_value})
                        else:
                            arp_val = tmcr_data[1]
                            attr_value = {layer.fields().indexFromName("SH_CONF"): arp_val}
                            provider.changeAttributeValues({feat.id(): attr_value})
                        layer.commitChanges()

                    else:
                        QMessageBox.information(None, "Layer Attributes", "1 row selected is required!")
                else:
                    QMessageBox.information(None, "Data Reference", "1 feature selected is required!")

    def tmcr_ref_value(self):
        self.set_value(0)
        self.main_selected_feature()
        if self.dlg.ch_auto_match.isChecked():
            self.main_match()
            if not self.dlg.txt_search_lot.text() == "":
                self.main_lot_search()

    def tmcr_fld_value(self):
        self.set_value(1)
        self.main_selected_feature()
        if self.dlg.ch_auto_match.isChecked():
            self.main_match()
            if not self.dlg.txt_search_lot.text() == "":
                self.main_lot_search()

    def tmcr_lot_value(self):
        self.set_value(2)
        self.main_selected_feature()
        if self.dlg.ch_auto_match.isChecked():
            self.main_match()
            if not self.dlg.txt_search_lot.text() == "":
                self.main_lot_search()

    def tmcr_conflict(self):
        if self.can_proc("SH_CONF"):
            self.set_value(3)
            self.main_selected_feature()
            if self.dlg.ch_auto_match.isChecked():
                self.main_match()
                if not self.dlg.txt_search_lot.text() == "":
                    self.main_lot_search()
        else:
            QMessageBox.information(None, "Invalid Proc", "No SH_CONF field in the attribute table.")

    def main_tmcr_match(self):
        mrow = self.dlg.tw_match.rowCount()
        trow = self.dlg.tw_tmcr.rowCount()
        match_count = 0
        dup_count = 0
        dup_list = []
        if mrow > 0 and trow > 0:
            for m in range(mrow):
                mitem = self.dlg.tw_match.item(m, 1).text().replace("REF@", "")
                for t in range(trow):
                    titem = self.dlg.tw_tmcr.item(t, 2).text()
                    if mitem == titem:
                        status = self.dlg.tw_tmcr.item(t, 1).text()
                        index = self.zero_based_num(m + 1, len(str(mrow)))
                        if status.__contains__("@ ["):
                            value = status + "[" + index + "] "
                            dup_count += 1
                            dup_list.append(titem)
                        else:
                            value = "@ [" + index + "] "
                            match_count += 1
                        item = QTableWidgetItem(value)
                        cell = self.dlg.tw_tmcr.item(t, 1)
                        cell.setBackground(QBrush(QColor(255, 255, 0)))
                        self.dlg.tw_tmcr.setItem(t, 1, item)
            self.dlg.lbl_status.setText("TMCR Matching recorded " + str(match_count) + "/" + str(trow) + " matches with " + str(dup_count) + " duplicates.")
            print(dup_list)

    def zero_based_num(self, base_number, max_length):
        result = str(base_number)
        base_length = len(str(base_number))
        if base_length < max_length:
            length_to_generate = max_length - base_length
            zero_base = ""
            for m in range(length_to_generate):
                zero_base = zero_base + "0"
            result = zero_base + str(base_number)
        return result


    def value_validation(self, val):
        if val == "NULL":
            return False
        elif val == "None":
            return False
        elif val == "":
            return False
        else:
            return True

    def use_value(self):
        curlot = self.get_active_feature("LOT_NO")
        self.dlg.lbl_lot.setText("[SHP] CURRENT LOT: [" + curlot[0] + "] " + curlot[1])
        if self.curdlg.tw_data.rowCount() > 0:
            items = self.curdlg.tw_data.selectedItems()
            if len(items) > 0:
                col = self.curdlg.tw_data.columnCount()
                if col > 0:
                    self.curdlg.tw_value.setRowCount(0)
                    self.curdlg.tw_value.setColumnCount(0)
                    if self.can_proc():
                        self.curdlg.tw_value.setRowCount(1)
                        self.curdlg.tw_value.setColumnCount(col)
                        columns = []
                        for i in range(col):
                            columns.append(self.curdlg.tw_data.horizontalHeaderItem(i).text())
                        self.curdlg.tw_value.setHorizontalHeaderLabels(columns)
                        for c in range(col):
                            item = str(items[c].text())
                            if item != "NULL":
                                val = QTableWidgetItem(item)
                                self.curdlg.tw_value.setItem(0, c, val)
                    else:
                        QMessageBox.information(None, "Invalid Proc", "No valid data to process!")

    def lot_value(self):
        if self.can_proc():
            if self.curdlg.tw_value.rowCount() > 0:
                layer = self.iface.activeLayer()
                feature = layer.selectedFeatures()
                provider = layer.dataProvider()
                selected = len(layer.selectedFeatures())
                col = len(layer.fields().names())
                if self.can_proc():
                    if selected == 1:
                        layer.startEditing()
                        item = self.curdlg.tw_value.item(0, 0).text()
                        if item != "None":
                            attr_value = {layer.fields().indexFromName("LOT_NO"): item}
                            provider.changeAttributeValues({feature[0].id(): attr_value})
                        layer.commitChanges()
                        self.main_attr()
        else:
            QMessageBox.information(None, "Invalid Proc", "No valid data to process!")

    def arp_value(self):
        if self.can_proc():
            if self.curdlg.tw_value.rowCount() > 0:
                layer = self.iface.activeLayer()
                feature = layer.selectedFeatures()
                provider = layer.dataProvider()
                selected = len(layer.selectedFeatures())
                exist = layer.fields().indexFromName("SH_NOTES")
                index = -1
                for c in range(self.curdlg.tw_value.columnCount()):
                    if self.curdlg.tw_value.horizontalHeaderItem(c).text() == "ARP_NO":
                        index = c
                if self.can_proc():
                    if selected == 1:
                        if exist >= 0 and index >= 0:
                            layer.startEditing()
                            item = "REF@" + str(self.curdlg.tw_value.item(0, index).text())
                            print("REF@" + str(self.curdlg.tw_value.item(0, index).text()))
                            if item != "None":
                                attr_value = {layer.fields().indexFromName("SH_NOTES"): item}
                                provider.changeAttributeValues({feature[0].id(): attr_value})
                            layer.commitChanges()
                            self.main_attr()

        else:
            QMessageBox.information(None, "Invalid Proc", "No valid data to process!")

    def get_req_pkg(self):
        import pkg_resources
        installed_packages = pkg_resources.working_set
        installed_packages_list = sorted(["%s==%s" % (i.key, i.version) for i in installed_packages])
        ready = 0
        for pkg in installed_packages_list:
            if pkg.startswith("mysqlclient"):
                ready = 1
        if ready == 0:
            import pip
            pip.main(["install", "mysqlclient"])

    def get_selected_lots(self):
        self.curdlg.tw_selected.setRowCount(0)
        self.curdlg.tw_selected.setColumnCount(0)
        layer = self.iface.activeLayer()
        features = layer.selectedFeatures()
        row = len(features)
        col = 2
        self.curdlg.tw_selected.setRowCount(row)
        self.curdlg.tw_selected.setColumnCount(col)
        columns = ["FID", "LOT_NO"]
        self.curdlg.tw_selected.setColumnWidth(0, 50)
        self.curdlg.tw_selected.setColumnWidth(1, 148)
        self.curdlg.tw_selected.setHorizontalHeaderLabels(columns)
        index = 0
        for feat in features:
            fid = feat.id()
            val_id = QTableWidgetItem(str(fid))
            self.curdlg.tw_selected.setItem(index, 0, val_id)
            lot = str(feat["LOT_NO"])
            val_lot = QTableWidgetItem(lot)
            self.curdlg.tw_selected.setItem(index, 1, val_lot)
            index += 1

    def tool_init(self):
        if self.open_conn():
            if self.can_proc():
                self.current_lot = self.get_active_feature("LOT_NO")[1]
                self.get_selected_lots()
                self.get_brgy_list()
                self.set_brgy()
                self.retrieve(self.current_lot)
                self.dlg_tool.lbl_brgy.setText("[SHP] CURRENT LOT: " + self.current_lot)

    def run_tool(self):
        if self.tool_start:
            self.tool_start = False
            self.dlg_tool.btn_get_data.clicked.connect(self.tool_get_data)
            self.dlg_tool.btn_use.clicked.connect(self.use_value)
            self.dlg_tool.btn_lot.clicked.connect(self.lot_value)
            self.dlg_tool.btn_arp.clicked.connect(self.arp_value)
            self.dlg_tool.btn_nsd.clicked.connect(self.set_survey_nsd)
            self.dlg_tool.btn_nsp.clicked.connect(self.set_survey_nsp)
            self.dlg_tool.btn_nsd_clear.clicked.connect(self.set_clear_nsd)
            self.dlg_tool.btn_nsp_clear.clicked.connect(self.set_clear_nsp)
        self.curdlg = self.dlg_tool
        self.tool_init()
        self.dlg_tool.show()

    def run_config(self):
        if self.config_start:
            self.config_start = False
            self.dlg_config.btn_connect.clicked.connect(self.save_conn)
        self.get_req_pkg()
        # Create query file
        # self.set_query("query1")
        self.curdlg = self.dlg_config
        if self.open_conn():
            self.dlg_config.input_data.clear()
            for mun in self.munname:
                self.dlg_config.input_data.addItem("erptax_" + mun.lower().replace(" ", "_"))
            self.dlg_config.input_host.setText(self.db[0])
            self.dlg_config.input_user.setText(self.db[1])
            self.dlg_config.input_pass.setText(self.db[2])
            index = self.dlg_config.input_data.findText(self.db[3], QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.dlg_config.input_data.setCurrentIndex(index)

        self.dlg_config.lbl_status.setText("")
        self.dlg_config.show()

    def main_skip_lot(self):
        curlot = self.get_active_feature("LOT_NO")
        # self.dlg.lbl_lot.setText("[SHP] CURRENT LOT: [" + curlot[0] + "] " + curlot[1])
        self.skipped_lots.append(curlot[1])
        self.main_match()

    def main_reload(self):
        if len(self.skipped_lots) > 0:
            if QMessageBox.question(self.iface.mainWindow(), 'Skipped Lots', 'Do you wish to clear the skipped lots', QMessageBox.Yes, QMessageBox.No) == QMessageBox.Yes:
                self.skipped_lots = []
        self.main_init()

    def main_init(self):
        if self.open_conn():
            self.main_attr()
            self.get_brgy_list()
            self.main_set_brgy()
            self.main_attr_field()
            self.dlg.cb_field_values.clear()
            feat = self.get_lot_list()
            if self.can_proc():
                for f in feat:
                    self.dlg.cb_field_values.addItem(str(f))
            self.main_selected_lot()
            self.main_match()
            self.retrieve(self.current_lot)
            self.dlg.lbl_database.setText(self.dbstatus)
            if self.current_lot is not None:
                curlot = self.get_active_feature("LOT_NO")
                self.dlg.lbl_lot.setText("[SHP] CURRENT LOT: [" + curlot[0] + "] " + curlot[1])
                self.main_show_feature_attr()
            self.dlg.lbl_database.setText("TARGETING:  [" + self.curcode + "] " + self.curname + " DATABASE")
            self.get_client_config()

    def featureSelected(self):
        selection = self.active_layer.selectedFeatures()
        layer_index = self.array_layer.index(self.iface.activeLayer())
        if len(selection) == 1:
            feats = []
            self.main_selected_feature()
            feats.append(str(selection[0].id()))
            self.array_feats[layer_index] = feats
        elif len(selection) > 0:
            if len(selection) > len(self.array_feats[layer_index]):
                for f in selection:
                    exist = False
                    for e in self.array_feats[layer_index]:
                        if e.__contains__(str(f.id())):
                            exist = True
                    if not exist:
                        self.array_feats[layer_index].append(str(f.id()))
            else:
                for e in self.array_feats[layer_index]:
                    missing = True
                    for f in selection:
                        if e == str(f.id()):
                            missing = False
                    if missing:
                        self.array_feats[layer_index].remove(e)
        else:
            feats = []
            self.array_feats[layer_index] = feats
        print(self.array_feats[layer_index])

    def layerChanged(self):
        try:
            self.active_layer = self.iface.activeLayer()
            if not self.array_layer.__contains__(self.active_layer):
                feats = []
                self.active_layer.selectionChanged.connect(self.featureSelected)
                self.array_layer.append(self.active_layer)
                self.array_feats.append(feats)
        except AttributeError as err:
            print(err)

    def set_client_config(self):
        stored_file = self.get_store_folder() + "/GIS DataBase/client.ini"
        if os.path.exists(stored_file):
            f = open(stored_file, "w+")
            f.write("AUTO-MATCH-DATA=" + str(self.dlg.ch_auto_match.isChecked()) + "\n")
            f.write("AUTO-LOCATE=" + str(self.dlg.ch_auto_locate.isChecked()) + "\n")
            f.close()
            QMessageBox.information(None, "Client Configuration", "Configuration has been saved.")
        else:
            QMessageBox.information(None, "Cache File", "Cache file does not exist!")

    def get_client_config(self):
        stored_file = self.get_store_folder() + "/GIS DataBase/client.ini"
        if os.path.exists(stored_file):
            f = open(stored_file, "r")
            lines = f.readlines()
            index = 0
            for line in lines:
                val = line.split("=")
                if index == 0:
                    self.dlg.ch_auto_match.setChecked(eval(val[1].strip()))
                elif index == 1:
                    self.dlg.ch_auto_locate.setChecked(eval(val[1].strip()))
                index += 1
            f.close()
        else:
            QMessageBox.information(None, "Cache File", "Cache file does not exist!")

    def show_progress(self, value):
        self.dlg.pb_status.setVisible(True)
        total_value = self.dlg.pb_status.value() + value
        if total_value >= 100:
            self.dlg.pb_status.setValue(98)
        else:
            self.dlg.pb_status.setValue(total_value)

    def hide_progress(self):
        self.dlg.pb_status.setVisible(False)
        self.dlg.pb_status.setValue(0)

    def run(self):
        """Run method that performs all the real work"""
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        # watas
        if self.first_start:
            self.first_start = False
            self.dlg.btn_get_data.clicked.connect(self.main_get_data)
            self.dlg.btn_reload.clicked.connect(self.main_reload)
            self.dlg.btn_analyze.clicked.connect(self.main_match)
            # self.dlg.tw_error.itemSelectionChanged.connect(self.tw_error_cell_click)
            # self.dlg.tw_match.itemSelectionChanged.connect(self.tw_match_cell_click)
            # self.dlg.tw_attr.itemSelectionChanged.connect(self.tw_attr_cell_click)
            self.dlg.tw_error.cellClicked.connect(self.tw_error_cell_click)
            self.dlg.tw_match.cellClicked.connect(self.tw_match_cell_click)
            self.dlg.tw_attr.cellClicked.connect(self.tw_attr_cell_click)
            self.dlg.tw_feature.cellClicked.connect(self.tw_feat_cell_click)
            self.dlg.btn_locate.clicked.connect(self.get_feat_location)
            self.dlg.btn_tmcr.clicked.connect(self.main_tmcr)
            # self.dlg.btn_tmcr_search.clicked.connect(self.main_tmcr_search)
            self.dlg.btn_irre.clicked.connect(self.main_attr_trim)
            self.dlg.btn_join.clicked.connect(self.main_attr_join)
            self.dlg.btn_commit.clicked.connect(self.main_attr)
            self.dlg.btn_backup.clicked.connect(self.main_attr_copy)
            self.dlg.btn_use.clicked.connect(self.use_value)
            self.dlg.btn_lot.clicked.connect(self.lot_value)
            self.dlg.btn_arp.clicked.connect(self.arp_value)
            self.dlg.txt_search_lot.returnPressed.connect(self.main_lot_search)
            self.dlg.txt_search.returnPressed.connect(self.main_tmcr_search)
            self.dlg.btn_feature.clicked.connect(self.main_selected_feature)
            self.dlg.btn_ref_shp.clicked.connect(self.tmcr_ref_value)
            self.dlg.btn_ref_own.clicked.connect(self.tmcr_fld_value)
            self.dlg.btn_ref_lot.clicked.connect(self.tmcr_lot_value)
            self.dlg.btn_ref_cft.clicked.connect(self.tmcr_conflict)
            self.dlg.btn_client_config.clicked.connect(self.set_client_config)
            self.dlg.btn_skip.clicked.connect(self.main_skip_lot)
            self.dlg.btn_tmcr_match.clicked.connect(self.main_tmcr_match)
            self.iface.actionSelect().trigger()
            self.active_layer = self.iface.activeLayer()
            if not self.array_layer.__contains__(self.active_layer):
                feats = []
                self.active_layer.selectionChanged.connect(self.featureSelected)
                self.array_layer.append(self.active_layer)
                self.array_feats.append(feats)
            self.iface.currentLayerChanged.connect(self.layerChanged)
        self.curdlg = self.dlg
        self.main_init()
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        # See if OK was pressed
        if result:

            pass