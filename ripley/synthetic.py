"""Small non-NFL adapter: synthetic inventory reorder decision."""
from datetime import datetime, timezone


class InventoryAdapter:
    domain_id = 'synthetic-inventory'
    version = '1'
    expected_output = {'reorder': bool, 'projected_stock': int}

    def snapshot_metadata(self, inputs):
        return {'observed_at': datetime.now(timezone.utc).isoformat(),
                'sources': ['synthetic-inventory-fixture'],
                'data_quality': 'synthetic'}

    def predict(self, inputs):
        stock, demand, threshold = (inputs[k] for k in ('stock', 'demand', 'threshold'))
        if not all(type(x) is int and x >= 0 for x in (stock, demand, threshold)):
            raise ValueError('nonnegative integers required')
        remaining = stock - demand
        return {'reorder': remaining < threshold, 'projected_stock': remaining}
