from collections import Counter
from flask import request
from flask_restful import Resource

from stripe import error
from libs.strings import gettext
from models.item import ItemModel
from models.order import OrderModel, ItemsInOrder
from schemas.order import OrderSchema

order_schema = OrderSchema()


class Order(Resource):
    @classmethod
    def get(cls):
        return order_schema.dump(OrderModel.find_all(), many=True), 200

    @classmethod
    def post(cls):
        """
        Expect a token and a list of item ids from the request body.
        Construct an order and talk to the Strip API to make a charge.
        :return:
        """
        data = request.get_json() # token + list of item ids
        items = []
        item_id_quantities = Counter(data["item_ids"])

        #iterate over items and retrieve them from the database
        for _id, count in item_id_quantities.most_common():
            item = ItemModel.find_by_id(_id)
            if not item:
                return {"message": gettext("order_item_by_id_not_found").format(_id)}, 404

            items.append(ItemsInOrder(item_id=_id, quantity=count))

        order = OrderModel(items=items, status="pending")
        order.save_to_db()  # this does not submit to Stripe

        try:
            order.set_status("failed")
            order.charge_with_stripe(data["token"])
            order.set_status("complete")
            return order_schema.dump(order), 200
        except(error.CardError, error.RateLimitError, error.InvalidRequestError, error.AuthenticationError,
               error.APIConnectionError, error.StripeError) as e:
            return e.json_body, e.http_status
        except Exception as e:
            print(e)
            return {"message": gettext("order_error")}, 500