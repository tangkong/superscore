import pytest

from superscore.backends.core import _Backend
from superscore.errors import (BackendError, EntryExistsError,
                               EntryNotFoundError)
from superscore.model import Collection, Parameter


class TestTestBackend:
    def test_retrieve(self, linac_backend):
        assert linac_backend.get_entry("441ff79f-4948-480e-9646-55a1462a5a70") is not None  # top-level Collection
        assert linac_backend.get_entry("be3d4655-7813-4974-bb10-19e4787f8a8e") is not None  # Inner Collection
        assert linac_backend.get_entry("2c83a9be-bec6-4436-8233-79df300af670") is not None  # Parameter
        with pytest.raises(EntryNotFoundError):
            linac_backend.get_entry("d3589b21-2f77-462d-9280-bb4d4e48d93b")  # Doesn't exist

    def test_create(self, linac_backend):
        collision_entry = Parameter(uuid="5ec33c74-7f4c-4905-a106-44fbfe138140")
        with pytest.raises(EntryExistsError):
            linac_backend.save_entry(collision_entry)

        new_entry = Parameter(uuid="8913b7af-830d-4e32-bebe-b34a4616ce79")
        linac_backend.save_entry(new_entry)
        assert linac_backend.get_entry("8913b7af-830d-4e32-bebe-b34a4616ce79") is not None

    def test_update(self, linac_backend):
        modified_entry = Collection(uuid="d5bade05-d992-4e44-87d8-0db2937209bf", description="This is the new description")
        linac_backend.update_entry(modified_entry)
        assert linac_backend.get_entry(modified_entry.uuid) == modified_entry

        missing_entry = Collection(uuid="d3589b21-2f77-462d-9280-bb4d4e48d93b")
        with pytest.raises(EntryNotFoundError):
            linac_backend.update_entry(missing_entry)

    def test_delete(self, linac_backend):
        entry = linac_backend.get_entry("2506d87a-5980-4470-b29a-63eea183f53d")
        linac_backend.delete_entry(entry)
        with pytest.raises(EntryNotFoundError):
            linac_backend.get_entry("2506d87a-5980-4470-b29a-63eea183f53d")

        entry = linac_backend.get_entry("aa11f29a-3e7e-4647-bfc9-133257647fb7")
        # need new instance because editing entry would automatically sync to the backend
        unsynced = Collection(**entry.__dict__)
        unsynced.description = "I haven't been synced with the backend"
        with pytest.raises(BackendError):
            linac_backend.delete_entry(unsynced)


@pytest.mark.parametrize('backends', [0], indirect=True)
def test_save_entry(backends: _Backend):
    new_entry = Parameter()

    backends.save_entry(new_entry)
    found_entry = backends.get_entry(new_entry.uuid)
    assert found_entry == new_entry


@pytest.mark.parametrize('backends', [0], indirect=True)
def test_delete_entry(backends: _Backend):
    entry = backends.root[0]
    backends.delete_entry(entry)

    assert backends.get_entry(entry.uuid) is None


@pytest.mark.parametrize('backends', [0], indirect=True)
def test_search_entry(backends: _Backend):
    # Given an entry we know is in the backend
    # Search by type
    # Search by field name
    # search by description
    assert True
