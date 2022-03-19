from otree.api import *
import time
from datetime import datetime
import random
import math


# Functions


def marginal_production_costs(t):
    c = round((max((600 - t), 0) * 50 + (600 - max(600 - t, 0)) * 100) / 600, 2)
    return c


def marginal_consumption_utility(t):
    u = round((max((600 - t), 0) * 100 + (600 - max(600 - t, 0)) * 50) / 600, 2)
    return u


def flatten(list_of_lists):  # Python function to unlist lists
    if len(list_of_lists) == 0:
        return list_of_lists
    if isinstance(list_of_lists[0], list):
        return flatten(list_of_lists[0]) + flatten(list_of_lists[1:])
    return list_of_lists[:1] + flatten(list_of_lists[1:])


doc = "Double auction market"


class C(BaseConstants):
    NAME_IN_URL = 'double_auction'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    BID_MIN = -1000
    ASK_MAX = 1000
    TIME_PER_UNIT = 600  # Time to produce/consume one unit is 10 minutes, i.e. 10*60=600 seconds
    MIN_TIMESTAMP = datetime(2000, 1, 1, 0, 0, 0, 0).timestamp()
    MAX_TIMESTAMP = datetime(3001, 1, 1, 0, 0, 0, 0).timestamp()


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    players = subsession.get_players()
    for p in players:
        # this means if the player's ID is not a multiple of 2, they are a buyer.
        # for more buyers, change the 2 to 3
        p.is_buyer = p.id_in_group % 2 > 0
        p.balance = 0
        p.session_description = p.session.config['description']
        p.current_offer_time = C.MAX_TIMESTAMP
        if p.is_buyer:
            p.current_offer = C.BID_MIN
        else:
            p.current_offer = C.ASK_MAX
        # Initialize participant variables
        participant = p.participant
        participant.offers = []
        participant.offer_times = []
        participant.trading_prices = []
        participant.trading_times = []
        participant.time_needed = 0
        participant.marginal_evaluation = 999
        participant.previous_timestamp = time.time()
        participant.current_timestamp = time.time()


class Group(BaseGroup):
    start_timestamp = models.IntegerField()


class Player(BasePlayer):
    session_description = models.StringField()
    is_buyer = models.BooleanField()
    current_offer = models.FloatField()
    current_offer_time = models.FloatField()
    balance = models.FloatField()


class Transaction(ExtraModel):
    group = models.Link(Group)
    buyer = models.Link(Player)
    seller = models.Link(Player)
    price = models.FloatField(doc="Price of this trade")
    buyer_valuation = models.FloatField(doc="Buyer's valuation of the item purchased (i.e. marginal utility)")
    seller_costs = models.FloatField(doc="Seller's production cost of the item purchased (i.e. marginal costs)")
    buyer_profits = models.FloatField(doc="Buyer's profit from this trade (if <0 then loss)")
    seller_profits = models.FloatField(doc="Seller's profit from this trade (if <0 then loss)")
    buyer_balance = models.FloatField(doc="Buyer's new balance after this trade")
    seller_balance = models.FloatField(doc="Seller's new balance after this trade")
    seconds = models.IntegerField(doc="Timestamp (seconds since beginning of trading)")
    description = models.StringField(doc="Description/Name of the Market given by experimenter")


def find_match(buyers, sellers):
    for buyer in buyers:
        for seller in sellers:
            if seller.current_offer <= buyer.current_offer:
                # return as soon as we find a match (the rest of the loop will be skipped)
                return [buyer, seller]


