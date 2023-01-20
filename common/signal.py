from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any, Callable, Dict, Iterable, Set, Tuple


def sorted_pairs(L: Iterable[Tuple[str, Any]]) -> Iterable[Tuple[str, Any]]:
    return sorted(L, key=lambda x: x[0])


@dataclass
class Node:
    children: Dict[Tuple[str, Any], "Node"] = field(default_factory=dict)
    callbacks: Set[Callable] = field(default_factory=set)


class Signal:
    """
    Signal is a publish-subscribe broker, allowing subscribers to listen to
    events and publishers to emit these events without worrying who listens to
    what, while efficiently invoking only subscribers that are interested in
    the published event.

    Subscribers provide a callback and a filter. Event matches the filter if
    (and only if):
        - event contains all fields specified by the filter
        - for these fields, values in the event are equal to ones in the filter

    which translates to the following predicate:

        def match(event, filter):
            for key, value in filter.keys():
                if event.get(key) != value:
                    return False

            return True

    To avoid evaluating this predicate for all registered subscribers, we
    construct a N-tree, where children are indexed by `(field name, field
    value)` pair. To add subscription, we sort filter items by `field name` and
    insert each item as a node into the tree.

    For example, adding subscription with filter `f={a: 1, c:3, b: 2}` and
    callback `cb=F` to an empty `Signal` results in a following tree:
        <root>:
            (a, 1):
                (b, 2):
                    (c, 3): {F}
    adding another subscription with `f={a: 1, b: 3}` and `cb=G` to the same
    `Signal` results in:
        <root>:
            (a, 1):
                (b, 2):
                    (c, 3): {F}
                (b, 3): {G}
    and another one with `f={b: 4, d: 5}` and `cb=H`:
        <root>:
            (a, 1):
                (b, 2):
                    (c, 3): {F}
                (b, 3): {G}
            (b, 4):
                (d, 5): {H}
    and another one with `f={a: 1, b: 2} and `cb=I`:
        <root>:
            (a, 1):
                (b, 2): {I}
                    (c, 3): {F}
                (b, 3): {G}
            (b, 4):
                (d, 5): {H}

    When publishing, we again sort event items by field name, set the current
    node `N` to `<root>`, and then for each item `i`:
     - unconditionally call all callbacks attached to the `N`
     - if `N` contains a child matching `i`, recurse from `N` set that child
       and remaining event fields
     - otherwise, stay at `N` and proceed to the next item

    Note that a published event may match more than one subscriber's filter,
    whether they live on the same path through the tree, or not. That's why we
    call the lookup recursively and *do not* return from the current branch -
    instead we continue as usual with the current node, until each recursion
    branch exhausts event fields.
    """

    def __init__(self):
        self.root = Node()

    async def publish(self, event: Dict[str, Any]):
        async def _publish(node: Node, match: Iterable[Tuple[str, Any]], event: Dict[str, Any]):
            for callback in set(node.callbacks):
                result = callback()
                if isawaitable(result):
                    await result

            while match:
                (key, value), *match = match
                if next := node.children.get((key, value)):
                    await _publish(next, match, event)

        await _publish(self.root, sorted_pairs(event.items()), event)

    def subscribe(self, filter: Dict[str, Any], callback: Callable):
        node = self.root

        for k, v in sorted_pairs(filter.items()):
            node = node.children.setdefault((k, v), Node())

        node.callbacks.add(callback)

        return lambda: node.callbacks.discard(callback)
