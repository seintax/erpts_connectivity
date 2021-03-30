# -*- coding: utf-8 -*-
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (QgsField)
# from qgis.core import QgsFeature, QgsFeatureRequest

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .zds_erpts_integration_dialog import eRPTSIntegrationDialog
import os.path
from .zds_erpts_integration_config_dialog import zdseRPTSIntegrationConfig
from .zds_erpts_integration_match_dialog import zdseRPTSIntegrationMatch
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
        self.dlg_config = zdseRPTSIntegrationConfig()
        self.dlg_match = zdseRPTSIntegrationMatch()
        self.first_start = None
        self.config_start = None
        self.match_start = None
        self.db = None
        self.current_lot = None
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
        icon_match_path = ':/plugins/zds_erpts_integration/img/zds_erpts_integration_config_icon.png'
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
            icon_match_path,
            text=self.tr(u'eRPT System Matching'),
            callback=self.run_match,
            parent=self.iface.mainWindow())
        # will be set False in run()
        self.first_start = True
        self.config_start = True
        self.match_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&eRPTS Integration'),
                action)
            self.iface.removeToolBarIcon(action)

    def connect(self):
        import MySQLdb as mdb
        DBHOST = self.dlg.input_host.text()
        DBUSER = self.dlg.input_user.text()
        DBPASS = self.dlg.input_pass.text()
        DBNAME = self.dlg.input_data.text()
        try:
            db = mdb.connect(DBHOST, DBUSER, DBPASS, DBNAME)
            print("Database Connected Successfully")
        except mdb.Error as e:
            print("Database Not Connected Successfully")

    def retrieve(self, lot):
        if lot:
            self.dlg.tw_value.setRowCount(0)
            self.dlg.tw_value.setColumnCount(0)
            cur = self.connect_to_db().cursor()
            self.dlg.lbl_database.setText(self.dbstatus)
            cur.execute(self.get_query1("liblandinfoall", lot, self.curcode, self.curbrgy))
            row = cur.fetchall()
            c_row = len(row)
            c_col = 0
            self.dlg.tw_data.setRowCount(0)
            self.dlg.tw_data.setColumnCount(0)
            self.dlg.tw_info.setRowCount(0)
            self.dlg.tw_info.setColumnCount(0)
            if c_row > 0:
                c_col = len(row[0])
                twr1 = 0
                twr2 = 0
                # self.dlg.tw_data.setRowCount(c_row)
                self.dlg.tw_data.setColumnCount(c_col)
                self.dlg.tw_info.setColumnCount(c_col)
                columns = []
                for i in range(len(cur.description)):
                    columns.append(cur.description[i][0])
                self.dlg.tw_data.setHorizontalHeaderLabels(columns)
                self.dlg.tw_info.setHorizontalHeaderLabels(columns)
                for r in range(c_row):
                    if row[r][c_col-1] is None:
                        twr1 += 1
                        self.dlg.tw_data.setRowCount(twr1)
                        for c in range(c_col):
                            item = QTableWidgetItem(str(row[r][c]))
                            self.dlg.tw_data.setItem(twr1 - 1, c, item)
                    else:
                        twr2 += 1
                        self.dlg.tw_info.setRowCount(twr2)
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
                            self.dlg.tw_info.setItem(twr2-1, c, item)

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

    def get_data(self):
        self.current_lot = self.dlg.cb_field_values.currentText()
        # self.curbrgy = self.barcode[self.barname.index(self.dlg.cb_field_brgys.currentText())]
        self.retrieve(self.current_lot)
        self.set_cache2()

    def connect_to_db(self):
        import MySQLdb as mdb
        DBHOST = self.db[0]
        DBUSER = self.db[1]
        DBPASS = self.db[2]
        DBNAME = self.db[3]
        try:
            db = mdb.connect(DBHOST, DBUSER, DBPASS, DBNAME)
            self.curcode = self.muncode[self.munname.index(self.db[3].replace("erptax_", "").upper())]
            self.curname = self.munname[self.munname.index(self.db[3].replace("erptax_", "").upper())]
            self.dbstatus = "CONNECTED TO:  [" + self.curcode + "] " + self.curname + " DATABASE"
            return db
        except mdb.Error as e:
            self.dbstatus = "Connection Failed!"

    def get_attr_field(self):
        layer = self.iface.activeLayer()
        self.dlg.cb_field_names.clear()
        for field in layer.fields():
            self.dlg.cb_field_names.addItem(field.name())

    def get_active_feature(self):
        layer = self.iface.activeLayer()
        field_name = self.dlg.cb_field_names.currentText()
        values = []
        for feat in layer.selectedFeatures():
            tmp_value = feat[field_name]
            self.current_lot = str(tmp_value)
        if self.current_lot != "":
            index = self.dlg.cb_field_values.findText(self.current_lot, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.dlg.cb_field_values.setCurrentIndex(index)

    def get_features(self):
        layer = self.iface.activeLayer()
        field_name = self.dlg.cb_field_names.currentText()
        self.dlg.cb_field_values.clear()
        feat = []
        if self.can_proc():
            for feature in layer.getFeatures():
                feat.append(feature["LOT_NO"])
            feat.sort()
            for f in feat:
                self.dlg.cb_field_values.addItem(str(f))

    def can_proc(self):
        layer = self.iface.activeLayer()
        attr_count = len(layer.fields().names())
        can_proc = False
        for x in range(attr_count):
            if layer.fields().names()[x] == "LOT_NO":
                can_proc = True
        return can_proc

    def set_cache2(self):
        if self.dlg.cb_field_brgys.currentText() != "":
            stored_file = self.get_store_folder() + "/GIS DataBase/cache2.ini"
            if os.path.exists(stored_file):
                f = open(stored_file, "w+")
                f.write("CURRENT_BRGY=" + self.dlg.cb_field_brgys.currentText())
                f.close()
            else:
                QMessageBox.information(None, "Cache File", "Cache file does not exist!")

    def layer_brgy(self):
        layer = self.iface.activeLayer()
        brgy_name = layer.name().lower().split("section")[0].replace("_", " ").strip().upper()
        print("Current Layer's Barangay: " + brgy_name)
        return brgy_name

    def cur_brgy(self):
        temp_name = self.layer_brgy().upper()
        index = self.dlg.cb_field_brgys.findText(temp_name, QtCore.Qt.MatchFixedString)
        print("temp_name: " + str(index))
        if index >= 0:
            self.curbrgy = self.barcode[self.barname.index(temp_name)]
            self.dlg.cb_field_brgys.setCurrentIndex(index)
        # else:
            # stored_file = self.get_store_folder() + "\\GIS DataBase\\cache2.ini"
            # if os.path.exists(stored_file):
            #     f = open(stored_file, "r")
            #     if f.mode == "r":
            #         content = f.read()
            #         self.curbrgy = self.barcode[self.barname.index(content.split("=")[1])]
            #         brgy = content.split("=")[1]
            #         index = self.dlg.cb_field_brgys.findText(brgy, QtCore.Qt.MatchFixedString)
            #         if index >= 0:
            #             self.dlg.cb_field_brgys.setCurrentIndex(index)
            #     f.close()

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
            self.set_cache1()
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
                self.curcode = self.muncode[self.munname.index(self.db[3].replace("erptax_", "").upper())]
                self.curname = self.munname[self.munname.index(self.db[3].replace("erptax_", "").upper())]
            f.close()
        return haspath

    def reload_config(self):
        if self.open_conn():
            self.get_brgy_list()
            self.cur_brgy()
            self.set_brgy()
            self.get_attr_field()
            self.get_features()
            self.get_active_feature()
            self.dlg.lbl_database.setText("RELOADED:  " + self.curname + " DATABASE")

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

    def set_cache1(self):
        import MySQLdb as mdb
        DBHOST = self.db[0]
        DBUSER = self.db[1]
        DBPASS = self.db[2]
        DBNAME = self.db[3]
        try:
            db = mdb.connect(DBHOST, DBUSER, DBPASS, DBNAME)
            muncode = self.muncode[self.munname.index(self.dlg_config.input_data.currentText().replace("erptax_", "").upper())]
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
            f.close()
        else:
            QMessageBox.information(None, "Cache File", "Cache file does not exist!")

    def set_brgy(self):
        if len(self.barname) > 0:
            self.dlg.cb_field_brgys.clear()
            for brgy in self.barname:
                self.dlg.cb_field_brgys.addItem(brgy)

    def tw_error_cell_click(self):
        if self.dlg.tw_error.rowCount() > 0:
            items = self.dlg.tw_error.selectedItems()
            if len(items) > 0:
                self.selected_lot = str(items[0].text()).strip()
                index = self.dlg.cb_field_values.findText(self.selected_lot, QtCore.Qt.MatchFixedString)
                if index >= 0:
                    self.dlg.cb_field_values.setCurrentIndex(index)

    def tw_match_cell_click(self):
        if self.dlg.tw_match.rowCount() > 0:
            items = self.dlg.tw_match.selectedItems()
            if len(items) > 0:
                self.selected_lot = str(items[0].text()).strip()
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

    def locate(self):
        if self.selected_lot is not None:
            layer = self.iface.activeLayer()
            selection = []
            layer.removeSelection()
            for feature in layer.getFeatures():
                geom = feature.geometry()
                lot = feature.attribute("LOT_NO")
                if lot == self.selected_lot:
                    selection.append(feature.id())
                    layer.select(selection)

    def tmcr(self):
        cur = self.connect_to_db().cursor()
        cur.execute(self.get_query3("liblandinfo", self.curcode, self.curbrgy))
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
                    for c in range(c_col):
                        item = QTableWidgetItem(str(row[r][c]))
                        self.dlg.tw_tmcr.setItem(twr-1, c, item)

    def tmcr_search(self):
        if self.dlg.cb_search.count() == 0:
            self.tmcr()
        else:
            field = self.dlg.cb_search.currentText()
            key = self.dlg.txt_search.text()
            cur = self.connect_to_db().cursor()
            cur.execute(self.get_query4("liblandsearch", self.curcode, self.curbrgy, "AND " + field + " LIKE '%" + key + "%'"))
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

    def match(self):
        self.reload_config()
        layer = self.iface.activeLayer()
        field_list = []
        brgy_name = self.layer_brgy()
        if self.curbrgy is not None:
            self.dlg.lbl_brgy.setText("CURRENT BARANGAY:  [" + self.curbrgy + "] " + brgy_name)
        if self.barname.__contains__(brgy_name):
            self.curbrgy = self.barcode[self.barname.index(brgy_name)]
            if self.can_proc():
                for feature in layer.getFeatures():
                    field_list.append(str(feature["LOT_NO"]))
                field_list.sort()
                print("Pre-match values:")
                print(field_list)
                cur = self.connect_to_db().cursor()
                cur.execute(self.get_query3("libmatch", self.curcode, self.curbrgy))
                row = cur.fetchall()
                c_row = len(row)
                self.dlg.tw_match.setRowCount(0)
                self.dlg.tw_match.setColumnCount(0)
                if c_row > 0:
                    c_col = len(row[0])
                    twr1 = 0
                    self.dlg.tw_match.setColumnCount(c_col)
                    columns = []
                    for i in range(len(cur.description)):
                        columns.append(cur.description[i][0])
                    # columns.append("MATCH_STATUS")
                    self.dlg.tw_match.setHorizontalHeaderLabels(columns)
                    for r in range(c_row):
                        if str(row[r][c_col - 1]) == "CANCELLED":
                            twr1 += 0
                        elif str(row[r][c_col - 1]) == "DELETED":
                            twr1 += 0
                        else:
                            if field_list.__contains__(str(row[r][0]).strip()):
                                existence = 0
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
                                    self.dlg.tw_match.setItem(twr1 - 1, 1, item)
                    print("Post-match values [Process I]:")
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
                        if c_row > 0:
                            c_col = len(row[0])
                            self.dlg.tw_error.setRowCount(len(field_list))
                            self.dlg.tw_error.setColumnCount(c_col)
                            c_count = 1
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
                                item = QTableWidgetItem("No record from current brgy!")
                                self.dlg.tw_error.setItem(c_row + rcount, 1, item)
                                rcount += 1
                    if len(field_list) > 0:
                        print("Post-match values [Process II]:")
                        print(field_list)
        else:
            QMessageBox.information(None, "Invalid Layer Name", "Layer name is not a valid ERPT Barangay!")

    def attr(self):
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

    def attr_trim(self):
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
                for c in range(col - 1, -1, -1):
                    field_name = layer.fields().names()[c]
                    relevant = False
                    if field_name.startswith("ER_"):
                        relevant = True
                    if field_name == "LOT_NO":
                        relevant = True
                    if not relevant:
                        print("kill: " + str(field_name))
                        provider.deleteAttributes([c])
                        layer.updateFields()
                cur = self.connect_to_db().cursor()
                cur.execute(self.get_query3("libjoindata", self.curcode, self.curbrgy))
                row = cur.fetchall()
                c_row = len(row)
                if c_row > 0:
                    for c in range(len(cur.description)):
                        if c > 0:
                            col_name = cur.description[c][0]
                            provider.addAttributes([QgsField("E_" + str(col_name), QVariant.String)])
                            layer.updateFields()
        self.attr()

    def attr_join(self):
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
                    # self.dlg.tw_attr.setColumnCount(self.dlg.tw_attr.columnCount() + c_col)
                    lots = []
                    data = []
                    for r in range(c_row - 1, -1, -1):
                        if str(row[r][c_col - 1]).strip() == "CANCELLED":
                            print("REMOVED LOT NO.: " + str(row[r][0]) + " [" + str(row[r][c_col - 1]) + "]")
                        elif str(row[r][c_col - 1]).strip() == "DELETED":
                            print("REMOVED LOT NO.: " + str(row[r][0]) + " [" + str(row[r][c_col - 1]) + "]")
                        else:
                            lots.append(str(row[r][0]))
                            data.append(row[r])
                    features = layer.getFeatures()
                    layer.startEditing()
                    col_count = len(cur.description)
                    for f in features:
                        lot_no = str(f["LOT_NO"])
                        for cc in range(col_count):
                            if int(cc) > 0:
                                data_list = []
                                num = 1
                                if lots.__contains__(lot_no):
                                    index = lots.index(lot_no)
                                    num += 1
                                    attr_value = {cc: data[index][cc]}
                                    provider.changeAttributeValues({f.id(): attr_value})
                    layer.commitChanges()
                    self.attr()

    def use_value(self):
        if self.dlg.tw_data.rowCount() > 0:
            items = self.dlg.tw_data.selectedItems()
            col = self.dlg.tw_data.columnCount()
            if col > 0:
                self.dlg.tw_value.setRowCount(0)
                self.dlg.tw_value.setColumnCount(0)
                if self.can_proc():
                    self.dlg.tw_value.setRowCount(1)
                    self.dlg.tw_value.setColumnCount(col)
                    columns = []
                    for i in range(col):
                        columns.append(self.dlg.tw_data.horizontalHeaderItem(i).text())
                    self.dlg.tw_value.setHorizontalHeaderLabels(columns)
                    for c in range(col):
                        item = str(items[c].text())
                        if item != "NULL":
                            val = QTableWidgetItem(item)
                            self.dlg.tw_value.setItem(0, c, val)
                else:
                    QMessageBox.information(None, "Invalid Proc", "No valid data to process!")
                for i in range(len(items)):
                    value = str(items[0].text()).strip()

    def apply_value(self):
        if self.can_proc():
            if self.dlg.tw_value.rowCount() > 0:
                layer = self.iface.activeLayer()
                feature = layer.selectedFeatures()
                provider = layer.dataProvider()
                selected = len(layer.selectedFeatures())
                col = len(layer.fields().names())
                if self.can_proc():
                    relevant = 0
                    for c in range(col):
                        field_name = layer.fields().names()[c]
                        if field_name.startswith("E_"):
                            relevant += 1
                    if relevant > 0 and selected == 1:
                        layer.startEditing()
                        for cc in range(col):
                            item = self.dlg.tw_value.item(0, cc).text()
                            if item != "None":
                                attr_value = {cc: item}
                                provider.changeAttributeValues({feature[0].id(): attr_value})
                        layer.commitChanges()
                        self.attr()
        else:
            QMessageBox.information(None, "Invalid Proc", "No valid data to process!")

    def get_dlg(self, dlg):
        print(dlg.tw_data.columnCount())

    def get_pkg(self):
        print("Installed packages:")
        import pkg_resources
        installed_packages = pkg_resources.working_set
        installed_packages_list = sorted(["%s==%s" % (i.key, i.version) for i in installed_packages])
        for pkg in installed_packages_list:
            print(pkg)

    def run_match(self):
        if self.match_start:
            self.match_start = False
            # self.dlg_match.btn_analyze.clicked.connect(self.match)
            # self.dlg_match.tw_data.itemSelectionChanged.connect(self.cell_click)
            # self.dlg_match.btn_locate.clicked.connect(self.locate)
        # self.open_conn()
        # self.get_brgy_list()
        # self.match()
        self.get_dlg(self.dlg)
        self.dlg_match.show()

    def run_config(self):
        if self.config_start:
            self.config_start = False
            self.dlg_config.btn_connect.clicked.connect(self.save_conn)

        # Create query file
        # self.set_query("query1")

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

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = eRPTSIntegrationDialog()
            self.dlg.btn_get_data.clicked.connect(self.get_data)
            self.dlg.btn_reload.clicked.connect(self.reload_config)
            self.dlg.btn_analyze.clicked.connect(self.match)
            self.dlg.tw_error.itemSelectionChanged.connect(self.tw_error_cell_click)
            self.dlg.tw_match.itemSelectionChanged.connect(self.tw_match_cell_click)
            self.dlg.tw_attr.itemSelectionChanged.connect(self.tw_attr_cell_click)
            self.dlg.btn_locate.clicked.connect(self.locate)
            self.dlg.btn_tmcr.clicked.connect(self.tmcr)
            self.dlg.btn_tmcr_search.clicked.connect(self.tmcr_search)
            self.dlg.btn_irre.clicked.connect(self.attr_trim)
            self.dlg.btn_join.clicked.connect(self.attr_join)
            self.dlg.btn_commit.clicked.connect(self.attr)
            self.dlg.btn_use.clicked.connect(self.use_value)
            self.dlg.btn_apply.clicked.connect(self.apply_value)
        self.get_pkg()
        if self.open_conn():
            self.attr()
            self.get_brgy_list()
            self.cur_brgy()
            self.set_brgy()
            self.get_attr_field()
            self.get_features()
            self.get_active_feature()
            self.dlg.lbl_database.setText("TARGETING:  [" + self.curcode + "] " + self.curname + " DATABASE")
            self.match()
            self.retrieve(self.current_lot)
            if self.current_lot is not None:
                self.dlg.lbl_lot.setText("[SHP] CURRENT LOT: " + self.current_lot)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        # See if OK was pressed
        if result:

            pass