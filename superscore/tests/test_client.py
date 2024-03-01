from superscore.client import Client
from superscore.model import Parameter, Value

# fixture for each backend


def test_save(client: Client):
    new_entry = Parameter()
    client.save(new_entry)

    assert client.search(meta_id=new_entry.meta_id)


def test_delete(client: Client):
    new_entry = Parameter()
    client.save(new_entry)

    client.delete(new_entry)
    assert not client.search(meta_id=new_entry.meta_id)


def test_compare(client: Client):
    # should differ in uuid, but contents are identical
    assert not client.compare(Parameter(), Parameter())

    # contents are different
    assert client.compare(Parameter(pv_name='FOO'), Parameter(pv_name='BAR'))
    assert client.compare(Value(data=1), Value(data='1'))


def test_apply(client: Client):
    # TODO: figure out how we want to mock the EPICS backend.  Caproto?
    assert True


def test_from_config(client: Client):
    # a smoke test for loading from a config file
    assert True
