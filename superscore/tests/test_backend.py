import pytest

from superscore.backends.core import _Backend
from superscore.model import Parameter


@pytest.mark.parametrize('backends', [0], indirect=True)
def test_save_entry(backends: _Backend):
    new_entry = Parameter()

    backends.save_entry(new_entry)
    found_entry = backends.get_entry(new_entry.meta_id)
    assert found_entry == new_entry


@pytest.mark.parametrize('backends', [0], indirect=True)
def test_delete_entry(backends: _Backend):
    entry = backends.root[0]
    backends.delete_entry(entry)

    assert backends.get_entry(entry.meta_id) is None


@pytest.mark.parametrize('backends', [0], indirect=True)
def test_search_entry(backends: _Backend):
    # Given an entry we know is in the backend
    # Search by type
    # Search by field name
    # search by description
    assert True
