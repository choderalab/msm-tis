import collections

# TODO: write tests!

def group_by(list_of_iterable, column_number):
    results = collections.defaultdict(list)
    for obj in list_of_iterable:
        results[obj[column_number]].append(obj)

    return results

def compare_sets(set1, set2):
    only_in_1 = set1 - set2
    only_in_2 = set2 - set1
    return (only_in_1, only_in_2)

def flatten(inputs, value_iter, classes):
    results = []
    for val in value_iter(inputs):
        if isinstance(val, classes):
            results += flatten(val, value_iter, classes)
        else:
            results.append(val)
    return results

def flatten_dict(dct):
    return flatten(dct, lambda x: x.values(), dict)

def flatten_iterable(ll):
    return flatten(ll, lambda x: x, (list, tuple, set))

def is_mappable(obj):
    return isinstance(dict)  # for now

def flatten_all(obj):
    return flatten(obj,
                   lambda x: x.values() if is_mappable(x) else x.__iter__(),
                   (list, tuple, set, dict))
