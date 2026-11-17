import unittest

from shop.orders import place_order, total_cost


class TestOrders(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total_cost([[1]]), 2)


def test_place_order():
    assert place_order([[1]])
