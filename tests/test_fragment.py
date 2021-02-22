from exporter.fragment import FragmentedJsonList

import os

data_dir = "data"
last_fragment_size = 3
fragment_size = 5
num_fragments = 10
fragments = [os.path.join(data_dir, f"{n}.json") for n in range(num_fragments)]

def patch_return(retval=None):
    return lambda *args, **kwargs: retval

def patch_return_first_arg():
    return lambda *args, **kwargs: args[0]

def patch_path_exists(filename):
    return filename == data_dir or filename in fragments

def create_spy(fn):
    return lambda *args, **kwargs: fn(*args, **kwargs)

def create_mock_data(generator):
    return [{"data": n} for n in generator]

def patch_read_json(self, filename):
    if filename not in fragments:
        raise FileNotFoundError()

    index = fragments.index(filename)
    base_index = index * fragment_size

    if index == num_fragments - 1:
        return create_mock_data(range(base_index, base_index + last_fragment_size))
    else:
        return create_mock_data(range(base_index, base_index + fragment_size))

def patch(monkeypatch):
    monkeypatch.setattr(os, "makedirs", patch_return())
    monkeypatch.setattr(os.path, "abspath", patch_return_first_arg())
    monkeypatch.setattr(os.path, "exists", patch_path_exists)
    monkeypatch.setattr(os.path, "isfile", patch_path_exists)

    monkeypatch.setattr(FragmentedJsonList, "_write_json", patch_return())
    monkeypatch.setattr(FragmentedJsonList, "_read_json", patch_read_json)

def test_read_basic(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)

    assert len(fragment) == fragment_size * (num_fragments - 1) + last_fragment_size

    counter = 0
    for i in fragment:
        assert "data" in i
        assert i["data"] == counter

        counter += 1

    assert fragment[0]["data"] == 0
    assert fragment[len(fragment) - 1]["data"] == len(fragment) - 1

def test_read_negative(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)

    assert fragment[-1]["data"] == len(fragment) - 1
    assert fragment[-1 * len(fragment)]["data"] == 0

def assert_slice(fragment, start, end, step):
    sliced = fragment[start:end:step]
    print(sliced)

    index = 0
    for n in range(0, len(fragment))[start:end:step]:
        assert sliced[index]["data"] == n
        index += 1

def test_read_slice_basic(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)
    assert_slice(fragment, 5, 15, None)

def test_read_slice_with_nones(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)
    assert_slice(fragment, None, 15, None)
    assert_slice(fragment, 5, None, None)

def test_read_slice_stepped(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)
    assert_slice(fragment, 1, 21, 2)

def test_read_slice_reverse(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)
    assert_slice(fragment, None, None, -1)
    assert_slice(fragment, -5, -20, -2)

def test_write_append(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)

    fragment.append({"data": "thunder"})

    assert fragment[-1]["data"] == "thunder"
    assert len(fragment.dirty_fragments) == 1

def test_write_extend(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)
    extension = [1, 2, 3]

    fragment.extend(extension)

    assert fragment[-len(extension):] == extension
    assert len(fragment.dirty_fragments) >= 1

def test_write_extend_large(monkeypatch, mocker):
    patch(monkeypatch)
    new_fragment_spy = mocker.spy(FragmentedJsonList, "create_new_fragment")

    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)
    fragments_to_create = 20
    extension = list(range(fragment_size * fragments_to_create))

    fragment.extend(extension)

    assert fragment[-len(extension):] == extension
    assert new_fragment_spy.call_count == fragments_to_create

def test_write_update(monkeypatch):
    patch(monkeypatch)
    fragment = FragmentedJsonList(data_dir, fragment_size=fragment_size)
    update_len = fragment_size

    for i in range(update_len):
        fragment.update(i, {
            "something": i
        })

    for i in range(update_len):
        assert "something" in fragment[i] and fragment[i]["something"] == i

    assert len(fragment.dirty_fragments) == 1 and 0 in fragment.dirty_fragments