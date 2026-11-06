"""Run: python -m demo"""
from ripley.core import Ripley
from ripley.synthetic import InventoryAdapter

if __name__ == '__main__':
    records = Ripley().run(InventoryAdapter(), {'stock': 10, 'demand': 8, 'threshold': 5})
    print('prediction:', dict(records['result'].data['output']))
    print('validation:', records['validation'].data['passed'])
    print('approval:', records['approval'].data['status'])
