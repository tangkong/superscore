
import json
import os
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from qtpy import QtCore, QtWidgets

from superscore.widgets.page.search import SavedFilter, SavedFiltersModel, SearchPage

# Mock apischema to avoid import issues if not available in test env,
# although we installed it.

@pytest.fixture
def saved_filter():
    return SavedFilter(
        name="Test Filter",
        types=["Snapshot", "Collection"],
        name_filter="MyName",
        desc_filter="MyDesc",
        pv_filter="MyPV",
        start_time="2023-01-01T12:00:00",
        end_time="2023-01-02T12:00:00"
    )

def test_saved_filter_model(saved_filter):
    model = SavedFiltersModel()
    assert model.rowCount() == 0

    model.add_filter(saved_filter)
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0)) == "Test Filter"

    retrieved = model.get_filter(0)
    assert retrieved == saved_filter

    model.remove_row(0)
    assert model.rowCount() == 0

@patch('superscore.widgets.page.search.QtWidgets.QInputDialog.getText')
@patch('superscore.widgets.page.search.SearchPage.get_filters_path')
def test_search_page_save_load(mock_get_path, mock_get_text, saved_filter, tmp_path, qtbot):
    # Setup tmp path for filters
    filters_file = tmp_path / "filters.json"
    mock_get_path.return_value = str(filters_file)

    # Mock user input for name
    mock_get_text.return_value = ("Test Filter", True)

    # Init SearchPage
    # We patch setup_ui to avoid loading the actual .ui file which requires display
    with patch('superscore.widgets.page.search.SearchPage.setup_ui') as mock_setup_ui, \
         patch('superscore.widgets.page.search.SearchPage.show_current_filter'):

        page = SearchPage()

        # Manually setup what we need for the test since setup_ui is mocked
        page.saved_filters_model = SavedFiltersModel(page.saved_filters)
        page.name_line_edit = QtWidgets.QLineEdit()
        page.desc_line_edit = QtWidgets.QLineEdit()
        page.pv_line_edit = QtWidgets.QLineEdit()
        page.start_dt_edit = QtWidgets.QDateTimeEdit()
        page.end_dt_edit = QtWidgets.QDateTimeEdit()
        page.type_checkboxes = [QtWidgets.QCheckBox() for _ in range(4)]
        page.filter_table_view = QtWidgets.QTableView()
        page.filter_table_view.setModel(page.saved_filters_model)

        # Set values
        page.name_line_edit.setText("MyName")
        page.desc_line_edit.setText("MyDesc")
        page.pv_line_edit.setText("MyPV")
        page.start_dt_edit.setDateTime(QtCore.QDateTime.fromString("2023-01-01T12:00:00", QtCore.Qt.ISODate))
        page.end_dt_edit.setDateTime(QtCore.QDateTime.fromString("2023-01-02T12:00:00", QtCore.Qt.ISODate))
        page.type_checkboxes[0].setChecked(True) # Snapshot
        page.type_checkboxes[1].setChecked(True) # Collection

        # Test Save
        page.save_current_filter()

        assert os.path.exists(filters_file)
        with open(filters_file, 'r') as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]['name'] == "Test Filter"
            assert data[0]['name_filter'] == "MyName"

        # Clear widgets
        page.name_line_edit.setText("")
        page.type_checkboxes[0].setChecked(False)

        # Test Load
        # Select the row
        selection_model = page.filter_table_view.selectionModel()
        selection_model.select(page.saved_filters_model.index(0, 0), QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)

        page.load_selected_filter()

        assert page.name_line_edit.text() == "MyName"
        assert page.type_checkboxes[0].isChecked()
        assert page.type_checkboxes[1].isChecked()
        assert not page.type_checkboxes[2].isChecked()
