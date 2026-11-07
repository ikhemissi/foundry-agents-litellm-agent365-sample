from azure.core.exceptions import ResourceNotFoundError


class FakeTable:
    """Keeps entities in memory, keyed like Azure Tables; a query matches the properties named in its parameters."""

    def __init__(self):
        self.entities = {}

    def upsert_entity(self, entity):
        self.entities[(entity["PartitionKey"], entity["RowKey"])] = dict(entity)

    def create_entity(self, entity):
        key = (entity["PartitionKey"], entity["RowKey"])
        assert key not in self.entities, "an entity with this key exists"
        self.entities[key] = dict(entity)

    def get_entity(self, partition_key, row_key):
        try:
            return dict(self.entities[(partition_key, row_key)])
        except KeyError:
            raise ResourceNotFoundError("not found") from None

    def query_entities(self, query_filter, *, parameters):
        matching = [e for e in self.entities.values() if all(e.get(k) == v for k, v in parameters.items())]
        return iter(sorted(matching, key=lambda entity: (entity["PartitionKey"], entity["RowKey"])))
