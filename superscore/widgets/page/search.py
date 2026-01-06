"""Search page"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from enum import auto
from typing import Any, Dict, List, Optional

import apischema
import qtawesome as qta
from dateutil import tz
from qtpy import QtCore, QtWidgets

from superscore.backends.core import SearchTerm
from superscore.model import Collection, Entry, Readback, Setpoint, Snapshot
from superscore.widgets import ICON_MAP
from superscore.widgets.core import Display, WindowLinker
from superscore.widgets.views import (BaseTableEntryModel, ButtonDelegate,
                                      HeaderEnum)

logger = logging.getLogger(__name__)


@dataclass
class SavedFilter:
    name: str
    types: List[str]
    name_filter: str
    desc_filter: str
    pv_filter: str
    start_time: str
    end_time: str


class SavedFilterHeader(HeaderEnum):
    NAME = 0


class SavedFiltersModel(QtCore.QAbstractTableModel):
    """
    Model for displaying SavedFilter objects in a QTableView.
    """
    def __init__(self, filters: List[SavedFilter] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if filters is None:
            self.filters = []
        else:
            self.filters = filters
        self.headers = ["Name"]

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.filters)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.headers)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        if role == QtCore.Qt.DisplayRole:
            filter_obj = self.filters[index.row()]
            if index.column() == SavedFilterHeader.NAME:
                return filter_obj.name

        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole) -> Any:
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        return None

    def add_filter(self, filter_obj: SavedFilter) -> None:
        self.beginInsertRows(QtCore.QModelIndex(), len(self.filters), len(self.filters))
        self.filters.append(filter_obj)
        self.endInsertRows()

    def remove_row(self, row: int) -> None:
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.filters.pop(row)
        self.endRemoveRows()

    def get_filter(self, row: int) -> Optional[SavedFilter]:
        if 0 <= row < len(self.filters):
            return self.filters[row]
        return None


class SearchPage(Display, QtWidgets.QWidget, WindowLinker):
    """
    Widget for searching and displaying Entry's.  Contains a variety of filter
    option input widgets, a sortable table view, and a filter management table.

    TODO: Implement filters (saving/loading)
    TODO: string-ified search query
    TODO: integration with global tree-view
    """
    filename = 'search_page.ui'

    # Left splitter, filter options select
    name_line_edit: QtWidgets.QLineEdit
    snapshot_checkbox: QtWidgets.QCheckBox
    collection_checkbox: QtWidgets.QCheckBox
    setpoint_checkbox: QtWidgets.QCheckBox
    readback_checkbox: QtWidgets.QCheckBox
    pv_line_edit: QtWidgets.QLineEdit
    desc_line_edit: QtWidgets.QLineEdit
    start_dt_edit: QtWidgets.QDateTimeEdit
    end_dt_edit: QtWidgets.QDateTimeEdit

    apply_filter_button: QtWidgets.QPushButton

    # Right splitter, filter results view
    name_subfilter_line_edit: QtWidgets.QLineEdit
    query_details_label: QtWidgets.QLabel
    save_filter_button: QtWidgets.QPushButton
    help_button: QtWidgets.QPushButton  # maybe a toolbutton for widget pop-out

    filter_table_view: QtWidgets.QTableView
    results_table_view: QtWidgets.QTableView

    def __init__(
        self,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.model: Optional[ResultModel] = None

        self.type_checkboxes: List[QtWidgets.QCheckBox] = [
            self.snapshot_checkbox, self.collection_checkbox,
            self.setpoint_checkbox, self.readback_checkbox,
        ]

        self.saved_filters: List[SavedFilter] = []
        self.load_saved_filters_from_disk()

        self.setup_ui()

    def setup_ui(self) -> None:
        # set up filter option widgets
        self.start_dt_edit.setDate(QtCore.QDate.currentDate().addDays(-365))
        self.start_dt_edit.setDisplayFormat("yyyy/MM/dd")
        self.end_dt_edit.setDate(QtCore.QDate.currentDate())
        self.end_dt_edit.setDisplayFormat("yyyy/MM/dd")
        self.apply_filter_button.clicked.connect(self.show_current_filter)

        self.collection_checkbox.setIcon(qta.icon(ICON_MAP[Collection]))
        self.snapshot_checkbox.setIcon(qta.icon(ICON_MAP[Snapshot]))
        self.setpoint_checkbox.setIcon(qta.icon(ICON_MAP[Setpoint]))
        self.readback_checkbox.setIcon(qta.icon(ICON_MAP[Readback]))

        # set up results table view
        self.model = ResultModel(entries=[])
        self.proxy_model = ResultFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.results_table_view.setModel(self.proxy_model)
        self.results_table_view.setSortingEnabled(True)
        horiz_header = self.results_table_view.horizontalHeader()
        horiz_header.setSectionResizeMode(horiz_header.Interactive)

        self.open_delegate = ButtonDelegate(button_text='open me')
        self.results_table_view.setItemDelegateForColumn(ResultsHeader.OPEN,
                                                         self.open_delegate)
        self.open_delegate.clicked.connect(self.proxy_model.open_row)

        self.name_subfilter_line_edit.textChanged.connect(self.subfilter_results)

        # set up saved filters table view
        self.saved_filters_model = SavedFiltersModel(self.saved_filters)
        self.filter_table_view.setModel(self.saved_filters_model)
        self.filter_table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.filter_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.filter_table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        # Connect save button
        self.save_filter_button.clicked.connect(self.save_current_filter)

        # Add load button (since not in ui file)
        # We need to find where save_filter_button is and add load button next to it.
        # Assuming they are in a layout.
        if self.save_filter_button.parentWidget():
            parent_layout = self.save_filter_button.parentWidget().layout()
            if parent_layout:
                self.load_filter_button = QtWidgets.QPushButton("Load Filter")
                self.load_filter_button.clicked.connect(self.load_selected_filter)
                # Find index of save button and insert after
                index = parent_layout.indexOf(self.save_filter_button)
                parent_layout.insertWidget(index + 1, self.load_filter_button)

    def _gather_search_terms(self) -> Dict[str, Any]:
        search_terms = []

        # type
        entry_type_list = [Snapshot, Collection, Setpoint, Readback]
        for checkbox, entry_type in zip(
            self.type_checkboxes,
            (Snapshot, Collection, Setpoint, Readback)
        ):
            if not checkbox.isChecked():
                entry_type_list.remove(entry_type)

        search_terms.append(SearchTerm('entry_type', 'eq', tuple(entry_type_list)))

        # name
        name = self.name_line_edit.text()
        if name:
            search_terms.append(
                SearchTerm('title', 'in', tuple(n.strip() for n in name.split(',')))
            )

        # description
        desc = self.desc_line_edit.text()
        if desc:
            search_terms.append(SearchTerm('description', 'like', desc))

        # TODO: sort out PVs
        pvs = self.pv_line_edit.text()
        if pvs:
            search_terms.append(
                SearchTerm('pvs', 'in', tuple(pv.strip() for pv in pvs.split(',')))
            )

        # time
        start_dt = self.start_dt_edit.dateTime().toPyDateTime()
        search_terms.append(SearchTerm('creation_time', 'gt', start_dt.astimezone(tz.UTC)))
        end_dt = self.end_dt_edit.date().endOfDay().toPyDateTime()
        search_terms.append(SearchTerm('creation_time', 'lt', end_dt.astimezone(tz.UTC)))

        logger.debug(f'gathered search terms: {search_terms}')
        return search_terms

    def show_current_filter(self) -> None:
        """
        Gather filter options and update source model with valid entries
        """
        # gather filter details
        search_terms = self._gather_search_terms()
        entries = self.client.search(*search_terms)

        # update source table model
        self.model.modelAboutToBeReset.emit()
        self.model.entries = list(entries)
        self.model.modelReset.emit()

    def subfilter_results(self) -> None:
        """Filter the table once more by name"""
        self.proxy_model.name_regexp.setPattern(self.name_subfilter_line_edit.text())
        self.proxy_model.invalidateFilter()

    def get_filters_path(self) -> str:
        """Return the path to the filters configuration file."""
        return os.path.expanduser("~/.superscore/filters.json")

    def load_saved_filters_from_disk(self) -> None:
        """Load saved filters from disk."""
        path = self.get_filters_path()
        if not os.path.exists(path):
            self.saved_filters = []
            return

        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self.saved_filters = [apischema.deserialize(SavedFilter, item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load filters from {path}: {e}")
            self.saved_filters = []

    def save_filters_to_disk(self) -> None:
        """Save filters to disk."""
        path = self.get_filters_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, 'w') as f:
                data = [apischema.serialize(item) for item in self.saved_filters]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save filters to {path}: {e}")

    def save_current_filter(self) -> None:
        """Save the current filter configuration."""
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Filter", "Filter Name:")
        if not ok or not name:
            return

        # Gather widget states
        types = []
        for checkbox, entry_type in zip(
            self.type_checkboxes,
            ("Snapshot", "Collection", "Setpoint", "Readback")
        ):
            if checkbox.isChecked():
                types.append(entry_type)

        saved_filter = SavedFilter(
            name=name,
            types=types,
            name_filter=self.name_line_edit.text(),
            desc_filter=self.desc_line_edit.text(),
            pv_filter=self.pv_line_edit.text(),
            start_time=self.start_dt_edit.dateTime().toString(QtCore.Qt.ISODate),
            end_time=self.end_dt_edit.dateTime().toString(QtCore.Qt.ISODate),
        )

        self.saved_filters_model.add_filter(saved_filter)
        self.save_filters_to_disk()

    def load_selected_filter(self) -> None:
        """Load the selected filter into the widgets."""
        selection = self.filter_table_view.selectionModel().selectedRows()
        if not selection:
            return

        row = selection[0].row()
        saved_filter = self.saved_filters_model.get_filter(row)
        if not saved_filter:
            return

        # Restore widgets
        self.name_line_edit.setText(saved_filter.name_filter)
        self.desc_line_edit.setText(saved_filter.desc_filter)
        self.pv_line_edit.setText(saved_filter.pv_filter)

        for checkbox, entry_type in zip(
            self.type_checkboxes,
            ("Snapshot", "Collection", "Setpoint", "Readback")
        ):
            checkbox.setChecked(entry_type in saved_filter.types)

        if saved_filter.start_time:
            self.start_dt_edit.setDateTime(QtCore.QDateTime.fromString(saved_filter.start_time, QtCore.Qt.ISODate))
        if saved_filter.end_time:
            self.end_dt_edit.setDateTime(QtCore.QDateTime.fromString(saved_filter.end_time, QtCore.Qt.ISODate))

        self.show_current_filter()


class ResultsHeader(HeaderEnum):
    NAME = 0
    TYPE = auto()
    DESCRIPTION = auto()
    CREATED = auto()
    OPEN = auto()


class ResultModel(BaseTableEntryModel):
    headers: List[str]
    _button_cols: List[ResultsHeader] = [ResultsHeader.OPEN]
    _editable_cols: Dict[int, bool] = {4: True}

    def __init__(self, *args, entries: List[Entry] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.header_enum = ResultsHeader
        self.headers = [h.header_name() for h in ResultsHeader]
        self.entries: List[Entry] = entries or []
        self.set_editable(ResultsHeader.OPEN, True)

    def data(self, index: QtCore.QModelIndex, role: int) -> Any:
        """
        Returns the data stored under the given role for the item
        referred to by the index.

        Parameters
        ----------
        index : QtCore.QModelIndex
            An index referring to a cell of the TableView
        role : int
            The requested data role.

        Returns
        -------
        Any
            the requested data
        """
        entry: Entry = self.entries[index.row()]

        # Special handling for open button delegate
        if index.column() == (len(self.headers) - 1):
            if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
                return 'click to open'

        if role != QtCore.Qt.DisplayRole:
            # table is read only
            return QtCore.QVariant()

        if index.column() == 0:  # name column
            name_text = getattr(entry, 'title', getattr(entry, 'pv_name', '<N/A>'))
            return name_text
        elif index.column() == 1:  # Type
            return type(entry).__name__
        elif index.column() == 2:  # Description
            return getattr(entry, 'description', '<no desc>')
        elif index.column() == 3:  # Creation time
            return entry.creation_time.strftime('%Y/%m/%d %H:%M')

        # if nothing is found, return invalid QVariant
        return QtCore.QVariant()


class ResultFilterProxyModel(QtCore.QSortFilterProxyModel, WindowLinker):
    """
    Filter proxy model specifically for ResultModel.  Enables per-column sorting
    and filtering table contents by name.
    """

    name_regexp: QtCore.QRegularExpression
    sourceModel: ResultModel

    def __init__(
        self,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.name_regexp = QtCore.QRegularExpression()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QtCore.QModelIndex
    ) -> bool:
        name_ok = True

        name_index = self.sourceModel().index(source_row, 0, source_parent)
        name = self.sourceModel().data(name_index, QtCore.Qt.DisplayRole)
        name_ok = self.name_regexp.match(name).hasMatch()

        return name_ok

    def open_row(self, proxy_index: QtCore.QModelIndex) -> None:
        """opens page for entry data at ``row`` (in proxy model)"""
        if self.open_page_slot is not None:
            source_row = self.mapToSource(proxy_index)
            logger.debug(f'Open page button for row: {proxy_index.row()}')
            self.open_page_slot(self.sourceModel().entries[source_row.row()])
