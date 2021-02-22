import ujson as json
import math
import os
import threading
import time

class Fragment:
    def __init__(self, index, data):
        self.index = index
        self.data = data

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, item, value):
        self.data[item] = value

class FragmentCommitThreadRunner:
    def __init__(self, fragment, frequency=900):
        self.fragment = fragment
        self.frequency = frequency

        self.thread = threading.Thread(target=self._thread_run)
        self.unloading = False

    def start(self):
        self.thread.start()

    def close(self):
        self.unloading = True
        self.thread.join()

    def _thread_run(self):
        i = 0
        while not self.unloading:
            if i == self.frequency:
                self.fragment.commit_fragments()
                i = 0

            time.sleep(1)
            i += 1

class FragmentFactory:
    def __init__(self):
        self._fragments: List[FragmentedJsonList] = []

    def close(self):
        for frag in self._fragments:
            frag.close()

    def create(self, *args, **kwargs):
        frag = FragmentedJsonList(*args, **kwargs)
        
        self._fragments.append(frag)

        return frag

class FragmentedJsonList:
    def __init__(self, data_dir, fragment_file_format="{}.json", fragment_size=5000):
        self.fragment_size = fragment_size
        self.data_dir = os.path.abspath(data_dir)
        self.fragment_file_format = fragment_file_format

        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        self.file_map = dict()
        self.fragment_map = dict()
        self.dirty_fragments = set()
        self.fragment_count = 0

        self.load_file_map()

        if self.fragment_count == 0:
            self.create_new_fragment()

    def close(self):
        self.commit_fragments()
        self.file_map.clear()
        self.fragment_map.clear()
        self.dirty_fragments.clear()

    def _write_json(self, filename, data):
        with open(filename, "w") as fd:
            json.dump(data, fd)

    def _read_json(self, filename):
        with open(filename, "r") as fd:
            return json.load(fd)

    def load_file_map(self):
        dir_format = os.path.join(self.data_dir, self.fragment_file_format)

        self.fragment_count = 0
        while True:
            filename = dir_format.format(self.fragment_count)

            if os.path.isfile(filename):
                self.file_map[self.fragment_count] = filename
            else:
                break

            self.fragment_count += 1

    def fragment_index(self, index):
        fragment = index // self.fragment_size
        fragment_index = index % self.fragment_size

        return (fragment, fragment_index)

    def is_fragment_loaded(self, fragment):
        return fragment in self.fragment_map.keys()

    def load_fragment(self, fragment):
        if fragment not in self.file_map.keys():
            raise RuntimeError()

        if self.is_fragment_loaded(fragment):
            return

        fragment_file = self.file_map[fragment]

        fragment_data = self._read_json(fragment_file)
        self.fragment_map[fragment] = Fragment(fragment, fragment_data)

    def commit_fragments(self):
        for fragment in self.dirty_fragments:
            fragment_file = self.file_map[fragment]
            fragment_data = self.fragment_map[fragment]

            self._write_json(fragment_file, fragment_data.data)

        self.dirty_fragments.clear()

    def create_new_fragment(self):
        fragment_index = self.fragment_count
        fragment_name = self.data_dir + '/' + self.fragment_file_format.format(fragment_index)

        self.file_map[fragment_index] = fragment_name
        self.fragment_map[fragment_index] = Fragment(fragment_index, [])
        self.dirty_fragments.add(fragment_index)

        self.fragment_count += 1

    def update(self, index, value):
        if index < 0:
            index += len(self)

        data = self[index]

        # get fragment index
        fragment, fragment_index = self.fragment_index(index)

        # update value
        self.fragment_map[fragment][fragment_index] = value

        # mark as dirty
        self.dirty_fragments.add(fragment)

    def append(self, value):
        self.extend([value])

    def extend(self, values):
        # no.
        if len(values) == 0:
            return

        # load last fragment
        last_index = self.fragment_count - 1
        self.load_fragment(last_index)

        # get last fragment and its size
        last_fragment = self.fragment_map[last_index]
        last_size = len(last_fragment)

        # mark last fragment as dirty
        self.dirty_fragments.add(last_index)

        # extend it and return, if we don't need a new fragment
        if last_size + len(values) <= self.fragment_size:
            last_fragment.data.extend(values)
        else:
            # we need a new fragment, so first extend to the limit
            size_to_add = self.fragment_size - last_size
            last_fragment.data.extend(values[:size_to_add])

            # create a new fragment
            self.create_new_fragment()

            # recursively call ourself. this allows us to add
            # even more fragments if the list is THAT big
            self.extend(values[size_to_add:])

    def get(self, fragment, fragment_index):
        if not self.is_fragment_loaded(fragment):
            self.load_fragment(fragment)

        return self.fragment_map[fragment][fragment_index]

    def __iter__(self):
        self.iterator_index = 0
        return self

    def __next__(self):
        if self.iterator_index >= len(self):
            raise StopIteration
        else:
            self.iterator_index += 1
            return self[self.iterator_index - 1]

    def __len__(self):
        last_fragment_index = self.fragment_count - 1
        self.load_fragment(last_fragment_index)
        return last_fragment_index * self.fragment_size + len(self.fragment_map[last_fragment_index])

    def __getitem__(self, index):
        print(f"__getitem__({index})")
        if isinstance(index, slice):
            return [self[i] for i in range(0, len(self))[index]]

        if index < 0:
            self.load_fragment(self.fragment_count - 1)
            index += len(self)

        return self.get(*self.fragment_index(index))
