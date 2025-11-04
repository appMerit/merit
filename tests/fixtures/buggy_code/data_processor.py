"""Data processor with list/index bugs."""


def get_first_item(items):
    """Get first item - BUG: No empty check!"""
    return items[0]


def process_batch(data_list, batch_size):
    """Process data in batches - BUG: Index out of range!"""
    results = []
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i + batch_size]
        # BUG: Assumes batch always has at least 2 items
        first = batch[0]
        second = batch[1]  
        results.append(first + second)
    return results


def get_last_three(items):
    """Get last 3 items - BUG: Doesn't handle lists < 3!"""
    return [items[-3], items[-2], items[-1]]


def safe_get(items, index):
    """Supposedly safe get - BUG: Only checks positive indices!"""
    if index < len(items):
        return items[index]
    return None


def merge_data(list1, list2):
    """Merge two lists - BUG: Assumes both non-empty!"""
    return [list1[0], list2[0], list1[-1], list2[-1]]

