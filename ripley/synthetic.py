"""Small non-NFL adapter: synthetic inventory reorder decision."""
class InventoryAdapter:
    domain_id = 'synthetic-inventory'
    version = '1'
    expected_output = {'reorder': bool, 'projected_stock': int}
    def predict(self, inputs):
        stock, demand, threshold = (inputs[k] for k in ('stock', 'demand', 'threshold'))
        if not all(type(x) is int and x >= 0 for x in (stock, demand, threshold)):
            raise ValueError('nonnegative integers required')
        remaining = stock - demand
        return {'reorder': remaining < threshold, 'projected_stock': remaining}