def live_method(player: Player, data):
    group = player.group
    players = group.get_players()
    buyers = [p for p in players if p.is_buyer]
    sellers = [p for p in players if not p.is_buyer]
    news = None
    participant = player.participant
    offers = participant.offers
    offer_times = participant.offer_times  # List of tuples of offers and respective timestamp
    if data:
        if data['type'] == 'offer':
            offers.append(int(data['offer']))
            participant.offers = offers
            offer_times.append((int(data['offer']), datetime.today().timestamp()))
            if player.is_buyer:
                offers.sort(reverse=True)  # Sort such that highest bid is first list element
                player.current_offer = offers[0]
                sorted_offer_times = [tuple for x in offers for tuple in offer_times if tuple[0] == x]
                participant.offer_times = sorted_offer_times
                player.current_offer_time = sorted_offer_times[0][1]
                match = find_match(buyers=[player], sellers=sellers)
            else:
                offers.sort(reverse=False)  # Sort such that lowest ask is first list element
                player.current_offer = offers[0]
                sorted_offer_times = [tuple for x in offers for tuple in offer_times if tuple[0] == x]
                participant.offer_times = sorted_offer_times
                player.current_offer_time = sorted_offer_times[0][1]
                match = find_match(buyers=buyers, sellers=[player])
            if match:
                [buyer, seller] = match
                if buyer.current_offer_time < seller.current_offer_time:
                    price = buyer.current_offer
                else:
                    price = seller.current_offer
                buyer_trading_times = buyer.participant.trading_times
                seller_trading_times = seller.participant.trading_times
                buyer_trading_prices = buyer.participant.trading_prices
                seller_trading_prices = seller.participant.trading_prices
                Transaction.create(
                    description=player.session.config['description'],
                    group=group,
                    buyer=buyer,
                    seller=seller,
                    price=price,
                    seconds=int(time.time() - time.mktime(
                        time.strptime(player.session.config['market_opening'], "%d %b %Y %X"))),
                    buyer_valuation=buyer.participant.marginal_evaluation,
                    seller_costs=seller.participant.marginal_evaluation,
                    buyer_profits=buyer.participant.marginal_evaluation - price,
                    seller_profits=price - seller.participant.marginal_evaluation,
                    buyer_balance=buyer.balance + buyer.participant.marginal_evaluation - price,
                    seller_balance=seller.balance + price - seller.participant.marginal_evaluation
                )
                # Calculate new balances
                buyer.balance += buyer.participant.marginal_evaluation - price
                seller.balance += price - seller.participant.marginal_evaluation
                # Create message about effected trade
                news = dict(buyer=buyer.id_in_group, seller=seller.id_in_group, price=price)
                # Delete bids/asks of effected trade from bid/ask cure
                buyer.participant.offers = buyer.participant.offers[1:]
                seller.participant.offers = seller.participant.offers[1:]
                buyer.participant.offer_times = buyer.participant.offer_times[1:]
                seller.participant.offer_times = seller.participant.offer_times[1:]
                if len(buyer.participant.offers) >= 1:
                    buyer.current_offer = buyer.participant.offers[0]
                    buyer.current_offer_time = buyer.participant.offer_times[0][1]
                else:
                    buyer.current_offer = C.BID_MIN
                    buyer.current_offer_time = C.MAX_TIMESTAMP
                if len(seller.participant.offers) >= 1:
                    seller.current_offer = seller.participant.offers[0]
                    seller.current_offer_time = seller.participant.offer_times[0][1]
                else:
                    seller.current_offer = C.ASK_MAX
                    seller.current_offer_time = C.MAX_TIMESTAMP
                # Update history of effected trades
                buyer_trading_prices.insert(0, int(price))
                seller_trading_prices.insert(0, int(price))
                buyer.participant.trading_prices = buyer_trading_prices
                seller.participant.trading_prices = seller_trading_prices
                buyer_trading_times.insert(0, str(datetime.today().ctime())),
                seller_trading_times.insert(0, str(datetime.today().ctime())),
                buyer.participant.trading_times = buyer_trading_times
                seller.participant.trading_times = seller_trading_times
                # Update remaining time needed for production/consumption
                buyer.participant.time_needed += C.TIME_PER_UNIT
                seller.participant.time_needed += C.TIME_PER_UNIT
        elif data['type'] == 'withdrawal':
            if int(data['withdrawal']) in offers:
                offers.remove(int(data['withdrawal']))
                # foo = [x for x in foo if x != ("Alba", "Texas")]
                offer_times = [x for x in offer_times if x[0] in offers]
            participant.offers = offers
            participant.offer_times = offer_times
            if player.is_buyer:
                offers.sort(reverse=True)  # Sort such that highest bid is first list element
                if len(offers) >= 1:
                    player.current_offer = offers[0]
                    player.current_offer_time = offer_times[0][1]
                else:
                    player.current_offer = C.BID_MIN
                    player.current_offer_time = C.MAX_TIMESTAMP
            else:
                offers.sort(reverse=False)  # Sort such that lowest ask is first list element
                if len(offers) >= 1:
                    player.current_offer = offers[0]
                    player.current_offer_time = offer_times[0][1]
                else:
                    player.current_offer = C.ASK_MAX
                    player.current_offer_time = C.MAX_TIMESTAMP
        elif data['type'] == 'time_update':
            # Update remaining time needed for production/consumption
            player.participant.current_timestamp = time.time()
            player.participant.time_needed = round(max(0, player.participant.time_needed -
                                                       (player.participant.current_timestamp -
                                                        player.participant.previous_timestamp)), 0)
            player.participant.previous_timestamp = player.participant.current_timestamp
            # Update marginal utility/costs
            if player.is_buyer:
                player.participant.marginal_evaluation = marginal_consumption_utility(player.participant.time_needed)
            else:
                player.participant.marginal_evaluation = marginal_production_costs(player.participant.time_needed)
    # Create lists of all asks/bids by all sellers/buyers
    raw_bids = [p.participant.offers for p in buyers]  # Collect bids from all buyers
    bids = flatten(raw_bids)  # Unnest list
    bids.sort(reverse=True)
    # Collect asks from all sellers
    raw_asks = [p.participant.offers for p in sellers]  # Collect asks from all sellers
    asks = flatten(raw_asks)  # Unnest list
    asks.sort(reverse=False)
    # Create chart
    highcharts_series = [[tx.seconds, tx.price] for tx in Transaction.filter(group=group)]
    return {
        p.id_in_group: dict(
            current_offer=p.current_offer,
            balance=round(p.balance, 2),
            bids=bids,
            asks=asks,
            highcharts_series=highcharts_series,
            news=news,
            offers=p.participant.offers,
            time_needed=p.participant.time_needed,
            marginal_evaluation=p.participant.marginal_evaluation,
            trading_prices=p.participant.trading_prices,
            trading_times=p.participant.trading_times,
        )
        for p in players
    }


# PAGES
class WaitToStart(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.start_timestamp = int(time.time())


class Trading(Page):
    live_method = live_method

    @staticmethod
    def js_vars(player: Player):
        return dict(id_in_group=player.id_in_group, is_buyer=player.is_buyer)

    @staticmethod
    def get_timeout_seconds(player: Player):
        import time

        group = player.group
        market_opening_timestamp = time.mktime(time.strptime(player.session.config['market_opening'], "%d %b %Y %X"))
        group.start_timestamp = int(market_opening_timestamp)
        market_closing_timestamp = time.mktime(time.strptime(player.session.config['market_closing'], "%d %b %Y %X"))
        # return (group.start_timestamp + 5 * 60) - time.time()
        return market_closing_timestamp - time.time()

    @staticmethod
    def vars_for_template(player: Player):
        market_opening = player.session.config['market_opening']
        market_closing = player.session.config['market_closing']
        return dict(
            market_opening=market_opening,
            market_closing=market_closing,
        )


class ResultsWaitPage(WaitPage):
    pass


class Results(Page):
    pass


page_sequence = [
    # WaitToStart,
    Trading,
    ResultsWaitPage,
    Results
]


# def custom_export(players):
#     yield ['balance']
#     for p in players:
#         yield [p.balance]


def custom_export(players):
    yield ['session', 'description', 'buyer', 'seller', 'price', 'seconds',
           'buyer_valuation', 'seller_costs', 'buyer_profits', 'seller_profits', 'buyer_balance', 'seller_balance']
    for p in players:
        for tx in Transaction.filter(seller=p):
            yield [p.session.code, tx.description, tx.buyer.id_in_group, tx.seller.id_in_group, tx.price, tx.seconds,
                   tx.buyer_valuation, tx.seller_costs, tx.buyer_profits, tx.seller_profits, tx.buyer_balance,
                   tx.seller_balance]
